"""
Base protocol for telemetry ingestors.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from ..models import TelemetryEvent


class BaseIngestor(ABC):
    """Abstract interface that all telemetry source adapters must implement."""

    @abstractmethod
    def ingest(self, raw_data: Any, site_id: str = "default") -> list[TelemetryEvent]:
        """
        Ingest raw input, sanitize PII, and return a normalized list of TelemetryEvents.
        """
        pass
