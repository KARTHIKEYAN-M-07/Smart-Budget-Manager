"""Health check API endpoints"""

import zoneinfo
from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import check_database_health

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    database: str
    environment: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Status",
)
async def get_health(response: Response) -> HealthResponse:
    """
    Returns application health and database connection status.
    If the database is unreachable, HTTP 503 is returned.
    No credentials or stack traces are ever exposed in this response.
    """
    db_connected = await check_database_health()

    tz = zoneinfo.ZoneInfo(settings.DEFAULT_TIMEZONE)
    current_time = datetime.now(tz).isoformat()

    if not db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="unhealthy",
            version=settings.APP_VERSION,
            timestamp=current_time,
            database="disconnected",
            environment=settings.ENVIRONMENT,
        )

    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        timestamp=current_time,
        database="connected",
        environment=settings.ENVIRONMENT,
    )
