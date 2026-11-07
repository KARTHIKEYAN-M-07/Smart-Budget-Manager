"""Transaction entity model"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    OptimisticLockMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    get_utc_now,
)

if TYPE_CHECKING:
    from app.models.account import FinancialAccount
    from app.models.attachment import Attachment
    from app.models.category import Category
    from app.models.household import Household
    from app.models.transfer import TransferGroup
    from app.models.user import User


class Transaction(Base, UUIDPrimaryKeyMixin, TimestampMixin, OptimisticLockMixin):
    """
    Immutable ledger transaction entry.
    All balance queries and financial reports aggregate from this table.
    Records are NEVER hard-deleted; status transitions to VOIDED or REVERSED.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "amount > 0 AND amount <= 100000000000.00",
            name="ck_transaction_amount_valid",
        ),
        CheckConstraint("direction IN ('INFLOW', 'OUTFLOW')", name="ck_transaction_direction"),
        CheckConstraint(
            "transaction_type IN ("
            "'INCOME', 'EXPENSE', 'TRANSFER_OUT', 'TRANSFER_IN', "
            "'REFUND', 'LOAN_DISBURSEMENT', 'LOAN_REPAYMENT', "
            "'INVESTMENT_BUY', 'INVESTMENT_SELL', 'OPENING_BALANCE'"
            ")",
            name="ck_transaction_type",
        ),
        CheckConstraint("visibility IN ('private', 'shared')", name="ck_transaction_visibility"),
        CheckConstraint("status IN ('POSTED', 'VOIDED', 'REVERSED')", name="ck_transaction_status"),
        Index("idx_transactions_account_date", "account_id", "transaction_date"),
        Index("idx_transactions_household_date", "household_id", "transaction_date"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("financial_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transfer_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    linked_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transactions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    visibility: Mapped[str] = mapped_column(String(10), default="shared", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="POSTED", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )

    # Relationships
    household: Mapped["Household"] = relationship("Household", back_populates="transactions")
    account: Mapped["FinancialAccount"] = relationship("FinancialAccount", back_populates="transactions")
    category: Mapped["Category | None"] = relationship("Category", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    transfer_group: Mapped["TransferGroup | None"] = relationship("TransferGroup", back_populates="transactions")
    linked_transaction: Mapped["Transaction | None"] = relationship("Transaction", remote_side="Transaction.id")
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
