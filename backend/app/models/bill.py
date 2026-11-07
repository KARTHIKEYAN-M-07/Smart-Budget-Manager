"""Recurring Bills and Loan EMI Entity Models"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OptimisticLockMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.account import FinancialAccount
    from app.models.category import Category
    from app.models.household import Household


class RecurringBill(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Recurring utility bills, rent, recharges, and subscriptions.
    Dates are strictly date-only fields representing Asia/Kolkata calendar dates.
    In accordance with financial accuracy: never marked PAID without explicit user settlement.
    """

    __tablename__ = "recurring_bills"
    __table_args__ = (
        CheckConstraint("expected_amount > 0 AND expected_amount <= 100000000000.00", name="ck_bill_amount_positive"),
        CheckConstraint(
            "frequency IN ('MONTHLY', 'QUARTERLY', 'YEARLY', 'ONCE')",
            name="ck_bill_frequency",
        ),
        Index("idx_bills_household_due", "household_id", "due_date", "is_active"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    biller_name: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="MONTHLY", nullable=False)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    household: Mapped["Household"] = relationship("Household")
    category: Mapped["Category | None"] = relationship("Category")


class Loan(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Loan account and EMI schedule (Home Loan, Car Loan, Education Loan).
    Loan receipt is a liability, not income.
    """

    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("principal_amount > 0 AND principal_amount <= 100000000000.00", name="ck_loan_principal_positive"),
        CheckConstraint("annual_interest_rate >= 0 AND annual_interest_rate <= 100.00", name="ck_loan_interest_valid"),
        CheckConstraint("tenure_months > 0 AND tenure_months <= 600", name="ck_loan_tenure_valid"),
        CheckConstraint("monthly_emi > 0 AND monthly_emi <= 100000000000.00", name="ck_loan_emi_positive"),
        Index("idx_loans_household_active", "household_id", "is_active"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lender_name: Mapped[str] = mapped_column(String(100), nullable=False)
    loan_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Home, Car, Personal, Education
    principal_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    annual_interest_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_emi: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    household: Mapped["Household"] = relationship("Household")
    account: Mapped["FinancialAccount | None"] = relationship("FinancialAccount")
