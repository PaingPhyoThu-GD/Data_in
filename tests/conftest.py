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

