"""
Abstract Base Component for Gemini communication and client adapters.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
import mimetypes
from gemini_ocr.config import DEFAULT_MODEL_NAME, GEMINI_API_KEY
from gemini_ocr.models import BatchOCRResult, OCRResultItem


@runtime_checkable
class GeminiClientProtocol(Protocol):
    """Protocol for Gemini API interaction enabling mock or real backends."""

    def call_ocr(self, files: list[str], prompt: str) -> list[dict[str, Any]]:
        """Process a batch of image files with the given prompt and return structured list of results."""
        ...


class MockGeminiClient:
    """
    Mock client simulating Gemini OCR responses for unit testing and offline development.
    Requires no API keys or internet connection.
    """

    def __init__(self, failure_count: int = 0) -> None:
        self.call_history: list[tuple[list[str], str]] = []
        self.failure_count: int = failure_count
        self.attempt_count: int = 0

    def call_ocr(self, files: list[str], prompt: str) -> list[dict[str, Any]]:
        self.attempt_count += 1
        self.call_history.append((files, prompt))

        if self.attempt_count <= self.failure_count:
            raise ConnectionError(f"Simulated transient network failure (attempt {self.attempt_count}/{self.failure_count})")

        results = []
        for idx, file_path in enumerate(files):
            p = Path(file_path)
            # Simulated realistic Myanmar + English extracted text
            simulated_text = (
                f"မြန်မာစာ OCR စမ်းသပ်မှု #{idx + 1}\n"
                f"File: {p.name}\n"
                f"Myanmar English Optical Character Recognition verified successfully."
            )
            results.append({
                "image_index": idx,
                "filename": p.name,
                "text": simulated_text,
                "language": "mixed",
                "confidence": 0.98,
            })
        return results


class RealGeminiClient:
    """
    Live Gemini client using the modern google-genai SDK with structured output enforcement.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> None:
        from google import genai
        from google.genai import types

        resolved_key = api_key or GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Gemini API key is required for RealGeminiClient. "
                "Provide it via constructor or set GEMINI_API_KEY in environment or .env file."
            )

        self.client = genai.Client(api_key=resolved_key)
        self.model_name = model_name
        self.types = types

    def _determine_mime_type(self, path: Path) -> str:
        mime, _ = mimetypes.guess_type(path.name)
        if mime:
            return mime
        suffix = path.suffix.lower()
        if suffix in (".jpg", ".jpeg", ".jpe"):
            return "image/jpeg"
        if suffix == ".png":
            return "image/png"
        if suffix == ".webp":
            return "image/webp"
        if suffix == ".bmp":
            return "image/bmp"
        return "application/octet-stream"

    def call_ocr(self, files: list[str], prompt: str) -> list[dict[str, Any]]:
        """Call live Gemini model with image parts and structured schema output."""
        contents: list[Any] = []

        # Add prompt first
        contents.append(prompt)

        # Upload or attach image bytes for each file in the batch
        for idx, file_path in enumerate(files):
            path = Path(file_path)
            if not path.is_file():
                raise FileNotFoundError(f"Image file not found: {file_path}")

            mime_type = self._determine_mime_type(path)
            image_bytes = path.read_bytes()

            # Pass metadata about which image corresponds to which index and filename
            contents.append(f"[Image {idx} - Filename: {path.name}]")
            contents.append(
                self.types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            )

        config = self.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BatchOCRResult,
            temperature=0.1,  # Low temperature for deterministic OCR precision
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        # Parse structured output from response text
        raw_text = response.text or "{}"
        batch_result = BatchOCRResult.model_validate_json(raw_text)
        return [item.model_dump() for item in batch_result.results]


class GeminiComponent(ABC):
    """
    Abstract base component defining standard Gemini communication interface
    as required in client system design.
    """

    @abstractmethod
    def init(self) -> None:
        """Initialize communication API or underlying client adapter."""
        pass

    @abstractmethod
    def set_content(self, content: str) -> None:
        """Set the prompt or instructions for Gemini."""
        pass

    @abstractmethod
    def set_file(self, file_list: list[str]) -> None:
        """Set the list of files to process."""
        pass

    @abstractmethod
    def operate(self) -> None:
        """Execute processing logic on configured files."""
        pass

    @abstractmethod
    def get_respond(self) -> Any:
        """Retrieve output response."""
        pass

