"""Transfer service executing atomic double-leg transfers and opening balances"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, FinancialAccount, Transaction, TransferGroup
from app.schemas.transfer import OpeningBalanceRequest, TransferCreateRequest


async def execute_atomic_transfer(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: TransferCreateRequest,
) -> tuple[TransferGroup, Transaction, Transaction]:
    """
    CRITICAL DOUBLE-ENTRY ACCOUNTING INVARIANT:
    A transfer consists of ONE TransferGroup with TWO balanced legs:
    - Leg 1 (Source): TRANSFER_OUT, OUTFLOW, amount
    - Leg 2 (Destination): TRANSFER_IN, INFLOW, amount
    Both legs must be committed in a single atomic database transaction.
    """
    # 1. Idempotency Check
    if payload.idempotency_key:
        stmt_idemp = (
            select(TransferGroup)
            .where(
                TransferGroup.household_id == household_id,
                TransferGroup.idempotency_key == payload.idempotency_key,
            )
            .options(selectinload(TransferGroup.transactions))
        )
        existing = (await db.execute(stmt_idemp)).scalar_one_or_none()
        if existing and len(existing.transactions) >= 2:
            out_leg = next(t for t in existing.transactions if t.direction == "OUTFLOW")
            in_leg = next(t for t in existing.transactions if t.direction == "INFLOW")
            return existing, out_leg, in_leg

    # 2. Validate Source Account
    stmt_src = select(FinancialAccount).where(
        FinancialAccount.id == payload.source_account_id,
        FinancialAccount.household_id == household_id,
    )
    src_acc = (await db.execute(stmt_src)).scalar_one_or_none()
    if not src_acc or not src_acc.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source account not found or inactive")
    if src_acc.visibility == "private" and src_acc.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source account not found")

    # 3. Validate Destination Account
    stmt_dst = select(FinancialAccount).where(
        FinancialAccount.id == payload.destination_account_id,
        FinancialAccount.household_id == household_id,
    )
    dst_acc = (await db.execute(stmt_dst)).scalar_one_or_none()
    if not dst_acc or not dst_acc.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination account not found or inactive")
    if dst_acc.visibility == "private" and dst_acc.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination account not found")

    txn_date = payload.transfer_date or datetime.now(UTC)
    if txn_date.tzinfo is None:
        txn_date = txn_date.replace(tzinfo=UTC)

    # 4. Create TransferGroup Header
    group = TransferGroup(
        household_id=household_id,
        created_by_user_id=user_id,
        total_amount=payload.amount,
        transfer_date=txn_date,
        description=payload.description.strip() if payload.description else None,
        idempotency_key=payload.idempotency_key,
    )
    db.add(group)
    await db.flush()

    # 5. Leg 1: Outflow from Source Account
    outflow_leg = Transaction(
        household_id=household_id,
        account_id=src_acc.id,
        user_id=user_id,
        transfer_group_id=group.id,
        amount=payload.amount,
        direction="OUTFLOW",
        transaction_type="TRANSFER_OUT",
        visibility="shared" if (src_acc.visibility == "shared" and dst_acc.visibility == "shared") else "private",
        description=payload.description or f"Transfer to {dst_acc.name}",
        transaction_date=txn_date,
        status="POSTED",
        version=1,
    )
    db.add(outflow_leg)

    # 6. Leg 2: Inflow into Destination Account
    inflow_leg = Transaction(
        household_id=household_id,
        account_id=dst_acc.id,
        user_id=user_id,
        transfer_group_id=group.id,
        amount=payload.amount,
        direction="INFLOW",
        transaction_type="TRANSFER_IN",
        visibility="shared" if (src_acc.visibility == "shared" and dst_acc.visibility == "shared") else "private",
        description=payload.description or f"Transfer from {src_acc.name}",
        transaction_date=txn_date,
        status="POSTED",
        version=1,
    )
    db.add(inflow_leg)

    # 7. Audit Log
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="TransferGroup",
        entity_id=group.id,
        action="CREATE",
        new_values={
            "source_account": str(src_acc.id),
            "destination_account": str(dst_acc.id),
            "amount": str(payload.amount),
        },
    )
    db.add(audit)

    await db.commit()
    await db.refresh(group)
    await db.refresh(outflow_leg)
    await db.refresh(inflow_leg)

    return group, outflow_leg, inflow_leg


async def set_opening_balance(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: OpeningBalanceRequest,
) -> Transaction:
    """Sets initial opening balance for an account via an OPENING_BALANCE transaction."""
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == payload.account_id,
        FinancialAccount.household_id == household_id,
    )
    acc = (await db.execute(stmt_acc)).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    date = payload.date or datetime.now(UTC)
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)

    txn = Transaction(
        household_id=household_id,
        account_id=acc.id,
        user_id=user_id,
        amount=payload.amount,
        direction="INFLOW",
        transaction_type="OPENING_BALANCE",
        visibility=acc.visibility,
        description=payload.description or "Initial Opening Balance",
        transaction_date=date,
        status="POSTED",
        version=1,
    )
    db.add(txn)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Transaction",
        entity_id=txn.id,
        action="CREATE",
        new_values={"type": "OPENING_BALANCE", "amount": str(payload.amount)},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(txn)
    return txn


async def reverse_transfer_group(
    db: AsyncSession,
    group_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
) -> TransferGroup:
    """
    Atomically voids both legs of a transfer group.
    """
    stmt = (
        select(TransferGroup)
        .where(TransferGroup.id == group_id, TransferGroup.household_id == household_id)
        .options(selectinload(TransferGroup.transactions))
    )
    group = (await db.execute(stmt)).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer group not found")

    for leg in group.transactions:
        if leg.status != "VOIDED":
            leg.status = "VOIDED"
            leg.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="TransferGroup",
        entity_id=group.id,
        action="VOID",
        new_values={"reason": reason, "status": "VOIDED"},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(group)
    return group
