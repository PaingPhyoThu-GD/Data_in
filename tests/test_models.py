"""
Unit tests for data models and GeminiRespond.
"""

from __future__ import annotations
import json
from gemini_ocr.models import GeminiRespond, GeminiResopnd, OCRResultItem, BatchOCRResult


def test_gemini_respond_initialization_and_serialization() -> None:
    content = "Extract Myanmar and English text"
    files = ["image1.png", "image2.jpg"]
    respond = [{"filename": "image1.png", "text": "မင်္ဂလာပါ"}]

    res = GeminiRespond(content=content, files=files, respond=respond)

    assert res.content == content
    assert res.files == files
    assert res.respond == respond
    assert res.date is not None

    # Test serialization
    data_dict = res.to_dict()
    assert data_dict["content"] == content
    assert data_dict["files"] == files
    assert data_dict["respond"] == respond

    json_str = res.to_json()
    loaded = json.loads(json_str)
    assert loaded["files"] == files
    assert loaded["respond"][0]["text"] == "မင်္ဂလာပါ"


def test_gemini_resopnd_alias_compatibility() -> None:
    # Verify backward-compatibility alias for client design
    assert GeminiResopnd is GeminiRespond
    res = GeminiResopnd("prompt", ["f1.png"], [])
    assert isinstance(res, GeminiRespond)


def test_pydantic_batch_ocr_result_schema() -> None:
    raw = {
        "results": [
            {
                "image_index": 0,
                "filename": "doc.png",
                "text": "Hello Myanmar မြန်မာ",
                "language": "mixed",
                "confidence": 0.99,
            }
        ]
    }
    batch = BatchOCRResult.model_validate(raw)
    assert len(batch.results) == 1
    assert batch.results[0].filename == "doc.png"
    assert batch.results[0].confidence == 0.99

