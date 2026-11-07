"""Authentication and Session Management Endpoints"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_session,
    get_current_user,
    verify_csrf,
)
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models import Household, HouseholdMember, SecurityEvent, User, UserSession
from app.schemas.auth import (
    AuthSessionResponse,
    HouseholdBriefResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_session_cookie(response: Response, raw_token: str) -> None:
    """Sets a hardened HttpOnly session cookie."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_EXPIRE_SECONDS,
        expires=settings.SESSION_EXPIRE_SECONDS,
        path="/",
        domain=None,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAME_SITE,
    )


def _clear_session_cookie(response: Response) -> None:
    """Clears the session cookie."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=settings.COOKIE_SAME_SITE,
    )


@router.post(
    "/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Initial User & Household",
)
async def register(
    payload: UserRegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> AuthSessionResponse:
    """
    Registers a new user, creates their initial Household, assigns the Owner role,
    and establishes an initial authenticated session.
    """
    email_clean = payload.email.lower().strip()
    existing_user = await db.execute(select(User).where(User.email == email_clean))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists",
        )

    # 1. Create User with Argon2id hash
    user = User(
        email=email_clean,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 2. Create default Household
    household_name = payload.household_name or f"{payload.full_name}'s Household"
    household = Household(
        name=household_name.strip(),
        currency=settings.DEFAULT_CURRENCY,
        timezone=settings.DEFAULT_TIMEZONE,
    )
    db.add(household)
    await db.flush()

    # 3. Associate user as Owner
    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="Owner",
    )
    db.add(membership)

    # 4. Create Session
    raw_session_token = generate_session_token()
    raw_csrf_token = generate_csrf_token()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.SESSION_EXPIRE_SECONDS)

    session_record = UserSession(
        user_id=user.id,
        session_token_hash=hash_session_token(raw_session_token),
        csrf_token=raw_csrf_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=expires_at,
        last_active_at=now,
    )
    db.add(session_record)

    # 5. Log Security Event
    event = SecurityEvent(
        user_id=user.id,
        event_type="LOGIN_SUCCESS",
        ip_address=request.client.host if request.client else None,
        metadata_json={"action": "registration"},
    )
    db.add(event)

    await db.commit()
    await db.refresh(user)
    await db.refresh(household)

    _set_session_cookie(response, raw_session_token)

    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        household=HouseholdBriefResponse(
            id=household.id,
            name=household.name,
            currency=household.currency,
            timezone=household.timezone,
            role="Owner",
        ),
        csrf_token=raw_csrf_token,
        message="Account registered successfully",
    )


@router.post(
    "/login",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate User and Create Session",
)
async def login(
    payload: UserLoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> AuthSessionResponse:
    """
    Authenticates email and password with Argon2id.
    Rotates/creates a server-side session and issues a hardened HttpOnly cookie.
    """
    email_clean = payload.email.lower().strip()
    stmt = (
        select(User)
        .where(User.email == email_clean)
        .options(selectinload(User.household_memberships).selectinload(HouseholdMember.household))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    ip = request.client.host if request.client else None

    # Constant-time comparison simulation / verify
    if not user or not verify_password(payload.password, user.password_hash):
        # Log failed attempt in security_events
        fail_event = SecurityEvent(
            user_id=user.id if user else None,
            event_type="LOGIN_FAILURE",
            ip_address=ip,
            metadata_json={"email": email_clean},
        )
        db.add(fail_event)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    # Find primary household
    primary_membership = user.household_memberships[0] if user.household_memberships else None
    if not primary_membership or not primary_membership.household:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No household associated with user",
        )

    # Session generation (rotation on login)
    raw_session_token = generate_session_token()
    raw_csrf_token = generate_csrf_token()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.SESSION_EXPIRE_SECONDS)

    session_record = UserSession(
        user_id=user.id,
        session_token_hash=hash_session_token(raw_session_token),
        csrf_token=raw_csrf_token,
        ip_address=ip,
        user_agent=request.headers.get("user-agent"),
        expires_at=expires_at,
        last_active_at=now,
    )
    db.add(session_record)

    success_event = SecurityEvent(
        user_id=user.id,
        event_type="LOGIN_SUCCESS",
        ip_address=ip,
        metadata_json={"action": "login"},
    )
    db.add(success_event)

    await db.commit()

    _set_session_cookie(response, raw_session_token)

    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        household=HouseholdBriefResponse(
            id=primary_membership.household.id,
            name=primary_membership.household.name,
            currency=primary_membership.household.currency,
            timezone=primary_membership.household.timezone,
            role=primary_membership.role,
        ),
        csrf_token=raw_csrf_token,
        message="Logged in successfully",
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log Out of Current Session",
    dependencies=[Depends(verify_csrf)],
)
async def logout(
    response: Response,
    request: Request,
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Revokes the current user session and clears the session cookie."""
    await db.delete(session)

    event = SecurityEvent(
        user_id=user.id,
        event_type="LOGOUT",
        ip_address=request.client.host if request.client else None,
        metadata_json={"session_id": str(session.id)},
    )
    db.add(event)
    await db.commit()

    _clear_session_cookie(response)
    return {"message": "Logged out successfully"}


@router.post(
    "/logout-all",
    status_code=status.HTTP_200_OK,
    summary="Log Out Everywhere (Revoke All Sessions)",
    dependencies=[Depends(verify_csrf)],
)
async def logout_all(
    response: Response,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Revokes all active sessions for the authenticated user across all devices."""
    stmt = delete(UserSession).where(UserSession.user_id == user.id)
    await db.execute(stmt)

    event = SecurityEvent(
        user_id=user.id,
        event_type="SESSION_REVOKED",
        ip_address=request.client.host if request.client else None,
        metadata_json={"scope": "all_sessions"},
    )
    db.add(event)
    await db.commit()

    _clear_session_cookie(response)
    return {"message": "All sessions revoked across all devices"}


@router.get(
    "/me",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile & Active Session",
)
async def get_me(
    user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
) -> AuthSessionResponse:
    """Returns profile information for the authenticated session."""
    household, role = household_and_role
    return AuthSessionResponse(
        user=UserResponse.model_validate(user),
        household=HouseholdBriefResponse(
            id=household.id,
            name=household.name,
            currency=household.currency,
            timezone=household.timezone,
            role=role,
        ),
        csrf_token=session.csrf_token,
        message="Session active",
    )
