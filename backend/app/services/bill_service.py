"""Recurring Bills and Loan EMI Calculation Service.
Adheres strictly to financial accuracy:
- Reducing balance loan EMI calculation with exact amortization schedule
- Bills are NEVER marked paid without an explicit settled ledger transaction
- Frequency due date rollovers for recurring household expenses
"""

import calendar
import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AuditLog, Category, FinancialAccount, Loan, RecurringBill, Transaction
from app.schemas.bill import (
    AmortizationScheduleItem,
    BillSettleRequest,
    LoanCreateRequest,
    LoanResponse,
    RecurringBillCreateRequest,
    RecurringBillResponse,
)


def calculate_reducing_balance_emi(
    principal: Decimal,
    annual_interest_rate: Decimal,
    tenure_months: int,
) -> tuple[Decimal, Decimal, list[AmortizationScheduleItem]]:
    """
    Computes EMI using standard Indian reducing-balance formula:
    EMI = [P x r x (1+r)^n] / [(1+r)^n - 1]
    where r = monthly interest rate = annual_rate / 12 / 100
    """
    p = float(principal)
    annual_rate_float = float(annual_interest_rate)
    n = tenure_months

    if annual_rate_float == 0:
        emi_float = p / n
        monthly_rate = 0.0
    else:
        monthly_rate = annual_rate_float / (12 * 100)
        numerator = p * monthly_rate * ((1 + monthly_rate) ** n)
        denominator = ((1 + monthly_rate) ** n) - 1
        emi_float = numerator / denominator

    monthly_emi = Decimal(str(emi_float)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Generate amortization schedule
    schedule: list[AmortizationScheduleItem] = []
    balance = principal
    total_interest = Decimal("0.00")

    for month_idx in range(1, tenure_months + 1):
        if monthly_rate > 0:
            interest = (balance * Decimal(str(monthly_rate))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            interest = Decimal("0.00")

        # For the final month, adjust principal to match exact remaining balance
        if month_idx == tenure_months:
            principal_paid = balance
            actual_emi = principal_paid + interest
        else:
            principal_paid = min(balance, monthly_emi - interest)
            actual_emi = monthly_emi

        balance = max(Decimal("0.00"), balance - principal_paid)
        total_interest += interest

        schedule.append(
            AmortizationScheduleItem(
                month_number=month_idx,
                emi_amount=actual_emi,
                principal_component=principal_paid,
                interest_component=interest,
                outstanding_balance=balance,
            )
        )

    return monthly_emi, total_interest, schedule


def advance_due_date(current_due: date, frequency: str) -> date:
    """Advances bill due date based on frequency."""
    year = current_due.year
    month = current_due.month
    day = current_due.day

    if frequency == "MONTHLY":
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif frequency == "QUARTERLY":
        month += 3
        while month > 12:
            month -= 12
            year += 1
    elif frequency == "YEARLY":
        year += 1
    else:
        return current_due

    # Adjust for month end (e.g. Feb 30 -> Feb 28/29)
    _, max_days = calendar.monthrange(year, month)
    adjusted_day = min(day, max_days)
    return date(year, month, adjusted_day)


# ------------------------------------------------------------------------------
# Recurring Bills Services
# ------------------------------------------------------------------------------
def build_bill_response(bill: RecurringBill, category_name: str | None = None) -> RecurringBillResponse:
    today = datetime.now(UTC).date()
    if bill.last_paid_date and bill.last_paid_date >= bill.due_date:
        bill_status = "PAID"
    elif bill.due_date < today:
        bill_status = "OVERDUE"
    else:
        bill_status = "DUE"

    if category_name is None and "category" in bill.__dict__ and bill.category is not None:
        category_name = bill.category.name

    return RecurringBillResponse(
        id=bill.id,
        household_id=bill.household_id,
        category_id=bill.category_id,
        category_name=category_name,
        biller_name=bill.biller_name,
        expected_amount=bill.expected_amount,
        due_date=bill.due_date,
        frequency=bill.frequency,
        reminder_days_before=bill.reminder_days_before,
        is_active=bill.is_active,
        last_paid_date=bill.last_paid_date,
        status=bill_status,
        version=bill.version,
    )


async def list_household_bills(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[RecurringBillResponse]:
    """Lists recurring bills with real-time status (DUE, OVERDUE, PAID)."""
    stmt = (
        select(RecurringBill)
        .where(RecurringBill.household_id == household_id)
        .options(selectinload(RecurringBill.category))
        .order_by(RecurringBill.is_active.desc(), RecurringBill.due_date)
    )
    bills = (await db.execute(stmt)).scalars().all()
    return [build_bill_response(b) for b in bills]


async def create_recurring_bill(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: RecurringBillCreateRequest,
) -> RecurringBillResponse:
    """Registers a recurring household utility/service bill."""
    bill = RecurringBill(
        household_id=household_id,
        category_id=payload.category_id,
        biller_name=payload.biller_name.strip(),
        expected_amount=payload.expected_amount,
        due_date=payload.due_date,
        frequency=payload.frequency,
        reminder_days_before=payload.reminder_days_before,
        is_active=True,
        version=1,
    )
    db.add(bill)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="RecurringBill",
        entity_id=bill.id,
        action="CREATE",
        new_values={"biller": bill.biller_name, "amount": str(bill.expected_amount), "due": str(bill.due_date)},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(bill)
    cat_name = None
    if bill.category_id:
        stmt_cat = select(Category.name).where(Category.id == bill.category_id)
        cat_name = (await db.execute(stmt_cat)).scalar_one_or_none()

    return build_bill_response(bill, category_name=cat_name)


async def settle_bill_payment(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    bill_id: uuid.UUID,
    payload: BillSettleRequest,
) -> tuple[RecurringBillResponse, Transaction]:
    """
    CRITICAL FINANCIAL INVARIANT:
    Never marks a bill paid without generating a reconciled ledger transaction.
    Settles bill -> Creates posted EXPENSE transaction -> Advances next due date.
    """
    stmt = select(RecurringBill).where(
        RecurringBill.id == bill_id,
        RecurringBill.household_id == household_id,
    )
    bill = (await db.execute(stmt)).scalar_one_or_none()
    if not bill or not bill.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found or inactive")

    # Validate paying account
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == payload.account_id,
        FinancialAccount.household_id == household_id,
    )
    acc = (await db.execute(stmt_acc)).scalar_one_or_none()
    if not acc or not acc.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment account not found or inactive")

    payment_amt = payload.amount or bill.expected_amount
    pay_date = payload.payment_date or datetime.now(UTC).date()
    pay_dt = datetime.combine(pay_date, time.min, tzinfo=UTC)

    # 1. Create Ledger Transaction
    txn = Transaction(
        household_id=household_id,
        account_id=acc.id,
        category_id=bill.category_id,
        user_id=user_id,
        amount=payment_amt,
        direction="OUTFLOW",
        transaction_type="EXPENSE",
        visibility="shared",
        description=f"Bill Settlement: {bill.biller_name}",
        transaction_date=pay_dt,
        status="POSTED",
        version=1,
    )
    db.add(txn)

    # 2. Update Bill Status & Advance Due Date
    bill.last_paid_date = pay_date
    if bill.frequency == "ONCE":
        bill.is_active = False
    else:
        bill.due_date = advance_due_date(bill.due_date, bill.frequency)
    bill.version += 1

    # 3. Audit Log
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="RecurringBill",
        entity_id=bill.id,
        action="UPDATE",
        new_values={"action": "SETTLE_BILL", "amount": str(payment_amt), "next_due": str(bill.due_date)},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(bill)
    await db.refresh(txn)

    cat_name = None
    if bill.category_id:
        stmt_cat = select(Category.name).where(Category.id == bill.category_id)
        cat_name = (await db.execute(stmt_cat)).scalar_one_or_none()

    return build_bill_response(bill, category_name=cat_name), txn


# ------------------------------------------------------------------------------
# Loan & EMI Services
# ------------------------------------------------------------------------------
async def create_loan_record(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: LoanCreateRequest,
) -> LoanResponse:
    """Registers a family loan and sets reducing-balance monthly EMI."""
    emi, _, _ = calculate_reducing_balance_emi(
        principal=payload.principal_amount,
        annual_interest_rate=payload.annual_interest_rate,
        tenure_months=payload.tenure_months,
    )

    loan = Loan(
        household_id=household_id,
        account_id=payload.account_id,
        lender_name=payload.lender_name.strip(),
        loan_type=payload.loan_type.strip(),
        principal_amount=payload.principal_amount,
        annual_interest_rate=payload.annual_interest_rate,
        tenure_months=payload.tenure_months,
        monthly_emi=emi,
        start_date=payload.start_date,
        is_active=True,
        version=1,
    )
    db.add(loan)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="Loan",
        entity_id=loan.id,
        action="CREATE",
        new_values={"lender": loan.lender_name, "principal": str(loan.principal_amount), "emi": str(emi)},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(loan)

    return LoanResponse.model_validate(loan)


async def list_household_loans(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[LoanResponse]:
    """Lists all active and settled loans for the household."""
    stmt = (
        select(Loan)
        .where(Loan.household_id == household_id)
        .order_by(Loan.is_active.desc(), Loan.start_date.desc())
    )
    loans = (await db.execute(stmt)).scalars().all()
    return [LoanResponse.model_validate(loan_item) for loan_item in loans]
