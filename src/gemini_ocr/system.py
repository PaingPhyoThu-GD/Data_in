"""
OCRSystem orchestrator coordinating FileImportComponent, GeminiMMENOCRComponent, and logging.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any, Sequence
from gemini_ocr.components.file_import import FileImportComponent
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent
from gemini_ocr.config import DEFAULT_LOG_DIR
from gemini_ocr.models import GeminiRespond

logger = logging.getLogger(__name__)


class OCRSystem:
    """
    Main orchestrator for the Gemini OCR system.

    Attributes:
        file_import_component (FileImportComponent): Component managing file input & validation.
        mmen_ocr_component (GeminiMMENOCRComponent): Component executing OCR operations.
        gemini_respond_list (list[GeminiRespond]): In-memory log of all GeminiRespond records.
        log_file_path (Path): Path to persistent JSON Lines log file.
    """

    def __init__(
        self,
        mmen_ocr_component: GeminiMMENOCRComponent | None = None,
        file_import_component: FileImportComponent | None = None,
        log_dir: str | Path = DEFAULT_LOG_DIR,
        log_filename: str = "gemini_ocr_log.jsonl",
    ) -> None:
        self.file_import_component: FileImportComponent = (
            file_import_component if file_import_component is not None else FileImportComponent()
        )
        self.mmen_ocr_component: GeminiMMENOCRComponent = (
            mmen_ocr_component if mmen_ocr_component is not None else GeminiMMENOCRComponent()
        )
        # Client design property: Geminirespondlist: ArrayList
        self.Geminirespondlist: list[GeminiRespond] = []
        self.gemini_respond_list: list[GeminiRespond] = self.Geminirespondlist

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file_path = self.log_dir / log_filename

    def write_log(self, gemini_respond: GeminiRespond) -> None:
        """Write GeminiRespond entry to the JSON Lines log file."""
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(gemini_respond.to_json() + "\n")
            logger.info(f"Appended OCR record to log: {self.log_file_path}")
        except Exception as exc:
            logger.error(f"Failed to write OCR log to {self.log_file_path}: {exc}")

    def operate(
        self,
        file_list: str | Path | Sequence[str | Path],
    ) -> GeminiRespond:
        """
        Execute OCR pipeline matching client pseudocode:
        1. file_import_component.setter(file_list)
        2. file_list = file_import_component.getter()
        3. mmen_ocr_component.set_file(file_list)
        4. mmen_ocr_component.operate()
        5. respond = mmen_ocr_component.get_respond()
        6. print(respond)
        7. gemini_respond = GeminiRespond(content, file_list, respond)
        8. Geminirespondlist.append(gemini_respond)
        9. write the gemini_respond to a gemini log file
        """
        # Step 1: accept files into FileImportComponent
        self.file_import_component.setter(file_list)

        # Step 2: retrieve validated file list
        imported_files = self.file_import_component.getter()

        # Step 3: set file list into OCR component
        self.mmen_ocr_component.set_file(imported_files)

        # Step 4: operate OCR batches
        self.mmen_ocr_component.operate()

        # Step 5: get respond
        respond = self.mmen_ocr_component.get_respond()

        # Step 6: print respond summary
        print(f"[OCRSystem] Completed recognition for {len(imported_files)} file(s).")
        for item in respond:
            fname = item.get("filename", "unknown")
            text_preview = item.get("text", "").replace("\n", " ")[:80]
            print(f"  -> File: {fname} | Text: {text_preview}...")

        # Step 7: construct GeminiRespond instance
        content = self.mmen_ocr_component.get_content()
        gemini_respond = GeminiRespond(
            content=content,
            files=imported_files,
            respond=respond,
        )

        # Step 8: append to in-memory list
        self.Geminirespondlist.append(gemini_respond)

        # Step 9: persist to log file
        self.write_log(gemini_respond)

        return gemini_respond


# Compatibility alias matching client diagram
ORCSystem = OCRSystem

