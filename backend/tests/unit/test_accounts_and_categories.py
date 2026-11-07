"""Unit & API Tests for Financial Accounts and Categories (Module 4)"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import decrypt_field
from app.models import Base, FinancialAccount, Transaction


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure clean tables before every test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _register_user_and_get_session(async_client: AsyncClient, email: str = "accuser@family.in") -> dict:
    """Helper to register user and obtain valid CSRF token."""
    payload = {
        "email": email,
        "full_name": "Account Owner",
        "password": "Password123!",
        "household_name": "Test Household",
    }
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    return res.json()


# ------------------------------------------------------------------------------
# 1. Financial Accounts Creation & AES-256-GCM Encryption
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_account_with_encryption(async_client: AsyncClient):
    """Test account creation with field-level encryption of sensitive account number."""
    auth_data = await _register_user_and_get_session(async_client)
    csrf_token = auth_data["csrf_token"]

    account_payload = {
        "name": "HDFC Salary Account",
        "account_type": "savings",
        "institution_name": "HDFC Bank",
        "account_number": "50100234567890",
        "account_number_last4": "7890",
        "visibility": "shared",
    }
    response = await async_client.post(
        "/api/v1/accounts",
        json=account_payload,
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "HDFC Salary Account"
    assert data["account_type"] == "savings"
    assert data["account_number_last4"] == "7890"
    assert data["derived_balance"] == "0.00"
    assert data["version"] == 1

    # Verify directly in DB that account_number was encrypted with AES-256-GCM
    account_id = uuid.UUID(data["id"])
    async with AsyncSessionLocal() as db:
        acc_db = (await db.execute(select(FinancialAccount).where(FinancialAccount.id == account_id))).scalar_one()
        assert acc_db.encrypted_account_number is not None
        assert "50100234567890" not in acc_db.encrypted_account_number
        # Verify decrypt works
        decrypted = decrypt_field(acc_db.encrypted_account_number)
        assert decrypted == "50100234567890"


# ------------------------------------------------------------------------------
# 2. Derived Balance for Asset vs Liability (Credit Card)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_derived_balance_asset_vs_liability(async_client: AsyncClient):
    """
    Test dynamic balance derivation:
    - Savings account: Inflow increases balance.
    - Credit Card: Outflow (spend) increases liability, Inflow (bill pay) decreases liability.
    """
    auth_data = await _register_user_and_get_session(async_client)
    csrf_token = auth_data["csrf_token"]
    user_id = uuid.UUID(auth_data["user"]["id"])
    household_id = uuid.UUID(auth_data["household"]["id"])

    # Create ICICI Credit Card
    card_res = await async_client.post(
        "/api/v1/accounts",
        json={
            "name": "ICICI Amazon Pay Card",
            "account_type": "credit_card",
            "institution_name": "ICICI Bank",
            "account_number_last4": "4321",
            "visibility": "shared",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert card_res.status_code == 201
    card_id = uuid.UUID(card_res.json()["id"])

    # Simulate card purchase of ₹3,500 (OUTFLOW on card)
    async with AsyncSessionLocal() as db:
        purchase = Transaction(
            household_id=household_id,
            account_id=card_id,
            user_id=user_id,
            amount=Decimal("3500.00"),
            direction="OUTFLOW",
            transaction_type="EXPENSE",
            description="Laptop accessories",
            status="POSTED",
        )
        db.add(purchase)
        await db.commit()

    # Query account -> liability balance should be ₹3,500.00
    card_query = await async_client.get(f"/api/v1/accounts/{card_id}")
    assert card_query.status_code == 200
    assert card_query.json()["derived_balance"] == "3500.00"

    # Settle partial bill ₹2,000 (INFLOW on card)
    async with AsyncSessionLocal() as db:
        bill_pay = Transaction(
            household_id=household_id,
            account_id=card_id,
            user_id=user_id,
            amount=Decimal("2000.00"),
            direction="INFLOW",
            transaction_type="TRANSFER_IN",
            description="Card bill partial settlement",
            status="POSTED",
        )
        db.add(bill_pay)
        await db.commit()

    # Query account -> remaining liability should be ₹1,500.00
    card_query_2 = await async_client.get(f"/api/v1/accounts/{card_id}")
    assert card_query_2.json()["derived_balance"] == "1500.00"


# ------------------------------------------------------------------------------
# 3. Optimistic Concurrency Control (Version Conflict Detection)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_optimistic_concurrency_conflict(async_client: AsyncClient):
    """Test that modifying an account with a stale version raises 409 Conflict."""
    auth_data = await _register_user_and_get_session(async_client)
    csrf_token = auth_data["csrf_token"]

    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "Cash Wallet", "account_type": "cash"},
        headers={"X-CSRF-Token": csrf_token},
    )
    acc_id = acc_res.json()["id"]
    version = acc_res.json()["version"]  # 1

    # First valid update (version 1 -> 2)
    update_1 = await async_client.patch(
        f"/api/v1/accounts/{acc_id}",
        json={"name": "Daily Cash", "version": version},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert update_1.status_code == 200
    assert update_1.json()["version"] == 2

    # Second update using stale version 1 -> Must raise 409 Conflict
    stale_update = await async_client.patch(
        f"/api/v1/accounts/{acc_id}",
        json={"name": "Stale Attempt", "version": version},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert stale_update.status_code == 409
    assert "modified by another session" in stale_update.json()["detail"]


# ------------------------------------------------------------------------------
# 4. IDOR Prevention & Visibility Isolation (Must return 404!)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_account_idor_and_private_visibility(async_client: AsyncClient):
    """
    CRITICAL IDOR CHECK:
    - Cross-household access returns 404.
    - Private account of another user in the same household returns 404.
    """
    # Household 1 with User 1
    u1_auth = await _register_user_and_get_session(async_client, email="u1@family.in")
    u1_csrf = u1_auth["csrf_token"]

    # User 1 creates private account
    priv_acc = await async_client.post(
        "/api/v1/accounts",
        json={"name": "User 1 Secret Fund", "account_type": "savings", "visibility": "private"},
        headers={"X-CSRF-Token": u1_csrf},
    )
    priv_acc_id = priv_acc.json()["id"]

    # Household 2 with User 2
    await _register_user_and_get_session(async_client, email="u2@other.in")

    # User 2 tries to access User 1's account -> Must return 404 (IDOR prevented!)
    idor_res = await async_client.get(f"/api/v1/accounts/{priv_acc_id}")
    assert idor_res.status_code == 404


# ------------------------------------------------------------------------------
# 5. Category Taxonomy & Seeding
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_category_seeding_and_custom_categories(async_client: AsyncClient):
    """Test category seeding with Indian defaults, and custom category hierarchy."""
    auth_data = await _register_user_and_get_session(async_client)
    csrf_token = auth_data["csrf_token"]

    # Seed default Indian categories
    seed_res = await async_client.post("/api/v1/categories/seed", headers={"X-CSRF-Token": csrf_token})
    assert seed_res.status_code == 200
    added = seed_res.json()["added_count"]
    assert added >= 30

    # Idempotent re-seed -> adds 0
    seed_res_2 = await async_client.post("/api/v1/categories/seed", headers={"X-CSRF-Token": csrf_token})
    assert seed_res_2.json()["added_count"] == 0

    # List expense categories
    exp_cats = await async_client.get("/api/v1/categories?type=expense")
    assert exp_cats.status_code == 200
    names = [c["name"] for c in exp_cats.json()]
    assert "Groceries & Supermarket" in names
    assert "Fuel (Petrol/Diesel/CNG)" in names
    assert "Electricity Bill (TNEB/BESCOM/Discom)" in names

    # Create custom category
    custom_res = await async_client.post(
        "/api/v1/categories",
        json={"name": "Badminton Coaching", "type": "expense", "icon": "activity"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert custom_res.status_code == 201
    custom_id = custom_res.json()["id"]

    # Duplicate custom category -> 400
    dup_res = await async_client.post(
        "/api/v1/categories",
        json={"name": "Badminton Coaching", "type": "expense"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert dup_res.status_code == 400

    # Delete custom category
    del_res = await async_client.delete(f"/api/v1/categories/{custom_id}", headers={"X-CSRF-Token": csrf_token})
    assert del_res.status_code == 200
