"""
High-level Telemetry Service and CLI Converter orchestrating Ingestors,
Privacy Sanitization, and SQLite WAL Storage.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Optional, Union

from .adapters import (
    BeaconIngestor,
    FileLogIngestor,
    LogDrainIngestor,
    VercelAPIIngestor,
)
from .models import (
    BeaconPing,
    TelemetryDashboardPayload,
    TelemetryEvent,
    VercelSyncRequest,
)
from .storage import TelemetryStorage


class TelemetryService:
    """
    Unified coordinator managing multi-adapter telemetry ingestion and analytics rollups.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.storage = TelemetryStorage(db_path=db_path)
        self.file_ingestor = FileLogIngestor()
        self.vercel_ingestor = VercelAPIIngestor()
        self.drain_ingestor = LogDrainIngestor()
        self.beacon_ingestor = BeaconIngestor()

    def ingest_file(
        self,
        raw_data: Union[str, bytes, Path],
        site_id: str = "default",
    ) -> TelemetryDashboardPayload:
        """
        Pathway B: Ingest NDJSON, CSV, or JSON logs and return updated dashboard analytics.
        """
        events = self.file_ingestor.ingest(raw_data, site_id=site_id)
        if events:
            self.storage.insert_events(events)

        payload = self.storage.get_dashboard_stats(site_id=site_id)
        payload.source_name = (
            Path(raw_data).name if isinstance(raw_data, (Path, str)) and len(str(raw_data)) < 260 and Path(raw_data).exists()
            else "uploaded_log"
        )
        return payload

    def ingest_vercel_api(self, req: VercelSyncRequest) -> TelemetryDashboardPayload:
        """
        Pathway A: Sync live web analytics directly from Vercel Cloud REST API.
        """
        events = self.vercel_ingestor.ingest(req, site_id=req.project_id)
        if events:
            self.storage.insert_events(events)

        payload = self.storage.get_dashboard_stats(site_id=req.project_id)
        payload.source_name = f"vercel_api ({req.project_id})"
        return payload

    def ingest_drain(
        self,
        raw_body: bytes,
        signature: Optional[str] = None,
        site_id: str = "vercel_drain",
    ) -> TelemetryDashboardPayload:
        """
        Pathway C: Ingest live streaming batch from Vercel Log Drain webhook.
        """
        if not self.drain_ingestor.verify_signature(raw_body, signature):
            raise PermissionError("Invalid x-vercel-signature HMAC.")

        events = self.drain_ingestor.ingest(raw_body, site_id=site_id)
        if events:
            self.storage.insert_events(events)

        payload = self.storage.get_dashboard_stats(site_id=site_id)
        payload.source_name = "vercel_log_drain"
        return payload

    def ingest_beacon(
        self,
        ping: BeaconPing,
        client_ip: str = "127.0.0.1",
        user_agent: str = "Mozilla/5.0",
    ) -> TelemetryEvent:
        """
        Pathway D: Ingest single ping from client-side telemetry.js script.
        """
        events = self.beacon_ingestor.ingest(
            ping,
            site_id=ping.site_id or "default",
            client_ip=client_ip,
            user_agent=user_agent,
        )
        if events:
            self.storage.insert_events(events)
            return events[0]
        raise ValueError("Failed to create beacon event.")

    def get_dashboard(
        self,
        site_id: Optional[str] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit_events: int = 150,
    ) -> TelemetryDashboardPayload:
        """
        Retrieve cached or persisted analytical summary.
        """
        return self.storage.get_dashboard_stats(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            limit_events=limit_events,
        )


class TelemetryConverter:
    """
    CLI & Automation wrapper for converting log files to structured JSON analytics.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.service = TelemetryService(db_path=db_path)

    def convert_file(
        self,
        input_file: str | Path,
        output_file: Optional[str | Path] = None,
        site_id: str = "default",
        indent: int = 2,
    ) -> TelemetryDashboardPayload:
        """
        Process an NDJSON/CSV log file and write the complete analytical summary to JSON.
        """
        in_path = Path(input_file).resolve()
        if not in_path.exists():
            raise FileNotFoundError(f"Input file not found: {in_path}")

        payload = self.service.ingest_file(in_path, site_id=site_id)

        if output_file:
            out_path = Path(output_file).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(payload.model_dump(), f, ensure_ascii=False, indent=indent)

        return payload
