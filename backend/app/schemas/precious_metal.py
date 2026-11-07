"""Pydantic schemas for precious metal holdings and manual price quotes"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.precious_metal import MetalForm, MetalType


class PreciousMetalHoldingCreate(BaseModel):
    metal_type: MetalType
    item_name: str = Field(..., min_length=1, max_length=100)
    form: MetalForm = MetalForm.JEWELLERY
    weight_grams: Decimal = Field(..., gt=Decimal("0.000"), le=Decimal("1000000.000"))
    purity_percentage: Decimal | None = Field(default=None, gt=Decimal("0.00"), le=Decimal("100.00"))
    purchase_date: date
    purchase_price: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("999999999.99"))
    storage_location: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class PreciousMetalHoldingUpdate(BaseModel):
    item_name: str | None = Field(default=None, min_length=1, max_length=100)
    weight_grams: Decimal | None = Field(default=None, gt=Decimal("0.000"), le=Decimal("1000000.000"))
    purity_percentage: Decimal | None = Field(default=None, gt=Decimal("0.00"), le=Decimal("100.00"))
    purchase_price: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("999999999.99"))
    storage_location: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    version: int = Field(..., description="Optimistic locking version")


class PreciousMetalHoldingResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    metal_type: MetalType
    item_name: str
    form: MetalForm
    weight_grams: Decimal
    purity_percentage: Decimal
    purchase_date: date
    purchase_price: Decimal
    storage_location: str | None = None
    notes: str | None = None
    version: int
    created_at: datetime
    # Derived valuation based on latest manual market quote
    current_rate_per_gram: Decimal | None = None
    current_estimated_value: Decimal | None = None
    unrealized_gain_loss: Decimal | None = None
    return_percentage: Decimal | None = None
    valuation_source: str | None = None
    valuation_date: date | None = None

    model_config = {"from_attributes": True}


class PreciousMetalPriceCreate(BaseModel):
    metal_type: MetalType
    rate_per_gram: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("9999999.99"))
    as_of_date: date
    source: str = Field(..., min_length=1, max_length=100, description="e.g. IBJA, GRT, Local Jeweller")
    notes: str | None = Field(default=None, max_length=255)


class PreciousMetalPriceResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    recorded_by_user_id: uuid.UUID
    metal_type: MetalType
    rate_per_gram: Decimal
    as_of_date: date
    source: str
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PreciousMetalPortfolioSummary(BaseModel):
    total_gold_grams: Decimal
    total_silver_grams: Decimal
    total_gold_24k_pure_equiv_grams: Decimal
    total_purchase_cost: Decimal
    total_estimated_value: Decimal
    total_unrealized_gain_loss: Decimal
    overall_return_percentage: Decimal
    holdings_count: int
    latest_rates: dict[str, PreciousMetalPriceResponse] = {}
