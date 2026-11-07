"""Unit & integration tests for Module 15: Notifications & Automation.
Verifies:
1. Strict duplicate-notification prevention (idempotent delivery)
2. Automated bill due date scan (horizon detection)
3. Automated budget threshold warnings (75%, 90%, 100% exceeded)
4. Read status management & unread counter
5. Cross-household IDOR 404 isolation
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_notification_prevention(async_client: AsyncClient):
    """
    Test that identical alerts do not trigger multiple notifications.
    Idempotency key prevents duplicate alerts.
    """
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "notif1@example.com",
            "password": "StrongPassword123!",
            "full_name": "Notification User",
            "household_name": "Notification Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Create a recurring bill due tomorrow
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    await async_client.post(
        "/api/v1/bills",
        json={
            "biller_name": "TNEB Electricity",
            "expected_amount": "1450.00",
            "due_date": tomorrow,
            "frequency": "MONTHLY",
        },
        headers=headers,
    )

    # 1. Trigger automated scan
    scan1 = await async_client.post("/api/v1/notifications/trigger-checks", headers=headers)
    assert scan1.status_code == 200
    assert scan1.json()["notifications_created"] == 1

    # Verify 1 unread notification exists
    list1 = await async_client.get("/api/v1/notifications", headers=headers)
    assert list1.status_code == 200
    assert list1.json()["unread_count"] == 1
    assert "TNEB Electricity" in list1.json()["notifications"][0]["title"]

    # 2. Trigger automated scan AGAIN -> Duplicate prevention ensures 0 new notifications
    scan2 = await async_client.post("/api/v1/notifications/trigger-checks", headers=headers)
    assert scan2.status_code == 200
    assert scan2.json()["notifications_created"] == 0

    # Still exactly 1 notification
    list2 = await async_client.get("/api/v1/notifications", headers=headers)
    assert list2.json()["unread_count"] == 1


@pytest.mark.asyncio
async def test_budget_threshold_alerts_progression(async_client: AsyncClient):
    """
    Tests dynamic budget alerts triggering at 75%, 90%, and 100% (exceeded).
    """
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "notif_budget@example.com",
            "password": "StrongPassword123!",
            "full_name": "Budget Alert User",
            "household_name": "Budget Alert Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Setup category & account
    await async_client.post("/api/v1/categories/seed", headers=headers)
    cats = (await async_client.get("/api/v1/categories", headers=headers)).json()
    dining_cat = next(c for c in cats if "Dining" in c["name"] or "Food" in c["name"])

    acc = (
        await async_client.post(
            "/api/v1/accounts",
            json={"name": "HDFC Card", "account_type": "credit_card"},
            headers=headers,
        )
    ).json()

    now = datetime.now(UTC)
    current_month = f"{now.year:04d}-{now.month:02d}"

    # Set Dining Out budget: ₹10,000
    b_res = await async_client.post(
        "/api/v1/budgets",
        json={
            "category_id": dining_cat["id"],
            "month": current_month,
            "amount": "10000.00",
        },
        headers=headers,
    )
    assert b_res.status_code == 201

    # 1. Record ₹8,000 expense (80% -> crosses 75% threshold)
    await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "category_id": dining_cat["id"],
            "amount": "8000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "transaction_date": f"{current_month}-05T12:00:00Z",
        },
        headers=headers,
    )

    # Trigger scan -> Expect 75% alert
    scan_75 = await async_client.post("/api/v1/notifications/trigger-checks", headers=headers)
    assert scan_75.json()["notifications_created"] == 1
    notifs = (await async_client.get("/api/v1/notifications", headers=headers)).json()["notifications"]
    assert any("75%" in n["title"] for n in notifs)

    # 2. Record additional ₹1,500 expense (total ₹9,500 = 95% -> crosses 90% threshold)
    await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "category_id": dining_cat["id"],
            "amount": "1500.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "transaction_date": f"{current_month}-06T12:00:00Z",
        },
        headers=headers,
    )

    scan_90 = await async_client.post("/api/v1/notifications/trigger-checks", headers=headers)
    assert scan_90.json()["notifications_created"] == 1
    notifs2 = (await async_client.get("/api/v1/notifications", headers=headers)).json()["notifications"]
    assert any("90%" in n["title"] for n in notifs2)

    # 3. Record additional ₹1,000 expense (total ₹10,500 = 105% -> exceeds 100%)
    await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "category_id": dining_cat["id"],
            "amount": "1000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "transaction_date": f"{current_month}-07T12:00:00Z",
        },
        headers=headers,
    )

    scan_100 = await async_client.post("/api/v1/notifications/trigger-checks", headers=headers)
    assert scan_100.json()["notifications_created"] == 1
    notifs3 = (await async_client.get("/api/v1/notifications", headers=headers)).json()["notifications"]
    assert any("Exceeded" in n["title"] for n in notifs3)


@pytest.mark.asyncio
async def test_notification_read_workflow_and_idor(async_client: AsyncClient):
    # Household A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "notif_user_a@example.com",
            "password": "Password123!",
            "full_name": "User A",
            "household_name": "Household A",
        },
    )
    headers_a = {"X-CSRF-Token": reg_a.json()["csrf_token"]}

    # Create bill and trigger check
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    await async_client.post(
        "/api/v1/bills",
        json={
            "biller_name": "Water Tax",
            "expected_amount": "500.00",
            "due_date": tomorrow,
            "frequency": "MONTHLY",
        },
        headers=headers_a,
    )
    await async_client.post("/api/v1/notifications/trigger-checks", headers=headers_a)

    notifs_a = (await async_client.get("/api/v1/notifications", headers=headers_a)).json()["notifications"]
    notif_id = notifs_a[0]["id"]

    # Mark as read
    read_res = await async_client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_a)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

    # Household B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "notif_user_b@example.com",
            "password": "Password123!",
            "full_name": "User B",
            "household_name": "Household B",
        },
    )
    headers_b = {"X-CSRF-Token": reg_b.json()["csrf_token"]}

    # IDOR check: Household B cannot read or mark Household A's notification as read
    idor_res = await async_client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_b)
    assert idor_res.status_code == 404
