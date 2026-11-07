"""Shopping order and returns service.
Guarantees anti-double-counting:
- Spending analytics derives ledger totals exclusively from transactions
- Orders can be linked to an existing payment transaction or recorded standalone
- Returns can generate or link to a REFUND transaction which reduces net expenses
"""

import uuid
from datetime import UTC, date, datetime, time

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AuditLog,
    FinancialAccount,
    OrderItemStatus,
    OrderReturn,
    OrderStatus,
    ReturnRefundStatus,
    ShoppingOrder,
    ShoppingOrderItem,
    Transaction,
)
from app.schemas.order import (
    OrderReturnCreate,
    OrderReturnResponse,
    ShoppingOrderCreate,
    ShoppingOrderItemResponse,
    ShoppingOrderResponse,
    ShoppingOrderUpdate,
)


def build_order_response(order: ShoppingOrder) -> ShoppingOrderResponse:
    item_responses = []
    for item in order.items:
        cat_name = item.category.name if item.category else None
        item_responses.append(
            ShoppingOrderItemResponse(
                id=item.id,
                order_id=item.order_id,
                category_id=item.category_id,
                category_name=cat_name,
                name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.total_price,
                status=OrderItemStatus(item.status),
            )
        )

    return_responses = []
    for ret in order.returns:
        return_responses.append(
            OrderReturnResponse(
                id=ret.id,
                order_id=ret.order_id,
                item_id=ret.item_id,
                refund_transaction_id=ret.refund_transaction_id,
                return_date=ret.return_date,
                refund_amount=ret.refund_amount,
                reason=ret.reason,
                refund_status=ReturnRefundStatus(ret.refund_status),
                notes=ret.notes,
                created_at=ret.created_at,
            )
        )

    user_name = order.user.full_name if order.user else None

    return ShoppingOrderResponse(
        id=order.id,
        household_id=order.household_id,
        user_id=order.user_id,
        user_name=user_name,
        payment_transaction_id=order.payment_transaction_id,
        is_payment_linked=order.payment_transaction_id is not None,
        merchant_name=order.merchant_name,
        order_number=order.order_number,
        order_date=order.order_date,
        status=OrderStatus(order.status),
        total_amount=order.total_amount,
        notes=order.notes,
        receipt_url=order.receipt_url,
        version=order.version,
        created_at=order.created_at,
        items=item_responses,
        returns=return_responses,
    )


async def create_shopping_order(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ShoppingOrderCreate,
) -> ShoppingOrderResponse:
    # 1. Validate payment transaction if provided
    if payload.payment_transaction_id:
        stmt_txn = select(Transaction).where(
            Transaction.id == payload.payment_transaction_id,
            Transaction.household_id == household_id,
            Transaction.status != "VOIDED",
        )
        res_txn = await db.execute(stmt_txn)
        txn = res_txn.scalar_one_or_none()
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked payment transaction not found in household",
            )

    # 2. Create Order
    order = ShoppingOrder(
        household_id=household_id,
        user_id=user_id,
        payment_transaction_id=payload.payment_transaction_id,
        merchant_name=payload.merchant_name,
        order_number=payload.order_number,
        order_date=payload.order_date,
        status=payload.status.value,
        total_amount=payload.total_amount,
        notes=payload.notes,
        receipt_url=payload.receipt_url,
        version=1,
    )
    db.add(order)
    await db.flush()

    # 3. Create items
    for item_data in payload.items:
        tot = item_data.total_price if item_data.total_price is not None else (item_data.unit_price * item_data.quantity)
        item = ShoppingOrderItem(
            order_id=order.id,
            category_id=item_data.category_id,
            name=item_data.name,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            total_price=tot,
            status=OrderItemStatus.ACTIVE.value,
        )
        db.add(item)

    # 4. Audit Log
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="ShoppingOrder",
        entity_id=order.id,
        action="CREATE",
        new_values={
            "merchant_name": order.merchant_name,
            "total_amount": str(order.total_amount),
            "order_date": str(order.order_date),
            "payment_linked": str(order.payment_transaction_id is not None),
        },
    )
    db.add(audit)

    await db.commit()

    # Reload with relationships
    return await get_shopping_order_by_id(db, household_id, order.id)


