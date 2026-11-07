"""Budget and Savings Goals Business Service"""

import calendar
import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Budget, Category, SavingsGoal, Transaction
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetResponse,
    SavingsGoalCreateRequest,
    SavingsGoalResponse,
    SavingsGoalUpdateRequest,
)


def compute_alert_threshold(pct: Decimal) -> str:
    """Computes budget threshold alert level."""
    if pct >= Decimal("100.00"):
        return "EXCEEDED_100"
    if pct >= Decimal("90.00"):
        return "WARNING_90"
    if pct >= Decimal("75.00"):
        return "WARNING_75"
    return "NORMAL"


async def get_budget_spend(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    category_id: uuid.UUID | None,
    month_str: str,
) -> Decimal:
    """
    Calculates actual net spend in real-time from posted ledger transactions
    for the specified month ("YYYY-MM").
    Net Spend = Expenses - Refunds.
    """
    year, month = map(int, month_str.split("-"))
    _, last_day = calendar.monthrange(year, month)

    start_dt = datetime.combine(date(year, month, 1), time.min, tzinfo=UTC)
    end_dt = datetime.combine(date(year, month, last_day), time.max, tzinfo=UTC)

    base_filter = [
        Transaction.household_id == household_id,
        Transaction.status == "POSTED",
        Transaction.transaction_date >= start_dt,
        Transaction.transaction_date <= end_dt,
        (Transaction.visibility == "shared") | (Transaction.user_id == user_id),
    ]
    if category_id:
        base_filter.append(Transaction.category_id == category_id)

    # Gross Expenses
    stmt_exp = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        *base_filter,
        Transaction.transaction_type == "EXPENSE",
    )
    gross_exp = (await db.execute(stmt_exp)).scalar() or Decimal("0.00")

    # Refunds
    stmt_ref = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        *base_filter,
        Transaction.transaction_type == "REFUND",
    )
    refunds = (await db.execute(stmt_ref)).scalar() or Decimal("0.00")

    return max(Decimal("0.00"), gross_exp - refunds)


