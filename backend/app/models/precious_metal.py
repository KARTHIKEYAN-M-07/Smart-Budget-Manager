"""Precious metals (Gold & Silver) models"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now

if TYPE_CHECKING:
    from app.models.household import Household
    from app.models.user import User


class MetalType(enum.StrEnum):
    GOLD_24K = "GOLD_24K"
    GOLD_22K = "GOLD_22K"
    GOLD_18K = "GOLD_18K"
    SILVER_999 = "SILVER_999"
    SILVER_925 = "SILVER_925"


class MetalForm(enum.StrEnum):
    JEWELLERY = "JEWELLERY"
    COIN = "COIN"
    BAR = "BAR"
    UTENSIL = "UTENSIL"
    OTHER = "OTHER"


class PreciousMetalHolding(Base, UUIDPrimaryKeyMixin):
    """Holding record for physical gold or silver."""

    __tablename__ = "precious_metal_holdings"

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    metal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    form: Mapped[str] = mapped_column(String(20), nullable=False, default=MetalForm.JEWELLERY.value)
    weight_grams: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    purity_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    storage_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        onupdate=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "metal_type IN ('GOLD_24K', 'GOLD_22K', 'GOLD_18K', 'SILVER_999', 'SILVER_925')",
            name="ck_precious_metal_holdings_metal_type",
        ),
        CheckConstraint(
            "form IN ('JEWELLERY', 'COIN', 'BAR', 'UTENSIL', 'OTHER')",
            name="ck_precious_metal_holdings_form",
        ),
        CheckConstraint("weight_grams > 0", name="ck_precious_metal_holdings_weight_positive"),
        CheckConstraint(
            "purity_percentage > 0 AND purity_percentage <= 100",
            name="ck_precious_metal_holdings_purity_valid",
        ),
        CheckConstraint("purchase_price >= 0", name="ck_precious_metal_holdings_purchase_price_positive"),
        Index("idx_metal_holdings_household_type", "household_id", "metal_type"),
    )

    household: Mapped["Household"] = relationship("Household")
    user: Mapped["User"] = relationship("User")


class PreciousMetalPrice(Base, UUIDPrimaryKeyMixin):
    """
    Manually logged market rate for gold or silver.
    Rule: Never invent market prices; require source and date.
    """

    __tablename__ = "precious_metal_prices"

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    metal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rate_per_gram: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "metal_type IN ('GOLD_24K', 'GOLD_22K', 'GOLD_18K', 'SILVER_999', 'SILVER_925')",
            name="ck_precious_metal_prices_metal_type",
        ),
        CheckConstraint("rate_per_gram > 0", name="ck_precious_metal_prices_rate_positive"),
        UniqueConstraint("household_id", "metal_type", "as_of_date", "source", name="uq_precious_metal_price_entry"),
        Index("idx_metal_prices_lookup", "household_id", "metal_type", "as_of_date"),
    )

    household: Mapped["Household"] = relationship("Household")
    recorded_by: Mapped["User"] = relationship("User")
