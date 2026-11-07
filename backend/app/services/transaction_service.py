"""Transaction Service handling financial mutations, audit logs, and search"""

import math
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Category, FinancialAccount, Transaction
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionPaginatedResponse,
    TransactionResponse,
    TransactionUpdateRequest,
    TransactionVoidRequest,
)


async def create_transaction(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TransactionCreateRequest,
) -> Transaction:
    """
    Creates an immutable ledger transaction.
    - Idempotency: Returns existing transaction if idempotency_key is repeated.
    - Auditing: Records creation in audit_logs.
    """
    # 1. Idempotency Check
    if payload.idempotency_key:
        stmt_idemp = select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.idempotency_key == payload.idempotency_key,
        )
        existing = (await db.execute(stmt_idemp)).scalar_one_or_none()
        if existing:
            return existing

    # 2. Account Validation & Isolation
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == payload.account_id,
        FinancialAccount.household_id == household_id,
    )
    account = (await db.execute(stmt_acc)).scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    if account.visibility == "private" and account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    # 3. Category Validation (if specified)
    if payload.category_id:
        stmt_cat = select(Category).where(
            Category.id == payload.category_id,
            Category.household_id == household_id,
        )
        cat = (await db.execute(stmt_cat)).scalar_one_or_none()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

    txn_date = payload.transaction_date or datetime.now(UTC)
    if txn_date.tzinfo is None:
        txn_date = txn_date.replace(tzinfo=UTC)

    txn = Transaction(
        household_id=household_id,
        account_id=account.id,
        category_id=payload.category_id,
        user_id=user_id,
        linked_transaction_id=payload.linked_transaction_id,
        amount=payload.amount,
        direction=payload.direction,
        transaction_type=payload.transaction_type,
        visibility=payload.visibility,
        description=payload.description.strip() if payload.description else None,
        transaction_date=txn_date,
        status="POSTED",
        version=1,
        idempotency_key=payload.idempotency_key,
    )
    db.add(txn)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Transaction",
        entity_id=txn.id,
        action="CREATE",
        new_values={
            "account_id": str(txn.account_id),
            "amount": str(txn.amount),
            "direction": txn.direction,
            "transaction_type": txn.transaction_type,
            "visibility": txn.visibility,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(txn)
    return txn


async def get_accessible_transaction(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Transaction | None:
    """
    Retrieves transaction enforcing household boundary and visibility.
    Returns None if missing, cross-household, or unauthorized private record.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.id == transaction_id)
        .options(
            selectinload(Transaction.account),
            selectinload(Transaction.category),
            selectinload(Transaction.user),
        )
    )
    txn = (await db.execute(stmt)).scalar_one_or_none()
    if not txn:
        return None

    # IDOR Prevention
    if txn.household_id != household_id:
        return None
    if txn.visibility == "private" and txn.user_id != user_id:
        return None

    return txn


async def list_transactions_paginated(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    direction: str | None = None,
    transaction_type: str | None = None,
    search_query: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> TransactionPaginatedResponse:
    """
    Queries transactions with multi-field filtering and pagination.
    Enforces record-level visibility.
    """
    base_filter = [
        Transaction.household_id == household_id,
        (Transaction.visibility == "shared") | (Transaction.user_id == user_id),
    ]

    if account_id:
        base_filter.append(Transaction.account_id == account_id)
    if category_id:
        base_filter.append(Transaction.category_id == category_id)
    if direction:
        base_filter.append(Transaction.direction == direction.upper())
    if transaction_type:
        base_filter.append(Transaction.transaction_type == transaction_type.upper())
    if search_query:
        base_filter.append(Transaction.description.ilike(f"%{search_query.strip()}%"))
    if start_date:
        base_filter.append(Transaction.transaction_date >= start_date)
    if end_date:
        base_filter.append(Transaction.transaction_date <= end_date)

    # Count
    count_stmt = select(func.count(Transaction.id)).where(*base_filter)
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Query items
    offset = (page - 1) * page_size
    query_stmt = (
        select(Transaction)
        .where(*base_filter)
        .options(
            selectinload(Transaction.account),
            selectinload(Transaction.category),
            selectinload(Transaction.user),
        )
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = (await db.execute(query_stmt)).scalars().all()

    response_items = [
        TransactionResponse(
            id=t.id,
            household_id=t.household_id,
            account_id=t.account_id,
            account_name=t.account.name if t.account else None,
            category_id=t.category_id,
            category_name=t.category.name if t.category else None,
            user_id=t.user_id,
            user_name=t.user.full_name if t.user else None,
            transfer_group_id=t.transfer_group_id,
            linked_transaction_id=t.linked_transaction_id,
            amount=t.amount,
            direction=t.direction,
            transaction_type=t.transaction_type,
            visibility=t.visibility,
            description=t.description,
            transaction_date=t.transaction_date,
            status=t.status,
            version=t.version,
            idempotency_key=t.idempotency_key,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in items
    ]

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return TransactionPaginatedResponse(
        items=response_items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def update_transaction(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TransactionUpdateRequest,
) -> Transaction:
    """Updates mutable metadata on a transaction with optimistic locking."""
    txn = await get_accessible_transaction(db, transaction_id, household_id, user_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    if txn.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction was modified by another session. Please refresh and retry.",
        )

    old_values = {
        "category_id": str(txn.category_id) if txn.category_id else None,
        "description": txn.description,
        "visibility": txn.visibility,
    }

    if payload.category_id is not None:
        # Validate category
        stmt_cat = select(Category).where(
            Category.id == payload.category_id,
            Category.household_id == household_id,
        )
        cat = (await db.execute(stmt_cat)).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        txn.category_id = payload.category_id

    if payload.description is not None:
        txn.description = payload.description.strip() if payload.description else None
    if payload.visibility is not None:
        txn.visibility = payload.visibility

    txn.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Transaction",
        entity_id=txn.id,
        action="UPDATE",
        old_values=old_values,
        new_values={
            "category_id": str(txn.category_id) if txn.category_id else None,
            "description": txn.description,
            "visibility": txn.visibility,
            "version": txn.version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(txn)
    return txn


async def void_transaction(
    db: AsyncSession,
    transaction_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TransactionVoidRequest,
) -> Transaction:
    """
    Voids a transaction without hard-deleting it.
    Financial invariant: Records are never deleted via SQL DELETE.
    """
    txn = await get_accessible_transaction(db, transaction_id, household_id, user_id)
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    if txn.status == "VOIDED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transaction is already voided")

    if txn.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transaction was modified by another session. Please refresh and retry.",
        )

    old_status = txn.status
    txn.status = "VOIDED"
    txn.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Transaction",
        entity_id=txn.id,
        action="VOID",
        old_values={"status": old_status},
        new_values={"status": "VOIDED", "reason": payload.reason, "version": txn.version},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(txn)
    return txn
