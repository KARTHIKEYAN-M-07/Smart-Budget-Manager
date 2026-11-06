"""Aggregated API v1 Router"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router

api_v1_router = APIRouter()

# Register v1 routes
api_v1_router.include_router(health_router, prefix="")
