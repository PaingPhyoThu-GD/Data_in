"""
Unit tests for GeminiMMENOCRComponent.
"""

from __future__ import annotations
from pathlib import Path
from gemini_ocr.components.base_gemini import MockGeminiClient
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent


def test_mmen_ocr_init_and_content_accessors() -> None:
    custom_prompt = "Custom Myanmar text recognition prompt."
    ocr = GeminiMMENOCRComponent(
        file_per_batch=3,
        content=custom_prompt,
        client=MockGeminiClient(),
    )

    assert ocr.get_content() == custom_prompt
    assert ocr._file_per_batch == 3

    # Update content
    new_prompt = "Updated prompt"
    ocr.set_content(new_prompt)
    assert ocr.get_content() == new_prompt


def test_mmen_ocr_batching_and_operate(temp_image_dir: Path) -> None:
    mock_client = MockGeminiClient()
    # 5 files with batch size 2 -> 3 batches (2, 2, 1)
    ocr = GeminiMMENOCRComponent(
        file_per_batch=2,
        content="Transcribe Myanmar English",
        client=mock_client,
    )

    image_files = [str(temp_image_dir / f"test_img_{i}.png") for i in range(1, 6)]
    ocr.set_file(image_files)
    ocr.operate()

    # Client should have received 3 batches
    assert len(mock_client.call_history) == 3
    assert len(mock_client.call_history[0][0]) == 2
    assert len(mock_client.call_history[1][0]) == 2
    assert len(mock_client.call_history[2][0]) == 1

    # Responses should be flattened to 5 individual 1-to-1 results
    responses = ocr.get_respond()
    assert len(responses) == 5
    for i, resp in enumerate(responses):
        assert resp["filename"] == f"test_img_{i+1}.png"
        assert "မြန်မာစာ" in resp["text"]


def test_mmen_ocr_retry_on_transient_failure(temp_image_dir: Path) -> None:
    # Client that fails once with ConnectionError, then succeeds
    failing_client = MockGeminiClient(failure_count=1)
    ocr = GeminiMMENOCRComponent(
        file_per_batch=2,
        client=failing_client,
        max_retries=3,
        backoff_factor=1.1,
    )

    image_files = [str(temp_image_dir / "test_img_1.png")]
    ocr.set_file(image_files)
    ocr.operate()

    # Attempt count should be 2 (1 failure + 1 success)
    assert failing_client.attempt_count == 2
    results = ocr.get_respond()
    assert len(results) == 1
    assert "မြန်မာစာ" in results[0]["text"]


def test_mmen_ocr_set_respond_handles_enclosed_dict() -> None:
    ocr = GeminiMMENOCRComponent(client=MockGeminiClient())
    enclosed = {
        "results": [
            {"filename": "a.png", "text": "A"},
            {"filename": "b.png", "text": "B"},
        ]
    }
    ocr.set_respond(enclosed)
    assert len(ocr.get_respond()) == 2
    assert ocr.get_respond()[0]["filename"] == "a.png"
    assert ocr.get_respond()[1]["filename"] == "b.png"

