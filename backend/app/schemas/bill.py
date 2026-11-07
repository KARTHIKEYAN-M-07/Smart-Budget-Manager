"""Recurring Bills and Loan EMI Schemas"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecurringBillCreateRequest(BaseModel):
    biller_name: str = Field(min_length=2, max_length=100)
    category_id: uuid.UUID | None = None
    expected_amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    due_date: date
    frequency: str = Field(default="MONTHLY", pattern=r"^(MONTHLY|QUARTERLY|YEARLY|ONCE)$")
    reminder_days_before: int = Field(default=3, ge=0, le=30)

    @field_validator("expected_amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v


class BillSettleRequest(BaseModel):
    account_id: uuid.UUID = Field(description="Account from which the bill is settled")
    amount: Decimal | None = Field(default=None, gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    payment_date: date | None = None


class RecurringBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    category_id: uuid.UUID | None
    category_name: str | None = None
    biller_name: str
    expected_amount: Decimal
    due_date: date
    frequency: str
    reminder_days_before: int
    is_active: bool
    last_paid_date: date | None
    status: str  # "DUE", "OVERDUE", "PAID"
    version: int


class LoanCalculateRequest(BaseModel):
    principal_amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    annual_interest_rate: Decimal = Field(ge=Decimal("0.00"), le=Decimal("100.00"))
    tenure_months: int = Field(gt=0, le=600)


class AmortizationScheduleItem(BaseModel):
    month_number: int
    emi_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    outstanding_balance: Decimal


class LoanCalculateResponse(BaseModel):
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_interest_payable: Decimal
    total_amount_payable: Decimal
    amortization_schedule: list[AmortizationScheduleItem]


class LoanCreateRequest(BaseModel):
    lender_name: str = Field(min_length=2, max_length=100)
    loan_type: str = Field(min_length=2, max_length=50)
    principal_amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    annual_interest_rate: Decimal = Field(ge=Decimal("0.00"), le=Decimal("100.00"))
    tenure_months: int = Field(gt=0, le=600)
    start_date: date
    account_id: uuid.UUID | None = None


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID | None
    lender_name: str
    loan_type: str
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    start_date: date
    is_active: bool
    version: int
