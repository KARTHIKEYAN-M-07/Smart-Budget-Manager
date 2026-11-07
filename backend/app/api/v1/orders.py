"""Shopping Orders API endpoints"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models.household import Household
from app.models.user import User
from app.schemas.order import (
    OrderReturnCreate,
    OrderReturnResponse,
    ShoppingOrderCreate,
    ShoppingOrderLinkTransactionRequest,
    ShoppingOrderResponse,
    ShoppingOrderUpdate,
)
from app.services.order_service import (
    create_shopping_order,
    get_shopping_order_by_id,
    link_order_payment_transaction,
    list_shopping_orders,
    process_order_return,
    update_shopping_order,
)

router = APIRouter(prefix="/orders", tags=["Shopping Orders"])


@router.post(
    "",
    response_model=ShoppingOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_order(
    payload: ShoppingOrderCreate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Record a shopping order with itemized breakdown."""
    household, _ = household_and_role
    return await create_shopping_order(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("", response_model=list[ShoppingOrderResponse])
async def get_orders(
    merchant_name: str | None = Query(None, description="Filter by merchant"),
    order_status: str | None = Query(None, alias="status", description="Filter by order status"),
    start_date: date | None = Query(None, description="Filter from order date"),
    end_date: date | None = Query(None, description="Filter to order date"),
    unlinked_only: bool = Query(False, description="Filter orders without linked payment transactions"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List orders for the authenticated user's household."""
    household, _ = household_and_role
    return await list_shopping_orders(
        db=db,
        household_id=household.id,
        merchant_name=merchant_name,
        order_status=order_status,
        start_date=start_date,
        end_date=end_date,
        unlinked_only=unlinked_only,
        limit=limit,
        offset=offset,
    )


@router.get("/{order_id}", response_model=ShoppingOrderResponse)
async def get_order(
    order_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve details of a specific order including items and returns."""
    household, _ = household_and_role
    return await get_shopping_order_by_id(
        db=db,
        household_id=household.id,
        order_id=order_id,
    )


@router.patch(
    "/{order_id}",
    response_model=ShoppingOrderResponse,
    dependencies=[Depends(verify_csrf)],
)
async def update_order(
    order_id: uuid.UUID,
    payload: ShoppingOrderUpdate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update order metadata with optimistic locking."""
    household, _ = household_and_role
    return await update_shopping_order(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        order_id=order_id,
        payload=payload,
    )


@router.post(
    "/{order_id}/link-payment",
    response_model=ShoppingOrderResponse,
    dependencies=[Depends(verify_csrf)],
)
async def link_payment(
    order_id: uuid.UUID,
    payload: ShoppingOrderLinkTransactionRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Link an existing payment transaction to an order to prevent double counting."""
    household, _ = household_and_role
    return await link_order_payment_transaction(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        order_id=order_id,
        transaction_id=payload.payment_transaction_id,
        version=payload.version,
    )


@router.post(
    "/{order_id}/returns",
    response_model=OrderReturnResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_return(
    order_id: uuid.UUID,
    payload: OrderReturnCreate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Record an item return and optionally create a reconciled REFUND transaction."""
    household, _ = household_and_role
    return await process_order_return(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        order_id=order_id,
        payload=payload,
    )
