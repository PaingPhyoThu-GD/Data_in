"""
Live Vercel Log Drain Webhook Ingestor (Pathway C).
Receives real-time streaming NDJSON edge logs and validates HMAC-SHA256 signatures.
"""

from __future__ import annotations
import hashlib
import hmac
from typing import Any, Optional

from ..models import TelemetryEvent
from .base import BaseIngestor
from .file_adapter import FileLogIngestor


class LogDrainIngestor(BaseIngestor):
    """
    Ingests live streaming HTTP POST payloads sent by Vercel Log Drains.
    Features optional HMAC signature verification and handshake ping handling.
    """

    def __init__(self, secret: Optional[str] = None) -> None:
        self.secret = secret
        self.file_parser = FileLogIngestor()

    def verify_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Validate HMAC-SHA256 signature from x-vercel-signature header.
        If no secret is configured, returns True.
        """
        if not self.secret:
            return True

        if not signature_header:
            return False

        expected = hmac.new(
            self.secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature_header.strip())

    def ingest(self, raw_data: Any, site_id: str = "vercel_drain") -> list[TelemetryEvent]:
        """
        Parse raw batch NDJSON or JSON payload from the webhook body.
        """
        events = self.file_parser.ingest(raw_data, site_id=site_id)
        for e in events:
            e.source_mode = "log_drain"
        return events
