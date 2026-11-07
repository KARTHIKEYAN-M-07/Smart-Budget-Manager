"""Transfer and Opening Balance Pydantic Schemas"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransferCreateRequest(BaseModel):
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    amount: Decimal = Field(
        gt=Decimal("0.00"),
        le=Decimal("100000000000.00"),
        description="Positive transfer amount in INR",
    )
    transfer_date: datetime | None = None
    description: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=64)

    @field_validator("amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v

    @field_validator("destination_account_id")
    @classmethod
    def validate_different_accounts(cls, v: uuid.UUID, info) -> uuid.UUID:
        source_id = info.data.get("source_account_id")
        if source_id and v == source_id:
            raise ValueError("Source and destination accounts must be different")
        return v


class OpeningBalanceRequest(BaseModel):
    account_id: uuid.UUID
    amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    date: datetime | None = None
    description: str | None = Field(default="Opening Balance", max_length=100)

    @field_validator("amount")
    @classmethod
    def validate_amount_scale(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount cannot have more than 2 decimal places")
        return v


class TransferGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    total_amount: Decimal
    transfer_date: datetime
    description: str | None
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID
    source_transaction_id: uuid.UUID
    destination_transaction_id: uuid.UUID
    created_at: datetime
