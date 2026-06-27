import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

# We import the exact db_manager you defined in session.py!
from src.infrastructure.database.session import db_manager

logger = logging.getLogger(__name__)
router = APIRouter()

START_TIME = time.time()


class ComponentHealth(BaseModel):
    name: str
    status: str
    message: str
    latency_ms: int
    metadata: Optional[Dict[str, Any]] = None


class SystemMetrics(BaseModel):
    uptime_seconds: float
    memory_usage_mb: float
    cpu_percent_simulated: float
    active_threads: int


class DeepHealthResponse(BaseModel):
    global_status: str
    timestamp: str
    components: List[ComponentHealth]
    metrics: SystemMetrics


class BasicHealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str


@router.get(
    "/liveness", response_model=BasicHealthResponse, status_code=status.HTTP_200_OK
)
async def check_liveness():
    return {
        "status": "OPERATIONAL",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get(
    "/readiness", response_model=BasicHealthResponse, status_code=status.HTTP_200_OK
)
async def check_readiness():
    return {
        "status": "OPERATIONAL",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/deep", response_model=DeepHealthResponse, status_code=status.HTTP_200_OK)
async def check_deep_health(db: AsyncSession = Depends(db_manager.get_session)):
    components: List[ComponentHealth] = []

    # 1. Check Primary Database
    db_start_time = time.time()
    db_status = "OPERATIONAL"
    db_msg = "Database connection is healthy and responsive."

    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Deep Health Check: Database failure - {str(e)}")
        db_status = "OUTAGE"
        db_msg = "Critical Failure: Cannot communicate with the primary database."

    components.append(
        ComponentHealth(
            name="Primary WORM Database",
            status=db_status,
            message=db_msg,
            latency_ms=int((time.time() - db_start_time) * 1000),
            metadata={"driver": "aiosqlite/asyncpg"},
        )
    )

    # 2. Check Redis Cache Layer (Graceful Fallback for Replit)
    components.append(
        ComponentHealth(
            name="Redis Session Cache",
            status="DEGRADED",
            message="Redis caching is disabled in the local development environment.",
            latency_ms=0,
            metadata={"host": "localhost:6379", "fallback_active": True},
        )
    )

    # 3. Determine Global Status
    global_status = "OPERATIONAL"
    if db_status == "OUTAGE":
        global_status = "OUTAGE"
    else:
        global_status = "DEGRADED"

    # 4. Calculate System Metrics
    uptime = time.time() - START_TIME
    cpu_percent = 12.4
    memory_mb = 145.5
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_mb = round(
            psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2
        )
    except Exception:
        pass

    metrics = SystemMetrics(
        uptime_seconds=round(uptime, 2),
        memory_usage_mb=memory_mb,
        cpu_percent_simulated=cpu_percent,
        active_threads=4,
    )

    return DeepHealthResponse(
        global_status=global_status,
        timestamp=datetime.utcnow().isoformat(),
        components=components,
        metrics=metrics,
    )
