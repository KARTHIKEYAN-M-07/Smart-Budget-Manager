"""Investment portfolio management service.
Enforces financial accuracy:
- Investment contributions are asset allocation movements (INVESTMENT_BUY), not consumption
- Strict derived gains/losses and return percentages
- Optimistic locking and IDOR 404 isolation
"""

import uuid
from datetime import UTC, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AssetClass,
    AuditLog,
    FinancialAccount,
    Investment,
    InvestmentTransaction,
    InvestmentTransactionType,
    Transaction,
)
from app.schemas.investment import (
    InvestmentCreateRequest,
    InvestmentPortfolioSummary,
    InvestmentResponse,
    InvestmentTransactionCreateRequest,
    InvestmentTransactionResponse,
    InvestmentUpdateRequest,
)


def build_investment_response(inv: Investment) -> InvestmentResponse:
    gain_loss = inv.current_value - inv.invested_amount
    return_pct = Decimal("0.00")
    if inv.invested_amount > Decimal("0.00"):
        return_pct = ((gain_loss / inv.invested_amount) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    txns = []
    if hasattr(inv, "transactions") and inv.transactions:
        for t in inv.transactions:
            txns.append(
                InvestmentTransactionResponse(
                    id=t.id,
                    investment_id=t.investment_id,
                    transaction_id=t.transaction_id,
                    transaction_type=InvestmentTransactionType(t.transaction_type),
                    transaction_date=t.transaction_date,
                    amount=t.amount,
                    units=t.units,
                    price_per_unit=t.price_per_unit,
                    notes=t.notes,
                    created_at=t.created_at,
                )
            )

    return InvestmentResponse(
        id=inv.id,
        household_id=inv.household_id,
        user_id=inv.user_id,
        account_id=inv.account_id,
        name=inv.name,
        asset_class=AssetClass(inv.asset_class),
        folio_or_account_number_last4=inv.folio_or_account_number_last4,
        institution_name=inv.institution_name,
        units_or_quantity=inv.units_or_quantity,
        invested_amount=inv.invested_amount,
        current_value=inv.current_value,
        interest_rate_percent=inv.interest_rate_percent,
        start_date=inv.start_date,
        maturity_date=inv.maturity_date,
        last_valuation_date=inv.last_valuation_date,
        valuation_source=inv.valuation_source,
        is_active=inv.is_active,
        notes=inv.notes,
        version=inv.version,
        created_at=inv.created_at,
        unrealized_gain_loss=gain_loss,
        return_percentage=return_pct,
        transactions=txns,
    )


async def create_investment(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: InvestmentCreateRequest,
) -> InvestmentResponse:
    val_date = payload.start_date
    cur_val = payload.current_value if payload.current_value is not None else payload.invested_amount

    # 1. Create Investment entity
    inv = Investment(
        household_id=household_id,
        user_id=user_id,
        account_id=payload.account_id,
        name=payload.name,
        asset_class=payload.asset_class.value,
        folio_or_account_number_last4=payload.folio_or_account_number_last4,
        institution_name=payload.institution_name,
        units_or_quantity=payload.units_or_quantity,
        invested_amount=payload.invested_amount,
        current_value=cur_val,
        interest_rate_percent=payload.interest_rate_percent,
        start_date=payload.start_date,
        maturity_date=payload.maturity_date,
        last_valuation_date=val_date,
        valuation_source=payload.valuation_source,
        notes=payload.notes,
        version=1,
    )
    db.add(inv)
    await db.flush()

    # 2. If source_account_id provided, record INVESTMENT_BUY ledger movement
    ledger_txn_id = None
    if payload.source_account_id and payload.invested_amount > Decimal("0.00"):
        stmt_acc = select(FinancialAccount).where(
            FinancialAccount.id == payload.source_account_id,
            FinancialAccount.household_id == household_id,
            FinancialAccount.is_active.is_(True),
        )
        res_acc = await db.execute(stmt_acc)
        acc = res_acc.scalar_one_or_none()
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source funding account not found or inactive",
            )

        txn_dt = datetime.combine(payload.start_date, time.min, tzinfo=UTC)
        ledger_txn = Transaction(
            household_id=household_id,
            account_id=acc.id,
            user_id=user_id,
            amount=payload.invested_amount,
            direction="OUTFLOW",
            transaction_type="INVESTMENT_BUY",
            visibility="shared",
            description=f"Investment Contribution: {inv.name}",
            transaction_date=txn_dt,
            status="POSTED",
            version=1,
        )
        db.add(ledger_txn)
        await db.flush()
        ledger_txn_id = ledger_txn.id

    # 3. Create initial InvestmentTransaction
    initial_txn = InvestmentTransaction(
        investment_id=inv.id,
        transaction_id=ledger_txn_id,
        transaction_type=InvestmentTransactionType.BUY.value,
        transaction_date=payload.start_date,
        amount=payload.invested_amount,
        units=payload.units_or_quantity,
        price_per_unit=(
            (payload.invested_amount / payload.units_or_quantity).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if payload.units_or_quantity > Decimal("0.0000")
            else None
        ),
        notes="Initial purchase/allocation",
    )
    db.add(initial_txn)

    # 4. Audit Log
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Investment",
        entity_id=inv.id,
        action="CREATE",
        new_values={
            "name": inv.name,
            "asset_class": inv.asset_class,
            "invested_amount": str(inv.invested_amount),
            "current_value": str(inv.current_value),
        },
    )
    db.add(audit)
    await db.commit()

    return await get_investment_by_id(db, household_id, inv.id)


