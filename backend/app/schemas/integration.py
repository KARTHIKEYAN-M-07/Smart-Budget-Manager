"""Pydantic schemas for privacy-preserving integrations"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IntegrationConsentCreate(BaseModel):
    provider: str = Field(..., description="GMAIL_RECEIPTS, ANDROID_SMS_SYNC, or ACCOUNT_AGGREGATOR")
    scopes: str = Field(default="read_only", max_length=255)
    auth_token: str | None = Field(default=None, description="Plaintext token to encrypt and store")
    refresh_token: str | None = Field(default=None, description="Plaintext refresh token to encrypt and store")


class IntegrationConsentResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    user_id: uuid.UUID
    provider: str
    scopes: str
    is_active: bool
    consented_at: datetime
    revoked_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocalSMSParseRequest(BaseModel):
    sms_text: str = Field(..., min_length=5, max_length=1000)
    sender: str | None = Field(default=None, max_length=50)


class LocalReceiptParseRequest(BaseModel):
    receipt_text: str = Field(..., min_length=5, max_length=5000)
    source_identifier: str = Field(..., max_length=150)
    receipt_date: date | None = None


class ParsedInboxItemResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    consent_id: uuid.UUID | None = None
    item_type: str
    source_identifier: str
    parsed_amount: Decimal
    parsed_merchant: str | None = None
    parsed_account_last4: str | None = None
    parsed_date: date
    raw_snippet: str | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InboxItemAcceptRequest(BaseModel):
    account_id: uuid.UUID = Field(..., description="Financial account to charge")
    category_id: uuid.UUID | None = Field(default=None, description="Category for spending")
    notes: str | None = Field(default=None, max_length=255)
