"""Pydantic schemas for investment tracking and portfolio valuation"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.investment import AssetClass, InvestmentTransactionType


class InvestmentTransactionCreateRequest(BaseModel):
    transaction_type: InvestmentTransactionType
    transaction_date: date
    amount: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("999999999.99"))
    units: Decimal = Field(default=Decimal("0.0000"), ge=Decimal("0.0000"))
    price_per_unit: Decimal | None = Field(default=None, ge=Decimal("0.0000"))
    source_account_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=255)


class InvestmentTransactionResponse(BaseModel):
    id: uuid.UUID
    investment_id: uuid.UUID
    transaction_id: uuid.UUID | None = None
    transaction_type: InvestmentTransactionType
    transaction_date: date
    amount: Decimal
    units: Decimal
    price_per_unit: Decimal | None = None
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    asset_class: AssetClass
    account_id: uuid.UUID | None = None
    folio_or_account_number_last4: str | None = Field(default=None, max_length=20)
    institution_name: str | None = Field(default=None, max_length=100)
    units_or_quantity: Decimal = Field(default=Decimal("1.0000"), ge=Decimal("0.0000"))
    invested_amount: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("999999999.99"))
    current_value: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("999999999.99"))
    interest_rate_percent: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("100.00"))
    start_date: date
    maturity_date: date | None = None
    valuation_source: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    # Accounting link: If source_account_id is provided, automatically records an INVESTMENT_BUY ledger transaction
    source_account_id: uuid.UUID | None = None


class InvestmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    units_or_quantity: Decimal | None = Field(default=None, ge=Decimal("0.0000"))
    current_value: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("999999999.99"))
    last_valuation_date: date | None = None
    valuation_source: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)
    version: int = Field(..., description="Optimistic locking version")


class InvestmentResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID | None = None
    name: str
    asset_class: AssetClass
    folio_or_account_number_last4: str | None = None
    institution_name: str | None = None
    units_or_quantity: Decimal
    invested_amount: Decimal
    current_value: Decimal
    interest_rate_percent: Decimal | None = None
    start_date: date
    maturity_date: date | None = None
    last_valuation_date: date
    valuation_source: str | None = None
    is_active: bool
    notes: str | None = None
    version: int
    created_at: datetime
    # Derived financial metrics
    unrealized_gain_loss: Decimal
    return_percentage: Decimal
    transactions: list[InvestmentTransactionResponse] = []

    model_config = {"from_attributes": True}


class InvestmentPortfolioSummary(BaseModel):
    total_invested: Decimal
    total_current_value: Decimal
    total_unrealized_gain_loss: Decimal
    overall_return_percentage: Decimal
    by_asset_class: dict[str, Decimal] = {}
    investments_count: int
