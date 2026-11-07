"""Category service and default Indian family taxonomy seeder"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category

DEFAULT_INDIAN_CATEGORIES: list[dict[str, str]] = [
    # Income
    {"name": "Salary & Wages", "type": "income", "icon": "briefcase", "color": "#16a34a"},
    {"name": "Business & Freelance", "type": "income", "icon": "trending-up", "color": "#22c55e"},
    {"name": "Rental Income", "type": "income", "icon": "home", "color": "#0ea5e9"},
    {"name": "Dividends & Capital Gains", "type": "income", "icon": "pie-chart", "color": "#6366f1"},
    {"name": "Interest Income (FD/Savings)", "type": "income", "icon": "percent", "color": "#8b5cf6"},
    {"name": "Cashback, Rewards & Gifts", "type": "income", "icon": "gift", "color": "#ec4899"},
    {"name": "Other Income", "type": "income", "icon": "plus-circle", "color": "#64748b"},
    # Expenses (Daily & Household)
    {"name": "Groceries & Supermarket", "type": "expense", "icon": "shopping-cart", "color": "#f97316"},
    {"name": "Vegetables & Fruits (Mandi)", "type": "expense", "icon": "apple", "color": "#84cc16"},
    {"name": "Milk & Dairy", "type": "expense", "icon": "coffee", "color": "#06b6d4"},
    {"name": "Dining Out & Food Delivery (Swiggy/Zomato)", "type": "expense", "icon": "utensils", "color": "#e11d48"},
    {"name": "Electricity Bill (TNEB/BESCOM/Discom)", "type": "expense", "icon": "zap", "color": "#eab308"},
    {"name": "Water & Piped Gas/LPG Cylinder", "type": "expense", "icon": "flame", "color": "#f59e0b"},
    {"name": "Mobile Recharge & Broadband WiFi", "type": "expense", "icon": "wifi", "color": "#3b82f6"},
    {"name": "House Rent & Society Maintenance", "type": "expense", "icon": "building", "color": "#7c3aed"},
    {"name": "Fuel (Petrol/Diesel/CNG)", "type": "expense", "icon": "fuel", "color": "#d97706"},
    {"name": "Public Transit & Cabs (Metro/Auto/Uber/Ola)", "type": "expense", "icon": "car", "color": "#ca8a04"},
    {"name": "School / College Fees & Education", "type": "expense", "icon": "book-open", "color": "#2563eb"},
    {"name": "Medicines & Pharmacy", "type": "expense", "icon": "pill", "color": "#dc2626"},
    {"name": "Doctor Consultation & Hospital", "type": "expense", "icon": "activity", "color": "#ef4444"},
    {"name": "Clothing & Apparel", "type": "expense", "icon": "shopping-bag", "color": "#a855f7"},
    {"name": "Domestic Help (Maid/Cook/Driver)", "type": "expense", "icon": "user-check", "color": "#14b8a6"},
    {"name": "Home Maintenance & Repairs", "type": "expense", "icon": "tool", "color": "#78716c"},
    {"name": "Loan EMI & Interest", "type": "expense", "icon": "credit-card", "color": "#b91c1c"},
    {"name": "Subscriptions (OTT/Apps)", "type": "expense", "icon": "tv", "color": "#9333ea"},
    {"name": "Religious, Festivals & Pooja", "type": "expense", "icon": "sun", "color": "#d946ef"},
    {"name": "Miscellaneous Expenses", "type": "expense", "icon": "more-horizontal", "color": "#94a3b8"},
    # Investments
    {"name": "Mutual Funds (SIP / Lumpsum)", "type": "investment", "icon": "line-chart", "color": "#0284c7"},
    {"name": "Direct Equities & Stocks", "type": "investment", "icon": "bar-chart-2", "color": "#4f46e5"},
    {"name": "Physical Gold & Silver (Jewellery/Coins)", "type": "investment", "icon": "award", "color": "#eab308"},
    {"name": "Fixed Deposit (FD)", "type": "investment", "icon": "lock", "color": "#059669"},
    {"name": "Recurring Deposit (RD)", "type": "investment", "icon": "calendar", "color": "#10b981"},
    {"name": "Public Provident Fund (PPF) / EPF", "type": "investment", "icon": "shield", "color": "#6366f1"},
    {"name": "Sovereign Gold Bonds (SGB)", "type": "investment", "icon": "gem", "color": "#f59e0b"},
    # Transfers
    {"name": "Internal Bank Transfer", "type": "transfer", "icon": "arrow-left-right", "color": "#64748b"},
    {"name": "ATM Cash Withdrawal", "type": "transfer", "icon": "dollar-sign", "color": "#0f766e"},
    {"name": "Cash Deposit", "type": "transfer", "icon": "upload", "color": "#047857"},
    {"name": "Credit Card Bill Settlement", "type": "transfer", "icon": "check-circle", "color": "#1d4ed8"},
]


async def seed_household_categories(db: AsyncSession, household_id: uuid.UUID) -> int:
    """
    Seeds standard Indian category taxonomy for a household.
    Idempotent: Skips categories that already exist with same name and type.
    """
    stmt = select(Category.name, Category.type).where(Category.household_id == household_id)
    existing_pairs = set((await db.execute(stmt)).all())

    new_categories = []
    for item in DEFAULT_INDIAN_CATEGORIES:
        if (item["name"], item["type"]) not in existing_pairs:
            cat = Category(
                household_id=household_id,
                name=item["name"],
                type=item["type"],
                icon=item.get("icon"),
                color=item.get("color"),
                is_system=True,
            )
            new_categories.append(cat)

    if new_categories:
        db.add_all(new_categories)
        await db.commit()

    return len(new_categories)
