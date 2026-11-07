"""Household, Membership, and Invitation entity models"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, get_utc_now

if TYPE_CHECKING:
    from app.models.account import FinancialAccount
    from app.models.category import Category
    from app.models.transaction import Transaction
    from app.models.transfer import TransferGroup
    from app.models.user import User


class Household(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "households"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)

    # Relationships
    members: Mapped[list["HouseholdMember"]] = relationship(
        "HouseholdMember",
        back_populates="household",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        back_populates="household",
        cascade="all, delete-orphan",
    )
    accounts: Mapped[list["FinancialAccount"]] = relationship(
        "FinancialAccount",
        back_populates="household",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="household",
        cascade="all, delete-orphan",
    )
    transfer_groups: Mapped[list["TransferGroup"]] = relationship(
        "TransferGroup",
        back_populates="household",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="household",
        cascade="all, delete-orphan",
    )


class HouseholdMember(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_member"),
        CheckConstraint(
            "role IN ('Owner', 'Administrator', 'Member', 'ReadOnly')",
            name="ck_household_member_role",
        ),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), default="Member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    household: Mapped["Household"] = relationship("Household", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="household_memberships")


class Invitation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invitations"
    __table_args__ = (CheckConstraint("role IN ('Administrator', 'Member', 'ReadOnly')", name="ck_invitation_role"),)

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="Member", nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_accepted: Mapped[bool] = mapped_column(default=False, nullable=False)

    household: Mapped["Household"] = relationship("Household", back_populates="invitations")
