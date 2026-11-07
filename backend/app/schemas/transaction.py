"""Transaction Pydantic Schemas"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionCreateRequest(BaseModel):
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    amount: Decimal = Field(
        gt=Decimal("0.00"),
        le=Decimal("100000000000.00"),
        description="Positive amount in INR with maximum 2 decimal places",
    )
    direction: str = Field(description="INFLOW or OUTFLOW")
    transaction_type: str = Field(
        description="INCOME, EXPENSE, TRANSFER_OUT, TRANSFER_IN, REFUND, LOAN_DISBURSEMENT, LOAN_REPAYMENT, INVESTMENT_BUY, INVESTMENT_SELL, OPENING_BALANCE"
    )
    visibility: str = Field(default="shared", description="shared or private")
    description: str | None = Field(default=None, max_length=500)
    transaction_date: datetime | None = None
    linked_transaction_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=64)

    @field_validator("amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places (paise precision)")
        return v

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        val = v.upper().strip()
        if val not in {"INFLOW", "OUTFLOW"}:
            raise ValueError("direction must be 'INFLOW' or 'OUTFLOW'")
        return val

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {
            "INCOME",
            "EXPENSE",
            "TRANSFER_OUT",
            "TRANSFER_IN",
            "REFUND",
            "LOAN_DISBURSEMENT",
            "LOAN_REPAYMENT",
            "INVESTMENT_BUY",
            "INVESTMENT_SELL",
            "OPENING_BALANCE",
        }
        val = v.upper().strip()
        if val not in valid_types:
            raise ValueError(f"Invalid transaction_type. Must be one of: {sorted(valid_types)}")
        return val

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        val = v.lower().strip()
        if val not in {"shared", "private"}:
            raise ValueError("visibility must be 'shared' or 'private'")
        return val


class TransactionUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=500)
    visibility: str | None = None
    version: int = Field(description="Version column for optimistic concurrency control")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None:
            val = v.lower().strip()
            if val not in {"shared", "private"}:
                raise ValueError("visibility must be 'shared' or 'private'")
            return val
        return None


class TransactionVoidRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=255)
    version: int = Field(description="Version column for optimistic concurrency control")


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str | None = None
    category_id: uuid.UUID | None
    category_name: str | None = None
    user_id: uuid.UUID
    user_name: str | None = None
    transfer_group_id: uuid.UUID | None
    linked_transaction_id: uuid.UUID | None
    amount: Decimal
    direction: str
    transaction_type: str
    visibility: str
    description: str | None
    transaction_date: datetime
    status: str
    version: int
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


class TransactionPaginatedResponse(BaseModel):
    items: list[TransactionResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int
