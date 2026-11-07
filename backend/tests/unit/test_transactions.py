"""Unit & API Tests for Transaction Management (Module 5)"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.models import AuditLog, Base, Transaction


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure clean tables before every test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _register_user_and_setup_account(async_client: AsyncClient, email: str = "txnuser@family.in") -> dict:
    """Helper creating user, household, and a default savings account."""
    reg_payload = {
        "email": email,
        "full_name": "Txn Owner",
        "password": "Password123!",
        "household_name": "Txn Family",
    }
    res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    auth_data = res.json()
    csrf = auth_data["csrf_token"]

    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "Primary Bank", "account_type": "savings"},
        headers={"X-CSRF-Token": csrf},
    )
    assert acc_res.status_code == 201
    auth_data["account_id"] = acc_res.json()["id"]
    return auth_data


# ------------------------------------------------------------------------------
# 1. Transaction Creation & Idempotency
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transaction_creation_and_idempotency(async_client: AsyncClient):
    """Test standard transaction creation and idempotent re-submission."""
    data = await _register_user_and_setup_account(async_client)
    csrf = data["csrf_token"]
    acc_id = data["account_id"]
    idemp_key = "idemp-" + str(uuid.uuid4())

    payload = {
        "account_id": acc_id,
        "amount": "150.00",
        "direction": "OUTFLOW",
        "transaction_type": "EXPENSE",
        "description": "₹150 cash grocery expense",
        "visibility": "shared",
        "idempotency_key": idemp_key,
    }

    # First POST -> 201 Created
    res1 = await async_client.post("/api/v1/transactions", json=payload, headers={"X-CSRF-Token": csrf})
    assert res1.status_code == 201
    txn1 = res1.json()
    assert txn1["amount"] == "150.00"
    assert txn1["direction"] == "OUTFLOW"
    assert txn1["status"] == "POSTED"
    assert txn1["idempotency_key"] == idemp_key

    # Re-submit with same idempotency_key -> Returns same transaction (idempotent)
    res2 = await async_client.post("/api/v1/transactions", json=payload, headers={"X-CSRF-Token": csrf})
    assert res2.status_code == 201
    txn2 = res2.json()
    assert txn2["id"] == txn1["id"]

    # Verify only 1 record exists in DB
    async with AsyncSessionLocal() as db:
        txns = (await db.execute(select(Transaction).where(Transaction.idempotency_key == idemp_key))).scalars().all()
        assert len(txns) == 1


# ------------------------------------------------------------------------------
# 2. Financial Amount & Precision Validations
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_invalid_amount_validations(async_client: AsyncClient):
    """Test that zero, negative, and invalid scale amounts are rejected."""
    data = await _register_user_and_setup_account(async_client)
    csrf = data["csrf_token"]
    acc_id = data["account_id"]

    # Zero amount -> 422
    zero_res = await async_client.post(
        "/api/v1/transactions",
        json={"account_id": acc_id, "amount": "0.00", "direction": "INFLOW", "transaction_type": "INCOME"},
        headers={"X-CSRF-Token": csrf},
    )
    assert zero_res.status_code == 422

    # Negative amount -> 422
    neg_res = await async_client.post(
        "/api/v1/transactions",
        json={"account_id": acc_id, "amount": "-150.00", "direction": "INFLOW", "transaction_type": "INCOME"},
        headers={"X-CSRF-Token": csrf},
    )
    assert neg_res.status_code == 422

    # More than 2 decimal places (fractional paise) -> 422
    fractional_res = await async_client.post(
        "/api/v1/transactions",
        json={"account_id": acc_id, "amount": "150.555", "direction": "INFLOW", "transaction_type": "INCOME"},
        headers={"X-CSRF-Token": csrf},
    )
    assert fractional_res.status_code == 422


# ------------------------------------------------------------------------------
# 3. Voiding Transactions (Financial Invariant: No Hard Deletes)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_void_transaction_preserves_audit_trail(async_client: AsyncClient):
    """
    Test that voiding sets status to VOIDED, records audit log,
    and updates derived balance without hard deleting the record.
    """
    data = await _register_user_and_setup_account(async_client)
    csrf = data["csrf_token"]
    acc_id = data["account_id"]

    # Post ₹5,000 income
    res = await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "amount": "5000.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "description": "Bonus",
        },
        headers={"X-CSRF-Token": csrf},
    )
    txn_id = res.json()["id"]
    version = res.json()["version"]

    # Derived balance should be ₹5,000.00
    acc_res1 = await async_client.get(f"/api/v1/accounts/{acc_id}")
    assert acc_res1.json()["derived_balance"] == "5000.00"

    # Void transaction with reason
    void_res = await async_client.post(
        f"/api/v1/transactions/{txn_id}/void",
        json={"reason": "Incorrect bonus entry", "version": version},
        headers={"X-CSRF-Token": csrf},
    )
    assert void_res.status_code == 200
    assert void_res.json()["status"] == "VOIDED"

    # Derived balance now drops to ₹0.00 (VOIDED transactions excluded from balance)
    acc_res2 = await async_client.get(f"/api/v1/accounts/{acc_id}")
    assert acc_res2.json()["derived_balance"] == "0.00"

    # Confirm transaction still exists in DB and AuditLog has VOID action
    async with AsyncSessionLocal() as db:
        txn_db = (await db.execute(select(Transaction).where(Transaction.id == uuid.UUID(txn_id)))).scalar_one()
        assert txn_db.status == "VOIDED"

        audit_db = (
            await db.execute(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(txn_id), AuditLog.action == "VOID"))
        ).scalar_one_or_none()
        assert audit_db is not None
        assert audit_db.new_values["reason"] == "Incorrect bonus entry"


# ------------------------------------------------------------------------------
# 4. Search, Filtering, and Pagination
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transaction_search_and_filtering(async_client: AsyncClient):
    """Test searching transactions by keyword, filtering by direction, and pagination."""
    data = await _register_user_and_setup_account(async_client)
    csrf = data["csrf_token"]
    acc_id = data["account_id"]

    # Seed 3 transactions
    items = [
        {"desc": "Blinkit grocery quick delivery", "amt": "340.00", "dir": "OUTFLOW", "typ": "EXPENSE"},
        {"desc": "Petrol bunk HPCL fuel", "amt": "1500.00", "dir": "OUTFLOW", "typ": "EXPENSE"},
        {"desc": "Monthly consulting income", "amt": "75000.00", "dir": "INFLOW", "typ": "INCOME"},
    ]
    for item in items:
        await async_client.post(
            "/api/v1/transactions",
            json={
                "account_id": acc_id,
                "amount": item["amt"],
                "direction": item["dir"],
                "transaction_type": item["typ"],
                "description": item["desc"],
            },
            headers={"X-CSRF-Token": csrf},
        )

    # Search keyword "petrol"
    search_res = await async_client.get("/api/v1/transactions?search=petrol")
    assert search_res.status_code == 200
    results = search_res.json()
    assert results["total_count"] == 1
    assert "HPCL" in results["items"][0]["description"]

    # Filter direction INFLOW
    inflow_res = await async_client.get("/api/v1/transactions?direction=INFLOW")
    assert inflow_res.status_code == 200
    assert inflow_res.json()["total_count"] == 1
    assert inflow_res.json()["items"][0]["amount"] == "75000.00"

    # Pagination: page_size=2
    page_res = await async_client.get("/api/v1/transactions?page=1&page_size=2")
    assert page_res.status_code == 200
    assert len(page_res.json()["items"]) == 2
    assert page_res.json()["total_pages"] == 2


# ------------------------------------------------------------------------------
# 5. IDOR & Visibility Isolation (404 Not Found)
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_transaction_idor_404_isolation(async_client: AsyncClient):
    """
    CRITICAL IDOR CHECK:
    Accessing a transaction belonging to another household or marked private by another user
    must return 404 (Not Found).
    """
    # User 1 creates a private transaction
    u1_data = await _register_user_and_setup_account(async_client, email="u1_txn@family.in")
    u1_res = await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": u1_data["account_id"],
            "amount": "999.00",
            "direction": "OUTFLOW",
            "transaction_type": "EXPENSE",
            "visibility": "private",
            "description": "Private purchase",
        },
        headers={"X-CSRF-Token": u1_data["csrf_token"]},
    )
    assert u1_res.status_code == 201
    private_txn_id = u1_res.json()["id"]

    # User 2 logs in from separate household
    await _register_user_and_setup_account(async_client, email="u2_txn@other.in")

    # User 2 tries to GET User 1's transaction -> Must return 404
    idor_get = await async_client.get(f"/api/v1/transactions/{private_txn_id}")
    assert idor_get.status_code == 404
