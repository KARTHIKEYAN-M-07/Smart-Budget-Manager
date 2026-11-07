"""Analytics and Reporting Endpoints"""

import calendar
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_household_and_role, get_current_user
from app.models import Household, User
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    FinancialYearReportResponse,
)
from app.services.analytics_service import (
    get_financial_year_report,
    get_overview_analytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics & Reports"])


@router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Overview Analytics & Breakdown",
)
async def get_overview(
    start_date: date | None = Query(
        default=None,
        description="Window start date (defaults to 1st of current month in UTC)",
    ),
    end_date: date | None = Query(
        default=None,
        description="Window end date (defaults to last day of current month in UTC)",
    ),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> AnalyticsOverviewResponse:
    """
    Computes SQL-aggregated real overview numbers:
    - Total Income
    - Total Net Expense (Gross expenses minus refunds)
    - Net Savings and Savings Rate (%)
    - Category breakdown
    - Family member spend distribution
    """
    household, _ = household_and_role
    now = datetime.now(UTC).date()

    if not start_date:
        start_date = date(now.year, now.month, 1)

    if not end_date:
        _, last_day = calendar.monthrange(now.year, now.month)
        end_date = date(now.year, now.month, last_day)

    return await get_overview_analytics(
        db=db,
        household_id=household.id,
        user_id=user.id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/financial-year",
    response_model=FinancialYearReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Indian Financial Year (Apr-Mar) Trend Report",
)
async def get_financial_year(
    year_offset: int = Query(
        default=0,
        description="Offset from current financial year (0 = current FY, -1 = previous FY)",
    ),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> FinancialYearReportResponse:
    """
    Generates 12-month aggregated trends for Indian Financial Year (April 1 to March 31).
    """
    household, _ = household_and_role
    return await get_financial_year_report(
        db=db,
        household_id=household.id,
        user_id=user.id,
        year_offset=year_offset,
    )
