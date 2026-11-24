"""Production-oriented HTTP API for OceanIQ.

This module exposes a lightweight FastAPI application that preserves the current
service boundaries:
- the frontend talks to this API over HTTP,
- the API invokes the validated backend services,
- the backend still uses DuckDB and Chroma as the source of truth.

The server is intentionally read-only and keeps the database, vector index, and
retrieval logic in the existing service layer instead of duplicating them here.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from services.orchestration_service import OrchestrationService
from services.profile_explorer_service import get_profile_explorer_service

app = FastAPI(
    title="OceanIQ API",
    version="1.0.0",
    description="Read-only HTTP API for OceanIQ retrieval, profile exploration and startup health checks.",
)

_allowed_origins = []
for origin in (os.getenv("CORS_ALLOW_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(","):
    candidate = origin.strip()
    if candidate:
        _allowed_origins.append(candidate)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestration_service = OrchestrationService()
profile_service = get_profile_explorer_service()


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness endpoint for local or hosted deployment checks."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "backend_host": settings.backend_host,
        "backend_port": settings.backend_port,
        "version": "1.0.0",
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    """Readiness endpoint returning dataset and runtime health information."""
    report = settings.validate_runtime(require_dataset=True)
    if report["status"] != "ok":
        raise HTTPException(status_code=503, detail={"status": "not_ready", "issues": report["issues"]})
    return {"status": "ready", "checks": report["checks"], "environment": settings.environment}


@app.post("/api/query")
def execute_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute the natural-language orchestration flow and return the existing structured response."""
    question = payload.get("question") if isinstance(payload, dict) else None
    if not isinstance(question, str) or not question.strip():
        raise HTTPException(status_code=400, detail="A non-empty 'question' field is required.")
    result = orchestration_service.execute(question)
    return result.model_dump(mode="json")


@app.get("/api/data/summary")
def get_summary() -> dict[str, Any]:
    return profile_service.get_summary()


@app.get("/api/data/profiles")
def list_profiles(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = None,
    parameter: str | None = None,
    region: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
) -> dict[str, Any]:
    return profile_service.list_profiles(
        limit=limit,
        offset=offset,
        search=search,
        parameter=parameter,
        region=region,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )


@app.get("/api/data/map")
def map_profiles(
    limit: int = Query(default=1000, ge=1, le=2000),
    search: str | None = None,
    parameter: str | None = None,
    region: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    latitude_min: float | None = None,
    latitude_max: float | None = None,
    longitude_min: float | None = None,
    longitude_max: float | None = None,
) -> dict[str, Any]:
    return profile_service.map_profiles(
        limit=limit,
        search=search,
        parameter=parameter,
        region=region,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        latitude_min=latitude_min,
        latitude_max=latitude_max,
        longitude_min=longitude_min,
        longitude_max=longitude_max,
    )


@app.get("/api/data/profile")
def profile_details(
    file_name: str = Query(...),
    profile_number: int = Query(..., ge=1),
    limit: int = Query(default=3000, ge=1, le=10000),
) -> dict[str, Any]:
    result = profile_service.get_profile(file_name=file_name, profile_number=profile_number, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Profile was not found.")
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
        log_level="info",
    )
