"""
Gemini Myanmar-English OCR Component with batch processing and structured output handling.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Optional
from gemini_ocr.components.base_gemini import (
    GeminiComponent,
    GeminiClientProtocol,
    MockGeminiClient,
    RealGeminiClient,
)
from gemini_ocr.config import DEFAULT_BATCH_SIZE, DEFAULT_OCR_PROMPT, GEMINI_API_KEY

logger = logging.getLogger(__name__)


class GeminiMMENOCRComponent(GeminiComponent):
    """
    Component specializing in Myanmar and English OCR using Gemini with batching capabilities.

    Attributes:
        _file_per_batch (int): Number of images processed in a single Gemini request batch.
        _content (str): Well-defined OCR prompt instructions.
        _file_list (list[str]): List of image file paths queued for OCR.
        _respond_list (list[dict]): Accumulated structured responses (one record per image).
        _client (GeminiClientProtocol): Client implementation (Real or Mock).
    """

    def __init__(
        self,
        file_per_batch: int = DEFAULT_BATCH_SIZE,
        content: str | None = None,
        client: Optional[GeminiClientProtocol] = None,
        max_retries: int = 4,
        backoff_factor: float = 2.0,
    ) -> None:
        self._file_per_batch: int = max(1, file_per_batch)
        self._content: str = ""
        self._file_list: list[str] = []
        self._respond_list: list[dict[str, Any]] = []
        self._client: Optional[GeminiClientProtocol] = client
        self._max_retries: int = max_retries
        self._backoff_factor: float = backoff_factor

        self.set_content(content or DEFAULT_OCR_PROMPT)
        self.init()

    def init(self) -> None:
        """Initialize communication client if not already provided."""
        if self._client is not None:
            return

        if GEMINI_API_KEY:
            try:
                self._client = RealGeminiClient(api_key=GEMINI_API_KEY)
                logger.info("GeminiMMENOCRComponent: Initialized with RealGeminiClient.")
            except Exception as exc:
                logger.warning(
                    f"GeminiMMENOCRComponent: Failed to initialize RealGeminiClient ({exc}). "
                    f"Falling back to MockGeminiClient for offline operation."
                )
                self._client = MockGeminiClient()
        else:
            logger.info("GeminiMMENOCRComponent: No GEMINI_API_KEY found; initialized with MockGeminiClient.")
            self._client = MockGeminiClient()

    def set_content(self, content: str) -> None:
        """Set a well-defined prompt instruction related to Myanmar-English OCR."""
        if not content or not content.strip():
            self._content = DEFAULT_OCR_PROMPT
        else:
            self._content = content.strip()

    def get_content(self) -> str:
        """Return the current OCR prompt instruction."""
        return self._content

    def set_file(self, file_list: list[str]) -> None:
        """Set image file paths for recognition."""
        self._file_list = list(file_list) if file_list is not None else []

    def _execute_batch_with_retry(self, batch_files: list[str]) -> list[dict[str, Any]]:
        """Execute a single batch with exponential backoff on transient errors."""
        if self._client is None:
            self.init()
            assert self._client is not None

        attempt = 0
        current_delay = 2.0

        while attempt < self._max_retries:
            attempt += 1
            try:
                return self._client.call_ocr(files=batch_files, prompt=self._content)
            except Exception as exc:
                is_transient = (
                    "429" in str(exc)
                    or "503" in str(exc)
                    or "unavailable" in str(exc).lower()
                    or "ResourceExhausted" in type(exc).__name__
                    or isinstance(exc, (ConnectionError, TimeoutError))
                    or "quota" in str(exc).lower()
                )
                if is_transient and attempt < self._max_retries:
                    logger.warning(
                        f"Transient error on batch {batch_files}: {exc}. "
                        f"Retrying in {current_delay:.1f}s (attempt {attempt}/{self._max_retries})..."
                    )
                    time.sleep(current_delay)
                    current_delay *= self._backoff_factor
                else:
                    logger.error(f"Batch execution failed on {batch_files}: {exc}")
                    # Construct error response records per image to avoid complete pipeline crash
                    return [
                        {
                            "image_index": i,
                            "filename": f,
                            "text": "",
                            "language": "unknown",
                            "confidence": 0.0,
                            "error": str(exc),
                        }
                        for i, f in enumerate(batch_files)
                    ]
        return []

    def set_respond(self, batch_respond: list[dict[str, Any]] | dict[str, Any]) -> None:
        """
        Divide and normalize a batch response into 1-to-1 mappings (one record per image)
        and append to private _respond_list.
        """
        if isinstance(batch_respond, dict):
            # Enclosed format e.g. {"results": [...]}
            items = batch_respond.get("results", [batch_respond])
        elif isinstance(batch_respond, list):
            items = batch_respond
        else:
            items = [{"raw_response": str(batch_respond)}]

        for item in items:
            self._respond_list.append(item)

    def operate(self) -> None:
        """
        Process all queued files in batches:
        1. Initialize connection if not done.
        2. Divide _file_list by _file_per_batch.
        3. Retrieve response for each batch.
        4. Append each item to private _respond_list using set_respond().
        """
        if not self._file_list:
            logger.info("GeminiMMENOCRComponent.operate(): No files queued.")
            return

        # Reset respond list for fresh operation
        self._respond_list = []

        total_files = len(self._file_list)
        batch_size = self._file_per_batch

        for i in range(0, total_files, batch_size):
            batch_files = self._file_list[i : i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1}: {len(batch_files)} image(s)")

            batch_result = self._execute_batch_with_retry(batch_files)
            self.set_respond(batch_result)

    def get_respond(self) -> list[dict[str, Any]]:
        """Return the accumulated response list."""
        return list(self._respond_list)

