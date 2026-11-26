"""
Pydantic v2 data contracts for the DuckLake Medallion pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

ALLOWED_SOURCES: tuple[str, ...] = (
    "gemini_ocr",
    "telegram_parser",
    "database_parser",
    "youtube_parser",
    "survey_extractor",
    "telemetry",
)

ALLOWED_MARTS: tuple[str, ...] = (
    "gold_ingestion_overview",
    "gold_sales_kpi_mart",
    "gold_telegram_engagement_mart",
    "gold_web_traffic_mart",
)

QUARANTINE_ENTITIES: tuple[str, ...] = (
    "ocr_extractions",
    "telegram_messages",
    "sales_orders",
    "youtube_channels",
    "youtube_videos",
    "survey_runs",
    "telemetry_events",
)


class QualityStatus(str, Enum):
    PASSED = "PASSED"
    PASSED_WITH_QUARANTINE = "PASSED_WITH_QUARANTINE"
    BLOCKED = "BLOCKED"


class BronzeEnvelope(BaseModel):
    """Canonical wrapper around unmodified upstream payloads in Bronze."""

    ingest_id: str = Field(..., alias="_ingest_id")
    batch_id: str = Field(..., alias="_batch_id")
    ingested_at: str = Field(..., alias="_ingested_at")
    source_name: str = Field(..., alias="_source_name")
    source_origin_type: Literal["jsonl", "sqlite", "landing_json"] = Field(..., alias="_source_origin_type")
    source_file: str = Field(..., alias="_source_file")
    record_key: str = Field(..., alias="_record_key")
    payload_hash: str = Field(..., alias="_payload_hash")
    is_test_artifact: bool = Field(default=False, alias="_is_test_artifact")
    payload_json: str

    model_config = {"populate_by_name": True}


class SourceIngestSummary(BaseModel):
    """Per-source Bronze ingestion metrics for a single Ingestion Batch."""

    source_name: str
    scanned_count: int = 0
    ingested_count: int = 0
    skipped_unchanged_count: int = 0
    bronze_file: Optional[str] = None


class QualityCheckResult(BaseModel):
    """Result of a single Quality Gate entity evaluation."""

    entity: str
    rule_id: str = Field(..., alias="_rule_id")
    status: QualityStatus
    pre_commit_rows: int = 0
    valid_rows: int = 0
    quarantined_rows: int = 0
    message: str = ""

    model_config = {"populate_by_name": True}


class QualityGateResult(BaseModel):
    """Aggregated Quality Gate result across all evaluated entities."""

    overall_status: QualityStatus = QualityStatus.PASSED
    entity_statuses: dict[str, QualityStatus] = Field(default_factory=dict)
    checks: list[QualityCheckResult] = Field(default_factory=list)
    total_quarantined: int = 0


class LayerCounts(BaseModel):
    """Row counts across all four Medallion layers."""

    bronze_by_source: dict[str, int] = Field(default_factory=dict)
    silver_by_entity: dict[str, int] = Field(default_factory=dict)
    quarantine_by_entity: dict[str, int] = Field(default_factory=dict)
    gold_by_mart: dict[str, int] = Field(default_factory=dict)


class MartPointer(BaseModel):
    """Committed Gold Mart snapshot pointer inside latest_manifest.json."""

    mart_name: str
    batch_id: str
    parquet_path: str
    row_count: int = 0
    updated_at: str


class ManifestState(BaseModel):
    """Atomic commit state persisted in lakehouse/metadata/latest_manifest.json."""

    schema_version: int = 1
    latest_batch_id: Optional[str] = None
    latest_status: Optional[QualityStatus] = None
    updated_at: Optional[str] = None
    committed_bronze_batches: dict[str, list[str]] = Field(default_factory=dict)
    silver_versions: dict[str, str] = Field(default_factory=dict)
    quarantine_batches: dict[str, list[str]] = Field(default_factory=dict)
    marts: dict[str, MartPointer] = Field(default_factory=dict)
    layer_counts: LayerCounts = Field(default_factory=LayerCounts)


class BatchRunReport(BaseModel):
    """Full execution report returned by CLI/API and appended to runs_history.jsonl."""

    batch_id: str
    started_at: str
    completed_at: str
    full_refresh: bool = False
    overall_status: QualityStatus
    sources: list[SourceIngestSummary] = Field(default_factory=list)
    quality: QualityGateResult = Field(default_factory=QualityGateResult)
    layer_counts: LayerCounts = Field(default_factory=LayerCounts)
    exported_duckdb_path: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class RunBatchRequest(BaseModel):
    """Optional JSON request body for POST /api/lakehouse/run."""

    sources: Optional[list[str]] = None
    full_refresh: bool = False
    export_duckdb: Optional[bool] = None


class QuarantinePage(BaseModel):
    """Paginated response for GET /api/lakehouse/quarantine."""

    total: int = 0
    limit: int = 50
    offset: int = 0
    entities: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class MartPreviewResponse(BaseModel):
    """Paginated response for GET /api/lakehouse/marts/{mart_name}."""

    mart_name: str
    batch_id: Optional[str] = None
    total: int = 0
    limit: int = 50
    offset: int = 0
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
