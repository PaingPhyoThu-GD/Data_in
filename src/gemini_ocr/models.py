"""
Domain models and response structures for Gemini OCR.
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
from typing import Any, List
from pydantic import BaseModel, Field


class OCRResultItem(BaseModel):
    """Structured OCR result for a single image."""
    image_index: int = Field(default=0, description="0-based index of the image in the batch")
    filename: str = Field(..., description="File name or relative path of the image")
    text: str = Field(..., description="Extracted Myanmar and/or English text")
    language: str = Field(default="mixed", description="Detected language ('my', 'en', or 'mixed')")
    confidence: float = Field(default=1.0, description="Confidence score from 0.0 to 1.0")


class BatchOCRResult(BaseModel):
    """Enclosed response format expected from Gemini structured output."""
    results: List[OCRResultItem] = Field(default_factory=list, description="List of OCR results per image")


class GeminiRespond:
    """
    Representation of an OCR response record as requested in client system design.

    Attributes:
        content (str): The prompt or instruction text sent to Gemini.
        date (datetime): Timestamp when the response was generated.
        files (list[str]): List of file paths processed.
        respond (Any): Extracted OCR results (list of dicts, strings, or structured data).
    """

    def __init__(
        self,
        content: str,
        files: list[str],
        respond: Any,
        date: datetime | None = None,
    ) -> None:
        self.content: str = content
        self.files: list[str] = list(files) if files is not None else []
        self.respond: Any = respond
        self.date: datetime = date if date is not None else datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert response instance into a JSON-serializable dictionary."""
        return {
            "content": self.content,
            "date": self.date.isoformat(),
            "files": self.files,
            "respond": self.respond,
        }

    def to_json(self, indent: int | None = None) -> str:
        """Convert response instance into a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def __repr__(self) -> str:
        return (
            f"GeminiRespond(date={self.date.isoformat()}, "
            f"files_count={len(self.files)}, respond_count={len(self.respond) if isinstance(self.respond, list) else 1})"
        )


# Backward compatibility alias for client spelling
GeminiResopnd = GeminiRespond

