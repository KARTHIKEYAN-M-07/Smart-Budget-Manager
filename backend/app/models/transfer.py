"""Transfer Group entity model"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now

if TYPE_CHECKING:
    from app.models.household import Household
    from app.models.transaction import Transaction
    from app.models.user import User


class TransferGroup(Base, UUIDPrimaryKeyMixin):
    """
    Parent group linking the two balanced legs of an account transfer.
    Leg 1: TRANSFER_OUT from source account
    Leg 2: TRANSFER_IN into destination account
    """

    __tablename__ = "transfer_groups"
    __table_args__ = (CheckConstraint("total_amount > 0", name="ck_transfer_total_amount_positive"),)

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )
    transfer_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    household: Mapped["Household"] = relationship("Household", back_populates="transfer_groups")
    created_by: Mapped["User"] = relationship("User")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="transfer_group",
    )