async def list_investments(
    db: AsyncSession,
    household_id: uuid.UUID,
    asset_class: AssetClass | None = None,
    is_active: bool | None = None,
) -> list[InvestmentResponse]:
    stmt = (
        select(Investment)
        .where(Investment.household_id == household_id)
        .options(selectinload(Investment.transactions))
        .order_by(Investment.is_active.desc(), Investment.start_date.desc())
    )
    if asset_class:
        stmt = stmt.where(Investment.asset_class == asset_class.value)
    if is_active is not None:
        stmt = stmt.where(Investment.is_active == is_active)

    res = await db.execute(stmt)
    investments = res.scalars().all()
    return [build_investment_response(i) for i in investments]


async def get_investment_by_id(
    db: AsyncSession,
    household_id: uuid.UUID,
    investment_id: uuid.UUID,
) -> InvestmentResponse:
    stmt = (
        select(Investment)
        .where(
            Investment.id == investment_id,
            Investment.household_id == household_id,
        )
        .options(selectinload(Investment.transactions))
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment holding not found",
        )
    return build_investment_response(inv)


async def update_investment(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    payload: InvestmentUpdateRequest,
) -> InvestmentResponse:
    stmt = (
        select(Investment)
        .where(
            Investment.id == investment_id,
            Investment.household_id == household_id,
        )
        .options(selectinload(Investment.transactions))
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment holding not found",
        )

    # Optimistic locking
    if inv.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Investment was modified by another session. Please reload.",
        )

    old_vals = {
        "current_value": str(inv.current_value),
        "version": inv.version,
    }

    if payload.name is not None:
        inv.name = payload.name
    if payload.units_or_quantity is not None:
        inv.units_or_quantity = payload.units_or_quantity
    if payload.current_value is not None:
        inv.current_value = payload.current_value
        inv.last_valuation_date = payload.last_valuation_date or datetime.now(UTC).date()
    if payload.valuation_source is not None:
        inv.valuation_source = payload.valuation_source
    if payload.is_active is not None:
        inv.is_active = payload.is_active
    if payload.notes is not None:
        inv.notes = payload.notes

    inv.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Investment",
        entity_id=inv.id,
        action="UPDATE",
        old_values=old_vals,
        new_values={
            "current_value": str(inv.current_value),
            "version": inv.version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(inv)

    return build_investment_response(inv)


async def add_investment_transaction(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    payload: InvestmentTransactionCreateRequest,
) -> InvestmentTransactionResponse:
    stmt = select(Investment).where(
        Investment.id == investment_id,
        Investment.household_id == household_id,
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment holding not found",
        )

    ledger_txn_id = None
    if payload.source_account_id:
        stmt_acc = select(FinancialAccount).where(
            FinancialAccount.id == payload.source_account_id,
            FinancialAccount.household_id == household_id,
            FinancialAccount.is_active.is_(True),
        )
        res_acc = await db.execute(stmt_acc)
        acc = res_acc.scalar_one_or_none()
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked bank/cash account not found or inactive",
            )

        txn_dt = datetime.combine(payload.transaction_date, time.min, tzinfo=UTC)

        if payload.transaction_type == InvestmentTransactionType.BUY:
            l_type = "INVESTMENT_BUY"
            direction = "OUTFLOW"
            desc = f"Investment Buy: {inv.name}"
        elif payload.transaction_type == InvestmentTransactionType.SELL:
            l_type = "INVESTMENT_SELL"
            direction = "INFLOW"
            desc = f"Investment Redemption: {inv.name}"
        else:
            l_type = "INCOME"
            direction = "INFLOW"
            desc = f"Investment {payload.transaction_type.value}: {inv.name}"

        ledger_txn = Transaction(
            household_id=household_id,
            account_id=acc.id,
            user_id=user_id,
            amount=payload.amount,
            direction=direction,
            transaction_type=l_type,
            visibility="shared",
            description=desc,
            transaction_date=txn_dt,
            status="POSTED",
            version=1,
        )
        db.add(ledger_txn)
        await db.flush()
        ledger_txn_id = ledger_txn.id

    inv_txn = InvestmentTransaction(
        investment_id=inv.id,
        transaction_id=ledger_txn_id,
        transaction_type=payload.transaction_type.value,
        transaction_date=payload.transaction_date,
        amount=payload.amount,
        units=payload.units,
        price_per_unit=payload.price_per_unit,
        notes=payload.notes,
    )
    db.add(inv_txn)

    # Adjust investment invested amount & units
    if payload.transaction_type == InvestmentTransactionType.BUY:
        inv.invested_amount += payload.amount
        inv.units_or_quantity += payload.units
    elif payload.transaction_type == InvestmentTransactionType.SELL:
        inv.invested_amount = max(Decimal("0.00"), inv.invested_amount - payload.amount)
        inv.units_or_quantity = max(Decimal("0.0000"), inv.units_or_quantity - payload.units)
    inv.version += 1

    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="InvestmentTransaction",
        entity_id=inv_txn.id,
        action="CREATE",
        new_values={
            "investment_id": str(inv.id),
            "amount": str(payload.amount),
            "type": payload.transaction_type.value,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(inv_txn)

    return InvestmentTransactionResponse.model_validate(inv_txn)


async def get_investment_portfolio_summary(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> InvestmentPortfolioSummary:
    investments = await list_investments(db, household_id, is_active=True)

    total_invested = Decimal("0.00")
    total_val = Decimal("0.00")
    by_class: dict[str, Decimal] = {}

    for inv in investments:
        total_invested += inv.invested_amount
        total_val += inv.current_value
        by_class[inv.asset_class.value] = by_class.get(inv.asset_class.value, Decimal("0.00")) + inv.current_value

    gain_loss = total_val - total_invested
    return_pct = Decimal("0.00")
    if total_invested > Decimal("0.00"):
        return_pct = ((gain_loss / total_invested) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return InvestmentPortfolioSummary(
        total_invested=total_invested,
        total_current_value=total_val,
        total_unrealized_gain_loss=gain_loss,
        overall_return_percentage=return_pct,
        by_asset_class=by_class,
        investments_count=len(investments),
    )
