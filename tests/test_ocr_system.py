"""
Integration tests for OCRSystem orchestrator.
"""

from __future__ import annotations
import json
from pathlib import Path
from gemini_ocr.components.base_gemini import MockGeminiClient
from gemini_ocr.components.file_import import FileImportComponent
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent
from gemini_ocr.system import OCRSystem, ORCSystem


def test_ocr_system_e2e_pipeline_and_logging(temp_image_dir: Path, tmp_path: Path) -> None:
    log_dir = tmp_path / "custom_logs"
    mock_client = MockGeminiClient()

    ocr_component = GeminiMMENOCRComponent(
        file_per_batch=2,
        client=mock_client,
    )
    import_component = FileImportComponent()

    system = OCRSystem(
        mmen_ocr_component=ocr_component,
        file_import_component=import_component,
        log_dir=log_dir,
    )

    # Execute system operate with directory containing 5 test images
    gemini_respond = system.operate(str(temp_image_dir))

    # 1. Check returned GeminiRespond
    assert gemini_respond is not None
    assert len(gemini_respond.files) == 5
    assert len(gemini_respond.respond) == 5

    # 2. Check in-memory list
    assert len(system.Geminirespondlist) == 1
    assert system.Geminirespondlist[0] is gemini_respond

    # 3. Check JSON Lines log file on disk
    log_file = system.log_file_path
    assert log_file.exists()

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1
    logged_record = json.loads(lines[0])
    assert logged_record["files"] == gemini_respond.files
    assert len(logged_record["respond"]) == 5


def test_orc_system_alias() -> None:
    # Verify exact naming from client system design
    assert ORCSystem is OCRSystem
    sys_instance = ORCSystem()
    assert hasattr(sys_instance, "file_import_component")
    assert hasattr(sys_instance, "mmen_ocr_component")
    assert hasattr(sys_instance, "Geminirespondlist")

