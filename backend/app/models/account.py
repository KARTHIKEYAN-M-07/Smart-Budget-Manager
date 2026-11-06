"""Financial Account entity model"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OptimisticLockMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.household import Household
    from app.models.transaction import Transaction
    from app.models.user import User


class FinancialAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Financial Account model.
    CRITICAL: Does NOT contain an editable balance column.
    Balances are strictly calculated by aggregating posted transaction inflows and outflows.
    """

    __tablename__ = "financial_accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('cash', 'savings', 'current', 'credit_card', 'loan', 'investment', 'wallet', 'other')",
            name="ck_account_type",
        ),
        CheckConstraint("visibility IN ('private', 'shared')", name="ck_account_visibility"),
        Index("idx_accounts_household_active", "household_id", "is_active"),
    )

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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    encrypted_account_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_number_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    visibility: Mapped[str] = mapped_column(String(10), default="shared", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    household: Mapped["Household"] = relationship("Household", back_populates="accounts")
    owner_user: Mapped["User"] = relationship("User", back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="account",
    )
