"""Unit & integration tests for Module 13: Gold & Silver Tracking.
Verifies:
1. Physical holding creation & standard hallmark purity assignment
2. Pure 24K gold equivalent calculation
3. Manual price logging with mandatory external source and date
4. Accurate market valuation and unrealized gain/loss computation
5. IDOR 404 isolation across households
6. Optimistic concurrency control (version column)
"""

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.precious_metal import MetalType


@pytest.mark.asyncio
async def test_gold_and_silver_holdings_and_valuation(async_client: AsyncClient):
    # 1. Register User & Household
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "golduser@example.com",
            "password": "StrongPassword123!",
            "full_name": "Gold Investor",
            "household_name": "Gold Household",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # 2. Add 22K Gold Necklace: 16 grams, purchased for ₹96,000 (rate was ₹6,000/g)
    necklace_payload = {
        "metal_type": MetalType.GOLD_22K.value,
        "item_name": "Traditional Gold Chain",
        "form": "JEWELLERY",
        "weight_grams": "16.000",
        "purchase_date": "2025-05-10",
        "purchase_price": "96000.00",
        "storage_location": "Home Safe",
    }
    gold_res = await async_client.post("/api/v1/metals/holdings", json=necklace_payload, headers=headers)
    assert gold_res.status_code == 201
    gold_data = gold_res.json()
    assert gold_data["item_name"] == "Traditional Gold Chain"
    assert Decimal(str(gold_data["purity_percentage"])) == Decimal("91.60")
    assert gold_data["current_estimated_value"] is None  # No market rate logged yet

    # 3. Add 999 Silver Coin: 100 grams, purchased for ₹8,000 (rate was ₹80/g)
    silver_payload = {
        "metal_type": MetalType.SILVER_999.value,
        "item_name": "Lakshmi Ganesh Silver Coin",
        "form": "COIN",
        "weight_grams": "100.000",
        "purchase_date": "2025-10-24",
        "purchase_price": "8000.00",
        "storage_location": "Pooja Almirah",
    }
    silver_res = await async_client.post("/api/v1/metals/holdings", json=silver_payload, headers=headers)
    assert silver_res.status_code == 201
    silver_data = silver_res.json()
    assert Decimal(str(silver_data["purity_percentage"])) == Decimal("99.90")

    # 4. Check initial summary without quotes: Total purchase cost = 96000 + 8000 = 104000
    summary_res1 = await async_client.get("/api/v1/metals/summary", headers=headers)
    assert summary_res1.status_code == 200
    sum1 = summary_res1.json()
    assert Decimal(str(sum1["total_gold_grams"])) == Decimal("16.000")
    # Pure 24K equiv = 16 * 0.916 = 14.656
    assert Decimal(str(sum1["total_gold_24k_pure_equiv_grams"])) == Decimal("14.656")
    assert Decimal(str(sum1["total_silver_grams"])) == Decimal("100.000")
    assert Decimal(str(sum1["total_purchase_cost"])) == Decimal("104000.00")

    # 5. Record Manual Bullion Price Quotes
    # 22K Gold rate: ₹6,750 / gram from "IBJA Official"
    rate_gold_res = await async_client.post(
        "/api/v1/metals/prices",
        json={
            "metal_type": MetalType.GOLD_22K.value,
            "rate_per_gram": "6750.00",
            "as_of_date": "2026-11-06",
            "source": "IBJA Official",
            "notes": "Chennai Closing Bullion Rate",
        },
        headers=headers,
    )
    assert rate_gold_res.status_code == 201

    # 999 Silver rate: ₹92.00 / gram from "IBJA Official"
    rate_silver_res = await async_client.post(
        "/api/v1/metals/prices",
        json={
            "metal_type": MetalType.SILVER_999.value,
            "rate_per_gram": "92.00",
            "as_of_date": "2026-11-06",
            "source": "IBJA Official",
        },
        headers=headers,
    )
    assert rate_silver_res.status_code == 201

    # 6. Verify valuation of gold holding:
    # 16 grams * 6,750 = ₹1,08,000
    # Gain = 1,08,000 - 96,000 = ₹12,000 (+12.50%)
    get_gold = (await async_client.get(f"/api/v1/metals/holdings/{gold_data['id']}", headers=headers)).json()
    assert Decimal(str(get_gold["current_estimated_value"])) == Decimal("108000.00")
    assert Decimal(str(get_gold["unrealized_gain_loss"])) == Decimal("12000.00")
    assert Decimal(str(get_gold["return_percentage"])) == Decimal("12.50")
    assert get_gold["valuation_source"] == "IBJA Official"

    # 7. Verify valuation of silver holding:
    # 100 grams * 92 = ₹9,200
    # Gain = 9,200 - 8,000 = ₹1,200 (+15.00%)
    get_silver = (await async_client.get(f"/api/v1/metals/holdings/{silver_data['id']}", headers=headers)).json()
    assert Decimal(str(get_silver["current_estimated_value"])) == Decimal("9200.00")
    assert Decimal(str(get_silver["unrealized_gain_loss"])) == Decimal("1200.00")
    assert Decimal(str(get_silver["return_percentage"])) == Decimal("15.00")

    # 8. Verify aggregated portfolio summary:
    # Total valuation: 1,08,000 + 9,200 = 1,17,200
    # Total cost: 1,04,000
    # Total gain: 13,200
    # Overall return: (13,200 / 104,000) * 100 = 12.69%
    summary_res2 = await async_client.get("/api/v1/metals/summary", headers=headers)
    sum2 = summary_res2.json()
    assert Decimal(str(sum2["total_estimated_value"])) == Decimal("117200.00")
    assert Decimal(str(sum2["total_unrealized_gain_loss"])) == Decimal("13200.00")
    assert Decimal(str(sum2["overall_return_percentage"])) == Decimal("12.69")


