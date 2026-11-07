"""Precious metals (Gold & Silver) API endpoints"""

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
from app.models.precious_metal import MetalType
from app.models.user import User
from app.schemas.precious_metal import (
    PreciousMetalHoldingCreate,
    PreciousMetalHoldingResponse,
    PreciousMetalHoldingUpdate,
    PreciousMetalPortfolioSummary,
    PreciousMetalPriceCreate,
    PreciousMetalPriceResponse,
)
from app.services.precious_metal_service import (
    create_precious_metal_holding,
    get_precious_metal_holding_by_id,
    get_precious_metal_portfolio_summary,
    list_precious_metal_holdings,
    list_precious_metal_prices,
    record_precious_metal_price,
    update_precious_metal_holding,
)

router = APIRouter(prefix="/metals", tags=["Precious Metals (Gold & Silver)"])


@router.get("/summary", response_model=PreciousMetalPortfolioSummary)
async def get_summary(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve aggregate gold & silver portfolio summary and valuation."""
    household, _ = household_and_role
    return await get_precious_metal_portfolio_summary(db=db, household_id=household.id)


@router.get("/holdings", response_model=list[PreciousMetalHoldingResponse])
async def get_holdings(
    metal_type: MetalType | None = Query(None, description="Filter by metal type"),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List physical holdings with valuation based on latest recorded manual quotes."""
    household, _ = household_and_role
    return await list_precious_metal_holdings(
        db=db,
        household_id=household.id,
        metal_type=metal_type,
    )


@router.post(
    "/holdings",
    response_model=PreciousMetalHoldingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_holding(
    payload: PreciousMetalHoldingCreate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Add a new gold or silver physical holding."""
    household, _ = household_and_role
    return await create_precious_metal_holding(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/holdings/{holding_id}", response_model=PreciousMetalHoldingResponse)
async def get_holding(
    holding_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieve details and valuation for a specific precious metal holding."""
    household, _ = household_and_role
    return await get_precious_metal_holding_by_id(
        db=db,
        household_id=household.id,
        holding_id=holding_id,
    )


@router.patch(
    "/holdings/{holding_id}",
    response_model=PreciousMetalHoldingResponse,
    dependencies=[Depends(verify_csrf)],
)
async def update_holding(
    holding_id: uuid.UUID,
    payload: PreciousMetalHoldingUpdate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update precious metal holding with optimistic concurrency check."""
    household, _ = household_and_role
    return await update_precious_metal_holding(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        holding_id=holding_id,
        payload=payload,
    )


@router.get("/prices", response_model=list[PreciousMetalPriceResponse])
async def get_prices(
    metal_type: MetalType | None = Query(None, description="Filter by metal type"),
    limit: int = Query(50, ge=1, le=100),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List historical recorded bullion price quotes with source and date."""
    household, _ = household_and_role
    return await list_precious_metal_prices(
        db=db,
        household_id=household.id,
        metal_type=metal_type,
        limit=limit,
    )


@router.post(
    "/prices",
    response_model=PreciousMetalPriceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_price(
    payload: PreciousMetalPriceCreate,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Record a manual market rate quote (IBJA, jeweller receipt, etc.). Never invent prices."""
    household, _ = household_and_role
    return await record_precious_metal_price(
        db=db,
        household_id=household.id,
        user_id=current_user.id,
        payload=payload,
    )
