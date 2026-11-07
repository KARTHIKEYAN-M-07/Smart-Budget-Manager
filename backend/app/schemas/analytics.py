"""Analytics and Reporting Schemas"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class CategorySpendItem(BaseModel):
    category_id: str | None
    category_name: str
    category_color: str | None
    total_amount: Decimal
    percentage: Decimal


class MemberSpendItem(BaseModel):
    user_id: str
    user_name: str
    total_amount: Decimal
    percentage: Decimal


class MonthlyTrendItem(BaseModel):
    month_name: str  # e.g. "Apr 2026"
    month_key: str  # e.g. "2026-04"
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal


class AnalyticsOverviewResponse(BaseModel):
    start_date: date
    end_date: date
    total_income: Decimal
    total_expense: Decimal
    total_refunds: Decimal
    net_savings: Decimal
    savings_rate: Decimal  # Percentage (e.g. 35.50%)
    categories: list[CategorySpendItem]
    members: list[MemberSpendItem]


class FinancialYearReportResponse(BaseModel):
    financial_year: str  # e.g. "FY 2026-27"
    start_date: date
    end_date: date
    total_income: Decimal
    total_expense: Decimal
    net_savings: Decimal
    monthly_trends: list[MonthlyTrendItem]
