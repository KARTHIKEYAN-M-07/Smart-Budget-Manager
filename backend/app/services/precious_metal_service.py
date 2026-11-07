"""Precious metal portfolio and valuation service.
Financial rules:
- Strictly never invent or simulate market prices
- Require manual source and date for every rate quote
- Pure equivalent calculations based on verified purity percentages
- Optimistic locking and IDOR 404 security checks
"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    MetalType,
    PreciousMetalHolding,
    PreciousMetalPrice,
)
from app.schemas.precious_metal import (
    PreciousMetalHoldingCreate,
    PreciousMetalHoldingResponse,
    PreciousMetalHoldingUpdate,
    PreciousMetalPortfolioSummary,
    PreciousMetalPriceCreate,
    PreciousMetalPriceResponse,
)


def get_standard_purity(metal_type: MetalType) -> Decimal:
    """Standard Indian hallmark purities."""
    match metal_type:
        case MetalType.GOLD_24K:
            return Decimal("99.90")
        case MetalType.GOLD_22K:
            return Decimal("91.60")
        case MetalType.GOLD_18K:
            return Decimal("75.00")
        case MetalType.SILVER_999:
            return Decimal("99.90")
        case MetalType.SILVER_925:
            return Decimal("92.50")
        case _:
            return Decimal("91.60")


async def get_latest_metal_prices(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> dict[str, PreciousMetalPrice]:
    """Retrieves the most recent recorded price quote for each metal type in the household."""
    stmt = (
        select(PreciousMetalPrice)
        .where(PreciousMetalPrice.household_id == household_id)
        .order_by(PreciousMetalPrice.as_of_date.desc(), PreciousMetalPrice.created_at.desc())
    )
    res = await db.execute(stmt)
    prices = res.scalars().all()

    latest_by_metal: dict[str, PreciousMetalPrice] = {}
    for p in prices:
        if p.metal_type not in latest_by_metal:
            latest_by_metal[p.metal_type] = p

    return latest_by_metal


def build_holding_response(
    holding: PreciousMetalHolding,
    latest_price: PreciousMetalPrice | None,
) -> PreciousMetalHoldingResponse:
    current_rate = None
    estimated_value = None
    gain_loss = None
    return_pct = None
    val_source = None
    val_date = None

    if latest_price:
        current_rate = latest_price.rate_per_gram
        val_source = latest_price.source
        val_date = latest_price.as_of_date
        # Valuation = weight * rate
        estimated_value = (holding.weight_grams * current_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        gain_loss = estimated_value - holding.purchase_price
        if holding.purchase_price > Decimal("0.00"):
            return_pct = ((gain_loss / holding.purchase_price) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            return_pct = Decimal("0.00")

    return PreciousMetalHoldingResponse(
        id=holding.id,
        household_id=holding.household_id,
        user_id=holding.user_id,
        metal_type=MetalType(holding.metal_type),
        item_name=holding.item_name,
        form=holding.form,
        weight_grams=holding.weight_grams,
        purity_percentage=holding.purity_percentage,
        purchase_date=holding.purchase_date,
        purchase_price=holding.purchase_price,
        storage_location=holding.storage_location,
        notes=holding.notes,
        version=holding.version,
        created_at=holding.created_at,
        current_rate_per_gram=current_rate,
        current_estimated_value=estimated_value,
        unrealized_gain_loss=gain_loss,
        return_percentage=return_pct,
        valuation_source=val_source,
        valuation_date=val_date,
    )


async def record_precious_metal_price(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: PreciousMetalPriceCreate,
) -> PreciousMetalPriceResponse:
    """Records a manual bullion rate quote from a verified local or national source."""
    # Check for existing quote with same source on same date
    stmt = select(PreciousMetalPrice).where(
        PreciousMetalPrice.household_id == household_id,
        PreciousMetalPrice.metal_type == payload.metal_type.value,
        PreciousMetalPrice.as_of_date == payload.as_of_date,
        PreciousMetalPrice.source == payload.source,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.rate_per_gram = payload.rate_per_gram
        existing.notes = payload.notes
        existing.recorded_by_user_id = user_id
        target = existing
        action = "UPDATE"
    else:
        target = PreciousMetalPrice(
            household_id=household_id,
            recorded_by_user_id=user_id,
            metal_type=payload.metal_type.value,
            rate_per_gram=payload.rate_per_gram,
            as_of_date=payload.as_of_date,
            source=payload.source,
            notes=payload.notes,
        )
        db.add(target)
        action = "CREATE"

    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="PreciousMetalPrice",
        entity_id=target.id,
        action=action,
        new_values={
            "metal_type": target.metal_type,
            "rate_per_gram": str(target.rate_per_gram),
            "source": target.source,
            "as_of_date": str(target.as_of_date),
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(target)

    return PreciousMetalPriceResponse.model_validate(target)


async def list_precious_metal_prices(
    db: AsyncSession,
    household_id: uuid.UUID,
    metal_type: MetalType | None = None,
    limit: int = 50,
) -> list[PreciousMetalPriceResponse]:
    stmt = (
        select(PreciousMetalPrice)
        .where(PreciousMetalPrice.household_id == household_id)
        .order_by(PreciousMetalPrice.as_of_date.desc(), PreciousMetalPrice.created_at.desc())
        .limit(limit)
    )
    if metal_type:
        stmt = stmt.where(PreciousMetalPrice.metal_type == metal_type.value)

    res = await db.execute(stmt)
    prices = res.scalars().all()
    return [PreciousMetalPriceResponse.model_validate(p) for p in prices]


async def create_precious_metal_holding(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: PreciousMetalHoldingCreate,
) -> PreciousMetalHoldingResponse:
    purity = payload.purity_percentage or get_standard_purity(payload.metal_type)

    holding = PreciousMetalHolding(
        household_id=household_id,
        user_id=user_id,
        metal_type=payload.metal_type.value,
        item_name=payload.item_name,
        form=payload.form.value,
        weight_grams=payload.weight_grams,
        purity_percentage=purity,
        purchase_date=payload.purchase_date,
        purchase_price=payload.purchase_price,
        storage_location=payload.storage_location,
        notes=payload.notes,
        version=1,
    )
    db.add(holding)
    await db.flush()

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="PreciousMetalHolding",
        entity_id=holding.id,
        action="CREATE",
        new_values={
            "item_name": holding.item_name,
            "metal_type": holding.metal_type,
            "weight_grams": str(holding.weight_grams),
            "purchase_price": str(holding.purchase_price),
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(holding)

    latest_prices = await get_latest_metal_prices(db, household_id)
    latest_quote = latest_prices.get(holding.metal_type)
    return build_holding_response(holding, latest_quote)


async def list_precious_metal_holdings(
    db: AsyncSession,
    household_id: uuid.UUID,
    metal_type: MetalType | None = None,
) -> list[PreciousMetalHoldingResponse]:
    stmt = (
        select(PreciousMetalHolding)
        .where(PreciousMetalHolding.household_id == household_id)
        .order_by(PreciousMetalHolding.purchase_date.desc(), PreciousMetalHolding.created_at.desc())
    )
    if metal_type:
        stmt = stmt.where(PreciousMetalHolding.metal_type == metal_type.value)

    res = await db.execute(stmt)
    holdings = res.scalars().all()

    latest_prices = await get_latest_metal_prices(db, household_id)
    return [build_holding_response(h, latest_prices.get(h.metal_type)) for h in holdings]


async def get_precious_metal_holding_by_id(
    db: AsyncSession,
    household_id: uuid.UUID,
    holding_id: uuid.UUID,
) -> PreciousMetalHoldingResponse:
    stmt = select(PreciousMetalHolding).where(
        PreciousMetalHolding.id == holding_id,
        PreciousMetalHolding.household_id == household_id,
    )
    res = await db.execute(stmt)
    holding = res.scalar_one_or_none()
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Precious metal holding not found",
        )

    latest_prices = await get_latest_metal_prices(db, household_id)
    return build_holding_response(holding, latest_prices.get(holding.metal_type))


async def update_precious_metal_holding(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    payload: PreciousMetalHoldingUpdate,
) -> PreciousMetalHoldingResponse:
    stmt = select(PreciousMetalHolding).where(
        PreciousMetalHolding.id == holding_id,
        PreciousMetalHolding.household_id == household_id,
    )
    res = await db.execute(stmt)
    holding = res.scalar_one_or_none()
    if not holding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Precious metal holding not found",
        )

    if holding.version != payload.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holding was modified by another session. Please reload.",
        )

    if payload.item_name is not None:
        holding.item_name = payload.item_name
    if payload.weight_grams is not None:
        holding.weight_grams = payload.weight_grams
    if payload.purity_percentage is not None:
        holding.purity_percentage = payload.purity_percentage
    if payload.purchase_price is not None:
        holding.purchase_price = payload.purchase_price
    if payload.storage_location is not None:
        holding.storage_location = payload.storage_location
    if payload.notes is not None:
        holding.notes = payload.notes

    holding.version += 1

    audit = AuditLog(
        household_id=household_id,
        user_id=user_id,
        entity_name="PreciousMetalHolding",
        entity_id=holding.id,
        action="UPDATE",
        new_values={
            "weight_grams": str(holding.weight_grams),
            "purchase_price": str(holding.purchase_price),
            "version": holding.version,
        },
    )
    db.add(audit)
    await db.commit()
    await db.refresh(holding)

    latest_prices = await get_latest_metal_prices(db, household_id)
    return build_holding_response(holding, latest_prices.get(holding.metal_type))


async def get_precious_metal_portfolio_summary(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> PreciousMetalPortfolioSummary:
    holdings_list = await list_precious_metal_holdings(db, household_id)
    latest_prices = await get_latest_metal_prices(db, household_id)

    total_gold_grams = Decimal("0.000")
    total_silver_grams = Decimal("0.000")
    pure_gold_equiv = Decimal("0.000")
    total_cost = Decimal("0.00")
    total_val = Decimal("0.00")

    for h in holdings_list:
        total_cost += h.purchase_price
        if h.current_estimated_value:
            total_val += h.current_estimated_value
        else:
            # If no price logged yet, default valuation to purchase cost
            total_val += h.purchase_price

        if "GOLD" in h.metal_type.value:
            total_gold_grams += h.weight_grams
            # Pure 24K equivalent = weight * (purity / 100)
            pure_gold_equiv += (h.weight_grams * (h.purity_percentage / Decimal("100.00"))).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )
        elif "SILVER" in h.metal_type.value:
            total_silver_grams += h.weight_grams

    gain_loss = total_val - total_cost
    return_pct = Decimal("0.00")
    if total_cost > Decimal("0.00"):
        return_pct = ((gain_loss / total_cost) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    formatted_rates = {
        m: PreciousMetalPriceResponse.model_validate(p) for m, p in latest_prices.items()
    }

    return PreciousMetalPortfolioSummary(
        total_gold_grams=total_gold_grams,
        total_silver_grams=total_silver_grams,
        total_gold_24k_pure_equiv_grams=pure_gold_equiv,
        total_purchase_cost=total_cost,
        total_estimated_value=total_val,
        total_unrealized_gain_loss=gain_loss,
        overall_return_percentage=return_pct,
        holdings_count=len(holdings_list),
        latest_rates=formatted_rates,
    )
