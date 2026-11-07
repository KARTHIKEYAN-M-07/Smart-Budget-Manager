"""Budget and Savings Goal Entity Models"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OptimisticLockMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.household import Household


class Budget(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Monthly spending limit for a specific category or entire household.
    Real-time spend and thresholds (75%, 90%, 100%) are calculated dynamically.
    """

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0 AND amount <= 100000000000.00", name="ck_budget_amount_positive"),
        UniqueConstraint("household_id", "category_id", "month", name="uq_household_category_month_budget"),
        Index("idx_budgets_household_month", "household_id", "month"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    month: Mapped[str] = mapped_column(
        String(7),  # "YYYY-MM"
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    # Relationships
    household: Mapped["Household"] = relationship("Household")
    category: Mapped["Category | None"] = relationship("Category")


class SavingsGoal(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Savings Goal for family planning (Emergency Fund, Gold purchase, Vacation, Education).
    """

    __tablename__ = "savings_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0 AND target_amount <= 100000000000.00", name="ck_goal_target_positive"),
        CheckConstraint("current_amount >= 0 AND current_amount <= 100000000000.00", name="ck_goal_current_positive"),
        CheckConstraint("status IN ('ACTIVE', 'ACHIEVED', 'CANCELLED')", name="ck_goal_status"),
        Index("idx_goals_household_status", "household_id", "status"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    # Relationships
    household: Mapped["Household"] = relationship("Household")
