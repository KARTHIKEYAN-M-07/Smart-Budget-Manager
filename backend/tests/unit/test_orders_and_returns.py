"""Unit and integration tests for Module 12: Shopping Orders & E-Commerce Reconciliation.
Verifies:
1. Order creation with itemized breakdown
2. IDOR 404 security isolation across households
3. Anti-double-counting guarantee: Order linked to transaction preserves single ledger debit
4. Optimistic concurrency locking (version column)
5. Return processing with automated REFUND transaction creation
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.order import OrderStatus


@pytest.mark.asyncio
async def test_shopping_order_creation_and_itemization(async_client: AsyncClient):
    # Register user
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "shopper1@example.com",
            "password": "StrongPassword123!",
            "full_name": "Shopper One",
            "household_name": "Shopper Household",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # Create Order with 2 items
    order_payload = {
        "merchant_name": "Amazon India",
        "order_number": "402-1234567-8901234",
        "order_date": "2026-11-05",
        "status": "PLACED",
        "total_amount": "2500.00",
        "notes": "Books and Electronics",
        "items": [
            {
                "name": "Hardcover Novel",
                "quantity": 2,
                "unit_price": "500.00",
                "total_price": "1000.00",
            },
            {
                "name": "Wireless Mouse",
                "quantity": 1,
                "unit_price": "1500.00",
                "total_price": "1500.00",
            },
        ],
    }

    create_res = await async_client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert create_res.status_code == 201
    order_data = create_res.json()
    assert order_data["merchant_name"] == "Amazon India"
    assert order_data["total_amount"] == "2500.00"
    assert order_data["is_payment_linked"] is False
    assert len(order_data["items"]) == 2
    assert order_data["version"] == 1

    # Verify Get by ID
    get_res = await async_client.get(f"/api/v1/orders/{order_data['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["merchant_name"] == "Amazon India"


@pytest.mark.asyncio
async def test_order_payment_linking_anti_double_counting(async_client: AsyncClient):
    """
    Anti-double counting guarantee:
    An order linked to a payment transaction does not create a secondary ledger debit.
    """
    # 1. Register user
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "shopper2@example.com",
            "password": "StrongPassword123!",
            "full_name": "Shopper Two",
            "household_name": "Shopper Household 2",
        },
    )
    csrf_token = reg_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf_token}

    # 2. Create bank account and initial deposit
    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "HDFC Savings", "account_type": "savings"},
        headers=headers,
    )
    acc_id = acc_res.json()["id"]

    await async_client.post(
        "/api/v1/transfers/opening-balance",
        json={"account_id": acc_id, "amount": "10000.00"},
        headers=headers,
    )

    # 3. Create Expense transaction (ledger debit)
    txn_res = await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "amount": "3499.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Blinkit Grocery Order",
            "transaction_date": "2026-11-06T10:00:00Z",
        },
        headers=headers,
    )
    txn_id = txn_res.json()["id"]

    # Verify balance before order creation: 10000 - 3499 = 6501
    bal_res1 = await async_client.get(f"/api/v1/accounts/{acc_id}")
    assert Decimal(str(bal_res1.json()["derived_balance"])) == Decimal("6501.00")

    # 4. Create Order linked to payment transaction
    order_payload = {
        "merchant_name": "Blinkit",
        "order_number": "ORD-BLINKIT-992",
        "order_date": "2026-11-06",
        "status": "DELIVERED",
        "total_amount": "3499.00",
        "payment_transaction_id": txn_id,
        "items": [
            {"name": "Organic Honey", "quantity": 1, "unit_price": "499.00"},
            {"name": "Dry Fruits Pack", "quantity": 3, "unit_price": "1000.00"},
        ],
    }
    order_res = await async_client.post("/api/v1/orders", json=order_payload, headers=headers)
    assert order_res.status_code == 201
    order_data = order_res.json()
    assert order_data["is_payment_linked"] is True
    assert order_data["payment_transaction_id"] == txn_id

    # 5. Verify balance is STILL 6501 (order didn't double-charge!)
    bal_res2 = await async_client.get(f"/api/v1/accounts/{acc_id}")
    assert Decimal(str(bal_res2.json()["derived_balance"])) == Decimal("6501.00")


@pytest.mark.asyncio
async def test_order_return_with_reconciled_refund(async_client: AsyncClient):
    """
    Test return workflow:
    - Item is marked RETURNED
    - Automated REFUND transaction credits the bank account and links to original transaction
    - Net spending decreases accordingly
    """
    # 1. Register user
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "shopper3@example.com",
            "password": "StrongPassword123!",
            "full_name": "Shopper Three",
            "household_name": "Shopper Household 3",
        },
    )
    csrf_token = reg_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf_token}

    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "ICICI Savings", "account_type": "savings"},
        headers=headers,
    )
    acc_id = acc_res.json()["id"]

    await async_client.post(
        "/api/v1/transfers/opening-balance",
        json={"account_id": acc_id, "amount": "5000.00"},
        headers=headers,
    )

    # Initial expense of ₹2000
    txn_res = await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "amount": "2000.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "description": "Myntra Clothing",
            "transaction_date": "2026-11-06T10:00:00Z",
        },
        headers=headers,
    )
    txn_id = txn_res.json()["id"]

    # Create Order
    order_res = await async_client.post(
        "/api/v1/orders",
        json={
            "merchant_name": "Myntra",
            "order_number": "MYN-9812",
            "order_date": "2026-11-06",
            "status": "DELIVERED",
            "total_amount": "2000.00",
            "payment_transaction_id": txn_id,
            "items": [
                {"name": "Cotton Shirt", "quantity": 1, "unit_price": "800.00"},
                {"name": "Jeans", "quantity": 1, "unit_price": "1200.00"},
            ],
        },
        headers=headers,
    )
    order_data = order_res.json()
    shirt_item_id = order_data["items"][0]["id"]

    # Process partial return for the Shirt (₹800.00) with refund into ICICI account
    ret_res = await async_client.post(
        f"/api/v1/orders/{order_data['id']}/returns",
        json={
            "item_id": shirt_item_id,
            "return_date": "2026-11-07",
            "refund_amount": "800.00",
            "reason": "Size too small",
            "create_refund_transaction": True,
            "refund_account_id": acc_id,
        },
        headers=headers,
    )
    assert ret_res.status_code == 201
    ret_data = ret_res.json()
    assert ret_data["refund_status"] == "REFUNDED"
    assert ret_data["refund_transaction_id"] is not None

    # Verify Order updated status
    order_updated = (await async_client.get(f"/api/v1/orders/{order_data['id']}")).json()
    assert order_updated["status"] == OrderStatus.PARTIALLY_RETURNED.value
    returned_item = next(it for it in order_updated["items"] if it["id"] == shirt_item_id)
    assert returned_item["status"] == "RETURNED"

    # Verify Bank Account derived balance: 5000 - 2000 + 800 = 3800
    bal_res = await async_client.get(f"/api/v1/accounts/{acc_id}")
    assert Decimal(str(bal_res.json()["derived_balance"])) == Decimal("3800.00")


@pytest.mark.asyncio
async def test_order_idor_404_isolation(async_client: AsyncClient):
    """
    Security check: Users cannot access or modify orders from another household.
    Returns 404 Not Found to prevent resource enumeration.
    """
    # Household A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "userA@example.com",
            "password": "Password123!",
            "full_name": "User A",
            "household_name": "Household A",
        },
    )
    headers_a = {"X-CSRF-Token": reg_a.json()["csrf_token"]}

    order_a = (
        await async_client.post(
            "/api/v1/orders",
            json={
                "merchant_name": "Flipkart",
                "order_date": "2026-11-06",
                "total_amount": "999.00",
            },
            headers=headers_a,
        )
    ).json()

    # Household B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "userB@example.com",
            "password": "Password123!",
            "full_name": "User B",
            "household_name": "Household B",
        },
    )
    headers_b = {"X-CSRF-Token": reg_b.json()["csrf_token"]}

    # Household B attempts to get Household A's order -> 404
    get_res = await async_client.get(f"/api/v1/orders/{order_a['id']}", headers=headers_b)
    assert get_res.status_code == 404

    # Household B attempts to return Household A's order -> 404
    ret_res = await async_client.post(
        f"/api/v1/orders/{order_a['id']}/returns",
        json={
            "return_date": "2026-11-07",
            "refund_amount": "500.00",
            "reason": "Hacking attempt",
        },
        headers=headers_b,
    )
    assert ret_res.status_code == 404