@pytest.mark.asyncio
async def test_metals_optimistic_locking(async_client: AsyncClient):
    """Test optimistic concurrency control (version column) on holdings."""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "lock_user@example.com",
            "password": "Password123!",
            "full_name": "Lock User",
            "household_name": "Lock Household",
        },
    )
    headers = {"X-CSRF-Token": reg.json()["csrf_token"]}

    holding = (
        await async_client.post(
            "/api/v1/metals/holdings",
            json={
                "metal_type": MetalType.GOLD_24K.value,
                "item_name": "Gold Bar 10g",
                "weight_grams": "10.000",
                "purchase_date": "2026-01-15",
                "purchase_price": "72000.00",
            },
            headers=headers,
        )
    ).json()

    # Optimistic locking: Version mismatch returns 409 Conflict
    conflict_res = await async_client.patch(
        f"/api/v1/metals/holdings/{holding['id']}",
        json={"storage_location": "Bank Locker", "version": 999},
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # Valid update
    valid_res = await async_client.patch(
        f"/api/v1/metals/holdings/{holding['id']}",
        json={"storage_location": "Bank Locker", "version": holding["version"]},
        headers=headers,
    )
    assert valid_res.status_code == 200
    assert valid_res.json()["version"] == 2
    assert valid_res.json()["storage_location"] == "Bank Locker"


@pytest.mark.asyncio
async def test_metals_idor_404_isolation(async_client: AsyncClient):
    """Security check: Cannot access precious metal holdings from another household."""
    # Household A
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "metal_a@example.com",
            "password": "Password123!",
            "full_name": "User Metal A",
            "household_name": "Household Metal A",
        },
    )
    headers_a = {"X-CSRF-Token": reg_a.json()["csrf_token"]}

    holding_a = (
        await async_client.post(
            "/api/v1/metals/holdings",
            json={
                "metal_type": MetalType.GOLD_24K.value,
                "item_name": "Gold Coin 5g",
                "weight_grams": "5.000",
                "purchase_date": "2026-02-01",
                "purchase_price": "36000.00",
            },
            headers=headers_a,
        )
    ).json()

    # Household B
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": "metal_b@example.com",
            "password": "Password123!",
            "full_name": "User Metal B",
            "household_name": "Household Metal B",
        },
    )
    headers_b = {"X-CSRF-Token": reg_b.json()["csrf_token"]}

    # Household B attempts to access Household A's holding -> 404
    get_res = await async_client.get(f"/api/v1/metals/holdings/{holding_a['id']}", headers=headers_b)
    assert get_res.status_code == 404
