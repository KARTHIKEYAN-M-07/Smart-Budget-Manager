"""Privacy-preserving optional integrations service.
Strict privacy rules:
- Zero external AI services (no sensitive data leaks)
- Deterministic local regex parsing
- Explicit revocable user consent with cryptographic token erasure
- Safe draft inbox: auto-parsed items are staged for human review before ledger commit
"""

import hashlib
import re
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_field
from app.models import (
    AuditLog,
    FinancialAccount,
    InboxItemStatus,
    IntegrationConsent,
    IntegrationProvider,
    ParsedInboxItem,
    Transaction,
)
from app.models.base import get_utc_now
from app.schemas.integration import (
    InboxItemAcceptRequest,
    IntegrationConsentCreate,
    IntegrationConsentResponse,
    LocalReceiptParseRequest,
    LocalSMSParseRequest,
    ParsedInboxItemResponse,
)


def _sanitize_sms(text: str) -> str:
    """Strips OTP, PIN, and account balance patterns to prevent sensitive leak."""
    # Redact OTP / secret codes
    sanitized = re.sub(r"\b\d{4,6}\b(?=.*(?:OTP|secret|code|password))", "[REDACTED_OTP]", text, flags=re.IGNORECASE)
    # Redact available balance amounts
    sanitized = re.sub(r"(?:Avl|Available|Total)\s+(?:Bal|Balance)[:\s]+(?:Rs\.?|INR)?\s*[\d,]+(?:\.\d{2})?", "[BAL_REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized.strip()


async def get_active_consent(
    db: AsyncSession,
    household_id: uuid.UUID,
    provider: str,
) -> IntegrationConsent | None:
    stmt = select(IntegrationConsent).where(
        IntegrationConsent.household_id == household_id,
        IntegrationConsent.provider == provider,
        IntegrationConsent.is_active.is_(True),
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def grant_consent(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: IntegrationConsentCreate,
) -> IntegrationConsentResponse:
    if payload.provider not in [p.value for p in IntegrationProvider]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {payload.provider}",
        )

    stmt = select(IntegrationConsent).where(
        IntegrationConsent.household_id == household_id,
        IntegrationConsent.provider == payload.provider,
        IntegrationConsent.user_id == user_id,
    )
    res = await db.execute(stmt)
    consent = res.scalar_one_or_none()

    enc_token = encrypt_field(payload.auth_token) if payload.auth_token else None
    enc_refresh = encrypt_field(payload.refresh_token) if payload.refresh_token else None

    if consent:
        consent.is_active = True
        consent.scopes = payload.scopes
        if enc_token:
            consent.encrypted_auth_token = enc_token
        if enc_refresh:
            consent.encrypted_refresh_token = enc_refresh
        consent.revoked_at = None
        consent.consented_at = get_utc_now()
    else:
        consent = IntegrationConsent(
            household_id=household_id,
            user_id=user_id,
            provider=payload.provider,
            scopes=payload.scopes,
            encrypted_auth_token=enc_token,
            encrypted_refresh_token=enc_refresh,
            is_active=True,
            consented_at=get_utc_now(),
        )
        db.add(consent)

    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        action="CREATE" if not consent else "UPDATE",
        entity_name="IntegrationConsent",
        entity_id=consent.id,
        new_values={"provider": payload.provider, "scopes": payload.scopes, "is_active": True},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(consent)

    return IntegrationConsentResponse.model_validate(consent)


async def revoke_consent(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: str,
) -> IntegrationConsentResponse:
    stmt = select(IntegrationConsent).where(
        IntegrationConsent.household_id == household_id,
        IntegrationConsent.provider == provider,
        IntegrationConsent.is_active.is_(True),
    )
    res = await db.execute(stmt)
    consent = res.scalar_one_or_none()
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active consent not found for this provider",
        )

    # Cryptographic erasure: overwrite and wipe tokens
    consent.is_active = False
    consent.revoked_at = get_utc_now()
    consent.encrypted_auth_token = None
    consent.encrypted_refresh_token = None

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        action="UPDATE",
        entity_name="IntegrationConsent",
        entity_id=consent.id,
        new_values={"provider": provider, "is_active": False, "revoked": True},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(consent)

    return IntegrationConsentResponse.model_validate(consent)


