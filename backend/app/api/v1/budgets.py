"""Budgets and Savings Goals Endpoints"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    verify_csrf,
)
from app.models import Household, User
from app.schemas.budget import (
    BudgetCreateRequest,
    BudgetResponse,
    SavingsGoalCreateRequest,
    SavingsGoalResponse,
    SavingsGoalUpdateRequest,
)
from app.services.budget_service import (
    create_savings_goal,
    delete_budget,
    list_household_budgets,
    list_savings_goals,
    set_or_create_budget,
    update_savings_goal,
)

router = APIRouter(prefix="/budgets", tags=["Budgets & Savings Goals"])


@router.get(
    "",
    response_model=list[BudgetResponse],
    status_code=status.HTTP_200_OK,
    summary="List Household Budgets with Real-Time Progress",
)
async def get_budgets(
    month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format (defaults to current month in UTC)",
    ),
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[BudgetResponse]:
    """Lists category and household budgets with dynamic spend, remaining amount, and alert thresholds (75%, 90%, 100%)."""
    household, _ = household_and_role
    if not month:
        now = datetime.now(UTC)
        month = f"{now.year:04d}-{now.month:02d}"

    return await list_household_budgets(db, household.id, user.id, month)


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set or Create Monthly Budget",
    dependencies=[Depends(verify_csrf)],
)
async def post_budget(
    payload: BudgetCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> BudgetResponse:
    """Sets a monthly spending limit for a specific category or the whole household."""
    household, _ = household_and_role
    return await set_or_create_budget(db, household.id, user.id, payload)


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Budget Limit",
    dependencies=[Depends(verify_csrf)],
)
async def remove_budget(
    budget_id: uuid.UUID,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Deletes a monthly budget limit."""
    household, _ = household_and_role
    await delete_budget(db, budget_id, household.id, user.id)
    return {"message": "Budget limit removed successfully"}


# ------------------------------------------------------------------------------
# Savings Goals Endpoints
# ------------------------------------------------------------------------------
@router.get(
    "/goals",
    response_model=list[SavingsGoalResponse],
    status_code=status.HTTP_200_OK,
    summary="List Savings Goals",
)
async def get_goals(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[SavingsGoalResponse]:
    """Lists active and completed family savings goals."""
    household, _ = household_and_role
    return await list_savings_goals(db, household.id)


@router.post(
    "/goals",
    response_model=SavingsGoalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Savings Goal",
    dependencies=[Depends(verify_csrf)],
)
async def post_goal(
    payload: SavingsGoalCreateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> SavingsGoalResponse:
    """Creates a new family savings goal."""
    household, _ = household_and_role
    return await create_savings_goal(db, household.id, user.id, payload)


@router.patch(
    "/goals/{goal_id}",
    response_model=SavingsGoalResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Savings Goal Progress",
    dependencies=[Depends(verify_csrf)],
)
async def patch_goal(
    goal_id: uuid.UUID,
    payload: SavingsGoalUpdateRequest,
    user: User = Depends(get_current_user),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> SavingsGoalResponse:
    """Updates goal progress amount, target date, or status with optimistic locking."""
    household, _ = household_and_role
    return await update_savings_goal(db, goal_id, household.id, user.id, payload)
