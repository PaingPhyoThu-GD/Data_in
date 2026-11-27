"""
Domain models and Pydantic schemas for the Telemetry & Traffic Intelligence Engine.
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """Normalized individual telemetry/traffic event."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    site_id: str = "default"
    source_mode: str = "file_upload"  # "file_upload", "vercel_api", "log_drain", "beacon"
    timestamp: int  # Millisecond epoch UTC
    datetime_utc: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    visitor_hash: str = "anonymous"  # Daily salted HMAC-SHA256 (Zero PII)
    session_id: str = "session_default"  # 30-min windowed session ID
    path: str = "/"
    method: str = "GET"
    status_code: int = 200
    latency_ms: float = 0.0
    duration_seconds: float = 0.0  # Client dwell time
    referrer: str = ""
    referrer_domain: str = "direct"
    country_code: str = "UNKNOWN"
    city: str = ""
    browser: str = "Unknown"
    os: str = "Unknown"
    device_type: str = "desktop"  # "desktop", "mobile", "tablet", "bot"


class RouteMetric(BaseModel):
    """Aggregated metrics for a single path/route."""
    path: str
    pageviews: int = 0
    unique_visitors: int = 0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0  # percentage (0-100)


class ReferrerMetric(BaseModel):
    """Aggregated metrics for a traffic source domain."""
    referrer_domain: str
    visits: int = 0
    percentage: float = 0.0


class GeoMetric(BaseModel):
    """Country breakdown metric."""
    country_code: str
    visits: int = 0
    percentage: float = 0.0


class DeviceMetric(BaseModel):
    """Device/OS/Browser distribution item."""
    name: str
    count: int = 0
    percentage: float = 0.0


class StatusCodeDistribution(BaseModel):
    """HTTP status code classification."""
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0


class TimeSeriesPoint(BaseModel):
    """Time-bucketed aggregation for trend charts."""
    timestamp_bucket: str  # e.g. "2026-11-10 10:00"
    pageviews: int = 0
    visitors: int = 0
    avg_latency_ms: float = 0.0


class TelemetryKPISummary(BaseModel):
    """Top-level 4 KPI overview cards."""
    total_pageviews: int = 0
    unique_visitors: int = 0
    total_sessions: int = 0
    bounce_rate_pct: float = 0.0
    avg_duration_seconds: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate_pct: float = 0.0


class TelemetryDashboardPayload(BaseModel):
    """Full telemetry analysis payload consumed by UI and API."""
    status: str = "success"
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    site_id: str = "default"
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_name: str = "telemetry_logs"
    total_records: int = 0
    kpis: TelemetryKPISummary = Field(default_factory=TelemetryKPISummary)
    routes: list[RouteMetric] = Field(default_factory=list)
    referrers: list[ReferrerMetric] = Field(default_factory=list)
    geos: list[GeoMetric] = Field(default_factory=list)
    devices: list[DeviceMetric] = Field(default_factory=list)
    browsers: list[DeviceMetric] = Field(default_factory=list)
    operating_systems: list[DeviceMetric] = Field(default_factory=list)
    status_distribution: StatusCodeDistribution = Field(default_factory=StatusCodeDistribution)
    timeseries: list[TimeSeriesPoint] = Field(default_factory=list)
    recent_events: list[TelemetryEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class VercelSyncRequest(BaseModel):
    """Payload to trigger on-demand Vercel REST API sync."""
    project_id: str
    token: str
    team_id: Optional[str] = None
    since: Optional[str] = None
    until: Optional[str] = None


class BeaconPing(BaseModel):
    """Client-side beacon payload sent from telemetry.js."""
    site_id: Optional[str] = "default"
    p: str = "/"  # path
    r: Optional[str] = ""  # referrer
    d: Optional[float] = 0.0  # duration seconds
    ts: Optional[int] = None  # client timestamp
