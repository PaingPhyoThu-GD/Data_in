"""
Vercel Cloud REST API Adapter (Pathway A).
Queries Vercel Web Analytics endpoints programmatically using Bearer Token authentication.
"""

from __future__ import annotations
import json
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Any, Optional

from ..models import TelemetryEvent, VercelSyncRequest
from .base import BaseIngestor


class VercelAPIIngestor(BaseIngestor):
    """
    Connects to Vercel Web Analytics Cloud REST API to fetch visits and aggregate metrics.
    Uses Python standard library urllib to avoid extra dependencies.
    """

    BASE_URL = "https://api.vercel.com/v1/query/web-analytics"

    def __init__(self, token: Optional[str] = None, project_id: Optional[str] = None) -> None:
        self.token = token
        self.project_id = project_id

    def ingest(self, raw_data: Any, site_id: str = "default") -> list[TelemetryEvent]:
        """
        Accepts VercelSyncRequest or raw response dictionary.
        """
        if isinstance(raw_data, VercelSyncRequest):
            return self.fetch_analytics(raw_data)
        elif isinstance(raw_data, dict):
            return self._parse_vercel_aggregate_payload(raw_data, site_id)
        return []

    def fetch_analytics(self, req: VercelSyncRequest) -> list[TelemetryEvent]:
        """
        Query Vercel Web Analytics aggregate endpoint for request paths and countries.
        """
        token = req.token or self.token
        if not token:
            raise ValueError("Vercel API Bearer token is required.")

        params = {
            "projectId": req.project_id or self.project_id,
            "by": "requestPath",
        }
        if req.team_id:
            params["teamId"] = req.team_id
        if req.since:
            params["since"] = req.since
        if req.until:
            params["until"] = req.until

        query_str = urllib.parse.urlencode(params)
        url = f"{self.BASE_URL}/visits/aggregate?{query_str}"

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "Gemini-OCR-Telemetry/1.0",
        }

        request = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return self._parse_vercel_aggregate_payload(data, site_id=req.project_id)
        except Exception as exc:
            # If network error or unauthorized, raise clear message
            raise RuntimeError(f"Vercel API request failed: {exc}")

    def _parse_vercel_aggregate_payload(self, data: dict[str, Any], site_id: str) -> list[TelemetryEvent]:
        """
        Convert Vercel aggregate response into synthetic TelemetryEvents for uniform storage.
        """
        events: list[TelemetryEvent] = []
        rows = data.get("data") or data.get("rows") or []
        now_ms = int(datetime.utcnow().timestamp() * 1000)

        for item in rows:
            path = item.get("requestPath") or item.get("path") or "/"
            pageviews = int(item.get("pageviews") or item.get("views") or 1)
            visitors = int(item.get("visitors") or 1)

            # Create representative events for the aggregate count
            for i in range(min(pageviews, 50)):  # capped to avoid flood
                v_hash = f"vh_vercel_{path.replace('/', '_')}_{i % visitors}"
                events.append(
                    TelemetryEvent(
                        id=str(uuid.uuid4()),
                        site_id=site_id,
                        source_mode="vercel_api",
                        timestamp=now_ms - (i * 60_000),
                        datetime_utc=datetime.utcnow().isoformat() + "Z",
                        visitor_hash=v_hash,
                        session_id=f"s_{v_hash}",
                        path=path,
                        method="GET",
                        status_code=200,
                        latency_ms=45.0,
                        referrer_domain="vercel_cloud",
                        device_type="desktop",
                    )
                )

        return events
