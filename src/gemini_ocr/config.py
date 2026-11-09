"""
Configuration settings for Gemini OCR System.
"""

from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically load environment variables from .env if present
load_dotenv()

DEFAULT_MODEL_NAME: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
DEFAULT_BATCH_SIZE: int = int(os.getenv("DEFAULT_BATCH_SIZE", "2"))
DEFAULT_LOG_DIR: Path = Path(os.getenv("LOG_DIR", "logs"))
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

DEFAULT_OCR_PROMPT: str = (
    "You are an expert OCR transcription engine specializing in Myanmar (Burmese) and English texts. "
    "Transcribe all text from each provided image with extreme fidelity, preserving sentence structure, "
    "line breaks, punctuation, numbers, and spelling in both Myanmar and English. "
    "Return the transcription per image in the required structured JSON format."
)

