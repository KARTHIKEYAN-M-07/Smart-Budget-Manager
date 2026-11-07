"""Category Management Endpoints"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    verify_csrf,
)
from app.models import Category, Household, Transaction
from app.schemas.category import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.services.category_service import seed_household_categories

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List Household Categories",
)
async def list_categories(
    type: str | None = Query(default=None, description="Optional type filter: income, expense, transfer, investment"),
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> list[CategoryResponse]:
    """Lists all categories defined for the caller's household."""
    household, _ = household_and_role
    stmt = select(Category).where(Category.household_id == household.id)
    if type:
        stmt = stmt.where(Category.type == type.lower().strip())
    stmt = stmt.order_by(Category.type, Category.name)

    categories = (await db.execute(stmt)).scalars().all()
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Custom Category",
    dependencies=[Depends(verify_csrf)],
)
async def create_category(
    payload: CategoryCreateRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    """Creates a custom category for the active household."""
    household, _ = household_and_role
    clean_name = payload.name.strip()

    # Check unique constraint (household_id, name, type)
    check_stmt = select(Category).where(
        Category.household_id == household.id,
        Category.name == clean_name,
        Category.type == payload.type,
    )
    existing = (await db.execute(check_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{clean_name}' of type '{payload.type}' already exists",
        )

    # Validate parent if specified
    if payload.parent_id:
        parent_stmt = select(Category).where(
            Category.id == payload.parent_id,
            Category.household_id == household.id,
        )
        parent = (await db.execute(parent_stmt)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent category not found",
            )

    cat = Category(
        household_id=household.id,
        name=clean_name,
        type=payload.type,
        icon=payload.icon,
        color=payload.color,
        is_system=False,
        parent_id=payload.parent_id,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return CategoryResponse.model_validate(cat)


@router.post(
    "/seed",
    status_code=status.HTTP_200_OK,
    summary="Seed Default Indian Category Taxonomy",
    dependencies=[Depends(verify_csrf)],
)
async def seed_categories(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str | int]:
    """
    Populates standard Indian category taxonomy (e.g. Groceries, Electricity, Fuel, EMI, Gold)
    for the active household. Idempotent: skips existing entries.
    """
    household, _ = household_and_role
    added_count = await seed_household_categories(db, household.id)
    return {
        "message": f"Seeded {added_count} default categories successfully",
        "added_count": added_count,
    }


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Category",
    dependencies=[Depends(verify_csrf)],
)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdateRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> CategoryResponse:
    """Updates category name, icon, color, or parent."""
    household, _ = household_and_role
    stmt = select(Category).where(Category.id == category_id, Category.household_id == household.id)
    cat = (await db.execute(stmt)).scalar_one_or_none()

    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if payload.name is not None:
        cat.name = payload.name.strip()
    if payload.icon is not None:
        cat.icon = payload.icon
    if payload.color is not None:
        cat.color = payload.color
    if payload.parent_id is not None:
        cat.parent_id = payload.parent_id

    await db.commit()
    await db.refresh(cat)
    return CategoryResponse.model_validate(cat)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Category",
    dependencies=[Depends(verify_csrf)],
)
async def delete_category(
    category_id: uuid.UUID,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Deletes category if not referenced by transactions and not system category."""
    household, _ = household_and_role
    stmt = select(Category).where(Category.id == category_id, Category.household_id == household.id)
    cat = (await db.execute(stmt)).scalar_one_or_none()

    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    # Check if referenced by transactions
    txn_stmt = select(Transaction).where(Transaction.category_id == category_id).limit(1)
    has_txns = (await db.execute(txn_stmt)).scalar_one_or_none()
    if has_txns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category because transactions are linked to it",
        )

    await db.delete(cat)
    await db.commit()
    return {"message": "Category deleted successfully"}
