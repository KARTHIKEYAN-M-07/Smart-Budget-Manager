"""Privacy-preserving optional integrations API endpoints"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models.household import Household
from app.models.user import User
from app.schemas.integration import (
    InboxItemAcceptRequest,
    IntegrationConsentCreate,
    IntegrationConsentResponse,
    LocalReceiptParseRequest,
    LocalSMSParseRequest,
    ParsedInboxItemResponse,
)
from app.services.integration_service import (
    accept_inbox_item,
    dismiss_inbox_item,
    grant_consent,
    list_consents,
    list_inbox_items,
    parse_and_stage_receipt,
    parse_and_stage_sms,
    revoke_consent,
)

router = APIRouter(prefix="/integrations", tags=["Optional Integrations"])


@router.get("/consents", response_model=list[IntegrationConsentResponse])
async def get_consents_endpoint(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List integration consent statuses for the household."""
    household, _ = household_and_role
    return await list_consents(db=db, household_id=household.id)


@router.post(
    "/consents",
    response_model=IntegrationConsentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def grant_consent_endpoint(
    payload: IntegrationConsentCreate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Grant or update explicit consent for an integration."""
    household, _ = household_and_role
    return await grant_consent(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/consents/{provider}",
    response_model=IntegrationConsentResponse,
    dependencies=[Depends(verify_csrf)],
)
async def revoke_consent_endpoint(
    provider: str,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Immediately revoke integration consent with cryptographic token erasure."""
    household, _ = household_and_role
    return await revoke_consent(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        provider=provider,
    )


@router.get("/inbox", response_model=list[ParsedInboxItemResponse])
async def get_inbox_endpoint(
    status_filter: str | None = Query(None, description="PENDING_REVIEW, ACCEPTED, or DISMISSED"),
    limit: int = Query(50, ge=1, le=100),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List staged draft items in the local inbox awaiting review."""
    household, _ = household_and_role
    return await list_inbox_items(
        db=db,
        household_id=household.id,
        status_filter=status_filter,
        limit=limit,
    )


@router.post(
    "/parse-sms",
    response_model=ParsedInboxItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def parse_sms_endpoint(
    payload: LocalSMSParseRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Locally parse financial SMS debit and stage to inbox (requires active consent)."""
    household, _ = household_and_role
    return await parse_and_stage_sms(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/parse-receipt",
    response_model=ParsedInboxItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def parse_receipt_endpoint(
    payload: LocalReceiptParseRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Locally parse receipt text and stage to inbox (requires active consent)."""
    household, _ = household_and_role
    return await parse_and_stage_receipt(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/inbox/{item_id}/accept",
    response_model=ParsedInboxItemResponse,
    dependencies=[Depends(verify_csrf)],
)
async def accept_inbox_item_endpoint(
    item_id: uuid.UUID,
    payload: InboxItemAcceptRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Accept staged item into real ledger transaction."""
    household, _ = household_and_role
    return await accept_inbox_item(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        item_id=item_id,
        payload=payload,
    )


@router.post(
    "/inbox/{item_id}/dismiss",
    response_model=ParsedInboxItemResponse,
    dependencies=[Depends(verify_csrf)],
)
async def dismiss_inbox_item_endpoint(
    item_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Dismiss staged item without writing to ledger."""
    household, _ = household_and_role
    return await dismiss_inbox_item(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        item_id=item_id,
    )
