"""
First-Party Cookieless Client Beacon Ingestor (Pathway D).
Receives ping events sent via navigator.sendBeacon from telemetry.js.
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Optional

from ..models import BeaconPing, TelemetryEvent
from ..sanitizer import (
    extract_referrer_domain,
    generate_visitor_hash,
    parse_user_agent,
)
from .base import BaseIngestor


class BeaconIngestor(BaseIngestor):
    """
    Decodes lightweight telemetry beacon pings sent from client-side browsers.
    """

    def ingest(
        self,
        raw_data: Any,
        site_id: str = "default",
        client_ip: str = "127.0.0.1",
        user_agent: str = "Mozilla/5.0",
    ) -> list[TelemetryEvent]:
        """
        Ingest single beacon ping or list of pings.
        """
        if isinstance(raw_data, BeaconPing):
            ping_dict = raw_data.model_dump()
        elif isinstance(raw_data, dict):
            ping_dict = raw_data
        else:
            return []

        path = ping_dict.get("p") or "/"
        referrer = ping_dict.get("r") or ""
        duration = float(ping_dict.get("d") or 0.0)
        ts_ms = ping_dict.get("ts") or int(datetime.utcnow().timestamp() * 1000)

        date_str = datetime.utcfromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d")
        visitor_hash = generate_visitor_hash(client_ip, user_agent, site_id=site_id, date_str=date_str)
        browser, os_name, dev_type = parse_user_agent(user_agent)
        session_id = f"s_{visitor_hash}_{ts_ms // (30 * 60 * 1000)}"

        event = TelemetryEvent(
            id=str(uuid.uuid4()),
            site_id=ping_dict.get("site_id") or site_id,
            source_mode="beacon",
            timestamp=ts_ms,
            datetime_utc=datetime.utcfromtimestamp(ts_ms / 1000.0).isoformat() + "Z",
            visitor_hash=visitor_hash,
            session_id=session_id,
            path=path,
            method="GET",
            status_code=200,
            latency_ms=12.0,  # lightweight client hit
            duration_seconds=duration,
            referrer=referrer,
            referrer_domain=extract_referrer_domain(referrer),
            country_code="LOCAL",
            browser=browser,
            os=os_name,
            device_type=dev_type,
        )

        return [event]
