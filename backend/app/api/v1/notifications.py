"""Notification and automation API endpoints"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models.household import Household
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    TriggerChecksResponse,
)
from app.services.notification_service import (
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    trigger_all_household_checks,
)

router = APIRouter(prefix="/notifications", tags=["Notifications & Automation"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List household notifications with total unread counter."""
    household, _ = household_and_role
    return await list_notifications(
        db=db,
        household_id=household.id,
        unread_only=unread_only,
        limit=limit,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    dependencies=[Depends(verify_csrf)],
)
async def mark_as_read(
    notification_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Mark a specific notification as read."""
    household, _ = household_and_role
    return await mark_notification_read(
        db=db,
        household_id=household.id,
        notification_id=notification_id,
    )


@router.post(
    "/mark-all-read",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf)],
)
async def mark_all_read(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Mark all unread notifications in the household as read."""
    household, _ = household_and_role
    count = await mark_all_notifications_read(db=db, household_id=household.id)
    return {"marked_read_count": count}


@router.post(
    "/trigger-checks",
    response_model=TriggerChecksResponse,
    dependencies=[Depends(verify_csrf)],
)
async def trigger_checks(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Run automated scan for upcoming bills and budget limits (75%, 90%, 100%).
    Fully idempotent: will not create duplicate alerts.
    """
    household, _ = household_and_role
    return await trigger_all_household_checks(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
    )
