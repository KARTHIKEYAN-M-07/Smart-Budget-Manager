"""Transaction API Endpoints"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models import Household, User
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionPaginatedResponse,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionVoidRequest,
)
from app.services.transaction_service import (
    create_transaction,
    get_accessible_transaction,
    list_transactions_paginated,
    update_transaction,
    void_transaction,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "",
    response_model=TransactionPaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="List, Search & Filter Transactions",
)
async def get_transactions(
    account_id: uuid.UUID | None = Query(default=None, description="Filter by account"),
    category_id: uuid.UUID | None = Query(default=None, description="Filter by category"),
    direction: str | None = Query(default=None, description="INFLOW or OUTFLOW"),
    transaction_type: str | None = Query(default=None, description="Transaction type filter"),
    search: str | None = Query(default=None, description="Search description keyword"),
    start_date: datetime | None = Query(default=None, description="Filter from start date"),
    end_date: datetime | None = Query(default=None, description="Filter to end date"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionPaginatedResponse:
    """
    Returns paginated transaction records filtered by criteria.
    Enforces record-level visibility.
    """
    household, _ = household_and_role
    return await list_transactions_paginated(
        db=db,
        household_id=household.id,
        user_id=user.id,
        account_id=account_id,
        category_id=category_id,
        direction=direction,
        transaction_type=transaction_type,
        search_query=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Transaction",
    dependencies=[Depends(verify_csrf)],
)
async def post_transaction(
    payload: TransactionCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionResponse:
    """
    Creates an immutable transaction ledger entry.
    Idempotent: Re-submitting with the same idempotency_key returns the existing transaction.
    """
    household, _ = household_and_role
    txn = await create_transaction(db, household.id, user.id, payload)

    return TransactionResponse(
        id=txn.id,
        household_id=txn.household_id,
        account_id=txn.account_id,
        category_id=txn.category_id,
        user_id=txn.user_id,
        transfer_group_id=txn.transfer_group_id,
        linked_transaction_id=txn.linked_transaction_id,
        amount=txn.amount,
        direction=txn.direction,
        transaction_type=txn.transaction_type,
        visibility=txn.visibility,
        description=txn.description,
        transaction_date=txn.transaction_date,
        status=txn.status,
        version=txn.version,
        idempotency_key=txn.idempotency_key,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Transaction Details",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionResponse:
    """
    Retrieves single transaction details.
    IDOR Prevention: Returns HTTP 404 for non-existent, cross-household, or unauthorized private entries.
    """
    household, _ = household_and_role
    txn = await get_accessible_transaction(db, transaction_id, household.id, user.id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    return TransactionResponse(
        id=txn.id,
        household_id=txn.household_id,
        account_id=txn.account_id,
        account_name=txn.account.name if txn.account else None,
        category_id=txn.category_id,
        category_name=txn.category.name if txn.category else None,
        user_id=txn.user_id,
        user_name=txn.user.full_name if txn.user else None,
        transfer_group_id=txn.transfer_group_id,
        linked_transaction_id=txn.linked_transaction_id,
        amount=txn.amount,
        direction=txn.direction,
        transaction_type=txn.transaction_type,
        visibility=txn.visibility,
        description=txn.description,
        transaction_date=txn.transaction_date,
        status=txn.status,
        version=txn.version,
        idempotency_key=txn.idempotency_key,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Transaction Metadata",
    dependencies=[Depends(verify_csrf)],
)
async def patch_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionResponse:
    """Updates category, description, or visibility with optimistic locking check."""
    household, _ = household_and_role
    txn = await update_transaction(db, transaction_id, household.id, user.id, payload)

    return TransactionResponse(
        id=txn.id,
        household_id=txn.household_id,
        account_id=txn.account_id,
        category_id=txn.category_id,
        user_id=txn.user_id,
        transfer_group_id=txn.transfer_group_id,
        linked_transaction_id=txn.linked_transaction_id,
        amount=txn.amount,
        direction=txn.direction,
        transaction_type=txn.transaction_type,
        visibility=txn.visibility,
        description=txn.description,
        transaction_date=txn.transaction_date,
        status=txn.status,
        version=txn.version,
        idempotency_key=txn.idempotency_key,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )


@router.post(
    "/{transaction_id}/void",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Void Transaction (No Hard Deletes)",
    dependencies=[Depends(verify_csrf)],
)
async def post_void_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionVoidRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionResponse:
    """
    Transitions transaction status to VOIDED without deleting the record.
    Preserves auditability.
    """
    household, _ = household_and_role
    txn = await void_transaction(db, transaction_id, household.id, user.id, payload)

    return TransactionResponse(
        id=txn.id,
        household_id=txn.household_id,
        account_id=txn.account_id,
        category_id=txn.category_id,
        user_id=txn.user_id,
        transfer_group_id=txn.transfer_group_id,
        linked_transaction_id=txn.linked_transaction_id,
        amount=txn.amount,
        direction=txn.direction,
        transaction_type=txn.transaction_type,
        visibility=txn.visibility,
        description=txn.description,
        transaction_date=txn.transaction_date,
        status=txn.status,
        version=txn.version,
        idempotency_key=txn.idempotency_key,
        created_at=txn.created_at,
        updated_at=txn.updated_at,
    )
