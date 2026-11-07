"""Notification delivery and background automation service.
Features:
- Idempotent deduplication guaranteeing zero spam/duplicate notifications
- Automated recurring bill due reminders
- Dynamic budget limit alerts (75%, 90%, 100% threshold detection)
- Cross-household isolation
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    Budget,
    Category,
    Notification,
    NotificationPriority,
    NotificationType,
    RecurringBill,
)
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    TriggerChecksResponse,
)
from app.services.budget_service import get_budget_spend


async def create_notification_idempotent(
    db: AsyncSession,
    household_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: NotificationType,
    idempotency_key: str,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    user_id: uuid.UUID | None = None,
) -> tuple[Notification, bool]:
    """
    Creates a notification only if the idempotency_key has not been issued for this household.
    Returns (notification, was_created).
    """
    stmt = select(Notification).where(
        Notification.household_id == household_id,
        Notification.idempotency_key == idempotency_key,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing, False

    notif = Notification(
        household_id=household_id,
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type.value,
        priority=priority.value,
        idempotency_key=idempotency_key,
        is_read=False,
    )
    db.add(notif)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id or uuid.UUID(int=0),
        entity_name="Notification",
        entity_id=notif.id,
        action="CREATE",
        new_values={
            "title": notif.title,
            "type": notif.notification_type,
            "idempotency_key": idempotency_key,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(notif)

    return notif, True


async def list_notifications(
    db: AsyncSession,
    household_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 50,
) -> NotificationListResponse:
    stmt = (
        select(Notification)
        .where(Notification.household_id == household_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))

    res = await db.execute(stmt)
    notifications = res.scalars().all()

    # Count total unread
    stmt_unread = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.household_id == household_id,
            Notification.is_read.is_(False),
        )
    )
    res_count = await db.execute(stmt_unread)
    unread_count = res_count.scalar() or 0

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        unread_count=unread_count,
    )


async def mark_notification_read(
    db: AsyncSession,
    household_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> NotificationResponse:
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.household_id == household_id,
    )
    res = await db.execute(stmt)
    notif = res.scalar_one_or_none()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(notif)

    return NotificationResponse.model_validate(notif)


async def mark_all_notifications_read(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> int:
    stmt = (
        select(Notification)
        .where(
            Notification.household_id == household_id,
            Notification.is_read.is_(False),
        )
    )
    res = await db.execute(stmt)
    unreads = res.scalars().all()

    now = datetime.now(UTC)
    for n in unreads:
        n.is_read = True
        n.read_at = now

    await db.commit()
    return len(unreads)


async def scan_and_dispatch_bill_due_alerts(
    db: AsyncSession,
    household_id: uuid.UUID,
    today: date | None = None,
) -> int:
    """Scans bills due within 3 days and generates idempotent notifications."""
    if today is None:
        today = datetime.now(UTC).date()

    alert_horizon = today + timedelta(days=3)

    stmt = select(RecurringBill).where(
        RecurringBill.household_id == household_id,
        RecurringBill.is_active.is_(True),
        RecurringBill.due_date >= today,
        RecurringBill.due_date <= alert_horizon,
    )
    res = await db.execute(stmt)
    bills = res.scalars().all()

    created_count = 0
    for bill in bills:
        days_left = (bill.due_date - today).days
        urgency = "today" if days_left == 0 else f"in {days_left} day(s)"
        key = f"bill_due_{bill.id}_{bill.due_date.isoformat()}"

        title = f"Bill Due Soon: {bill.biller_name}"
        msg = f"Payment of ₹{bill.expected_amount:,.2f} for {bill.biller_name} is due {urgency} on {bill.due_date}."

        _, was_created = await create_notification_idempotent(
            db=db,
            household_id=household_id,
            title=title,
            message=msg,
            notification_type=NotificationType.BILL_DUE,
            priority=NotificationPriority.HIGH if days_left <= 1 else NotificationPriority.NORMAL,
            idempotency_key=key,
        )
        if was_created:
            created_count += 1

    return created_count


async def scan_and_dispatch_budget_threshold_alerts(
    db: AsyncSession,
    household_id: uuid.UUID,
    month: str | None = None,
    user_id: uuid.UUID | None = None,
) -> int:
    """
    Evaluates spending against active budgets for the month.
    Generates idempotent alerts at 75%, 90%, and 100% (exceeded) limits.
    """
    if month is None:
        now = datetime.now(UTC)
        month = f"{now.year:04d}-{now.month:02d}"

    stmt_budgets = select(Budget).where(
        Budget.household_id == household_id,
        Budget.month == month,
    )
    res_b = await db.execute(stmt_budgets)
    budgets = res_b.scalars().all()

    created_count = 0

    for b in budgets:
        net_spent = await get_budget_spend(db, household_id, user_id or uuid.UUID(int=0), b.category_id, b.month)

        if b.amount <= Decimal("0.00"):
            continue

        pct = (net_spent / b.amount) * Decimal("100")

        # Category name lookup if applicable
        cat_name = "Household Overall"
        if b.category_id:
            stmt_c = select(Category.name).where(Category.id == b.category_id)
            c_res = await db.execute(stmt_c)
            cat_name = c_res.scalar_one_or_none() or "Category"

        if pct >= Decimal("100.00"):
            key = f"budget_exceeded_{b.id}_{month}"
            title = f"Budget Exceeded: {cat_name}"
            msg = f"You have spent ₹{net_spent:,.2f} exceeding your {month} budget limit of ₹{b.amount:,.2f} ({pct:.1f}%)."
            _, was_created = await create_notification_idempotent(
                db=db,
                household_id=household_id,
                title=title,
                message=msg,
                notification_type=NotificationType.BUDGET_EXCEEDED,
                priority=NotificationPriority.CRITICAL,
                idempotency_key=key,
            )
            if was_created:
                created_count += 1
        elif pct >= Decimal("90.00"):
            key = f"budget_90_{b.id}_{month}"
            title = f"Budget Alert (90%): {cat_name}"
            msg = f"You have reached {pct:.1f}% (₹{net_spent:,.2f}) of your ₹{b.amount:,.2f} budget for {cat_name} in {month}."
            _, was_created = await create_notification_idempotent(
                db=db,
                household_id=household_id,
                title=title,
                message=msg,
                notification_type=NotificationType.BUDGET_WARNING,
                priority=NotificationPriority.HIGH,
                idempotency_key=key,
            )
            if was_created:
                created_count += 1
        elif pct >= Decimal("75.00"):
            key = f"budget_75_{b.id}_{month}"
            title = f"Budget Notice (75%): {cat_name}"
            msg = f"You have reached {pct:.1f}% (₹{net_spent:,.2f}) of your ₹{b.amount:,.2f} budget for {cat_name} in {month}."
            _, was_created = await create_notification_idempotent(
                db=db,
                household_id=household_id,
                title=title,
                message=msg,
                notification_type=NotificationType.BUDGET_WARNING,
                priority=NotificationPriority.NORMAL,
                idempotency_key=key,
            )
            if was_created:
                created_count += 1

    return created_count


async def trigger_all_household_checks(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> TriggerChecksResponse:
    """Executes full scan for upcoming bills and budget threshold alerts."""
    bills_created = await scan_and_dispatch_bill_due_alerts(db, household_id)
    budgets_created = await scan_and_dispatch_budget_threshold_alerts(db, household_id, user_id=user_id)

    # Get total bills and budgets count
    stmt_b = select(func.count()).select_from(RecurringBill).where(
        RecurringBill.household_id == household_id, RecurringBill.is_active.is_(True)
    )
    b_count = (await db.execute(stmt_b)).scalar() or 0

    stmt_bg = select(func.count()).select_from(Budget).where(Budget.household_id == household_id)
    bg_count = (await db.execute(stmt_bg)).scalar() or 0

    return TriggerChecksResponse(
        bills_checked=b_count,
        budgets_checked=bg_count,
        notifications_created=bills_created + budgets_created,
    )
