"""Investment portfolio API endpoints"""

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
from app.models.investment import AssetClass
from app.models.user import User
from app.schemas.investment import (
    InvestmentCreateRequest,
    InvestmentPortfolioSummary,
    InvestmentResponse,
    InvestmentTransactionCreateRequest,
    InvestmentTransactionResponse,
    InvestmentUpdateRequest,
)
from app.services.investment_service import (
    add_investment_transaction,
    create_investment,
    get_investment_by_id,
    get_investment_portfolio_summary,
    list_investments,
    update_investment,
)

router = APIRouter(prefix="/investments", tags=["Investments & Portfolio"])


@router.get("/summary", response_model=InvestmentPortfolioSummary)
async def get_summary(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve aggregate investment portfolio summary and asset class allocation."""
    household, _ = household_and_role
    return await get_investment_portfolio_summary(db=db, household_id=household.id)


@router.get("", response_model=list[InvestmentResponse])
async def get_investments(
    asset_class: AssetClass | None = Query(None, description="Filter by asset class"),
    is_active: bool | None = Query(None, description="Filter active/matured investments"),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List investment holdings for the household."""
    household, _ = household_and_role
    return await list_investments(
        db=db,
        household_id=household.id,
        asset_class=asset_class,
        is_active=is_active,
    )


@router.post(
    "",
    response_model=InvestmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_new_investment(
    payload: InvestmentCreateRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Record a new investment holding.
    If source_account_id is provided, automatically records an INVESTMENT_BUY
    ledger movement (not an expense) to debit the funding account.
    """
    household, _ = household_and_role
    return await create_investment(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/{investment_id}", response_model=InvestmentResponse)
async def get_investment(
    investment_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve details and transaction history for an investment holding."""
    household, _ = household_and_role
    return await get_investment_by_id(
        db=db,
        household_id=household.id,
        investment_id=investment_id,
    )


@router.patch(
    "/{investment_id}",
    response_model=InvestmentResponse,
    dependencies=[Depends(verify_csrf)],
)
async def update_investment_details(
    investment_id: uuid.UUID,
    payload: InvestmentUpdateRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update current valuation or notes with optimistic locking."""
    household, _ = household_and_role
    return await update_investment(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        investment_id=investment_id,
        payload=payload,
    )


@router.post(
    "/{investment_id}/transactions",
    response_model=InvestmentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def add_transaction(
    investment_id: uuid.UUID,
    payload: InvestmentTransactionCreateRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Record an investment Buy, Sell, Dividend, or Interest.
    If source_account_id is provided, reconciles against the cash/bank ledger.
    """
    household, _ = household_and_role
    return await add_investment_transaction(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        investment_id=investment_id,
        payload=payload,
    )
