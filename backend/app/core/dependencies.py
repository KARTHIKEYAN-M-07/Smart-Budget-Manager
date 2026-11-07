"""FastAPI Authentication, RBAC, CSRF, and Isolation Dependencies"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db_session
from app.core.security import hash_session_token
from app.models import Household, HouseholdMember, SecurityEvent, User, UserSession

ROLE_HIERARCHY = {
    "Owner": 4,
    "Administrator": 3,
    "Member": 2,
    "ReadOnly": 1,
}


async def get_current_session_and_user(
    request: Request,
    sfbm_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db_session),
) -> tuple[UserSession, User]:
    """
    Extracts session token from HttpOnly cookie or Authorization Bearer header.
    Validates expiration, idle timeout, and updates activity timestamp.
    """
    token: str | None = sfbm_session
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Cookie"},
        )

    token_hash = hash_session_token(token)
    stmt = (
        select(UserSession).where(UserSession.session_token_hash == token_hash).options(selectinload(UserSession.user))
    )
    result = await db.execute(stmt)
    session_record = result.scalar_one_or_none()

    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked session",
        )

    now = datetime.now(UTC)

    # 1. Check absolute expiry
    expires_at = session_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if now > expires_at:
        await db.delete(session_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired",
        )

    # 2. Check idle timeout
    last_active = session_record.last_active_at
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=UTC)

    idle_limit = timedelta(seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS)
    if (now - last_active) > idle_limit:
        await db.delete(session_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to inactivity",
        )

    # Update activity timestamp
    session_record.last_active_at = now
    await db.commit()

    if not session_record.user or not session_record.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or disabled",
        )

    return session_record, session_record.user


async def get_current_user(
    session_and_user: tuple[UserSession, User] = Depends(get_current_session_and_user),
) -> User:
    """Dependency returning the authenticated User."""
    return session_and_user[1]


async def get_current_session(
    session_and_user: tuple[UserSession, User] = Depends(get_current_session_and_user),
) -> UserSession:
    """Dependency returning the active UserSession."""
    return session_and_user[0]


async def get_current_household_and_role(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> tuple[Household, str]:
    """
    Derives active household and user's role from server-side database relations.
    Never trusts household_id from client parameters.
    """
    stmt = (
        select(HouseholdMember)
        .where(HouseholdMember.user_id == user.id)
        .options(selectinload(HouseholdMember.household))
    )
    result = await db.execute(stmt)
    membership = result.scalars().first()

    if not membership or not membership.household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No household associated with this account",
        )

    return membership.household, membership.role


def require_role(min_role: str):
    """
    RBAC dependency factory enforcing minimum role level:
    Owner (4) >= Administrator (3) >= Member (2) >= ReadOnly (1).
    """

    async def role_checker(
        household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
        db: AsyncSession = Depends(get_db_session),
        user: User = Depends(get_current_user),
        request: Request = None,
    ) -> tuple[Household, str]:
        household, role = household_and_role
        user_level = ROLE_HIERARCHY.get(role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 0)

        if user_level < required_level:
            # Log security event for denied privilege attempt
            event = SecurityEvent(
                user_id=user.id,
                event_type="ACCESS_DENIED",
                ip_address=request.client.host if request and request.client else None,
                metadata_json={"required_role": min_role, "actual_role": role},
            )
            db.add(event)
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Action requires minimum '{min_role}' role privileges",
            )
        return household, role

    return role_checker


async def verify_csrf(
    request: Request,
    session: UserSession = Depends(get_current_session),
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> None:
    """
    Validates CSRF token header on all state-changing requests (POST, PUT, PATCH, DELETE).
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if not x_csrf_token or x_csrf_token != session.csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token validation failed",
            )


def enforce_resource_visibility(
    resource_household_id: uuid.UUID,
    resource_user_id: uuid.UUID,
    resource_visibility: str,
    current_household_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> None:
    """
    Enforces tenant isolation and record visibility.
    CRITICAL: Returns HTTP 404 (Not Found) instead of 403 (Forbidden)
    to eliminate existence probing and prevent IDOR attacks.
    """
    # Cross-household boundary check
    if resource_household_id != current_household_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    # Private visibility check
    if resource_visibility == "private" and resource_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
