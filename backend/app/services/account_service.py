"""Account service handling derived balance queries and access control"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FinancialAccount, Transaction

LIABILITY_ACCOUNT_TYPES = {"credit_card", "loan"}


async def calculate_derived_balance(db: AsyncSession, account_id: uuid.UUID, account_type: str) -> Decimal:
    """
    CRITICAL FINANCIAL ACCURACY ENGINE:
    Calculates derived balance directly from posted ledger transactions.
    - Asset accounts (Savings, Cash, Current): Inflows - Outflows.
    - Liability accounts (Credit Card, Loan): Outflows (purchases) - Inflows (bill settlements).
    """
    # Sum Inflows
    inflow_stmt = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        Transaction.account_id == account_id,
        Transaction.status == "POSTED",
        Transaction.direction == "INFLOW",
    )
    total_inflow = (await db.execute(inflow_stmt)).scalar() or Decimal("0.00")

    # Sum Outflows
    outflow_stmt = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        Transaction.account_id == account_id,
        Transaction.status == "POSTED",
        Transaction.direction == "OUTFLOW",
    )
    total_outflow = (await db.execute(outflow_stmt)).scalar() or Decimal("0.00")

    if account_type.lower() in LIABILITY_ACCOUNT_TYPES:
        # Net liability balance
        return total_outflow - total_inflow
    # Net asset balance
    return total_inflow - total_outflow


async def list_accessible_accounts(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[tuple[FinancialAccount, Decimal]]:
    """
    Lists accounts accessible to the current user in their active household.
    Enforces visibility: shared accounts OR private accounts created by this user.
    """
    stmt = (
        select(FinancialAccount)
        .where(
            FinancialAccount.household_id == household_id,
            (FinancialAccount.visibility == "shared") | (FinancialAccount.user_id == user_id),
        )
        .order_by(FinancialAccount.is_active.desc(), FinancialAccount.name)
    )
    accounts = (await db.execute(stmt)).scalars().all()

    results = []
    for acc in accounts:
        balance = await calculate_derived_balance(db, acc.id, acc.account_type)
        results.append((acc, balance))
    return results


async def get_accessible_account(
    db: AsyncSession,
    account_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[FinancialAccount, Decimal] | None:
    """
    Retrieves an account only if it belongs to the current household and is accessible.
    Returns None if missing, cross-household, or unauthorized private account.
    """
    stmt = select(FinancialAccount).where(FinancialAccount.id == account_id)
    acc = (await db.execute(stmt)).scalar_one_or_none()

    if not acc:
        return None
    # IDOR Prevention: Check household boundary
    if acc.household_id != household_id:
        return None
    # Visibility check: If private, only the owner can access
    if acc.visibility == "private" and acc.user_id != user_id:
        return None

    balance = await calculate_derived_balance(db, acc.id, acc.account_type)
    return acc, balance
