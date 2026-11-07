"""Comprehensive Security, Authentication, RBAC, CSRF, and Isolation Tests"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import enforce_resource_visibility
from app.core.security import (
    decrypt_field,
    encrypt_field,
    hash_password,
    verify_password,
)
from app.models import Base, SecurityEvent, UserSession


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Ensure clean tables before every test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ------------------------------------------------------------------------------
# 1. Argon2id Password Security
# ------------------------------------------------------------------------------
def test_argon2id_hashing():
    """Test Argon2id password hashing and constant-time verification."""
    password = "SuperSecurePassword123!"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False

    with pytest.raises(ValueError, match="at least 8 characters"):
        hash_password("short")


# ------------------------------------------------------------------------------
# 2. Field-Level AES-256-GCM Encryption
# ------------------------------------------------------------------------------
def test_field_level_encryption_aes_gcm():
    """Test AES-256-GCM field encryption and decryption."""
    raw_account_number = "1234567890123456"
    encrypted = encrypt_field(raw_account_number)

    assert encrypted != raw_account_number
    assert len(encrypted) > 20

    decrypted = decrypt_field(encrypted)
    assert decrypted == raw_account_number


# ------------------------------------------------------------------------------
# 3. Registration and Session Issuance
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_user_registration_and_session(async_client: AsyncClient):
    """Test full registration flow, session cookie creation, and Owner role."""
    payload = {
        "email": "newowner@family.in",
        "full_name": "Family Owner",
        "password": "CorrectHorseBattery99!",
        "household_name": "Verma Household",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["user"]["email"] == "newowner@family.in"
    assert data["household"]["name"] == "Verma Household"
    assert data["household"]["role"] == "Owner"
    assert "csrf_token" in data

    # Check HttpOnly cookie set
    cookies = response.cookies
    assert "sfbm_session" in cookies

    # Verify duplicate email is blocked
    dup_res = await async_client.post("/api/v1/auth/register", json=payload)
    assert dup_res.status_code == 400


# ------------------------------------------------------------------------------
# 4. Login, Failed Login Security Event, and Session Rotation
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_success_and_failure(async_client: AsyncClient):
    """Test login success and verify that failed attempts log to security_events."""
    reg_payload = {
        "email": "loginuser@family.in",
        "full_name": "Login User",
        "password": "ValidPassword123!",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # 1. Invalid password -> Expect 401
    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@family.in", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401

    # Verify LOGIN_FAILURE logged in security_events
    async with AsyncSessionLocal() as db:
        events = (
            (await db.execute(select(SecurityEvent).where(SecurityEvent.event_type == "LOGIN_FAILURE"))).scalars().all()
        )
        assert len(events) >= 1

    # 2. Correct password -> Expect 200 with new session cookie
    good_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@family.in", "password": "ValidPassword123!"},
    )
    assert good_login.status_code == 200
    assert "sfbm_session" in good_login.cookies


# ------------------------------------------------------------------------------
# 5. CSRF Protection on State-Changing Endpoints
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_csrf_token_enforcement(async_client: AsyncClient):
    """Test that POST /logout without or with invalid X-CSRF-Token fails with 403."""
    reg_payload = {
        "email": "csrfuser@family.in",
        "full_name": "CSRF User",
        "password": "ValidPassword123!",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    valid_csrf = reg_res.json()["csrf_token"]

    # 1. Attempt logout without CSRF header -> 403 Forbidden
    res_no_csrf = await async_client.post("/api/v1/auth/logout")
    assert res_no_csrf.status_code == 403
    assert "CSRF" in res_no_csrf.json()["detail"]

    # 2. Attempt logout with bad CSRF token -> 403 Forbidden
    res_bad_csrf = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "bad-invalid-csrf-token"},
    )
    assert res_bad_csrf.status_code == 403

    # 3. Valid CSRF header -> 200 OK
    res_good = await async_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": valid_csrf},
    )
    assert res_good.status_code == 200


# ------------------------------------------------------------------------------
# 6. Session Revocation ("Log Out Everywhere")
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_logout_everywhere(async_client: AsyncClient):
    """Test global session revocation across multiple devices."""
    reg_payload = {
        "email": "multidevice@family.in",
        "full_name": "Multi User",
        "password": "ValidPassword123!",
    }
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    csrf_token = reg_res.json()["csrf_token"]
    user_id = uuid.UUID(reg_res.json()["user"]["id"])

    # Simulate 2 additional active sessions on other devices
    async with AsyncSessionLocal() as db:
        for _ in range(2):
            extra_session = UserSession(
                user_id=user_id,
                session_token_hash=str(uuid.uuid4()),
                csrf_token="csrf",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
            db.add(extra_session)
        await db.commit()

        # Confirm 3 total sessions exist
        count = (await db.execute(select(UserSession).where(UserSession.user_id == user_id))).scalars().all()
        assert len(count) == 3

    # Execute logout-all
    logout_all_res = await async_client.post(
        "/api/v1/auth/logout-all",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_all_res.status_code == 200

    # Verify all sessions are wiped
    async with AsyncSessionLocal() as db:
        remaining = (await db.execute(select(UserSession).where(UserSession.user_id == user_id))).scalars().all()
        assert len(remaining) == 0


# ------------------------------------------------------------------------------
# 7. Session Expiry & Idle Timeout
# ------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_session_idle_timeout(async_client: AsyncClient):
    """Test that a session idle for longer than 2 hours is rejected with 401."""
    reg_payload = {
        "email": "idletest@family.in",
        "full_name": "Idle User",
        "password": "ValidPassword123!",
    }
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    # Manually backdate last_active_at by 3 hours
    async with AsyncSessionLocal() as db:
        session_obj = (await db.execute(select(UserSession))).scalar_one()
        session_obj.last_active_at = datetime.now(UTC) - timedelta(hours=3)
        await db.commit()

    # Query /me -> expect 401 due to inactivity
    res = await async_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "inactivity" in res.json()["detail"].lower()


# ------------------------------------------------------------------------------
# 8. IDOR Prevention & Visibility Isolation (Must return 404!)
# ------------------------------------------------------------------------------
def test_idor_404_prevention():
    """
    CRITICAL SECURITY CHECK:
    Accessing another household's data or another user's private data
    must raise HTTP 404 (Not Found), NEVER 403 (Forbidden), to prevent resource probing.
    """
    household_a = uuid.uuid4()
    household_b = uuid.uuid4()
    user_1 = uuid.uuid4()
    user_2 = uuid.uuid4()

    # 1. Cross-household access attempt -> Expect 404
    with pytest.raises(HTTPException) as exc_info:
        enforce_resource_visibility(
            resource_household_id=household_b,
            resource_user_id=user_2,
            resource_visibility="shared",
            current_household_id=household_a,
            current_user_id=user_1,
        )
    assert exc_info.value.status_code == 404

    # 2. Same household, but private record of user_2 -> Expect 404
    with pytest.raises(HTTPException) as exc_info:
        enforce_resource_visibility(
            resource_household_id=household_a,
            resource_user_id=user_2,
            resource_visibility="private",
            current_household_id=household_a,
            current_user_id=user_1,
        )
    assert exc_info.value.status_code == 404

    # 3. Same household and shared visibility -> Allowed (No exception)
    enforce_resource_visibility(
        resource_household_id=household_a,
        resource_user_id=user_2,
        resource_visibility="shared",
        current_household_id=household_a,
        current_user_id=user_1,
    )

    # 4. Same household and private record of user_1 (self) -> Allowed (No exception)
    enforce_resource_visibility(
        resource_household_id=household_a,
        resource_user_id=user_1,
        resource_visibility="private",
        current_household_id=household_a,
        current_user_id=user_1,
    )
