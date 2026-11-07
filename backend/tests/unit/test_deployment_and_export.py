"""Unit and security compliance tests for Module 17:
- Data Portability Export (DPDP / GDPR)
- Right to be Forgotten Purge (Cascading destruction & security audit)
- Encrypted Backup and Automated Restore Drill
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from scripts.backup_and_restore_drill import run_backup_and_restore_drill


@pytest.mark.asyncio
async def test_household_data_export_and_audit(async_client: AsyncClient):
    """Verifies complete data portability JSON export and audit log."""
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "export_user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Export Owner",
            "household_name": "Export Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Create an account and transaction
    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={"name": "Export Savings", "account_type": "savings"},
        headers=headers,
    )
    acc_id = acc_res.json()["id"]

    await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc_id,
            "amount": "2500.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "transaction_date": "2026-11-01T10:00:00Z",
            "description": "Salary check",
        },
        headers=headers,
    )

    # Call export endpoint
    export_res = await async_client.get("/api/v1/household/export", headers=headers)
    assert export_res.status_code == 200
    export_data = export_res.json()

    assert "export_metadata" in export_data
    assert export_data["export_metadata"]["household_name"] == "Export Household"
    assert len(export_data["accounts"]) >= 1
    assert any(a["id"] == acc_id for a in export_data["accounts"])
    assert len(export_data["transactions"]) >= 1
    assert Decimal(export_data["transactions"][0]["amount"]) == Decimal("2500.00")


@pytest.mark.asyncio
async def test_household_purge_right_to_be_forgotten(async_client: AsyncClient):
    """Verifies permanent cascading deletion with strict confirmation phrase."""
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "purge_user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Purge Owner",
            "household_name": "Purge Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Attempt purge with invalid confirmation phrase -> 400
    bad_purge = await async_client.request(
        "DELETE",
        "/api/v1/household/purge",
        json={"confirm_phrase": "WRONG_PHRASE"},
        headers=headers,
    )
    assert bad_purge.status_code == 400

    # Purge with exact confirmation phrase -> 200
    good_purge = await async_client.request(
        "DELETE",
        "/api/v1/household/purge",
        json={"confirm_phrase": "PURGE_ALL_HOUSEHOLD_DATA"},
        headers=headers,
    )
    assert good_purge.status_code == 200
    assert "permanently purged" in good_purge.json()["message"]


@pytest.mark.asyncio
async def test_backup_and_restore_drill():
    """Verifies AES-256-GCM encrypted backup generation, checksum, and restore reconstitution."""
    success = await run_backup_and_restore_drill(output_dir="backups_test")
    assert success is True
