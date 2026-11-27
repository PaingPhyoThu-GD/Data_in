"""
Multi-adapter implementations for Telemetry ingestion.
"""

from .base import BaseIngestor
from .file_adapter import FileLogIngestor
from .vercel_api_adapter import VercelAPIIngestor
from .drain_adapter import LogDrainIngestor
from .beacon_adapter import BeaconIngestor

__all__ = [
    "BaseIngestor",
    "FileLogIngestor",
    "VercelAPIIngestor",
    "LogDrainIngestor",
    "BeaconIngestor",
]
