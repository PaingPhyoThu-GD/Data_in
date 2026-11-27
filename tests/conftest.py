"""
Pytest configuration and shared fixtures.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pytest
from PIL import Image

# Ensure src is on Python search path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemini_ocr.components.base_gemini import MockGeminiClient


@pytest.fixture
def mock_client() -> MockGeminiClient:
    return MockGeminiClient()


@pytest.fixture
def temp_image_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with 5 dummy image files and 1 non-image file."""
    img_dir = tmp_path / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, 6):
        img = Image.new("RGB", (100, 100), color=(i * 40, i * 40, i * 40))
        img.save(img_dir / f"test_img_{i}.png")

    # Add a non-image file that should be ignored by FileImportComponent
    txt_file = img_dir / "notes.txt"
    txt_file.write_text("not an image", encoding="utf-8")

    return img_dir


@pytest.fixture(autouse=True)
def isolated_frontend_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate FastAPI log/upload/DB targets into tmp_path when frontend.app is loaded."""
    if "frontend.app" not in sys.modules:
        return

    import frontend.app as frontend_app
    from gemini_ocr import OCRSystem as RealOCRSystem
    from telemetry import TelemetryService

    tmp_logs = tmp_path / "logs"
    tmp_uploads = tmp_path / "uploads"
    tmp_logs.mkdir(parents=True, exist_ok=True)
    tmp_uploads.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(frontend_app, "DEFAULT_LOG_DIR", tmp_logs)
    monkeypatch.setattr(frontend_app, "UPLOADS_DIR", tmp_uploads)
    monkeypatch.setattr(frontend_app, "TELEGRAM_LOG_FILE", tmp_logs / "telegram_parser_log.jsonl")
    monkeypatch.setattr(frontend_app, "DATABASE_LOG_FILE", tmp_logs / "database_parser_log.jsonl")
    monkeypatch.setattr(frontend_app, "YOUTUBE_LOG_FILE", tmp_logs / "youtube_parser_log.jsonl")
    monkeypatch.setattr(frontend_app, "SURVEY_LOG_FILE", tmp_logs / "survey_extractor_log.jsonl")
    monkeypatch.setattr(frontend_app, "TELEMETRY_LOG_FILE", tmp_logs / "telemetry_parser_log.jsonl")

    tmp_telemetry_db = tmp_logs / "telemetry.db"
    monkeypatch.setattr(frontend_app, "TELEMETRY_DB_FILE", tmp_telemetry_db)
    monkeypatch.setattr(frontend_app, "telemetry_service", TelemetryService(db_path=tmp_telemetry_db))

    class IsolatedOCRSystem(RealOCRSystem):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("log_dir", tmp_logs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(frontend_app, "OCRSystem", IsolatedOCRSystem)

    from ducklake import LakehouseConfig, LakehouseService

    tmp_lh = tmp_path / "lakehouse"
    monkeypatch.setattr(
        frontend_app.app.state,
        "lakehouse_service",
        LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=tmp_logs, lakehouse_dir=tmp_lh)),
        raising=False,
    )


