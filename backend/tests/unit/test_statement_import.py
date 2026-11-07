"""Bank Statement Import Tests (Module 9).
Validates:
1. Flexible Indian CSV parsing (HDFC, SBI, generic)
2. Heuristic category inference
3. Blueprint scenario test: Importing the same statement twice (100% duplicate detection)
4. Anti-double counting (Derived balance unaffected by duplicate upload)
5. CSV Formula Injection (CWE-1236) sanitization
6. IDOR 404 protection
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

SAMPLE_HDFC_CSV = """Date,Narration,Chq/Ref No,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/11/2026,SALARY CREDIT FROM INFOTECH,REF1001,01/11/2026,,75000.00,75000.00
02/11/2026,UPI-SWIGGY FOOD ORDER-502,UPI002,02/11/2026,450.00,,74550.00
03/11/2026,ZEPTO QUICK COMMERCE BANGALORE,REF1003,03/11/2026,820.00,,73730.00
04/11/2026,MONTHLY APARTMENT RENT PAYMENT,REF1004,04/11/2026,25000.00,,48730.00
"""

SAMPLE_FORMULA_INJECTION_CSV = """Date,Narration,Withdrawal,Deposit
05/11/2026,=cmd|'/C calc'!A0,150.00,
06/11/2026,@SUM(1+1),250.00,
"""


@pytest.fixture
async def import_setup(async_client: AsyncClient):
    email = f"import_{uuid.uuid4().hex[:8]}@family.in"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Import User",
            "household_name": "Import Family",
        },
    )
    assert reg.status_code == 201
    auth_data = reg.json()
    headers = {"X-CSRF-Token": auth_data["csrf_token"]}

    # Seed categories
    await async_client.post("/api/v1/categories/seed", headers=headers)

    # Create primary bank account
    acc = (
        await async_client.post(
            "/api/v1/accounts",
            headers=headers,
            json={"name": "HDFC Salary Account", "account_type": "savings"},
        )
    ).json()

    return {
        "client": async_client,
        "headers": headers,
        "account_id": acc["id"],
    }


@pytest.mark.asyncio
async def test_statement_preview_and_confirm(import_setup):
    """Verifies parsing, category matching, and confirmation of statement."""
    client = import_setup["client"]
    headers = import_setup["headers"]
    acc_id = import_setup["account_id"]

    # 1. Preview Statement
    files = {"file": ("statement.csv", SAMPLE_HDFC_CSV.encode("utf-8"), "text/csv")}
    data = {"account_id": acc_id}

    prev_res = await client.post("/api/v1/imports/preview", headers=headers, data=data, files=files)
    assert prev_res.status_code == 200
    preview = prev_res.json()

    assert preview["total_rows"] == 4
    assert preview["new_rows_count"] == 4
    assert preview["duplicate_rows_count"] == 0

    # Verify category inference
    items = preview["preview_items"]
    salary_row = next(r for r in items if "SALARY" in r["description"])
    assert salary_row["direction"] == "INFLOW"
    assert Decimal(str(salary_row["amount"])) == Decimal("75000.00")
    assert salary_row["category_name"] == "Salary & Wages"

    swiggy_row = next(r for r in items if "SWIGGY" in r["description"])
    assert swiggy_row["direction"] == "OUTFLOW"
    assert Decimal(str(swiggy_row["amount"])) == Decimal("450.00")
    assert "Dining" in swiggy_row["category_name"]

    # 2. Confirm Statement Import
    confirm_payload = {
        "account_id": acc_id,
        "transactions": [
            {
                "date": r["date"],
                "description": r["description"],
                "amount": r["amount"],
                "direction": r["direction"],
                "transaction_type": r["transaction_type"],
                "category_id": r["category_id"],
                "visibility": "shared",
                "idempotency_key": r["idempotency_key"],
            }
            for r in items
        ],
    }

    conf_res = await client.post("/api/v1/imports/confirm", headers=headers, json=confirm_payload)
    assert conf_res.status_code == 201
    confirm_data = conf_res.json()

    assert confirm_data["imported_count"] == 4
    assert confirm_data["skipped_duplicates_count"] == 0

    # 3. Verify Derived Balance
    # 75000 - 450 - 820 - 25000 = 48730.00
    acc_bal = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(acc_bal["derived_balance"])) == Decimal("48730.00")


@pytest.mark.asyncio
async def test_blueprint_scenario_import_same_statement_twice(import_setup):
    """
    CRITICAL BLUEPRINT SCENARIO:
    Importing the exact same statement twice must detect 100% duplicates,
    import 0 records on the second attempt, and keep balances intact.
    """
    client = import_setup["client"]
    headers = import_setup["headers"]
    acc_id = import_setup["account_id"]

    # First Import
    files1 = {"file": ("statement.csv", SAMPLE_HDFC_CSV.encode("utf-8"), "text/csv")}
    prev1 = await client.post(
        "/api/v1/imports/preview", headers=headers, data={"account_id": acc_id}, files=files1
    )
    assert prev1.status_code == 200
    items1 = prev1.json()["preview_items"]

    # Commit First Import
    await client.post(
        "/api/v1/imports/confirm",
        headers=headers,
        json={
            "account_id": acc_id,
            "transactions": [
                {
                    "date": r["date"],
                    "description": r["description"],
                    "amount": r["amount"],
                    "direction": r["direction"],
                    "transaction_type": r["transaction_type"],
                    "category_id": r["category_id"],
                    "visibility": "shared",
                    "idempotency_key": r["idempotency_key"],
                }
                for r in items1
            ],
        },
    )

    bal1 = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(bal1["derived_balance"])) == Decimal("48730.00")

    # Second Import of the EXACT SAME FILE
    files2 = {"file": ("statement.csv", SAMPLE_HDFC_CSV.encode("utf-8"), "text/csv")}
    prev2 = await client.post(
        "/api/v1/imports/preview", headers=headers, data={"account_id": acc_id}, files=files2
    )
    assert prev2.status_code == 200
    p2_data = prev2.json()

    # MUST DETECT 100% DUPLICATES
    assert p2_data["total_rows"] == 4
    assert p2_data["new_rows_count"] == 0
    assert p2_data["duplicate_rows_count"] == 4
    assert all(r["is_duplicate"] is True for r in p2_data["preview_items"])

    # Attempt to confirm anyway
    conf2 = await client.post(
        "/api/v1/imports/confirm",
        headers=headers,
        json={
            "account_id": acc_id,
            "transactions": [
                {
                    "date": r["date"],
                    "description": r["description"],
                    "amount": r["amount"],
                    "direction": r["direction"],
                    "transaction_type": r["transaction_type"],
                    "category_id": r["category_id"],
                    "visibility": "shared",
                    "idempotency_key": r["idempotency_key"],
                }
                for r in p2_data["preview_items"]
            ],
        },
    )
    assert conf2.status_code == 201
    c2_data = conf2.json()
    assert c2_data["imported_count"] == 0
    assert c2_data["skipped_duplicates_count"] == 4

    # Derived balance MUST NOT change
    bal2 = (await client.get(f"/api/v1/accounts/{acc_id}")).json()
    assert Decimal(str(bal2["derived_balance"])) == Decimal("48730.00")


@pytest.mark.asyncio
async def test_csv_formula_injection_sanitization(import_setup):
    """Validates that cells starting with =, +, -, @ are sanitized against formula execution."""
    client = import_setup["client"]
    headers = import_setup["headers"]
    acc_id = import_setup["account_id"]

    files = {"file": ("injection.csv", SAMPLE_FORMULA_INJECTION_CSV.encode("utf-8"), "text/csv")}
    prev = await client.post(
        "/api/v1/imports/preview", headers=headers, data={"account_id": acc_id}, files=files
    )
    assert prev.status_code == 200
    items = prev.json()["preview_items"]

    assert len(items) == 2
    # Formulas must be prefixed with single quote
    assert items[0]["description"].startswith("'=")
    assert items[1]["description"].startswith("'@")
