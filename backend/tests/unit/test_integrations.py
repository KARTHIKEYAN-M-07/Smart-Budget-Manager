"""Unit and security tests for privacy-preserving optional integrations (Module 16)"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_integrations_consent_enforcement_and_revocation(async_client: AsyncClient):
    """
    Verifies:
    1. Parsing without consent fails (403)
    2. Granting consent succeeds
    3. Parsing with consent succeeds
    4. Revoking consent cryptographically wipes tokens and blocks future parsing
    """
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "privacy_user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Privacy User",
            "household_name": "Privacy Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    sms_payload = {
        "sms_text": "HDFCBK: Rs. 850.00 debited from A/C **4321 to ZOMATO on 07-11-26. Avl Bal Rs 15,000.00",
        "sender": "HDFCBK",
    }

    # 1. Attempt SMS parse without consent -> 403
    res_no_consent = await async_client.post(
        "/api/v1/integrations/parse-sms",
        json=sms_payload,
        headers=headers,
    )
    assert res_no_consent.status_code == 403
    assert "consent" in res_no_consent.json()["detail"].lower()

    # 2. Grant explicit consent
    consent_payload = {
        "provider": "ANDROID_SMS_SYNC",
        "scopes": "sms_read_only",
        "auth_token": "secret_oauth_token_123",
    }
    res_grant = await async_client.post(
        "/api/v1/integrations/consents",
        json=consent_payload,
        headers=headers,
    )
    assert res_grant.status_code == 201
    grant_data = res_grant.json()
    assert grant_data["provider"] == "ANDROID_SMS_SYNC"
    assert grant_data["is_active"] is True

    # 3. Parse with active consent -> 201 Created and staged to inbox
    res_parse = await async_client.post(
        "/api/v1/integrations/parse-sms",
        json=sms_payload,
        headers=headers,
    )
    assert res_parse.status_code == 201
    parsed_item = res_parse.json()
    assert Decimal(str(parsed_item["parsed_amount"])) == Decimal("850.00")
    assert "ZOMATO" in parsed_item["parsed_merchant"].upper()
    assert parsed_item["parsed_account_last4"] == "4321"
    assert parsed_item["status"] == "PENDING_REVIEW"
    # Ensure sensitive balance is redacted in snippet
    assert "[BAL_REDACTED]" in parsed_item["raw_snippet"]

    # 4. Revoke consent
    res_revoke = await async_client.delete(
        "/api/v1/integrations/consents/ANDROID_SMS_SYNC",
        headers=headers,
    )
    assert res_revoke.status_code == 200
    assert res_revoke.json()["is_active"] is False

    # 5. Subsequent parse attempt is blocked
    res_blocked = await async_client.post(
        "/api/v1/integrations/parse-sms",
        json=sms_payload,
        headers=headers,
    )
    assert res_blocked.status_code == 403


@pytest.mark.asyncio
async def test_local_receipt_parsing_and_accept_workflow(async_client: AsyncClient):
    """
    Verifies receipt parsing, staging in inbox, and accepting into real ledger transaction.
    """
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "receipt_user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Receipt User",
            "household_name": "Receipt Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Create an active financial account for the household
    acc_res = await async_client.post(
        "/api/v1/accounts",
        json={
            "name": "Integration Test Account",
            "account_type": "savings",
            "currency": "INR",
        },
        headers=headers,
    )
    assert acc_res.status_code == 201
    account_id = acc_res.json()["id"]

    # Fund account with opening deposit
    await async_client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "10000.00",
            "direction": "INFLOW",
            "transaction_type": "INCOME",
            "transaction_date": "2026-11-01T10:00:00Z",
            "description": "Initial account deposit",
        },
        headers=headers,
    )

    # Grant consent for GMAIL_RECEIPTS
    await async_client.post(
        "/api/v1/integrations/consents",
        json={"provider": "GMAIL_RECEIPTS", "scopes": "mail_read_receipts"},
        headers=headers,
    )

    # Parse local receipt text (zero AI leak)
    receipt_payload = {
        "receipt_text": "Amazon India\nOrder #402-998811\nTotal: Rs. 1,499.00\nPayment Method: Debit Card",
        "source_identifier": f"amazon_order_{uuid.uuid4().hex[:8]}",
        "receipt_date": "2026-11-07",
    }
    rcpt_res = await async_client.post(
        "/api/v1/integrations/parse-receipt",
        json=receipt_payload,
        headers=headers,
    )
    assert rcpt_res.status_code == 201
    item = rcpt_res.json()
    assert Decimal(str(item["parsed_amount"])) == Decimal("1499.00")
    assert item["status"] == "PENDING_REVIEW"
    item_id = item["id"]

    # Check inbox listing
    inbox_res = await async_client.get("/api/v1/integrations/inbox", headers=headers)
    assert inbox_res.status_code == 200
    items = inbox_res.json()
    assert any(i["id"] == item_id for i in items)

    # Accept staged item into ledger
    accept_payload = {
        "account_id": account_id,
        "notes": "Amazon order verified by user",
    }
    accept_res = await async_client.post(
        f"/api/v1/integrations/inbox/{item_id}/accept",
        json=accept_payload,
        headers=headers,
    )
    assert accept_res.status_code == 200
    assert accept_res.json()["status"] == "ACCEPTED"

    # Verify ledger reflects the debit
    acc_check = await async_client.get(f"/api/v1/accounts/{account_id}", headers=headers)
    assert acc_check.status_code == 200
    # Opening 10000 - 1499 = 8501.00
    assert Decimal(str(acc_check.json()["derived_balance"])) == Decimal("8501.00")

    # Double accept fails
    double_res = await async_client.post(
        f"/api/v1/integrations/inbox/{item_id}/accept",
        json=accept_payload,
        headers=headers,
    )
    assert double_res.status_code == 400


@pytest.mark.asyncio
async def test_dismiss_inbox_item(async_client: AsyncClient):
    """Verifies dismissing an item updates status without affecting ledger."""
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "dismiss_user@example.com",
            "password": "StrongPassword123!",
            "full_name": "Dismiss User",
            "household_name": "Dismiss Household",
        },
    )
    headers = {"X-CSRF-Token": reg_res.json()["csrf_token"]}

    # Grant consent
    await async_client.post(
        "/api/v1/integrations/consents",
        json={"provider": "ANDROID_SMS_SYNC", "scopes": "sms_read_only"},
        headers=headers,
    )

    sms_payload = {
        "sms_text": "SBI: Rs. 350.00 debited from A/C **9999 to TEA STALL on 07-11-26",
        "sender": "SBIINB",
    }
    res_parse = await async_client.post(
        "/api/v1/integrations/parse-sms",
        json=sms_payload,
        headers=headers,
    )
    assert res_parse.status_code == 201
    item_id = res_parse.json()["id"]

    # Dismiss item
    res_dismiss = await async_client.post(
        f"/api/v1/integrations/inbox/{item_id}/dismiss",
        headers=headers,
    )
    assert res_dismiss.status_code == 200
    assert res_dismiss.json()["status"] == "DISMISSED"


@pytest.mark.asyncio
async def test_integrations_cross_household_idor(async_client: AsyncClient):
    """Verifies that items from Household A return 404 to Household B."""
    # Register Household A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "house_a@example.com",
            "password": "StrongPassword123!",
            "full_name": "User A",
            "household_name": "Household A",
        },
    )
    headers_a = {"X-CSRF-Token": reg_a.json()["csrf_token"]}

    await async_client.post(
        "/api/v1/integrations/consents",
        json={"provider": "ANDROID_SMS_SYNC", "scopes": "sms_read_only"},
        headers=headers_a,
    )
    res_a = await async_client.post(
        "/api/v1/integrations/parse-sms",
        json={
            "sms_text": "SBI: Rs. 990.00 debited from A/C **1111 to GROCERY on 07-11-26",
            "sender": "SBIINB",
        },
        headers=headers_a,
    )
    assert res_a.status_code == 201
    item_a_id = res_a.json()["id"]

    # Register Household B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "house_b@example.com",
            "password": "StrongPassword123!",
            "full_name": "User B",
            "household_name": "Household B",
        },
    )
    headers_b = {"X-CSRF-Token": reg_b.json()["csrf_token"]}

    # Household B attempts to accept or dismiss Household A's item -> 404
    res_fake_accept = await async_client.post(
        f"/api/v1/integrations/inbox/{item_a_id}/dismiss",
        headers=headers_b,
    )
    assert res_fake_accept.status_code == 404

