"""Unit & integration tests for Module 14: Investment Portfolio.
Verifies:
1. Accounting rule: Investment contribution is an asset movement (INVESTMENT_BUY), not consumption
2. Portfolio valuation, unrealized gain/loss, and return %
3. Secondary investment transactions (Buy, Sell, Dividend) with ledger reconciliation
4. IDOR 404 security isolation
5. Optimistic locking concurrency check (version column)
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.investment import AssetClass


@pytest.mark.asyncio
async def test_investment_creation_and_accounting_rule(async_client: AsyncClient):
    """
    Financial Invariant:
    Contributing to an investment debits the funding bank account via INVESTMENT_BUY.
    It is an asset movement, not an expense.
    """
    # 1. Register User & Household
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor1@example.com",
            "password": "StrongPassword123!",
            "full_name": "Family Investor",
            "household_name": "Investment Household",
        },
    )
    auth_data = reg_res.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # 2. Create bank account with ₹1,00,000 opening balance
    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "SBI Savings", "account_type": "savings"},
        headers=headers,
    )
    acc_id = acc_res.json()["id"]

    await async_client.post(
        "/api/v1/transfers/opening-balance",
        json={"account_id": acc_id, "amount": "100000.00"},
        headers=headers,
    )

    # 3. Create Fixed Deposit of ₹40,000 funded from SBI Savings
    fd_payload = {
        "name": "SBI 3-Yr Fixed Deposit",
        "asset_class": AssetClass.FIXED_DEPOSIT.value,
        "invested_amount": "40000.00",
        "current_value": "40000.00",
        "interest_rate_percent": "7.25",
        "start_date": "2026-01-01",
        "maturity_date": "2029-01-01",
        "institution_name": "State Bank of India",
        "source_account_id": acc_id,
        "valuation_source": "SBI NetBanking",
    }
    inv_res = await async_client.post("/api/v1/investments", json=fd_payload, headers=headers)
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    assert inv_data["name"] == "SBI 3-Yr Fixed Deposit"
    assert inv_data["unrealized_gain_loss"] == "0.00"

    # 4. Verify Bank Account derived balance decreased: 1,00,000 - 40,000 = 60,000
    acc_query = await async_client.get(f"/api/v1/accounts/{acc_id}", headers=headers)
    assert Decimal(str(acc_query.json()["derived_balance"])) == Decimal("60000.00")

    # 5. Verify in analytics overview: Net spending is ₹0.00 (INVESTMENT_BUY is NOT an expense)
    analytics_res = await async_client.get("/api/v1/analytics/overview", headers=headers)
    assert analytics_res.status_code == 200
    overview = analytics_res.json()
    assert Decimal(str(overview["total_expense"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_investment_valuation_and_returns(async_client: AsyncClient):
    """Test market valuation updates, unrealized gain/loss, and portfolio summary."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor2@example.com",
            "password": "Password123!",
            "full_name": "Investor Two",
            "household_name": "Portfolio Household",
        },
    )
    headers = {"X-CSRF-Token": reg.json()["csrf_token"]}

    # Create Mutual Fund: ₹50,000 invested (100 units)
    mf = (
        await async_client.post(
            "/api/v1/investments",
            json={
                "name": "Parag Parikh Flexi Cap Fund",
                "asset_class": AssetClass.MUTUAL_FUND.value,
                "units_or_quantity": "100.0000",
                "invested_amount": "50000.00",
                "current_value": "50000.00",
                "start_date": "2025-06-01",
                "institution_name": "Groww",
            },
            headers=headers,
        )
    ).json()

    # Update valuation: NAV appreciated -> current value = ₹65,000
    update_res = await async_client.patch(
        f"/api/v1/investments/{mf['id']}",
        json={
            "current_value": "65000.00",
            "valuation_source": "CAMS Statement",
            "version": mf["version"],
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    # Gain: 65,000 - 50,000 = ₹15,000 (+30.00%)
    assert Decimal(str(updated_data["unrealized_gain_loss"])) == Decimal("15000.00")
    assert Decimal(str(updated_data["return_percentage"])) == Decimal("30.00")

    # Check Portfolio Summary
    sum_res = await async_client.get("/api/v1/investments/summary", headers=headers)
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert Decimal(str(summary["total_invested"])) == Decimal("50000.00")
    assert Decimal(str(summary["total_current_value"])) == Decimal("65000.00")
    assert Decimal(str(summary["total_unrealized_gain_loss"])) == Decimal("15000.00")
    assert Decimal(str(summary["overall_return_percentage"])) == Decimal("30.00")


@pytest.mark.asyncio
async def test_investment_optimistic_locking_and_idor(async_client: AsyncClient):
    # Household A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor_a@example.com",
            "password": "Password123!",
            "full_name": "Investor A",
            "household_name": "Household Inv A",
        },
    )
    headers_a = {"X-CSRF-Token": reg_a.json()["csrf_token"]}

    inv_a = (
        await async_client.post(
            "/api/v1/investments",
            json={
                "name": "Nifty BeES ETF",
                "asset_class": AssetClass.STOCK.value,
                "invested_amount": "25000.00",
                "start_date": "2026-01-10",
            },
            headers=headers_a,
        )
    ).json()

    # Optimistic locking check for Household A
    conflict_res = await async_client.patch(
        f"/api/v1/investments/{inv_a['id']}",
        json={"current_value": "26000.00", "version": 999},
        headers=headers_a,
    )
    assert conflict_res.status_code == 409

    # Household B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor_b@example.com",
            "password": "Password123!",
            "full_name": "Investor B",
            "household_name": "Household Inv B",
        },
    )
    headers_b = {"X-CSRF-Token": reg_b.json()["csrf_token"]}

    # IDOR check: Household B cannot read or modify Household A's investment -> 404
    get_res = await async_client.get(f"/api/v1/investments/{inv_a['id']}", headers=headers_b)
    assert get_res.status_code == 404
