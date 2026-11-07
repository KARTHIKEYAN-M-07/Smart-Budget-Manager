"""Aggregated API v1 Router"""

from fastapi import APIRouter

from app.api.v1.accounts import router as accounts_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.bills import router as bills_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.categories import router as categories_router
from app.api.v1.health import router as health_router
from app.api.v1.household import router as household_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.investments import router as investments_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.orders import router as orders_router
from app.api.v1.precious_metals import router as metals_router
from app.api.v1.statement_import import router as statement_import_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.transfers import router as transfers_router

api_v1_router = APIRouter()

# Register v1 routes
api_v1_router.include_router(health_router, prefix="")
api_v1_router.include_router(auth_router, prefix="")
api_v1_router.include_router(accounts_router, prefix="")
api_v1_router.include_router(categories_router, prefix="")
api_v1_router.include_router(transactions_router, prefix="")
api_v1_router.include_router(transfers_router, prefix="")
api_v1_router.include_router(analytics_router, prefix="")
api_v1_router.include_router(statement_import_router, prefix="")
api_v1_router.include_router(budgets_router, prefix="")
api_v1_router.include_router(bills_router, prefix="")
api_v1_router.include_router(orders_router, prefix="")
api_v1_router.include_router(metals_router, prefix="")
api_v1_router.include_router(investments_router, prefix="")
api_v1_router.include_router(notifications_router, prefix="")
api_v1_router.include_router(integrations_router, prefix="")
api_v1_router.include_router(household_router, prefix="")
