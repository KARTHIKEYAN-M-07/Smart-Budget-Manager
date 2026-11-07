"""Comprehensive Financial Accounting Scenario Tests.
Validates all blueprint ledger scenarios and anti-double-counting rules:
1. Cash expense of ₹150
2. Cash income
3. ATM cash withdrawal (Bank Outflow -> Cash Inflow, net spending = ₹0)
4. ATM withdrawal followed by later cash purchase (Spending = ₹150, not ₹5,150)
5. Internal bank transfer (Savings -> Current)
6. Credit card purchase then bill payment (Bill payment is transfer, not expense; net spend = purchase only)
7. Refund linked to purchase (Reduces spending, not income)
8. Atomic transfer reversal (Voids both legs)
9. Idempotent transfer duplicate prevention
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.fixture
async def registered_user(async_client: AsyncClient):
    email = f"fin_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword#2026!"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Finance User",
            "household_name": "Finance Household",
        },
    )
    assert reg_resp.status_code == 201
    data = reg_resp.json()
    csrf_token = data["csrf_token"]
    household_id = data["household"]["id"]

    # Default headers with CSRF
    headers = {"X-CSRF-Token": csrf_token}

    # Seed categories
    cat_resp = await async_client.post("/api/v1/categories/seed", headers=headers)
    assert cat_resp.status_code == 200

    # Fetch categories to have IDs
    cats_get = await async_client.get("/api/v1/categories")
    categories = cats_get.json()

    groceries_cat = next(c for c in categories if "Groceries" in c["name"])
    salary_cat = next(c for c in categories if "Salary" in c["name"])

    return {
        "client": async_client,
        "headers": headers,
        "household_id": household_id,
        "groceries_cat_id": groceries_cat["id"],
        "salary_cat_id": salary_cat["id"],
    }


@pytest.mark.asyncio
async def test_scenario_a_cash_expense_150(registered_user):
    """Scenario A: ₹150 Cash Grocery Expense decreases cash balance correctly."""
    client = registered_user["client"]
    headers = registered_user["headers"]

    # 1. Create Cash account
    acc_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Wallet Cash", "account_type": "cash", "visibility": "shared"},
    )
    assert acc_res.status_code == 201
    cash_acc_id = acc_res.json()["id"]

    # 2. Set opening balance ₹1,000
    op_res = await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": cash_acc_id, "amount": "1000.00", "description": "Initial Cash"},
    )
    assert op_res.status_code == 201

    # Check balance before expense
    bal1 = await client.get(f"/api/v1/accounts/{cash_acc_id}")
    assert Decimal(str(bal1.json()["derived_balance"])) == Decimal("1000.00")

    # 3. Spend ₹150 on Groceries
    exp_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": cash_acc_id,
            "category_id": registered_user["groceries_cat_id"],
            "amount": "150.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Vegetables & Milk",
            "visibility": "shared",
        },
    )
    assert exp_res.status_code == 201

    # 4. Check balance after expense = ₹850.00
    bal2 = await client.get(f"/api/v1/accounts/{cash_acc_id}")
    assert Decimal(str(bal2.json()["derived_balance"])) == Decimal("850.00")


@pytest.mark.asyncio
async def test_scenario_b_cash_income(registered_user):
    """Scenario B: Cash income increases cash balance."""
    client = registered_user["client"]
    headers = registered_user["headers"]

    acc_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Cash Box", "account_type": "cash", "visibility": "shared"},
    )
    cash_id = acc_res.json()["id"]

    # Add income ₹5,000
    inc_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": cash_id,
            "category_id": registered_user["salary_cat_id"],
            "amount": "5000.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "description": "Cash consulting gig",
            "visibility": "shared",
        },
    )
    assert inc_res.status_code == 201

    bal = await client.get(f"/api/v1/accounts/{cash_id}")
    assert Decimal(str(bal.json()["derived_balance"])) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_scenario_c_atm_withdrawal_net_zero_spending(registered_user):
    """Scenario C: ATM cash withdrawal (Bank Outflow -> Cash Inflow, net spending = ₹0)."""
    client = registered_user["client"]
    headers = registered_user["headers"]

    # Bank account with ₹25,000 opening balance
    bank_acc = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "HDFC Savings", "account_type": "savings", "visibility": "shared"},
        )
    ).json()
    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": bank_acc["id"], "amount": "25000.00"},
    )

    # Cash wallet with ₹500 opening balance
    cash_acc = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Physical Wallet", "account_type": "cash", "visibility": "shared"},
        )
    ).json()
    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": cash_acc["id"], "amount": "500.00"},
    )

    # ATM Withdrawal of ₹5,000: Savings -> Cash
    transfer_res = await client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": bank_acc["id"],
            "destination_account_id": cash_acc["id"],
            "amount": "5000.00",
            "description": "ATM cash withdrawal",
        },
    )
    assert transfer_res.status_code == 201
    group_data = transfer_res.json()
    assert Decimal(str(group_data["total_amount"])) == Decimal("5000.00")

    # Verify balances:
    # Bank = 25000 - 5000 = 20000
    bank_bal = (await client.get(f"/api/v1/accounts/{bank_acc['id']}")).json()
    assert Decimal(str(bank_bal["derived_balance"])) == Decimal("20000.00")

    # Cash = 500 + 5000 = 5500
    cash_bal = (await client.get(f"/api/v1/accounts/{cash_acc['id']}")).json()
    assert Decimal(str(cash_bal["derived_balance"])) == Decimal("5500.00")

    # Total liquid assets across both accounts before transfer = ₹25,500; after transfer = ₹25,500.
    total_assets = Decimal(str(bank_bal["derived_balance"])) + Decimal(str(cash_bal["derived_balance"]))
    assert total_assets == Decimal("25500.00")


@pytest.mark.asyncio
async def test_scenario_d_atm_withdrawal_and_later_purchase_anti_double_counting(registered_user):
    """
    Scenario D: Anti-Double-Counting Rule:
    ATM withdrawal ₹5,000 followed by ₹150 cash purchase.
    Total household spending must be ₹150, NOT ₹5,150.
    """
    client = registered_user["client"]
    headers = registered_user["headers"]

    # Bank account with ₹10,000
    bank_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "SBI Savings", "account_type": "savings", "visibility": "shared"},
    )
    bank_id = bank_res.json()["id"]
    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": bank_id, "amount": "10000.00"},
    )

    # Cash wallet
    cash_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Pocket Cash", "account_type": "cash", "visibility": "shared"},
    )
    cash_id = cash_res.json()["id"]

    # Step 1: ATM withdrawal ₹5,000
    await client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": bank_id,
            "destination_account_id": cash_id,
            "amount": "5000.00",
            "description": "ATM Cash Withdrawal",
        },
    )

    # Step 2: Later cash purchase ₹150 (Groceries)
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": cash_id,
            "category_id": registered_user["groceries_cat_id"],
            "amount": "150.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Vegetables from local bazaar",
            "visibility": "shared",
        },
    )

    # Fetch all transactions to compute total expense
    txns_res = await client.get("/api/v1/transactions")
    all_txns = txns_res.json()["items"]

    # Filter strictly for EXPENSE type
    expenses = [
        Decimal(str(t["amount"]))
        for t in all_txns
        if t["transaction_type"] == "EXPENSE" and t["status"] == "POSTED"
    ]
    total_expense = sum(expenses, Decimal("0.00"))

    # Net spending MUST be exactly ₹150.00, NOT ₹5,150.00
    assert total_expense == Decimal("150.00")

    # Balances verification:
    # Bank = 10,000 - 5,000 = 5,000
    # Cash = 5,000 - 150 = 4,850
    # Total net assets = 9,850 (Original 10,000 - 150 expense)
    bank_bal = (await client.get(f"/api/v1/accounts/{bank_id}")).json()
    cash_bal = (await client.get(f"/api/v1/accounts/{cash_id}")).json()
    assert Decimal(str(bank_bal["derived_balance"])) == Decimal("5000.00")
    assert Decimal(str(cash_bal["derived_balance"])) == Decimal("4850.00")
    assert Decimal(str(bank_bal["derived_balance"])) + Decimal(str(cash_bal["derived_balance"])) == Decimal("9850.00")


@pytest.mark.asyncio
async def test_scenario_e_credit_card_purchase_then_bill_payment(registered_user):
    """
    Scenario E: Credit Card purchase increases liability; bill payment is a transfer settling liability.
    Spending is recorded when purchase occurs. Bill payment does NOT count as an expense.
    """
    client = registered_user["client"]
    headers = registered_user["headers"]

    # Bank account with ₹50,000
    bank_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Salary Account", "account_type": "savings", "visibility": "shared"},
    )
    bank_id = bank_res.json()["id"]
    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": bank_id, "amount": "50000.00"},
    )

    # Credit card account
    cc_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "ICICI Amazon Pay CC", "account_type": "credit_card", "visibility": "shared"},
    )
    cc_id = cc_res.json()["id"]

    # 1. Purchase ₹2,500 on credit card
    await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": cc_id,
            "category_id": registered_user["groceries_cat_id"],
            "amount": "2500.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Monthly pantry items",
            "visibility": "shared",
        },
    )

    # CC balance is outstanding liability = ₹2,500.00
    cc_bal1 = (await client.get(f"/api/v1/accounts/{cc_id}")).json()
    assert Decimal(str(cc_bal1["derived_balance"])) == Decimal("2500.00")

    # 2. Pay Credit Card bill from Bank account: Bank -> CC (Transfer)
    transfer_res = await client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": bank_id,
            "destination_account_id": cc_id,
            "amount": "2500.00",
            "description": "Credit Card Bill Payment",
        },
    )
    assert transfer_res.status_code == 201

    # 3. Check balances:
    # CC liability settled to ₹0.00
    cc_bal2 = (await client.get(f"/api/v1/accounts/{cc_id}")).json()
    assert Decimal(str(cc_bal2["derived_balance"])) == Decimal("0.00")

    # Bank balance reduced to ₹47,500.00
    bank_bal = (await client.get(f"/api/v1/accounts/{bank_id}")).json()
    assert Decimal(str(bank_bal["derived_balance"])) == Decimal("47500.00")

    # 4. Anti-double-counting check: Total EXPENSE transactions = strictly ₹2,500.00
    txns = (await client.get("/api/v1/transactions")).json()["items"]
    expenses = [
        Decimal(str(t["amount"]))
        for t in txns
        if t["transaction_type"] == "EXPENSE" and t["status"] == "POSTED"
    ]
    assert sum(expenses, Decimal("0.00")) == Decimal("2500.00")


@pytest.mark.asyncio
async def test_scenario_f_refund_linked_to_purchase(registered_user):
    """
    Scenario F: Refund links to original purchase and reduces net spending (not treated as income).
    """
    client = registered_user["client"]
    headers = registered_user["headers"]

    acc_res = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Checking Account", "account_type": "current", "visibility": "shared"},
    )
    acc_id = acc_res.json()["id"]

    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": acc_id, "amount": "10000.00"},
    )

    # 1. Purchase of ₹1,000
    purchase_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": registered_user["groceries_cat_id"],
            "amount": "1000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Online Order",
            "visibility": "shared",
        },
    )
    assert purchase_res.status_code == 201
    purchase_id = purchase_res.json()["id"]

    # 2. Refund of ₹300 linked to original purchase
    refund_res = await client.post(
        "/api/v1/transactions",
        headers=headers,
        json={
            "account_id": acc_id,
            "category_id": registered_user["groceries_cat_id"],
            "linked_transaction_id": purchase_id,
            "amount": "300.00",
            "direction": "INFLOW",
            "transaction_type": "REFUND",
            "description": "Item out of stock refund",
            "visibility": "shared",
        },
    )
    assert refund_res.status_code == 201

    # 3. Check account balance: 10,000 - 1,000 + 300 = 9,300
    acc_bal = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(acc_bal["derived_balance"])) == Decimal("9300.00")

    # 4. Check Net Spending calculation:
    # Gross expense = 1,000; Refund = 300; Net spend = 700. Income = 0 (Refund is NOT income).
    txns = (await client.get("/api/v1/transactions")).json()["items"]
    expenses = sum(
        (Decimal(str(t["amount"])) for t in txns if t["transaction_type"] == "EXPENSE"),
        Decimal("0.00"),
    )
    refunds = sum(
        (Decimal(str(t["amount"])) for t in txns if t["transaction_type"] == "REFUND"),
        Decimal("0.00"),
    )
    income = sum(
        (Decimal(str(t["amount"])) for t in txns if t["transaction_type"] == "INCOME"),
        Decimal("0.00"),
    )

    assert expenses == Decimal("1000.00")
    assert refunds == Decimal("300.00")
    assert income == Decimal("0.00")
    net_spending = expenses - refunds
    assert net_spending == Decimal("700.00")


@pytest.mark.asyncio
async def test_scenario_g_atomic_transfer_reversal(registered_user):
    """
    Scenario G: Reversing a transfer group voids BOTH legs atomically, restoring balances.
    """
    client = registered_user["client"]
    headers = registered_user["headers"]

    acc1 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Account Alpha", "account_type": "savings", "visibility": "shared"},
        )
    ).json()
    acc2 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Account Beta", "account_type": "savings", "visibility": "shared"},
        )
    ).json()

    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": acc1["id"], "amount": "5000.00"},
    )
    await client.post(
        "/api/v1/transfers/opening-balance",
        headers=headers,
        json={"account_id": acc2["id"], "amount": "2000.00"},
    )

    # Transfer ₹1,500 from Alpha to Beta
    t_res = await client.post(
        "/api/v1/transfers",
        headers=headers,
        json={
            "source_account_id": acc1["id"],
            "destination_account_id": acc2["id"],
            "amount": "1500.00",
            "description": "Inter-account fund shift",
        },
    )
    assert t_res.status_code == 201
    group_id = t_res.json()["id"]

    # Pre-reversal balances: Alpha = 3500, Beta = 3500
    bal_a1 = (await client.get(f"/api/v1/accounts/{acc1['id']}")).json()
    bal_b1 = (await client.get(f"/api/v1/accounts/{acc2['id']}")).json()
    assert Decimal(str(bal_a1["derived_balance"])) == Decimal("3500.00")
    assert Decimal(str(bal_b1["derived_balance"])) == Decimal("3500.00")

    # Reverse transfer group
    rev_res = await client.post(f"/api/v1/transfers/{group_id}/reverse", headers=headers)
    assert rev_res.status_code == 200

    # Post-reversal balances: Alpha restored to 5000, Beta restored to 2000
    bal_a2 = (await client.get(f"/api/v1/accounts/{acc1['id']}")).json()
    bal_b2 = (await client.get(f"/api/v1/accounts/{acc2['id']}")).json()
    assert Decimal(str(bal_a2["derived_balance"])) == Decimal("5000.00")
    assert Decimal(str(bal_b2["derived_balance"])) == Decimal("2000.00")


@pytest.mark.asyncio
async def test_scenario_h_idempotent_transfer(registered_user):
    """
    Scenario H: Repeating transfer with identical idempotency key returns existing transfer without duplicate legs.
    """
    client = registered_user["client"]
    headers = registered_user["headers"]

    acc1 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Idemp Src", "account_type": "savings", "visibility": "shared"},
        )
    ).json()
    acc2 = (
        await client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "Idemp Dst", "account_type": "savings", "visibility": "shared"},
        )
    ).json()

    idemp_key = f"key_{uuid.uuid4().hex}"
    payload = {
        "source_account_id": acc1["id"],
        "destination_account_id": acc2["id"],
        "amount": "1200.00",
        "description": "Idempotent transfer test",
        "idempotency_key": idemp_key,
    }

    # Call 1
    call1 = await client.post("/api/v1/transfers", headers=headers, json=payload)
    assert call1.status_code == 201
    group1_id = call1.json()["id"]

    # Call 2 with identical key
    call2 = await client.post("/api/v1/transfers", headers=headers, json=payload)
    assert call2.status_code == 201
    group2_id = call2.json()["id"]

    # Must return the same TransferGroup ID
    assert group1_id == group2_id
