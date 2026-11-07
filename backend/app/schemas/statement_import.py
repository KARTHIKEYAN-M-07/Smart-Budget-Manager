"""Bank Statement Import Schemas"""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ParsedStatementRow(BaseModel):
    row_number: int
    date: date
    description: str
    amount: Decimal
    direction: str  # "INFLOW" or "OUTFLOW"
    transaction_type: str  # "EXPENSE" or "INCOME"
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    is_duplicate: bool
    duplicate_reason: str | None = None
    idempotency_key: str


class StatementPreviewResponse(BaseModel):
    account_id: uuid.UUID
    account_name: str
    total_rows: int
    new_rows_count: int
    duplicate_rows_count: int
    preview_items: list[ParsedStatementRow]


class StatementConfirmRow(BaseModel):
    date: date
    description: str
    amount: Decimal = Field(gt=Decimal("0.00"), le=Decimal("100000000000.00"))
    direction: str
    transaction_type: str
    category_id: uuid.UUID | None = None
    visibility: str = "shared"
    idempotency_key: str


class StatementConfirmRequest(BaseModel):
    account_id: uuid.UUID
    transactions: list[StatementConfirmRow]


class StatementConfirmResponse(BaseModel):
    account_id: uuid.UUID
    imported_count: int
    skipped_duplicates_count: int
    total_imported_amount: Decimal
    message: str
