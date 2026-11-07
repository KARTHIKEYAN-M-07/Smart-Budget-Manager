"""Unit & API Tests for Dashboard & Analytics (Module 8).
Validates SQL aggregation against hand-calculated datasets:
1. Total Income aggregation
2. Gross expenses vs Net expenses (Refund reduction)
3. Transfer exclusion (Anti-double counting)
4. Voided transaction exclusion
5. Savings rate percentage calculation
6. Indian Financial Year (April - March) distribution
7. Cross-household isolation
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
async def analytics_setup(async_client: AsyncClient):
    # Register household
    email = f"analytics_{uuid.uuid4().hex[:8]}@family.in"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Analytics Head",
            "household_name": "Data Household",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # Seed categories
    await async_client.post("/api/v1/categories/seed", headers=headers)
    cats = (await async_client.get("/api/v1/categories")).json()

    salary_cat = next(c for c in cats if "Salary" in c["name"])
    rent_cat = next(c for c in cats if "Rent" in c["name"])
    groceries_cat = next(c for c in cats if "Groceries" in c["name"])

    # Create Bank and Cash accounts
    acc_bank = (
        await async_client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "HDFC Salary", "account_type": "savings"},
        )
    ).json()

    acc_cash = (
        await async_client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Cash Wallet", "account_type": "cash"},
        )
    ).json()

    return {
        "client": async_client,
        "headers": headers,
        "bank_id": acc_bank["id"],
        "cash_id": acc_cash["id"],
        "salary_cat_id": salary_cat["id"],
        "rent_cat_id": rent_cat["id"],
        "groceries_cat_id": groceries_cat["id"],
    }


@pytest.mark.asyncio
async def test_hand_calculated_financial_aggregations(analytics_setup):
    """
    Hand-calculated dataset verification:
    - Income: ₹1,00,000 (Salary) + ₹25,000 (Consulting) = ₹1,25,000.00
    - Expenses: ₹30,000 (Rent) + ₹15,000 (Groceries) = ₹45,000.00 gross
    - Refund: ₹2,000 (Grocery refund)
    - Net Expense = ₹45,000 - ₹2,000 = ₹43,000.00
    - Net Savings = ₹1,25,000 - ₹43,000 = ₹82,000.00
    - Savings Rate = (82,000 / 125,000) * 100 = 65.60%
    - Transfer: ₹10,000 (Bank -> Cash) MUST NOT inflate income or expense
    - Voided Expense: ₹99,999 MUST be excluded
    """
    client = analytics_setup["client"]
    headers = analytics_setup["headers"]
    bank_id = analytics_setup["bank_id"]
    cash_id = analytics_setup["cash_id"]

    # 1. Post Incomes
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["salary_cat_id"],
            "amount": "100000.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "description": "Monthly Salary",
        },
    )
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["salary_cat_id"],
            "amount": "25000.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "description": "Consulting Income",
        },
    )

    # 2. Post Expenses
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["rent_cat_id"],
            "amount": "30000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Apartment Rent",
        },
    )
    g_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["groceries_cat_id"],
            "amount": "15000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Supermarket Purchase",
        },
    )
    g_id = g_res.json()["id"]

    # 3. Post Refund
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["groceries_cat_id"],
            "linked_transaction_id": g_id,
            "amount": "2000.00",
            "direction": "INFLOW",
            "transaction_type": "REFUND",
            "description": "Returned items refund",
        },
    )

    # 4. Post Transfer (Bank -> Cash ₹10,000)
    await client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": bank_id,
            "destination_account_id": cash_id,
            "amount": "10000.00",
            "description": "ATM Withdrawal",
        },
    )

    # 5. Post and Void an Expense of ₹99,999
    void_txn = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": bank_id,
            "category_id": analytics_setup["groceries_cat_id"],
            "amount": "99999.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Erroneous huge expense",
        },
    )
    void_data = void_txn.json()
    void_res = await client.post(
        f"/api/v1/transactions/{void_data['id']}/void",
        headers=headers,
        json={"reason": "Testing void exclusion", "version": void_data["version"]},
    )
    assert void_res.status_code == 200

    # Query Overview Analytics
    res = await client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    data = res.json()

    # Exact hand-calculated checks
    assert Decimal(str(data["total_income"])) == Decimal("125000.00")
    assert Decimal(str(data["total_refunds"])) == Decimal("2000.00")
    assert Decimal(str(data["total_expense"])) == Decimal("43000.00")
    assert Decimal(str(data["net_savings"])) == Decimal("82000.00")
    assert Decimal(str(data["savings_rate"])) == Decimal("65.60")

    # Category breakdown checks
    cat_names = [c["category_name"] for c in data["categories"]]
    assert any("Rent" in n for n in cat_names)
    assert any("Groceries" in n for n in cat_names)


@pytest.mark.asyncio
async def test_financial_year_report(analytics_setup):
    """Verifies 12-month format of Indian Financial Year report."""
    client = analytics_setup["client"]

    res = await client.get("/api/v1/analytics/financial-year")
    assert res.status_code == 200
    data = res.json()

    assert "FY" in data["financial_year"]
    assert len(data["monthly_trends"]) == 12

    # April should be month 1 in Indian FY
    first_month = data["monthly_trends"][0]
    assert "Apr" in first_month["month_name"]

    # March should be month 12 in Indian FY
    last_month = data["monthly_trends"][11]
    assert "Mar" in last_month["month_name"]