async def get_shopping_order_by_id(
    db: AsyncSession,
    household_id: uuid.UUID,
    order_id: uuid.UUID,
) -> ShoppingOrderResponse:
    stmt = (
        select(ShoppingOrder)
        .where(
            ShoppingOrder.id == order_id,
            ShoppingOrder.household_id == household_id,
        )
        .options(
            selectinload(ShoppingOrder.user),
            selectinload(ShoppingOrder.items).selectinload(ShoppingOrderItem.category),
            selectinload(ShoppingOrder.returns),
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return build_order_response(order)


async def list_shopping_orders(
    db: AsyncSession,
    household_id: uuid.UUID,
    merchant_name: str | None = None,
    order_status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    unlinked_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[ShoppingOrderResponse]:
    stmt = (
        select(ShoppingOrder)
        .where(ShoppingOrder.household_id == household_id)
        .options(
            selectinload(ShoppingOrder.user),
            selectinload(ShoppingOrder.items).selectinload(ShoppingOrderItem.category),
            selectinload(ShoppingOrder.returns),
        )
        .order_by(ShoppingOrder.order_date.desc(), ShoppingOrder.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if merchant_name:
        stmt = stmt.where(ShoppingOrder.merchant_name.ilike(f"%{merchant_name}%"))
    if order_status:
        stmt = stmt.where(ShoppingOrder.status == order_status)
    if start_date:
        stmt = stmt.where(ShoppingOrder.order_date >= start_date)
    if end_date:
        stmt = stmt.where(ShoppingOrder.order_date <= end_date)
    if unlinked_only:
        stmt = stmt.where(ShoppingOrder.payment_transaction_id.is_(None))

    res = await db.execute(stmt)
    orders = res.scalars().all()
    return [build_order_response(o) for o in orders]


async def update_shopping_order(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    payload: ShoppingOrderUpdate,
) -> ShoppingOrderResponse:
    stmt = (
        select(ShoppingOrder)
        .where(
            ShoppingOrder.id == order_id,
            ShoppingOrder.household_id == household_id,
        )
        .options(
            selectinload(ShoppingOrder.user),
            selectinload(ShoppingOrder.items).selectinload(ShoppingOrderItem.category),
            selectinload(ShoppingOrder.returns),
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # Optimistic locking check
    if order.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order was modified by another request. Please reload.",
        )

    old_vals = {
        "status": order.status,
        "total_amount": str(order.total_amount),
        "version": order.version,
    }

    if payload.merchant_name is not None:
        order.merchant_name = payload.merchant_name
    if payload.order_number is not None:
        order.order_number = payload.order_number
    if payload.order_date is not None:
        order.order_date = payload.order_date
    if payload.status is not None:
        order.status = payload.status.value
    if payload.total_amount is not None:
        order.total_amount = payload.total_amount
    if payload.notes is not None:
        order.notes = payload.notes
    if payload.receipt_url is not None:
        order.receipt_url = payload.receipt_url
    if payload.payment_transaction_id is not None:
        # Validate transaction
        stmt_txn = select(Transaction).where(
            Transaction.id == payload.payment_transaction_id,
            Transaction.household_id == household_id,
            Transaction.status != "VOIDED",
        )
        t_res = await db.execute(stmt_txn)
        if not t_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found in household",
            )
        order.payment_transaction_id = payload.payment_transaction_id

    order.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="ShoppingOrder",
        entity_id=order.id,
        action="UPDATE",
        old_values=old_vals,
        new_values={
            "status": order.status,
            "total_amount": str(order.total_amount),
            "version": order.version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(order)
    return await get_shopping_order_by_id(db, household_id, order.id)


async def link_order_payment_transaction(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    transaction_id: uuid.UUID,
    version: int,
) -> ShoppingOrderResponse:
    stmt = (
        select(ShoppingOrder)
        .where(
            ShoppingOrder.id == order_id,
            ShoppingOrder.household_id == household_id,
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.version != version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order was modified by another request. Please reload.",
        )

    # Validate payment transaction
    stmt_txn = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.household_id == household_id,
        Transaction.status != "VOIDED",
    )
    res_txn = await db.execute(stmt_txn)
    txn = res_txn.scalar_one_or_none()
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found in household",
        )

    order.payment_transaction_id = transaction_id
    order.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="ShoppingOrder",
        entity_id=order.id,
        action="UPDATE",
        new_values={"payment_transaction_id": str(transaction_id), "version": order.version},
    )
    db.add(audit)
    await db.commit()
    return await get_shopping_order_by_id(db, household_id, order.id)


async def process_order_return(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    order_id: uuid.UUID,
    payload: OrderReturnCreate,
) -> OrderReturnResponse:
    # 1. Fetch order
    stmt = (
        select(ShoppingOrder)
        .where(
            ShoppingOrder.id == order_id,
            ShoppingOrder.household_id == household_id,
        )
        .options(
            selectinload(ShoppingOrder.items),
            selectinload(ShoppingOrder.returns),
        )
    )
    res = await db.execute(stmt)
    order = res.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    # 2. If item_id provided, verify and mark item RETURNED
    target_item = None
    if payload.item_id:
        target_item = next((it for it in order.items if it.id == payload.item_id), None)
        if not target_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order item not found",
            )
        target_item.status = OrderItemStatus.RETURNED.value

    # 3. Create refund transaction if requested
    refund_txn_id = None
    refund_status = ReturnRefundStatus.PENDING.value

    if payload.create_refund_transaction:
        if not payload.refund_account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="refund_account_id is required when create_refund_transaction is True",
            )
        stmt_acc = select(FinancialAccount).where(
            FinancialAccount.id == payload.refund_account_id,
            FinancialAccount.household_id == household_id,
            FinancialAccount.is_active.is_(True),
        )
        res_acc = await db.execute(stmt_acc)
        acc = res_acc.scalar_one_or_none()
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refund receiving account not found or inactive",
            )

        ret_dt = datetime.combine(payload.return_date, time.min, tzinfo=UTC)
        cat_id = target_item.category_id if target_item else None

        refund_txn = Transaction(
            household_id=household_id,
            account_id=acc.id,
            category_id=cat_id,
            user_id=user_id,
            linked_transaction_id=order.payment_transaction_id,
            amount=payload.refund_amount,
            direction="INFLOW",
            transaction_type="REFUND",
            visibility="shared",
            description=f"Refund: {order.merchant_name} - {payload.reason}",
            transaction_date=ret_dt,
            status="POSTED",
            version=1,
        )
        db.add(refund_txn)
        await db.flush()
        refund_txn_id = refund_txn.id
        refund_status = ReturnRefundStatus.REFUNDED.value

    # 4. Create OrderReturn record
    order_return = OrderReturn(
        order_id=order.id,
        item_id=payload.item_id,
        refund_transaction_id=refund_txn_id,
        return_date=payload.return_date,
        refund_amount=payload.refund_amount,
        reason=payload.reason,
        refund_status=refund_status,
        notes=payload.notes,
    )
    db.add(order_return)
    await db.flush()

    # 5. Calculate cumulative returns to update order status
    total_returned_now = sum(r.refund_amount for r in order.returns) + payload.refund_amount
    if total_returned_now >= order.total_amount:
        order.status = OrderStatus.RETURNED.value
    else:
        order.status = OrderStatus.PARTIALLY_RETURNED.value
    order.version += 1

    # 6. Audit Log
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="OrderReturn",
        entity_id=order_return.id,
        action="CREATE",
        new_values={
            "order_id": str(order.id),
            "refund_amount": str(payload.refund_amount),
            "refund_status": refund_status,
            "refund_txn_id": str(refund_txn_id) if refund_txn_id else None,
        },
    )
    db.add(audit)

    await db.commit()
    await db.refresh(order_return)

    return OrderReturnResponse(
        id=order_return.id,
        order_id=order_return.order_id,
        item_id=order_return.item_id,
        refund_transaction_id=order_return.refund_transaction_id,
        return_date=order_return.return_date,
        refund_amount=order_return.refund_amount,
        reason=order_return.reason,
        refund_status=ReturnRefundStatus(order_return.refund_status),
        notes=order_return.notes,
        created_at=order_return.created_at,
    )
