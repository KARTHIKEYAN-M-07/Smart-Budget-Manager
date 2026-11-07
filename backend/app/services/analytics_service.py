"""Analytics and financial aggregation service.
Adheres strictly to financial accuracy rules:
- Excludes VOIDED transactions
- Respects household boundary and private transaction visibility
- Transfers (TRANSFER_IN / TRANSFER_OUT) and OPENING_BALANCE are strictly EXCLUDED from spending/income
- Refunds reduce net expenses (never inflated into income)
- Indian Financial Year (April 1 - March 31) calculation
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Transaction, User
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    CategorySpendItem,
    FinancialYearReportResponse,
    MemberSpendItem,
    MonthlyTrendItem,
)


def get_current_financial_year(ref_date: date | None = None) -> tuple[str, date, date]:
    """
    Computes Indian Financial Year boundaries (April 1 to March 31).
    Example:
    - 2026-11-07 -> FY 2026-27 (2026-04-01 to 2027-03-31)
    - 2026-02-15 -> FY 2025-26 (2025-04-01 to 2026-03-31)
    """
    current = ref_date or datetime.now(UTC).date()
    if current.month >= 4:
        start_year = current.year
        end_year = current.year + 1
    else:
        start_year = current.year - 1
        end_year = current.year

    fy_label = f"FY {start_year}-{str(end_year)[-2:]}"
    start_date = date(start_year, 4, 1)
    end_date = date(end_year, 3, 31)
    return fy_label, start_date, end_date


async def get_overview_analytics(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> AnalyticsOverviewResponse:
    """Aggregates overview metrics within the given date window."""
    start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_date, time.max, tzinfo=UTC)

    base_filter = [
        Transaction.household_id == household_id,
        Transaction.status == "POSTED",
        Transaction.transaction_date >= start_dt,
        Transaction.transaction_date <= end_dt,
        (Transaction.visibility == "shared") | (Transaction.user_id == user_id),
    ]

    # 1. Total Income
    stmt_income = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        *base_filter,
        Transaction.transaction_type == "INCOME",
    )
    total_income = (await db.execute(stmt_income)).scalar() or Decimal("0.00")

    # 2. Gross Expenses
    stmt_expense = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        *base_filter,
        Transaction.transaction_type == "EXPENSE",
    )
    gross_expense = (await db.execute(stmt_expense)).scalar() or Decimal("0.00")

    # 3. Total Refunds (Reduces spending, not income)
    stmt_refunds = select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
        *base_filter,
        Transaction.transaction_type == "REFUND",
    )
    total_refunds = (await db.execute(stmt_refunds)).scalar() or Decimal("0.00")

    # Net Expense
    net_expense = max(Decimal("0.00"), gross_expense - total_refunds)
    net_savings = total_income - net_expense

    # Savings Rate: (Net Savings / Total Income) * 100
    if total_income > Decimal("0.00"):
        savings_rate = ((net_savings / total_income) * Decimal("100.00")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        savings_rate = Decimal("0.00")

    # 4. Category Spend Breakdown
    stmt_cats = (
        select(
            Category.id,
            Category.name,
            Category.color,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("cat_total"),
        )
        .outerjoin(Category, Transaction.category_id == Category.id)
        .where(
            *base_filter,
            Transaction.transaction_type == "EXPENSE",
        )
        .group_by(Category.id, Category.name, Category.color)
        .order_by(func.sum(Transaction.amount).desc())
    )
    cat_rows = (await db.execute(stmt_cats)).all()

    category_items: list[CategorySpendItem] = []
    for cid, cname, ccolor, camount in cat_rows:
        pct = (
            ((camount / gross_expense) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if gross_expense > 0
            else Decimal("0.00")
        )
        category_items.append(
            CategorySpendItem(
                category_id=str(cid) if cid else None,
                category_name=cname or "Uncategorized",
                category_color=ccolor or "#94a3b8",
                total_amount=camount,
                percentage=pct,
            )
        )

    # 5. Member Spend Breakdown
    stmt_members = (
        select(
            User.id,
            User.full_name,
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00")).label("user_total"),
        )
        .join(User, Transaction.user_id == User.id)
        .where(
            *base_filter,
            Transaction.transaction_type == "EXPENSE",
        )
        .group_by(User.id, User.full_name)
        .order_by(func.sum(Transaction.amount).desc())
    )
    member_rows = (await db.execute(stmt_members)).all()

    member_items: list[MemberSpendItem] = []
    for uid, uname, uamount in member_rows:
        pct = (
            ((uamount / gross_expense) * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if gross_expense > 0
            else Decimal("0.00")
        )
        member_items.append(
            MemberSpendItem(
                user_id=str(uid),
                user_name=uname,
                total_amount=uamount,
                percentage=pct,
            )
        )

    return AnalyticsOverviewResponse(
        start_date=start_date,
        end_date=end_date,
        total_income=total_income,
        total_expense=net_expense,
        total_refunds=total_refunds,
        net_savings=net_savings,
        savings_rate=savings_rate,
        categories=category_items,
        members=member_items,
    )


async def get_financial_year_report(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    year_offset: int = 0,
) -> FinancialYearReportResponse:
    """Generates 12-month report across the Indian Financial Year (April 1 to March 31)."""
    now = datetime.now(UTC).date()
    fy_label, start_date, end_date = get_current_financial_year(
        date(now.year + year_offset, now.month, now.day)
    )

    start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_date, time.max, tzinfo=UTC)

    base_filter = [
        Transaction.household_id == household_id,
        Transaction.status == "POSTED",
        Transaction.transaction_date >= start_dt,
        Transaction.transaction_date <= end_dt,
        (Transaction.visibility == "shared") | (Transaction.user_id == user_id),
    ]

    # Fetch all posted income and expense transactions in the FY
    stmt = select(
        Transaction.transaction_type,
        Transaction.amount,
        Transaction.transaction_date,
    ).where(
        *base_filter,
        Transaction.transaction_type.in_(["INCOME", "EXPENSE", "REFUND"]),
    )
    rows = (await db.execute(stmt)).all()

    # Pre-populate 12 months in Indian FY order (April to March)
    months_order = [
        (4, start_date.year),
        (5, start_date.year),
        (6, start_date.year),
        (7, start_date.year),
        (8, start_date.year),
        (9, start_date.year),
        (10, start_date.year),
        (11, start_date.year),
        (12, start_date.year),
        (1, end_date.year),
        (2, end_date.year),
        (3, end_date.year),
    ]

    month_data: dict[str, dict[str, Decimal]] = {}
    month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for m, y in months_order:
        key = f"{y:04d}-{m:02d}"
        label = f"{month_names[m]} {y}"
        month_data[key] = {
            "label": label,
            "income": Decimal("0.00"),
            "expense": Decimal("0.00"),
            "refund": Decimal("0.00"),
        }

    # Aggregate transactions
    for ttype, amt, tdate in rows:
        key = f"{tdate.year:04d}-{tdate.month:02d}"
        if key in month_data:
            if ttype == "INCOME":
                month_data[key]["income"] += amt
            elif ttype == "EXPENSE":
                month_data[key]["expense"] += amt
            elif ttype == "REFUND":
                month_data[key]["refund"] += amt

    monthly_trends: list[MonthlyTrendItem] = []
    total_fy_income = Decimal("0.00")
    total_fy_expense = Decimal("0.00")

    for key, data in month_data.items():
        net_exp = max(Decimal("0.00"), data["expense"] - data["refund"])
        savings = data["income"] - net_exp
        total_fy_income += data["income"]
        total_fy_expense += net_exp

        monthly_trends.append(
            MonthlyTrendItem(
                month_name=data["label"],
                month_key=key,
                total_income=data["income"],
                total_expense=net_exp,
                net_savings=savings,
            )
        )

    return FinancialYearReportResponse(
        financial_year=fy_label,
        start_date=start_date,
        end_date=end_date,
        total_income=total_fy_income,
        total_expense=total_fy_expense,
        net_savings=total_fy_income - total_fy_expense,
        monthly_trends=monthly_trends,
    )
