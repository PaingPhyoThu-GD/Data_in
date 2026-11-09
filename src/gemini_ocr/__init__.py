"""
Gemini Myanmar-English OCR Backend Package.
Modular component-based architecture for multi-image batch OCR processing.
"""

from gemini_ocr.models import GeminiRespond, OCRResultItem, BatchOCRResult
from gemini_ocr.components.base_gemini import GeminiComponent, GeminiClientProtocol, MockGeminiClient
from gemini_ocr.components.file_import import FileImportComponent
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent
from gemini_ocr.system import OCRSystem

# Retain client naming aliases for complete design diagram fidelity
ORCSystem = OCRSystem
GeminiResopnd = GeminiRespond

__all__ = [
    "GeminiRespond",
    "GeminiResopnd",
    "OCRResultItem",
    "BatchOCRResult",
    "GeminiComponent",
    "GeminiClientProtocol",
    "MockGeminiClient",
    "FileImportComponent",
    "GeminiMMENOCRComponent",
    "OCRSystem",
    "ORCSystem",
]

