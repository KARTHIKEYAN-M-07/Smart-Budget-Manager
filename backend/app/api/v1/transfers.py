"""Transfer API Endpoints"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models import Household, TransferGroup, User
from app.schemas.transaction import TransactionResponse
from app.schemas.transfer import (
    OpeningBalanceRequest,
    TransferCreateRequest,
    TransferGroupResponse,
)
from app.services.transfer_service import (
    execute_atomic_transfer,
    reverse_transfer_group,
    set_opening_balance,
)

router = APIRouter(prefix="/transfers", tags=["Transfers"])


@router.post(
    "",
    response_model=TransferGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute Atomic Double-Leg Account Transfer",
    dependencies=[Depends(verify_csrf)],
)
async def post_transfer(
    payload: TransferCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransferGroupResponse:
    """
    Executes an atomic transfer between two accounts under a single TransferGroup:
    - Leg 1 (Source): TRANSFER_OUT, OUTFLOW
    - Leg 2 (Destination): TRANSFER_IN, INFLOW
    Can be used for:
    - Internal bank transfers (Savings -> Current)
    - ATM Cash withdrawals (Savings -> Cash Account)
    - Credit Card bill payments (Savings -> Credit Card, settling liability)
    """
    household, _ = household_and_role
    group, out_leg, in_leg = await execute_atomic_transfer(db, household.id, user.id, payload)

    return TransferGroupResponse(
        id=group.id,
        household_id=group.household_id,
        total_amount=group.total_amount,
        transfer_date=group.transfer_date,
        description=group.description,
        source_account_id=out_leg.account_id,
        destination_account_id=in_leg.account_id,
        source_transaction_id=out_leg.id,
        destination_transaction_id=in_leg.id,
        created_at=group.created_at,
    )


@router.post(
    "/opening-balance",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set Account Opening Balance",
    dependencies=[Depends(verify_csrf)],
)
async def post_opening_balance(
    payload: OpeningBalanceRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransactionResponse:
    """Sets initial balance on an account via an OPENING_BALANCE ledger transaction."""
    household, _ = household_and_role
    txn = await set_opening_balance(db, household.id, user.id, payload)

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
    "/{group_id}",
    response_model=TransferGroupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Transfer Group Details",
)
async def get_transfer(
    group_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> TransferGroupResponse:
    """Retrieves transfer group and associated legs."""
    household, _ = household_and_role
    stmt = (
        select(TransferGroup)
        .where(TransferGroup.id == group_id, TransferGroup.household_id == household.id)
        .options(selectinload(TransferGroup.transactions))
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer group not found")

    out_leg = next((t for t in group.transactions if t.direction == "OUTFLOW"), None)
    in_leg = next((t for t in group.transactions if t.direction == "INFLOW"), None)

    if not out_leg or not in_leg:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Incomplete transfer group")

    return TransferGroupResponse(
        id=group.id,
        household_id=group.household_id,
        total_amount=group.total_amount,
        transfer_date=group.transfer_date,
        description=group.description,
        source_account_id=out_leg.account_id,
        destination_account_id=in_leg.account_id,
        source_transaction_id=out_leg.id,
        destination_transaction_id=in_leg.id,
        created_at=group.created_at,
    )


@router.post(
    "/{group_id}/reverse",
    status_code=status.HTTP_200_OK,
    summary="Reverse Transfer Group (Atomic Void)",
    dependencies=[Depends(verify_csrf)],
)
async def post_reverse_transfer(
    group_id: uuid.UUID,
    reason: str = Query(default="Transfer reversed by user", description="Reason for reversal"),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Atomically voids both legs of a transfer group."""
    household, _ = household_and_role
    await reverse_transfer_group(db, group_id, household.id, user.id, reason)
    return {"message": "Transfer group reversed successfully"}
