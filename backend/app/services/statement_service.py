"""Bank statement parsing and duplicate detection service.
Secure against CSV formula injection.
Zero external dependencies (uses standard library csv and hashlib).
Supports major Indian bank formats (HDFC, SBI, ICICI, Axis, Kotak, etc.).
"""

import csv
import hashlib
import io
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Category, FinancialAccount, Transaction
from app.schemas.statement_import import (
    ParsedStatementRow,
    StatementConfirmRequest,
    StatementConfirmResponse,
    StatementPreviewResponse,
)

# Indian category keyword heuristic rules
KEYWORD_CATEGORY_MAP = {
    "swiggy": "Dining Out & Food Delivery (Swiggy/Zomato)",
    "zomato": "Dining Out & Food Delivery (Swiggy/Zomato)",
    "zepto": "Groceries & Supermarket",
    "blinkit": "Groceries & Supermarket",
    "instamart": "Groceries & Supermarket",
    "bigbasket": "Groceries & Supermarket",
    "supermarket": "Groceries & Supermarket",
    "dmart": "Groceries & Supermarket",
    "milk": "Milk & Dairy",
    "dairy": "Milk & Dairy",
    "petrol": "Fuel (Petrol/Diesel/CNG)",
    "fuel": "Fuel (Petrol/Diesel/CNG)",
    "hpcl": "Fuel (Petrol/Diesel/CNG)",
    "bpcl": "Fuel (Petrol/Diesel/CNG)",
    "ioc": "Fuel (Petrol/Diesel/CNG)",
    "uber": "Public Transit & Cabs (Metro/Auto/Uber/Ola)",
    "ola": "Public Transit & Cabs (Metro/Auto/Uber/Ola)",
    "metro": "Public Transit & Cabs (Metro/Auto/Uber/Ola)",
    "electricity": "Electricity Bill (TNEB/BESCOM/Discom)",
    "tneb": "Electricity Bill (TNEB/BESCOM/Discom)",
    "bescom": "Electricity Bill (TNEB/BESCOM/Discom)",
    "airtel": "Mobile Recharge & Broadband WiFi",
    "jio": "Mobile Recharge & Broadband WiFi",
    "broadband": "Mobile Recharge & Broadband WiFi",
    "rent": "House Rent & Society Maintenance",
    "pharmacy": "Medicines & Pharmacy",
    "apollo": "Medicines & Pharmacy",
    "medplus": "Medicines & Pharmacy",
    "salary": "Salary & Wages",
    "interest": "Interest Income (FD/Savings)",
    "atm": "ATM Cash Withdrawal",
}


def sanitize_csv_cell(value: str) -> str:
    """
    Prevents CSV Formula Injection (CWE-1236).
    Neutralizes formula triggers (=, +, -, @, tab, cr).
    """
    val = value.strip()
    if val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val}"
    return val


def parse_date_flexible(raw_date: str) -> date:
    """Parses various Indian date representations into date object."""
    cleaned = raw_date.strip().split(" ")[0].replace("/", "-").replace(".", "-")
    parts = cleaned.split("-")
    if len(parts) == 3:
        # DD-MM-YYYY or DD-MM-YY
        if len(parts[2]) == 4:
            return datetime.strptime(f"{parts[0]}-{parts[1]}-{parts[2]}", "%d-%m-%Y").date()
        if len(parts[0]) == 4:
            # YYYY-MM-DD
            return datetime.strptime(f"{parts[0]}-{parts[1]}-{parts[2]}", "%Y-%m-%d").date()
        if len(parts[2]) == 2:
            # DD-MM-YY
            return datetime.strptime(f"{parts[0]}-{parts[1]}-20{parts[2]}", "%d-%m-%Y").date()
    raise ValueError(f"Unrecognized date format: {raw_date}")


def parse_amount(val: str) -> Decimal:
    """Parses currency string safely into positive Decimal."""
    cleaned = re.sub(r"[^\d.]", "", val.strip())
    if not cleaned:
        return Decimal("0.00")
    try:
        amt = Decimal(cleaned)
        if amt < 0:
            return Decimal("0.00")
        return amt.quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def generate_row_idempotency_key(
    household_id: uuid.UUID,
    account_id: uuid.UUID,
    row_date: date,
    amount: Decimal,
    direction: str,
    description: str,
) -> str:
    """Generates deterministic idempotency key for statement line."""
    norm_desc = re.sub(r"\s+", " ", description.lower().strip())
    raw = f"{household_id}:{account_id}:{row_date.isoformat()}:{amount}:{direction}:{norm_desc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


