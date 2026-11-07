"""Optional privacy-preserving integrations models"""

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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now


class IntegrationProvider(enum.StrEnum):
    GMAIL_RECEIPTS = "GMAIL_RECEIPTS"
    ANDROID_SMS_SYNC = "ANDROID_SMS_SYNC"
    ACCOUNT_AGGREGATOR = "ACCOUNT_AGGREGATOR"


class InboxItemStatus(enum.StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"


class IntegrationConsent(Base, UUIDPrimaryKeyMixin):
    """
    Explicit, revocable user consent for optional third-party integrations.
    Requires minimum permissions, AES-256-GCM encrypted tokens, and immediate revocation.
    """

    __tablename__ = "integration_consents"

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
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scopes: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "provider IN ('GMAIL_RECEIPTS', 'ANDROID_SMS_SYNC', 'ACCOUNT_AGGREGATOR')",
            name="ck_integration_provider",
        ),
        UniqueConstraint("household_id", "provider", "user_id", name="uq_integration_consent"),
        Index("idx_integration_consent_active", "household_id", "provider", "is_active"),
    )

    household = relationship("Household")
    user = relationship("User")


class ParsedInboxItem(Base, UUIDPrimaryKeyMixin):
    """
    Draft transaction parsed strictly locally from consented receipts or SMS.
    Never sent to external AI services; requires human family review before posting.
    """

    __tablename__ = "parsed_inbox_items"

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("integration_consents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    parsed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    parsed_merchant: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parsed_account_last4: Mapped[str | None] = mapped_column(String(10), nullable=True)
    parsed_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=InboxItemStatus.PENDING_REVIEW.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("parsed_amount > 0", name="ck_parsed_inbox_amount_positive"),
        CheckConstraint(
            "status IN ('PENDING_REVIEW', 'ACCEPTED', 'DISMISSED')",
            name="ck_parsed_inbox_status",
        ),
        UniqueConstraint("household_id", "source_identifier", name="uq_parsed_inbox_source_id"),
        Index("idx_parsed_inbox_pending", "household_id", "status"),
    )

    household = relationship("Household")
    consent = relationship("IntegrationConsent")
