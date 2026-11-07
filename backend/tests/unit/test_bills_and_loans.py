"""Recurring Bills and Loan EMI Tests (Module 11).
Validates:
1. Standard Indian reducing balance EMI calculation formula
2. Complete amortization schedule generation (final balance zero)
3. Zero interest loan edge case
4. Recurring bill settlement (atomic ledger transaction generation)
5. Anti-fake rule: Bill is never marked paid without an authentic ledger transaction
6. Due date rollover based on recurrence frequency
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
async def bill_setup(async_client: AsyncClient):
    email = f"bills_{uuid.uuid4().hex[:8]}@family.in"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Bill Manager",
            "household_name": "Bills Household",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # Seed categories
    await async_client.post("/api/v1/categories/seed", headers=headers)
    cats = (await async_client.get("/api/v1/categories")).json()
    elec_cat = next(c for c in cats if "Electricity" in c["name"])

    # Create Bank Account with ₹50,000 opening balance
    acc = (
        await async_client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "HDFC Savings", "account_type": "savings"},
        )
    ).json()

    await async_client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": acc["id"], "amount": "50000.00"},
    )

    return {
        "client": async_client,
        "headers": headers,
        "account_id": acc["id"],
        "category_id": elec_cat["id"],
    }


@pytest.mark.asyncio
async def test_reducing_balance_emi_calculation(bill_setup):
    """
    Validates standard Indian reducing-balance EMI formula:
    Loan: ₹10,00,000 (10 Lakhs) at 9.00% annual interest for 60 months (5 years).
    Calculated EMI must be ₹20,758.36.
    Final month outstanding balance must be strictly ₹0.00.
    """
    client = bill_setup["client"]

    res = await client.post(
        "/api/v1/loans/calculate",
        json={
            "principal_amount": "1000000.00",
            "annual_interest_rate": "9.00",
            "tenure_months": 60,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert Decimal(str(data["monthly_emi"])) == Decimal("20758.36")
    schedule = data["amortization_schedule"]
    assert len(schedule) == 60

    # Month 1 interest = 1,000,000 * (0.09 / 12) = 7500.00
    m1 = schedule[0]
    assert Decimal(str(m1["interest_component"])) == Decimal("7500.00")
    assert Decimal(str(m1["principal_component"])) == Decimal("13258.36")

    # Final month balance = 0.00
    m60 = schedule[59]
    assert Decimal(str(m60["outstanding_balance"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_zero_interest_loan_calculation(bill_setup):
    """Zero percent interest loan: EMI = Principal / Months."""
    client = bill_setup["client"]

    res = await client.post(
        "/api/v1/loans/calculate",
        json={
            "principal_amount": "60000.00",
            "annual_interest_rate": "0.00",
            "tenure_months": 12,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert Decimal(str(data["monthly_emi"])) == Decimal("5000.00")
    assert Decimal(str(data["total_interest_payable"])) == Decimal("0.00")


@pytest.mark.asyncio
async def test_recurring_bill_settlement_creates_reconciled_transaction(bill_setup):
    """
    CRITICAL RULE:
    Bill settlement MUST create an authentic posted transaction in the ledger,
    decrement bank balance, and advance next due date.
    """
    client = bill_setup["client"]
    headers = bill_setup["headers"]
    acc_id = bill_setup["account_id"]
    cat_id = bill_setup["category_id"]

    # 1. Register Monthly Electricity Bill ₹2,500 due on 15th
    b_res = await client.post(
        "/api/v1/bills",
        headers=headers,
        json={
            "biller_name": "BESCOM Electricity",
            "category_id": cat_id,
            "expected_amount": "2500.00",
            "due_date": "2026-11-15",
            "frequency": "MONTHLY",
            "reminder_days_before": 3,
        },
    )
    assert b_res.status_code == 201
    bill = b_res.json()
    bill_id = bill["id"]
    assert bill["status"] == "DUE"

    # Pre-settlement balance = ₹50,000.00
    bal1 = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(bal1["derived_balance"])) == Decimal("50000.00")

    # 2. Settle Bill from Bank Account
    settle_res = await client.post(
        f"/api/v1/bills/{bill_id}/settle",
        headers=headers,
        json={"account_id": acc_id, "amount": "2500.00"},
    )
    assert settle_res.status_code == 200
    res_data = settle_res.json()

    # Reconciled transaction created
    txn = res_data["transaction"]
    assert txn["transaction_type"] == "EXPENSE"
    assert Decimal(str(txn["amount"])) == Decimal("2500.00")
    assert txn["status"] == "POSTED"

    # Post-settlement balance = ₹47,500.00
    bal2 = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(bal2["derived_balance"])) == Decimal("47500.00")

    # Next due date advanced to 2026-12-15 (1 month ahead)
    updated_bill = res_data["bill"]
    assert updated_bill["due_date"] == "2026-12-15"
