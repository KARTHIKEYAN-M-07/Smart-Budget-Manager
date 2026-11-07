"""Notification model with duplicate-notification prevention"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin, get_utc_now


class NotificationType(enum.StrEnum):
    BILL_DUE = "BILL_DUE"
    BUDGET_WARNING = "BUDGET_WARNING"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    STATEMENT_REMINDER = "STATEMENT_REMINDER"
    SECURITY_ALERT = "SECURITY_ALERT"
    GENERAL = "GENERAL"


class NotificationPriority(enum.StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Notification(Base, UUIDPrimaryKeyMixin):
    """Notification entity with idempotent deduplication."""

    __tablename__ = "notifications"

    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=NotificationPriority.NORMAL.value)
    idempotency_key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=get_utc_now,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "notification_type IN ('BILL_DUE', 'BUDGET_WARNING', 'BUDGET_EXCEEDED', 'STATEMENT_REMINDER', 'SECURITY_ALERT', 'GENERAL')",
            name="ck_notifications_type",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'NORMAL', 'HIGH', 'CRITICAL')",
            name="ck_notifications_priority",
        ),
        UniqueConstraint("household_id", "idempotency_key", name="uq_household_notification_idempotency"),
        Index("idx_notifications_household_unread", "household_id", "is_read"),
    )

    household = relationship("Household")
    user = relationship("User")
