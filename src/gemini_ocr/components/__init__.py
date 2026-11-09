"""
Core modular components for File Import, Base Gemini Communication, and Myanmar-English OCR.
"""

from gemini_ocr.components.base_gemini import GeminiComponent, GeminiClientProtocol, MockGeminiClient
from gemini_ocr.components.file_import import FileImportComponent
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent

__all__ = [
    "GeminiComponent",
    "GeminiClientProtocol",
    "MockGeminiClient",
    "FileImportComponent",
    "GeminiMMENOCRComponent",
]