async def list_household_budgets(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    month_str: str,
) -> list[BudgetResponse]:
    """Lists all budgets for a given month with dynamic spend and threshold calculations."""
    stmt = (
        select(Budget)
        .where(Budget.household_id == household_id, Budget.month == month_str)
        .options(selectinload(Budget.category))
        .order_by(Budget.amount.desc())
    )
    budgets = (await db.execute(stmt)).scalars().all()

    response: list[BudgetResponse] = []
    for b in budgets:
        spend = await get_budget_spend(db, household_id, user_id, b.category_id, b.month)
        remaining = max(Decimal("0.00"), b.amount - spend)
        pct = (
            ((spend / b.amount) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if b.amount > 0
            else Decimal("0.00")
        )
        threshold = compute_alert_threshold(pct)

        response.append(
            BudgetResponse(
                id=b.id,
                household_id=b.household_id,
                category_id=b.category_id,
                category_name=b.category.name if b.category else "All Categories",
                month=b.month,
                amount=b.amount,
                current_spend=spend,
                remaining_amount=remaining,
                percentage_used=pct,
                alert_threshold=threshold,
                version=b.version,
            )
        )
    return response


async def set_or_create_budget(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: BudgetCreateRequest,
) -> BudgetResponse:
    """Creates or updates a monthly budget limit."""
    # Check if category exists
    cat_name = "All Categories"
    if payload.category_id:
        stmt_cat = select(Category).where(
            Category.id == payload.category_id,
            Category.household_id == household_id,
        )
        cat = (await db.execute(stmt_cat)).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        cat_name = cat.name

    # Check for existing budget in this month
    stmt_exist = select(Budget).where(
        Budget.household_id == household_id,
        Budget.category_id == payload.category_id,
        Budget.month == payload.month,
    )
    existing = (await db.execute(stmt_exist)).scalar_one_or_none()

    if existing:
        existing.amount = payload.amount
        existing.version += 1
        budget_obj = existing
        action = "UPDATE"
    else:
        budget_obj = Budget(
            household_id=household_id,
            category_id=payload.category_id,
            month=payload.month,
            amount=payload.amount,
            version=1,
        )
        db.add(budget_obj)
        action = "CREATE"

    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Budget",
        entity_id=budget_obj.id,
        action=action,
        new_values={"month": payload.month, "amount": str(payload.amount), "category": cat_name},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(budget_obj)

    spend = await get_budget_spend(db, household_id, user_id, budget_obj.category_id, budget_obj.month)
    remaining = max(Decimal("0.00"), budget_obj.amount - spend)
    pct = (
        ((spend / budget_obj.amount) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if budget_obj.amount > 0
        else Decimal("0.00")
    )

    return BudgetResponse(
        id=budget_obj.id,
        household_id=budget_obj.household_id,
        category_id=budget_obj.category_id,
        category_name=cat_name,
        month=budget_obj.month,
        amount=budget_obj.amount,
        current_spend=spend,
        remaining_amount=remaining,
        percentage_used=pct,
        alert_threshold=compute_alert_threshold(pct),
        version=budget_obj.version,
    )


async def delete_budget(
    db: AsyncSession,
    budget_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Removes a budget limit."""
    stmt = select(Budget).where(Budget.id == budget_id, Budget.household_id == household_id)
    budget = (await db.execute(stmt)).scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Budget",
        entity_id=budget.id,
        action="VOID",
        old_values={"month": budget.month, "amount": str(budget.amount)},
    )
    db.add(audit)
    await db.delete(budget)
    await db.commit()


# ------------------------------------------------------------------------------
# Savings Goals Services
# ------------------------------------------------------------------------------
def build_goal_response(g: SavingsGoal) -> SavingsGoalResponse:
    pct = (
        ((g.current_amount / g.target_amount) * Decimal("100.00")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if g.target_amount > 0
        else Decimal("0.00")
    )
    remaining = max(Decimal("0.00"), g.target_amount - g.current_amount)
    return SavingsGoalResponse(
        id=g.id,
        household_id=g.household_id,
        name=g.name,
        target_amount=g.target_amount,
        current_amount=g.current_amount,
        target_date=g.target_date,
        status=g.status,
        percentage_achieved=pct,
        remaining_amount=remaining,
        version=g.version,
    )


async def list_savings_goals(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[SavingsGoalResponse]:
    """Lists all active and achieved savings goals."""
    stmt = (
        select(SavingsGoal)
        .where(SavingsGoal.household_id == household_id)
        .order_by(SavingsGoal.status, SavingsGoal.target_date.nulls_last())
    )
    goals = (await db.execute(stmt)).scalars().all()
    return [build_goal_response(g) for g in goals]


async def create_savings_goal(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SavingsGoalCreateRequest,
) -> SavingsGoalResponse:
    """Creates a new savings goal."""
    status_str = "ACHIEVED" if payload.current_amount >= payload.target_amount else "ACTIVE"

    goal = SavingsGoal(
        household_id=household_id,
        name=payload.name.strip(),
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        target_date=payload.target_date,
        status=status_str,
        version=1,
    )
    db.add(goal)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="SavingsGoal",
        entity_id=goal.id,
        action="CREATE",
        new_values={"name": goal.name, "target": str(goal.target_amount)},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(goal)
    return build_goal_response(goal)


async def update_savings_goal(
    db: AsyncSession,
    goal_id: uuid.UUID,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: SavingsGoalUpdateRequest,
) -> SavingsGoalResponse:
    """Updates goal progress or metadata with optimistic locking."""
    stmt = select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.household_id == household_id)
    goal = (await db.execute(stmt)).scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    if goal.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Goal was updated by another session. Please refresh and retry.",
        )

    if payload.name is not None:
        goal.name = payload.name.strip()
    if payload.target_amount is not None:
        goal.target_amount = payload.target_amount
    if payload.current_amount is not None:
        goal.current_amount = payload.current_amount
    if payload.target_date is not None:
        goal.target_date = payload.target_date
    if payload.status is not None:
        goal.status = payload.status

    # Auto transition to ACHIEVED if reached
    if goal.current_amount >= goal.target_amount and goal.status == "ACTIVE":
        goal.status = "ACHIEVED"

    goal.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="SavingsGoal",
        entity_id=goal.id,
        action="UPDATE",
        new_values={"current": str(goal.current_amount), "status": goal.status},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(goal)
    return build_goal_response(goal)
