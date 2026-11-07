"""Bank Statement Import Endpoints"""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models import Household, User
from app.schemas.statement_import import (
    StatementConfirmRequest,
    StatementConfirmResponse,
    StatementPreviewResponse,
)
from app.services.statement_service import (
    confirm_statement_import,
    preview_statement_csv,
)

router = APIRouter(prefix="/imports", tags=["Statement Import"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/preview",
    response_model=StatementPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview Statement CSV and Detect Duplicates",
)
async def post_preview_statement(
    account_id: uuid.UUID = Form(...),
    file: UploadFile = Form(...),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> StatementPreviewResponse:
    """
    Parses an uploaded bank statement CSV:
    - Validates columns (Date, Description, Debit/Credit)
    - Automatically detects duplicates against existing ledger transactions
    - Suggests category matches based on standard Indian bank narrations
    - Safe against CSV formula injection
    """
    household, _ = household_and_role

    # Validate file type
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV statement files (.csv) are currently supported.",
        )

    # Read content with size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10 MB limit.",
        )

    return await preview_statement_csv(
        db=db,
        household_id=household.id,
        user_id=user.id,
        account_id=account_id,
        csv_bytes=content,
    )


@router.post(
    "/confirm",
    response_model=StatementConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm and Commit Statement Transactions",
    dependencies=[Depends(verify_csrf)],
)
async def post_confirm_statement(
    payload: StatementConfirmRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> StatementConfirmResponse:
    """
    Atomically commits approved statement transactions into the ledger:
    - Skips duplicate rows
    - Records audit log
    - Guarantees zero duplicate balance effects
    """
    household, _ = household_and_role
    return await confirm_statement_import(
        db=db,
        household_id=household.id,
        user_id=user.id,
        payload=payload,
    )
