"""Budget and Savings Goal Pydantic Schemas"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetCreateRequest(BaseModel):
    category_id: uuid.UUID | None = Field(default=None, description="Category ID or null for total household budget")
    month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Target month in YYYY-MM format")
    amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"), description="Budget limit in INR")

    @field_validator("amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v


class BudgetUpdateRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    version: int = Field(description="Optimistic locking version")

    @field_validator("amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    category_id: uuid.UUID | None
    category_name: str | None = None
    month: str
    amount: Decimal
    current_spend: Decimal
    remaining_amount: Decimal
    percentage_used: Decimal
    alert_threshold: str  # NORMAL, WARNING_75, WARNING_90, EXCEEDED_100
    version: int


class SavingsGoalCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    target_amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    current_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("100000000000.00"))
    target_date: date | None = None

    @field_validator("target_amount", "current_amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v


class SavingsGoalUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    target_amount: Decimal | None = Field(default=None, gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    current_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("100000000000.00"))
    target_date: date | None = None
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|ACHIEVED|CANCELLED)$")
    version: int = Field(description="Optimistic locking version")


class SavingsGoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    status: str
    percentage_achieved: Decimal
    remaining_amount: Decimal
    version: int
