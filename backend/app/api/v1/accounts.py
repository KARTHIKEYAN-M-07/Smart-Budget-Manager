"""Financial Account Endpoints"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.core.security import encrypt_field
from app.models import AuditLog, FinancialAccount, Household, User
from app.schemas.account import (
    AccountCreateRequest,
    AccountResponse,
    AccountUpdateRequest,
)
from app.services.account_service import (
    calculate_derived_balance,
    get_accessible_account,
    list_accessible_accounts,
)

router = APIRouter(prefix="/accounts", tags=["Financial Accounts"])


@router.get(
    "",
    response_model=list[AccountResponse],
    status_code=status.HTTP_200_OK,
    summary="List Accessible Household Accounts",
)
async def get_accounts(
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[AccountResponse]:
    """
    Returns all accounts accessible to the caller within their active household.
    Shared accounts + Caller's private accounts are included.
    Derived balance is dynamically computed from transactions.
    """
    household, _ = household_and_role
    accounts_with_balances = await list_accessible_accounts(db, household.id, user.id)

    return [
        AccountResponse(
            id=acc.id,
            household_id=acc.household_id,
            user_id=acc.user_id,
            name=acc.name,
            account_type=acc.account_type,
            institution_name=acc.institution_name,
            account_number_last4=acc.account_number_last4,
            visibility=acc.visibility,
            is_active=acc.is_active,
            version=acc.version,
            derived_balance=balance,
            created_at=acc.created_at,
            updated_at=acc.updated_at,
        )
        for acc, balance in accounts_with_balances
    ]


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Financial Account",
    dependencies=[Depends(verify_csrf)],
)
async def create_account(
    payload: AccountCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    """
    Creates a new financial account.
    Full account number is encrypted via AES-256-GCM before saving.
    Last 4 digits are stored in cleartext for UI display.
    """
    household, _ = household_and_role

    # Encrypt full account number if provided
    encrypted_number = None
    if payload.account_number:
        encrypted_number = encrypt_field(payload.account_number)

    # Derive last 4 digits if not explicitly given
    last4 = payload.account_number_last4
    if not last4 and payload.account_number and len(payload.account_number) >= 4:
        candidate = payload.account_number[-4:]
        if candidate.isdigit():
            last4 = candidate

    account = FinancialAccount(
        household_id=household.id,
        user_id=user.id,
        name=payload.name.strip(),
        account_type=payload.account_type,
        institution_name=payload.institution_name.strip() if payload.institution_name else None,
        encrypted_account_number=encrypted_number,
        account_number_last4=last4,
        visibility=payload.visibility,
        is_active=True,
        version=1,
    )
    db.add(account)
    await db.flush()

    # Log to audit_logs
    audit = AuditLog(
        household_id=household.id,
        user_id=user.id,
        entity_name="FinancialAccount",
        entity_id=account.id,
        action="CREATE",
        new_values={
            "name": account.name,
            "account_type": account.account_type,
            "visibility": account.visibility,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(account)

    derived_balance = await calculate_derived_balance(db, account.id, account.account_type)

    return AccountResponse(
        id=account.id,
        household_id=account.household_id,
        user_id=account.user_id,
        name=account.name,
        account_type=account.account_type,
        institution_name=account.institution_name,
        account_number_last4=account.account_number_last4,
        visibility=account.visibility,
        is_active=account.is_active,
        version=account.version,
        derived_balance=derived_balance,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


@router.get(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Financial Account Details",
)
async def get_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    """
    Retrieves single account details.
    IDOR Prevention: Returns HTTP 404 (never 403) for non-existent, cross-household,
    or unauthorized private accounts.
    """
    household, _ = household_and_role
    result = await get_accessible_account(db, account_id, household.id, user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    acc, balance = result
    return AccountResponse(
        id=acc.id,
        household_id=acc.household_id,
        user_id=acc.user_id,
        name=acc.name,
        account_type=acc.account_type,
        institution_name=acc.institution_name,
        account_number_last4=acc.account_number_last4,
        visibility=acc.visibility,
        is_active=acc.is_active,
        version=acc.version,
        derived_balance=balance,
        created_at=acc.created_at,
        updated_at=acc.updated_at,
    )


@router.patch(
    "/{account_id}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Account with Optimistic Concurrency Control",
    dependencies=[Depends(verify_csrf)],
)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> AccountResponse:
    """
    Updates account fields and verifies optimistic locking version to prevent silent overwrites.
    """
    household, _ = household_and_role
    result = await get_accessible_account(db, account_id, household.id, user.id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    acc, _ = result

    # Optimistic Concurrency Check
    if acc.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account was modified by another session. Please refresh and retry.",
        )

    old_values = {
        "name": acc.name,
        "visibility": acc.visibility,
        "is_active": acc.is_active,
    }

    if payload.name is not None:
        acc.name = payload.name.strip()
    if payload.institution_name is not None:
        acc.institution_name = payload.institution_name.strip()
    if payload.account_number_last4 is not None:
        acc.account_number_last4 = payload.account_number_last4
    if payload.visibility is not None:
        acc.visibility = payload.visibility
    if payload.is_active is not None:
        acc.is_active = payload.is_active

    # Increment version
    acc.version += 1

    audit = AuditLog(
        household_id=household.id,
        user_id=user.id,
        entity_name="FinancialAccount",
        entity_id=acc.id,
        action="UPDATE",
        old_values=old_values,
        new_values={
            "name": acc.name,
            "visibility": acc.visibility,
            "is_active": acc.is_active,
            "version": acc.version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(acc)

    derived_balance = await calculate_derived_balance(db, acc.id, acc.account_type)

    return AccountResponse(
        id=acc.id,
        household_id=acc.household_id,
        user_id=acc.user_id,
        name=acc.name,
        account_type=acc.account_type,
        institution_name=acc.institution_name,
        account_number_last4=acc.account_number_last4,
        visibility=acc.visibility,
        is_active=acc.is_active,
        version=acc.version,
        derived_balance=derived_balance,
        created_at=acc.created_at,
        updated_at=acc.updated_at,
    )
