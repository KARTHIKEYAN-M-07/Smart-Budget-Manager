"""Financial Account Pydantic Schemas"""

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    account_type: str = Field(
        description="One of: cash, savings, current, credit_card, loan, investment, wallet, other"
    )
    institution_name: str | None = Field(default=None, max_length=100)
    account_number: str | None = Field(
        default=None,
        description="Full account number (will be AES-256-GCM encrypted; not stored in plaintext)",
    )
    account_number_last4: str | None = Field(
        default=None,
        description="Last 4 digits for UI reconciliation (must be exactly 4 digits)",
    )
    visibility: str = Field(default="shared", description="shared or private")

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        valid_types = {
            "cash",
            "savings",
            "current",
            "credit_card",
            "loan",
            "investment",
            "wallet",
            "other",
        }
        val = v.lower().strip()
        if val not in valid_types:
            raise ValueError(f"Invalid account_type. Must be one of: {sorted(valid_types)}")
        return val

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        val = v.lower().strip()
        if val not in {"shared", "private"}:
            raise ValueError("visibility must be 'shared' or 'private'")
        return val

    @field_validator("account_number_last4")
    @classmethod
    def validate_last4(cls, v: str | None) -> str | None:
        if v is not None:
            v_clean = v.strip()
            if not re.match(r"^\d{4}$", v_clean):
                raise ValueError("account_number_last4 must be exactly 4 numeric digits")
            return v_clean
        return None


class AccountUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    institution_name: str | None = Field(default=None, max_length=100)
    account_number_last4: str | None = None
    visibility: str | None = None
    is_active: bool | None = None
    version: int = Field(description="Current version for optimistic concurrency control")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None:
            val = v.lower().strip()
            if val not in {"shared", "private"}:
                raise ValueError("visibility must be 'shared' or 'private'")
            return val
        return None

    @field_validator("account_number_last4")
    @classmethod
    def validate_last4(cls, v: str | None) -> str | None:
        if v is not None:
            v_clean = v.strip()
            if not re.match(r"^\d{4}$", v_clean):
                raise ValueError("account_number_last4 must be exactly 4 numeric digits")
            return v_clean
        return None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: str
    institution_name: str | None
    account_number_last4: str | None
    visibility: str
    is_active: bool
    version: int
    derived_balance: Decimal = Field(
        description="Calculated dynamically by summing ledger entries (never editable directly)"
    )
    created_at: datetime
    updated_at: datetime
