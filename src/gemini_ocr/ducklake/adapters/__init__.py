"""
Registry of DuckLake upstream SourceAdapters.
"""

from __future__ import annotations

from .base import SourceAdapter
from .database import DatabaseAdapter
from .gemini_ocr import GeminiOCRAdapter
from .survey import SurveyAdapter
from .telegram import TelegramAdapter
from .telemetry import TelemetryAdapter
from .youtube import YouTubeAdapter

ADAPTERS: dict[str, SourceAdapter] = {
    "gemini_ocr": GeminiOCRAdapter(),
    "telegram_parser": TelegramAdapter(),
    "database_parser": DatabaseAdapter(),
    "youtube_parser": YouTubeAdapter(),
    "survey_extractor": SurveyAdapter(),
    "telemetry": TelemetryAdapter(),
}


def get_adapter(name: str) -> SourceAdapter:
    """Return a registered SourceAdapter by canonical source name."""
    if name not in ADAPTERS:
        raise ValueError(f"Unknown source adapter: {name!r}")
    return ADAPTERS[name]


def get_all_adapters() -> list[SourceAdapter]:
    """Return all registered SourceAdapters in canonical order."""
    return list(ADAPTERS.values())