async def preview_statement_csv(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    csv_bytes: bytes,
) -> StatementPreviewResponse:
    """Parses CSV statement and performs duplicate detection."""
    # 1. Validate Account
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == account_id,
        FinancialAccount.household_id == household_id,
    )
    acc = (await db.execute(stmt_acc)).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # 2. Fetch categories for auto-tagging
    stmt_cats = select(Category).where(Category.household_id == household_id)
    categories = (await db.execute(stmt_cats)).scalars().all()
    cat_by_name = {c.name.lower(): c for c in categories}

    # 3. Decode CSV safely
    try:
        text = csv_bytes.decode("utf-8-sig")  # Handles UTF-8 BOM
    except UnicodeDecodeError:
        try:
            text = csv_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to decode file encoding"
            ) from None

    # 4. Fetch existing idempotency keys for this account
    stmt_keys = select(Transaction.idempotency_key).where(
        Transaction.account_id == account_id,
        Transaction.idempotency_key.isnot(None),
    )
    existing_keys = set((await db.execute(stmt_keys)).scalars().all())

    # 5. Parse lines
    stream = io.StringIO(text)
    # Detect delimiter
    sample = text[:2048]
    delimiter = ","
    if "\t" in sample and sample.count("\t") > sample.count(","):
        delimiter = "\t"
    elif ";" in sample and sample.count(";") > sample.count(","):
        delimiter = ";"

    reader = csv.reader(stream, delimiter=delimiter)
    header = None
    rows_parsed: list[ParsedStatementRow] = []

    # Column index trackers
    idx_date = -1
    idx_desc = -1
    idx_debit = -1
    idx_credit = -1
    idx_amount = -1
    idx_type = -1

    for row_num, row in enumerate(reader, start=1):
        if not row or all(not cell.strip() for cell in row):
            continue

        if header is None:
            # Detect header row
            lowered = [cell.lower().strip() for cell in row]
            has_date = any("date" in c for c in lowered)
            has_money = any(any(k in c for k in ("debit", "withdrawal", "credit", "deposit", "amount")) for c in lowered)

            if has_date and has_money:
                header = lowered
                for i, col in enumerate(lowered):
                    if any(k in col for k in ("date", "txn date", "value date")):
                        idx_date = i
                    elif any(k in col for k in ("narration", "description", "particulars", "remarks", "details")):
                        idx_desc = i
                    elif any(k in col for k in ("withdrawal", "debit", "dr")):
                        idx_debit = i
                    elif any(k in col for k in ("deposit", "credit", "cr")):
                        idx_credit = i
                    elif "amount" in col:
                        idx_amount = i
                    elif "type" in col:
                        idx_type = i
                continue
            else:
                continue

        # Process transaction row
        try:
            if idx_date < 0 or idx_date >= len(row):
                continue
            raw_date = row[idx_date]
            if not raw_date.strip():
                continue
            txn_date = parse_date_flexible(raw_date)

            raw_desc = row[idx_desc] if idx_desc >= 0 and idx_desc < len(row) else "Imported Transaction"
            clean_desc = sanitize_csv_cell(raw_desc)

            # Determine Amount and Direction
            amount = Decimal("0.00")
            direction = "OUTFLOW"

            if idx_debit >= 0 and idx_credit >= 0:
                raw_deb = row[idx_debit] if idx_debit < len(row) else ""
                raw_cred = row[idx_credit] if idx_credit < len(row) else ""
                deb_val = parse_amount(raw_deb)
                cred_val = parse_amount(raw_cred)

                if cred_val > 0:
                    amount = cred_val
                    direction = "INFLOW"
                elif deb_val > 0:
                    amount = deb_val
                    direction = "OUTFLOW"
                else:
                    continue  # Zero amount row
            elif idx_amount >= 0:
                amount = parse_amount(row[idx_amount])
                if amount <= 0:
                    continue
                if idx_type >= 0 and idx_type < len(row):
                    type_str = row[idx_type].lower()
                    if "cr" in type_str or "deposit" in type_str or "inflow" in type_str:
                        direction = "INFLOW"
                    else:
                        direction = "OUTFLOW"
            else:
                continue

            # Infer Category
            suggested_cat_id = None
            suggested_cat_name = None
            desc_lower = clean_desc.lower()
            for kw, target_cat in KEYWORD_CATEGORY_MAP.items():
                if kw in desc_lower and target_cat.lower() in cat_by_name:
                    cat = cat_by_name[target_cat.lower()]
                    suggested_cat_id = cat.id
                    suggested_cat_name = cat.name
                    break

            # Idempotency and duplicate check
            idemp_key = generate_row_idempotency_key(
                household_id=household_id,
                account_id=account_id,
                row_date=txn_date,
                amount=amount,
                direction=direction,
                description=clean_desc,
            )

            is_dup = idemp_key in existing_keys
            dup_reason = "Transaction already imported" if is_dup else None

            rows_parsed.append(
                ParsedStatementRow(
                    row_number=row_num,
                    date=txn_date,
                    description=clean_desc,
                    amount=amount,
                    direction=direction,
                    transaction_type="INCOME" if direction == "INFLOW" else "EXPENSE",
                    category_id=suggested_cat_id,
                    category_name=suggested_cat_name,
                    is_duplicate=is_dup,
                    duplicate_reason=dup_reason,
                    idempotency_key=idemp_key,
                )
            )
        except (ValueError, KeyError, InvalidOperation, IndexError):
            continue

    if not rows_parsed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid transaction rows could be parsed. Please check date and amount columns.",
        )

    dup_count = sum(1 for r in rows_parsed if r.is_duplicate)
    new_count = len(rows_parsed) - dup_count

    return StatementPreviewResponse(
        account_id=acc.id,
        account_name=acc.name,
        total_rows=len(rows_parsed),
        new_rows_count=new_count,
        duplicate_rows_count=dup_count,
        preview_items=rows_parsed,
    )


