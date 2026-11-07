"""Household management, data portability export, and DPDP / GDPR right-to-be-forgotten purge"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import (
    get_current_household_and_role,
    get_current_user,
    require_role,
    verify_csrf,
)
from app.models import (
    AuditLog,
    Category,
    FinancialAccount,
    Household,
    Investment,
    Loan,
    PreciousMetalHolding,
    RecurringBill,
    SecurityEvent,
    Transaction,
    User,
)
from app.models.base import get_utc_now

router = APIRouter(prefix="/household", tags=["Household & Privacy Compliance"])


class HouseholdPurgeRequest(BaseModel):
    confirm_phrase: str = Field(..., description="Must equal 'PURGE_ALL_HOUSEHOLD_DATA' to authorize destruction")


@router.get("/export", response_model=dict[str, Any])
async def export_household_data(
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    DPDP / GDPR Data Portability: Exports complete household data in machine-readable JSON.
    Accessible to all active members of the household.
    """
    household, role = household_and_role
    h_id = household.id

    # 1. Accounts
    acc_res = await db.execute(select(FinancialAccount).where(FinancialAccount.household_id == h_id))
    accounts = [
        {
            "id": str(a.id),
            "name": a.name,
            "account_type": a.account_type,
            "institution_name": a.institution_name,
            "account_number_last4": a.account_number_last4,
            "visibility": a.visibility,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat(),
        }
        for a in acc_res.scalars().all()
    ]

    # 2. Categories
    cat_res = await db.execute(select(Category).where(Category.household_id == h_id))
    categories = [
        {
            "id": str(c.id),
            "name": c.name,
            "icon": c.icon,
            "color": c.color,
            "parent_id": str(c.parent_id) if c.parent_id else None,
        }
        for c in cat_res.scalars().all()
    ]

    # 3. Transactions
    txn_res = await db.execute(
        select(Transaction).where(Transaction.household_id == h_id).order_by(Transaction.transaction_date.desc())
    )
    transactions = [
        {
            "id": str(t.id),
            "account_id": str(t.account_id),
            "category_id": str(t.category_id) if t.category_id else None,
            "amount": str(t.amount),
            "direction": t.direction,
            "transaction_type": t.transaction_type,
            "description": t.description,
            "transaction_date": t.transaction_date.isoformat(),
            "status": t.status,
            "visibility": t.visibility,
        }
        for t in txn_res.scalars().all()
    ]

    # 4. Recurring Bills & Loans
    bill_res = await db.execute(select(RecurringBill).where(RecurringBill.household_id == h_id))
    bills = [
        {
            "id": str(b.id),
            "biller_name": b.biller_name,
            "expected_amount": str(b.expected_amount),
            "due_date": b.due_date.isoformat(),
            "frequency": b.frequency,
            "is_active": b.is_active,
        }
        for b in bill_res.scalars().all()
    ]

    loan_res = await db.execute(select(Loan).where(Loan.household_id == h_id))
    loans = [
        {
            "id": str(loan_item.id),
            "lender_name": loan_item.lender_name,
            "principal_amount": str(loan_item.principal_amount),
            "interest_rate": str(loan_item.annual_interest_rate),
            "emi_amount": str(loan_item.monthly_emi),
            "total_tenure_months": loan_item.tenure_months,
            "start_date": loan_item.start_date.isoformat(),
        }
        for loan_item in loan_res.scalars().all()
    ]

    # 5. Precious Metals
    metal_res = await db.execute(select(PreciousMetalHolding).where(PreciousMetalHolding.household_id == h_id))
    metals = [
        {
            "id": str(m.id),
            "metal_type": m.metal_type,
            "form": m.form,
            "purity_percentage": str(m.purity_percentage),
            "weight_grams": str(m.weight_grams),
            "purchase_price": str(m.purchase_price),
            "purchase_date": m.purchase_date.isoformat(),
        }
        for m in metal_res.scalars().all()
    ]

    # 6. Investments
    inv_res = await db.execute(select(Investment).where(Investment.household_id == h_id))
    investments = [
        {
            "id": str(i.id),
            "name": i.name,
            "asset_class": i.asset_class,
            "current_valuation": str(i.current_value),
            "total_invested": str(i.invested_amount),
        }
        for i in inv_res.scalars().all()
    ]

    # 7. Audit trail
    audit_res = await db.execute(
        select(AuditLog).where(AuditLog.household_id == h_id).order_by(AuditLog.created_at.desc()).limit(100)
    )
    audits = [
        {
            "id": str(a.id),
            "entity_name": a.entity_name,
            "entity_id": str(a.entity_id),
            "action": a.action,
            "created_at": a.created_at.isoformat(),
        }
        for a in audit_res.scalars().all()
    ]

    # Record security event for data export
    sec_evt = SecurityEvent(
        user_id=current_user.id,
        event_type="DATA_EXPORT",
        ip_address="127.0.0.1",
        user_agent="SFBM Client",
        metadata_json={"household_id": str(h_id), "exported_tables_count": 7},
    )
    db.add(sec_evt)
    await db.commit()

    return {
        "export_metadata": {
            "household_id": str(household.id),
            "household_name": household.name,
            "exported_at": get_utc_now().isoformat(),
            "exported_by_user_id": str(current_user.id),
            "exported_by_user_name": current_user.full_name,
            "format_version": "1.0",
        },
        "accounts": accounts,
        "categories": categories,
        "transactions": transactions,
        "bills": bills,
        "loans": loans,
        "precious_metals": metals,
        "investments": investments,
        "recent_audit_trail": audits,
    }


@router.delete(
    "/purge",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_csrf), Depends(require_role("Owner"))],
)
async def purge_household_data(
    payload: HouseholdPurgeRequest,
    household_and_role: tuple[Household, str] = Depends(get_current_household_and_role),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    DPDP / GDPR Right to be Forgotten: Permanently deletes all household data,
    cascading transactions, holdings, and accounts.
    Requires Owner role and explicit confirmation phrase.
    """
    household, role = household_and_role
    if payload.confirm_phrase != "PURGE_ALL_HOUSEHOLD_DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase mismatch. Must provide exactly 'PURGE_ALL_HOUSEHOLD_DATA'",
        )

    h_id = household.id

    # Record final security event before purging
    sec_evt = SecurityEvent(
        user_id=current_user.id,
        event_type="HOUSEHOLD_PURGED",
        ip_address="127.0.0.1",
        user_agent="SFBM Client",
        metadata_json={"household_id": str(h_id), "purged_by": current_user.email},
    )
    db.add(sec_evt)
    await db.flush()

    # Cascade delete household (Foreign keys ondelete=CASCADE remove all child rows)
    await db.execute(delete(Household).where(Household.id == h_id))
    await db.commit()

    return {
        "message": "Household and all associated financial records have been permanently purged.",
        "household_id": str(h_id),
        "purged_at": get_utc_now().isoformat(),
    }
