"""
Telemetry & Traffic Intelligence Engine (Module 6).
Multi-adapter ingestion, privacy sanitization, SQLite WAL storage, and analytical rollups.
"""

from .models import (
    BeaconPing,
    DeviceMetric,
    GeoMetric,
    ReferrerMetric,
    RouteMetric,
    StatusCodeDistribution,
    TelemetryDashboardPayload,
    TelemetryEvent,
    TelemetryKPISummary,
    TimeSeriesPoint,
    VercelSyncRequest,
)
from .sanitizer import (
    extract_referrer_domain,
    generate_visitor_hash,
    parse_user_agent,
    truncate_ip,
)
from .storage import TelemetryStorage
from .service import TelemetryConverter, TelemetryService
from .adapters import (
    BaseIngestor,
    BeaconIngestor,
    FileLogIngestor,
    LogDrainIngestor,
    VercelAPIIngestor,
)

__all__ = [
    "TelemetryEvent",
    "TelemetryKPISummary",
    "RouteMetric",
    "ReferrerMetric",
    "GeoMetric",
    "DeviceMetric",
    "StatusCodeDistribution",
    "TimeSeriesPoint",
    "TelemetryDashboardPayload",
    "VercelSyncRequest",
    "BeaconPing",
    "truncate_ip",
    "generate_visitor_hash",
    "extract_referrer_domain",
    "parse_user_agent",
    "TelemetryStorage",
    "TelemetryService",
    "TelemetryConverter",
    "BaseIngestor",
    "FileLogIngestor",
    "VercelAPIIngestor",
    "LogDrainIngestor",
    "BeaconIngestor",
]