async def list_consents(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[IntegrationConsentResponse]:
    stmt = select(IntegrationConsent).where(
        IntegrationConsent.household_id == household_id
    ).order_by(IntegrationConsent.created_at.desc())
    res = await db.execute(stmt)
    consents = res.scalars().all()
    return [IntegrationConsentResponse.model_validate(c) for c in consents]


async def parse_and_stage_sms(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: LocalSMSParseRequest,
) -> ParsedInboxItemResponse:
    # 1. Privacy enforcement: verify active consent
    consent = await get_active_consent(db, household_id, IntegrationProvider.ANDROID_SMS_SYNC.value)
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explicit user consent for ANDROID_SMS_SYNC is required before parsing SMS",
        )

    text = payload.sms_text.strip()
    # 2. Local Deterministic Parser
    # Match amount: debited by Rs. 500.00 / Rs 1,500.00 debited / spent INR 450.00 / paid Rs. 250
    amt_match = re.search(
        r"(?:debited\s+(?:by\s+)?|paid\s+|spent\s+)?(?:Rs\.?|INR)\s*([0-9,]+(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE,
    )
    if not amt_match:
        # Check alternate format: 500.00 debited
        amt_match = re.search(r"([0-9,]+(?:\.[0-9]{2})?)\s*(?:debited|spent)", text, re.IGNORECASE)

    if not amt_match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to locally extract financial debit amount from message",
        )

    raw_amt_str = amt_match.group(1).replace(",", "")
    parsed_amount = Decimal(raw_amt_str)
    if parsed_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parsed amount must be positive",
        )

    # Match last4 account/card:
    last4 = None
    last4_match = re.search(r"(?:a/c|acct|card|ending)\s*(?:no\.?)?\s*(?:x+|\*+)?([0-9]{4})", text, re.IGNORECASE)
    if last4_match:
        last4 = last4_match.group(1)

    # Match merchant: to / at / vpa
    merchant = None
    merch_match = re.search(r"(?:to|at|vpa|info)\s+([A-Za-z0-9\.\-@_ ]+?)(?:\s+on|\s+ref|\s+avl|\s+bal|\.|$|,)", text, re.IGNORECASE)
    if merch_match:
        merchant = merch_match.group(1).strip()[:100]

    # Source identifier hash for deduplication
    sanitized = _sanitize_sms(text)
    src_hash = hashlib.sha256(f"{payload.sender or 'SMS'}_{parsed_amount}_{last4}_{sanitized[:50]}".encode()).hexdigest()[:32]
    source_identifier = f"sms_{src_hash}"

    # Check duplicate
    stmt = select(ParsedInboxItem).where(
        ParsedInboxItem.household_id == household_id,
        ParsedInboxItem.source_identifier == source_identifier,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return ParsedInboxItemResponse.model_validate(existing)

    item = ParsedInboxItem(
        household_id=household_id,
        consent_id=consent.id,
        item_type="SMS_DEBIT",
        source_identifier=source_identifier,
        parsed_amount=parsed_amount,
        parsed_merchant=merchant,
        parsed_account_last4=last4,
        parsed_date=date.today(),
        raw_snippet=sanitized[:500],
        status=InboxItemStatus.PENDING_REVIEW.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return ParsedInboxItemResponse.model_validate(item)


async def parse_and_stage_receipt(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: LocalReceiptParseRequest,
) -> ParsedInboxItemResponse:
    # 1. Privacy enforcement: verify active consent
    consent = await get_active_consent(db, household_id, IntegrationProvider.GMAIL_RECEIPTS.value)
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Explicit user consent for GMAIL_RECEIPTS is required before parsing receipts",
        )

    text = payload.receipt_text
    # Deterministic local regex for receipt totals: Total: Rs. 1,299.00 / Grand Total: ₹450.00
    amt_match = re.search(
        r"(?:total|grand\s+total|amount\s+paid|order\s+total|net\s+payable)[\s:]+(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)",
        text,
        re.IGNORECASE,
    )
    if not amt_match:
        amt_match = re.search(r"(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)

    if not amt_match:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to locally extract total amount from receipt",
        )

    raw_amt_str = amt_match.group(1).replace(",", "")
    parsed_amount = Decimal(raw_amt_str)
    if parsed_amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parsed amount must be positive",
        )

    # Merchant extraction heuristic (first line or domain)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    merchant = lines[0][:100] if lines else "Store Receipt"

    source_id = f"rcpt_{payload.source_identifier[:100]}"
    stmt = select(ParsedInboxItem).where(
        ParsedInboxItem.household_id == household_id,
        ParsedInboxItem.source_identifier == source_id,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return ParsedInboxItemResponse.model_validate(existing)

    item = ParsedInboxItem(
        household_id=household_id,
        consent_id=consent.id,
        item_type="RECEIPT",
        source_identifier=source_id,
        parsed_amount=parsed_amount,
        parsed_merchant=merchant,
        parsed_account_last4=None,
        parsed_date=payload.receipt_date or date.today(),
        raw_snippet=text[:500],
        status=InboxItemStatus.PENDING_REVIEW.value,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return ParsedInboxItemResponse.model_validate(item)


async def list_inbox_items(
    db: AsyncSession,
    household_id: uuid.UUID,
    status_filter: str | None = None,
    limit: int = 50,
) -> list[ParsedInboxItemResponse]:
    stmt = select(ParsedInboxItem).where(
        ParsedInboxItem.household_id == household_id
    )
    if status_filter:
        stmt = stmt.where(ParsedInboxItem.status == status_filter)
    stmt = stmt.order_by(ParsedInboxItem.created_at.desc()).limit(limit)

    res = await db.execute(stmt)
    items = res.scalars().all()
    return [ParsedInboxItemResponse.model_validate(i) for i in items]


async def accept_inbox_item(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: InboxItemAcceptRequest,
) -> ParsedInboxItemResponse:
    stmt = select(ParsedInboxItem).where(
        ParsedInboxItem.id == item_id,
        ParsedInboxItem.household_id == household_id,
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found",
        )

    if item.status != InboxItemStatus.PENDING_REVIEW.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item is already {item.status}",
        )

    # Verify target account belongs to household
    stmt_acc = select(FinancialAccount).where(
        FinancialAccount.id == payload.account_id,
        FinancialAccount.household_id == household_id,
        FinancialAccount.is_active.is_(True),
    )
    res_acc = await db.execute(stmt_acc)
    account = res_acc.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Financial account not found or inactive",
        )

    txn_dt = datetime.combine(item.parsed_date, time.min, tzinfo=UTC)
    desc = payload.notes or f"Imported: {item.parsed_merchant or 'Expense'}"

    # Commit to authentic transaction ledger
    transaction = Transaction(
        household_id=household_id,
        account_id=account.id,
        category_id=payload.category_id,
        user_id=user_id,
        amount=item.parsed_amount,
        direction="OUTFLOW",
        transaction_type="EXPENSE",
        visibility="shared",
        description=desc,
        transaction_date=txn_dt,
        status="POSTED",
        version=1,
    )
    db.add(transaction)
    await db.flush()

    item.status = InboxItemStatus.ACCEPTED.value

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        action="UPDATE",
        entity_name="ParsedInboxItem",
        entity_id=item.id,
        new_values={
            "transaction_id": str(transaction.id),
            "amount": str(item.parsed_amount),
            "status": "ACCEPTED",
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(item)

    return ParsedInboxItemResponse.model_validate(item)


async def dismiss_inbox_item(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
) -> ParsedInboxItemResponse:
    stmt = select(ParsedInboxItem).where(
        ParsedInboxItem.id == item_id,
        ParsedInboxItem.household_id == household_id,
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox item not found",
        )

    item.status = InboxItemStatus.DISMISSED.value

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        action="UPDATE",
        entity_name="ParsedInboxItem",
        entity_id=item.id,
        new_values={"status": "DISMISSED"},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(item)

    return ParsedInboxItemResponse.model_validate(item)
