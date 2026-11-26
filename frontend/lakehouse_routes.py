"""
FastAPI router exposing DuckLake pipeline triggers, status, Quarantine, and Gold Mart previews.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ducklake import (
    ALLOWED_MARTS,
    ALLOWED_SOURCES,
    BatchRunReport,
    LakehouseLockError,
    LakehouseService,
    ManifestState,
)
from ducklake.models import MartPreviewResponse, QuarantinePage, RunBatchRequest

router = APIRouter(prefix="/api/lakehouse", tags=["lakehouse"])


def get_lakehouse_service(request: Request) -> LakehouseService:
    svc = getattr(request.app.state, "lakehouse_service", None)
    if svc is None:
        svc = LakehouseService()
        request.app.state.lakehouse_service = svc
    return svc


@router.post("/run", response_model=BatchRunReport)
async def trigger_lakehouse_batch(
    payload: Optional[RunBatchRequest] = Body(default=None),
    service: LakehouseService = Depends(get_lakehouse_service),
) -> BatchRunReport:
    req = payload or RunBatchRequest()
    if req.sources is not None:
        invalid = [s for s in req.sources if s not in ALLOWED_SOURCES]
        if invalid:
            raise HTTPException(status_code=422, detail=f"Unknown source(s): {invalid}")

    try:
        return await asyncio.to_thread(
            service.run_batch,
            sources=req.sources,
            full_refresh=req.full_refresh,
            export_duckdb=req.export_duckdb,
        )
    except LakehouseLockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/status", response_model=ManifestState)
async def get_lakehouse_status(
    service: LakehouseService = Depends(get_lakehouse_service),
) -> ManifestState:
    return await asyncio.to_thread(service.get_status)


@router.get("/runs", response_model=list[BatchRunReport])
async def get_lakehouse_runs(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: LakehouseService = Depends(get_lakehouse_service),
) -> list[BatchRunReport]:
    return await asyncio.to_thread(service.list_runs, limit=limit, offset=offset)


@router.get("/quarantine", response_model=QuarantinePage)
async def get_lakehouse_quarantine(
    entity: Optional[str] = Query(default=None),
    batch_id: Optional[str] = Query(default=None, pattern=r"^[a-f0-9_-]+$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: LakehouseService = Depends(get_lakehouse_service),
) -> QuarantinePage:
    try:
        return await asyncio.to_thread(
            service.get_quarantine,
            entity=entity,
            batch_id=batch_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/marts/{mart_name}", response_model=MartPreviewResponse)
async def get_lakehouse_mart(
    mart_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: LakehouseService = Depends(get_lakehouse_service),
) -> MartPreviewResponse:
    if mart_name not in ALLOWED_MARTS:
        raise HTTPException(status_code=404, detail=f"Unknown Gold Mart: {mart_name!r}")
    return await asyncio.to_thread(service.get_mart_preview, mart_name=mart_name, limit=limit, offset=offset)
