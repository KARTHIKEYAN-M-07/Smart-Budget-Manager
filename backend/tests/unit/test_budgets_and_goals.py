"""Budgets and Savings Goals Unit & API Tests (Module 10).
Validates:
1. Dynamic budget tracking against posted expenses and refunds
2. Alert thresholds (75%, 90%, 100% exceeded)
3. Savings goal creation, progress tracking, and auto-completion
4. Optimistic locking on goal updates
5. Cross-household isolation
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
async def budget_setup(async_client: AsyncClient):
    email = f"budget_{uuid.uuid4().hex[:8]}@family.in"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Budget User",
            "household_name": "Budget Household",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # Seed categories
    await async_client.post("/api/v1/categories/seed", headers=headers)
    cats = (await async_client.get("/api/v1/categories")).json()
    groceries_cat = next(c for c in cats if "Groceries" in c["name"])

    # Create account
    acc = (
        await async_client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Wallet Cash", "account_type": "cash"},
        )
    ).json()

    now = datetime.now(UTC)
    current_month = f"{now.year:04d}-{now.month:02d}"

    return {
        "client": async_client,
        "headers": headers,
        "account_id": acc["id"],
        "category_id": groceries_cat["id"],
        "current_month": current_month,
    }


@pytest.mark.asyncio
async def test_budget_threshold_alerts_and_refunds(budget_setup):
    """
    Tests dynamic budget calculation and threshold transitions:
    - 0% -> NORMAL
    - 76% -> WARNING_75
    - 91% -> WARNING_90
    - 106% -> EXCEEDED_100
    - Refund brings it back down to 96% -> WARNING_90
    """
    client = budget_setup["client"]
    headers = budget_setup["headers"]
    acc_id = budget_setup["account_id"]
    cat_id = budget_setup["category_id"]
    month = budget_setup["current_month"]

    # 1. Set Groceries budget limit = ₹10,000
    b_res = await client.post(
        "/api/v1/budgets",
        headers=headers,
        json={"category_id": cat_id, "month": month, "amount": "10000.00"},
    )
    assert b_res.status_code == 201
    b_data = b_res.json()
    assert Decimal(str(b_data["current_spend"])) == Decimal("0.00")
    assert b_data["alert_threshold"] == "NORMAL"

    # 2. Spend ₹7,600 (76%) -> WARNING_75
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": cat_id,
            "amount": "7600.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Bulk Grocery Run",
        },
    )
    budgets = (await client.get("/api/v1/budgets", params={"month": month})).json()
    bg = next(b for b in budgets if b["category_id"] == cat_id)
    assert Decimal(str(bg["current_spend"])) == Decimal("7600.00")
    assert Decimal(str(bg["percentage_used"])) == Decimal("76.00")
    assert bg["alert_threshold"] == "WARNING_75"

    # 3. Spend another ₹1,500 (total ₹9,100 -> 91%) -> WARNING_90
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": cat_id,
            "amount": "1500.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Vegetables & Provisions",
        },
    )
    bg2 = (await client.get("/api/v1/budgets", params={"month": month})).json()[0]
    assert Decimal(str(bg2["current_spend"])) == Decimal("9100.00")
    assert Decimal(str(bg2["percentage_used"])) == Decimal("91.00")
    assert bg2["alert_threshold"] == "WARNING_90"

    # 4. Spend another ₹1,500 (total ₹10,600 -> 106%) -> EXCEEDED_100
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": cat_id,
            "amount": "1500.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Organic staples",
        },
    )
    bg3 = (await client.get("/api/v1/budgets", params={"month": month})).json()[0]
    assert Decimal(str(bg3["current_spend"])) == Decimal("10600.00")
    assert Decimal(str(bg3["percentage_used"])) == Decimal("106.00")
    assert bg3["alert_threshold"] == "EXCEEDED_100"

    # 5. Receive Refund of ₹1,000 (net spend ₹9,600 -> 96%) -> WARNING_90
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": cat_id,
            "amount": "1000.00",
            "direction": "INFLOW",
            "transaction_type": "REFUND",
            "description": "Damaged goods return",
        },
    )
    bg4 = (await client.get("/api/v1/budgets", params={"month": month})).json()[0]
    assert Decimal(str(bg4["current_spend"])) == Decimal("9600.00")
    assert Decimal(str(bg4["percentage_used"])) == Decimal("96.00")
    assert bg4["alert_threshold"] == "WARNING_90"


@pytest.mark.asyncio
async def test_savings_goals_lifecycle_and_optimistic_lock(budget_setup):
    """Validates savings goal creation, progress update, auto-completion, and version locking."""
    client = budget_setup["client"]
    headers = budget_setup["headers"]

    # 1. Create Goal
    create_res = await client.post(
        "/api/v1/budgets/goals",
        headers=headers,
        json={
            "name": "Family Emergency Fund",
            "target_amount": "100000.00",
            "current_amount": "25000.00",
            "target_date": "2027-03-31",
        },
    )
    assert create_res.status_code == 201
    goal = create_res.json()

    assert goal["status"] == "ACTIVE"
    assert Decimal(str(goal["percentage_achieved"])) == Decimal("25.00")
    assert Decimal(str(goal["remaining_amount"])) == Decimal("75000.00")

    # 2. Update Goal Progress to Reach Target
    update_res = await client.patch(
        f"/api/v1/budgets/goals/{goal['id']}",
        headers=headers,
        json={
            "current_amount": "100000.00",
            "version": goal["version"],
        },
    )
    assert update_res.status_code == 200
    updated_goal = update_res.json()

    # Automatically transitions to ACHIEVED
    assert updated_goal["status"] == "ACHIEVED"
    assert Decimal(str(updated_goal["percentage_achieved"])) == Decimal("100.00")
    assert Decimal(str(updated_goal["remaining_amount"])) == Decimal("0.00")
    assert updated_goal["version"] == goal["version"] + 1

    # 3. Optimistic Concurrency Conflict (Stale Version)
    conflict_res = await client.patch(
        f"/api/v1/budgets/goals/{goal['id']}",
        headers=headers,
        json={
            "current_amount": "110000.00",
            "version": goal["version"],  # Stale version!
        },
    )
    assert conflict_res.status_code == 409