async def confirm_statement_import(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: StatementConfirmRequest,
) -> StatementConfirmResponse:
    """Atomically commits non-duplicate statement rows into the ledger."""
    # Validate account
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == payload.account_id,
        FinancialAccount.household_id == household_id,
    )
    acc = (await db.execute(stmt_acc)).scalar_one_or_none()
    if not acc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    # Fetch existing idempotency keys
    keys_in_payload = [t.idempotency_key for t in payload.transactions]
    stmt_existing = select(Transaction.idempotency_key).where(
        Transaction.idempotency_key.in_(keys_in_payload)
    )
    existing_keys = set((await db.execute(stmt_existing)).scalars().all())

    imported_count = 0
    skipped_count = 0
    total_amount = Decimal("0.00")

    for item in payload.transactions:
        if item.idempotency_key in existing_keys:
            skipped_count += 1
            continue

        txn_dt = datetime.combine(item.date, datetime.min.time(), tzinfo=UTC)

        txn = Transaction(
            household_id=household_id,
            account_id=acc.id,
            category_id=item.category_id,
            user_id=user_id,
            amount=item.amount,
            direction=item.direction,
            transaction_type=item.transaction_type,
            visibility=item.visibility,
            description=item.description,
            transaction_date=txn_dt,
            status="POSTED",
            version=1,
            idempotency_key=item.idempotency_key,
        )
        db.add(txn)
        existing_keys.add(item.idempotency_key)
        imported_count += 1
        total_amount += item.amount

    # Audit entry
    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="StatementImport",
        entity_id=acc.id,
        action="CREATE",
        new_values={
            "account_id": str(acc.id),
            "imported_count": imported_count,
            "skipped_duplicates": skipped_count,
            "total_amount": str(total_amount),
        },
    )
    db.add(audit)
    await db.commit()

    return StatementConfirmResponse(
        account_id=acc.id,
        imported_count=imported_count,
        skipped_duplicates_count=skipped_count,
        total_imported_amount=total_amount,
        message=f"Successfully imported {imported_count} transactions ({skipped_count} duplicates skipped).",
    )
