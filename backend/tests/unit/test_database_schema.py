"""Unit tests for Database Schema, Invariants, and Constraints"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal, engine
from app.models import (
    Base,
    FinancialAccount,
    Household,
    HouseholdMember,
    Transaction,
    User,
)


@pytest.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_no_editable_balance_column_on_accounts():
    """
    CRITICAL FINANCIAL INVARIANT:
    FinancialAccount must NOT have a balance column.
    Balances are strictly derived from ledger transactions.
    """
    column_names = [col.name for col in FinancialAccount.__table__.columns]
    assert "balance" not in column_names
    assert "current_balance" not in column_names
    assert "available_balance" not in column_names


@pytest.mark.asyncio
async def test_create_user_and_household():
    """Verify clean creation of User, Household, and HouseholdMember."""
    async with AsyncSessionLocal() as session:
        user = User(
            email="owner@example.com",
            full_name="Household Owner",
            password_hash="argon2id$mockedhash123",
        )
        household = Household(
            name="Sharma Family",
            currency="INR",
            timezone="Asia/Kolkata",
        )
        session.add_all([user, household])
        await session.commit()
        await session.refresh(user)
        await session.refresh(household)

        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="Owner",
        )
        session.add(membership)
        await session.commit()

        # Query back
        res = await session.execute(select(HouseholdMember).where(HouseholdMember.household_id == household.id))
        member = res.scalar_one()
        assert member.role == "Owner"
        assert member.user_id == user.id


@pytest.mark.asyncio
async def test_duplicate_user_email_rejected():
    """Verify unique constraint on user email."""
    async with AsyncSessionLocal() as session:
        user1 = User(
            email="test@example.com",
            full_name="User One",
            password_hash="argon2hash",
        )
        user2 = User(
            email="test@example.com",
            full_name="User Two",
            password_hash="argon2hash",
        )
        session.add(user1)
        await session.commit()

        session.add(user2)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_derived_balance_calculation():
    """Verify account balance derivation: Inflows minus Outflows."""
    async with AsyncSessionLocal() as session:
        # Setup tenant
        user = User(email="test_ledger@example.com", full_name="Ledger User", password_hash="hash")
        household = Household(name="Test Family")
        session.add_all([user, household])
        await session.commit()

        account = FinancialAccount(
            household_id=household.id,
            user_id=user.id,
            name="SBI Savings",
            account_type="savings",
            account_number_last4="5678",
        )
        session.add(account)
        await session.commit()

        # Inflow 1: ₹50,000 Salary
        tx1 = Transaction(
            household_id=household.id,
            account_id=account.id,
            user_id=user.id,
            amount=Decimal("50000.00"),
            direction="INFLOW",
            transaction_type="INCOME",
            description="Monthly Salary",
        )
        # Outflow 1: ₹150 Groceries
        tx2 = Transaction(
            household_id=household.id,
            account_id=account.id,
            user_id=user.id,
            amount=Decimal("150.00"),
            direction="OUTFLOW",
            transaction_type="EXPENSE",
            description="Groceries purchase",
        )
        session.add_all([tx1, tx2])
        await session.commit()

        # Derive balance via SQL aggregation
        txs = (
            (
                await session.execute(
                    select(Transaction).where(Transaction.account_id == account.id, Transaction.status == "POSTED")
                )
            )
            .scalars()
            .all()
        )

        inflows = sum(t.amount for t in txs if t.direction == "INFLOW")
        outflows = sum(t.amount for t in txs if t.direction == "OUTFLOW")
        derived_balance = inflows - outflows

        assert derived_balance == Decimal("49850.00")


@pytest.mark.asyncio
async def test_optimistic_locking_version():
    """Verify version column is present and can be queried for optimistic concurrency."""
    async with AsyncSessionLocal() as session:
        user = User(email="optimistic@example.com", full_name="User", password_hash="hash")
        household = Household(name="Family")
        session.add_all([user, household])
        await session.commit()

        account = FinancialAccount(
            household_id=household.id,
            user_id=user.id,
            name="Cash Wallet",
            account_type="cash",
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

        assert account.version == 1

        # Simulate update
        account.name = "Primary Cash Wallet"
        account.version += 1
        await session.commit()
        await session.refresh(account)

        assert account.version == 2
