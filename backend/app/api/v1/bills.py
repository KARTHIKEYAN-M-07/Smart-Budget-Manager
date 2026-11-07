"""Recurring Bills and Loan EMI Endpoints"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models import Household, User
from app.schemas.bill import (
    BillSettleRequest,
    LoanCalculateRequest,
    LoanCalculateResponse,
    LoanCreateRequest,
    LoanResponse,
    RecurringBillCreateRequest,
    RecurringBillResponse,
)
from app.schemas.transaction import TransactionResponse
from app.services.bill_service import (
    calculate_reducing_balance_emi,
    create_loan_record,
    create_recurring_bill,
    list_household_bills,
    list_household_loans,
    settle_bill_payment,
)

router = APIRouter(prefix="", tags=["Bills, EMI & Loans"])


# ------------------------------------------------------------------------------
# Recurring Bills
# ------------------------------------------------------------------------------
@router.get(
    "/bills",
    response_model=list[RecurringBillResponse],
    status_code=status.HTTP_200_OK,
    summary="List Recurring Household Bills",
)
async def get_bills(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[RecurringBillResponse]:
    """Lists recurring utility bills and subscriptions with real-time DUE, OVERDUE, or PAID status."""
    household, _ = household_and_role
    return await list_household_bills(db, household.id)


@router.post(
    "/bills",
    response_model=RecurringBillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Recurring Bill",
    dependencies=[Depends(verify_csrf)],
)
async def post_bill(
    payload: RecurringBillCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> RecurringBillResponse:
    """Creates a new recurring household bill schedule."""
    household, _ = household_and_role
    return await create_recurring_bill(db, household.id, user.id, payload)


@router.post(
    "/bills/{bill_id}/settle",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Settle Bill and Post Ledger Expense",
    dependencies=[Depends(verify_csrf)],
)
async def post_settle_bill(
    bill_id: uuid.UUID,
    payload: BillSettleRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    CRITICAL FINANCIAL INVARIANT:
    Never marks a bill paid without generating an authentic ledger transaction.
    Settles the bill, writes an atomic EXPENSE transaction, and advances next due date.
    """
    household, _ = household_and_role
    bill_resp, txn = await settle_bill_payment(db, household.id, user.id, bill_id, payload)

    return {
        "bill": bill_resp.model_dump(),
        "transaction": TransactionResponse.model_validate(txn).model_dump(),
        "message": f"Bill '{bill_resp.biller_name}' settled successfully.",
    }


# ------------------------------------------------------------------------------
# Loan EMI & Amortization
# ------------------------------------------------------------------------------
@router.post(
    "/loans/calculate",
    response_model=LoanCalculateResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Reducing-Balance EMI & Amortization Schedule",
)
def calculate_emi(
    payload: LoanCalculateRequest,
) -> LoanCalculateResponse:
    """
    Computes reducing balance monthly EMI and month-by-month principal/interest amortization schedule.
    Pure calculation; does not modify database state.
    """
    emi, total_interest, schedule = calculate_reducing_balance_emi(
        principal=payload.principal_amount,
        annual_interest_rate=payload.annual_interest_rate,
        tenure_months=payload.tenure_months,
    )
    total_payable = payload.principal_amount + total_interest

    return LoanCalculateResponse(
        principal_amount=payload.principal_amount,
        annual_interest_rate=payload.annual_interest_rate,
        tenure_months=payload.tenure_months,
        monthly_emi=emi,
        total_interest_payable=total_interest,
        total_amount_payable=total_payable,
        amortization_schedule=schedule,
    )


@router.get(
    "/loans",
    response_model=list[LoanResponse],
    status_code=status.HTTP_200_OK,
    summary="List Family Loans",
)
async def get_loans(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[LoanResponse]:
    """Lists registered family loans."""
    household, _ = household_and_role
    return await list_household_loans(db, household.id)


@router.post(
    "/loans",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Loan Account",
    dependencies=[Depends(verify_csrf)],
)
async def post_loan(
    payload: LoanCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> LoanResponse:
    """Registers a family loan."""
    household, _ = household_and_role
    return await create_loan_record(db, household.id, user.id, payload)
