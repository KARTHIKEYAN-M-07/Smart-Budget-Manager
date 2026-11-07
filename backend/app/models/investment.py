"""Investment portfolio entity models"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now


class AssetClass(enum.StrEnum):
    MUTUAL_FUND = "MUTUAL_FUND"
    STOCK = "STOCK"
    FIXED_DEPOSIT = "FIXED_DEPOSIT"
    RECURRING_DEPOSIT = "RECURRING_DEPOSIT"
    PPF = "PPF"
    EPF = "EPF"
    NPS = "NPS"
    SGB = "SGB"
    OTHER = "OTHER"


class InvestmentTransactionType(enum.StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"


class Investment(Base, UUIDPrimaryKeyMixin):
    """Investment holding record."""

    __tablename__ = "investments"

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
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    folio_or_account_number_last4: Mapped[str | None] = mapped_column(String(20), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    units_or_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("1.0000"))
    invested_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    interest_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    last_valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valuation_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
            "asset_class IN ('MUTUAL_FUND', 'STOCK', 'FIXED_DEPOSIT', 'RECURRING_DEPOSIT', 'PPF', 'EPF', 'NPS', 'SGB', 'OTHER')",
            name="ck_investments_asset_class",
        ),
        CheckConstraint("units_or_quantity >= 0", name="ck_investments_quantity_positive"),
        CheckConstraint("invested_amount >= 0", name="ck_investments_invested_amount_positive"),
        CheckConstraint("current_value >= 0", name="ck_investments_current_value_positive"),
        Index("idx_investments_household_active", "household_id", "is_active"),
    )

    transactions: Mapped[list["InvestmentTransaction"]] = relationship(
        "InvestmentTransaction",
        back_populates="investment",
        cascade="all, delete-orphan",
        order_by="InvestmentTransaction.transaction_date.desc()",
    )


class InvestmentTransaction(Base, UUIDPrimaryKeyMixin):
    """Buy, Sell, or Income transaction recorded against an investment."""

    __tablename__ = "investment_transactions"

    investment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("investments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('BUY', 'SELL', 'DIVIDEND', 'INTEREST')",
            name="ck_investment_transactions_type",
        ),
        CheckConstraint("amount >= 0", name="ck_investment_transactions_amount_positive"),
    )

    investment: Mapped["Investment"] = relationship("Investment", back_populates="transactions")
