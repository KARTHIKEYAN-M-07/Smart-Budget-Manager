"""Pydantic schemas for notifications and alert delivery"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.notification import NotificationPriority, NotificationType


class NotificationResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID | None = None
    title: str
    message: str
    notification_type: NotificationType
    priority: NotificationPriority
    idempotency_key: str
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int


class TriggerChecksResponse(BaseModel):
    bills_checked: int
    budgets_checked: int
    notifications_created: int
