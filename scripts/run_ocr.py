"""
Command-line runner for Gemini OCR Backend System.
Supports both mock mode and live Gemini API execution.
"""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gemini_ocr.components.base_gemini import MockGeminiClient, RealGeminiClient
from gemini_ocr.components.file_import import FileImportComponent
from gemini_ocr.components.mmen_ocr import GeminiMMENOCRComponent
from gemini_ocr.system import OCRSystem
from gemini_ocr.config import GEMINI_API_KEY


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Gemini Myanmar-English OCR Backend.")
    parser.add_argument(
        "--input",
        type=str,
        default="sample_images",
        help="Input image file path or directory containing images.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Number of images per Gemini processing batch (default: 2).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force using MockGeminiClient (useful for testing without API keys).",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory where JSONL logs will be appended.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"[ERROR] Input path does not exist: {input_path}")
        sys.exit(1)

    # Setup client
    if args.mock:
        print("[MODE] Using MockGeminiClient (offline simulation mode).")
        client = MockGeminiClient()
    elif GEMINI_API_KEY:
        print("[MODE] Using RealGeminiClient with live Gemini API.")
        client = RealGeminiClient(api_key=GEMINI_API_KEY)
    else:
        print("[MODE] No GEMINI_API_KEY detected. Defaulting to MockGeminiClient.")
        client = MockGeminiClient()

    # Build modular components
    ocr_component = GeminiMMENOCRComponent(
        file_per_batch=args.batch_size,
        client=client,
    )
    import_component = FileImportComponent()

    # Build orchestrator system
    system = OCRSystem(
        mmen_ocr_component=ocr_component,
        file_import_component=import_component,
        log_dir=args.log_dir,
    )

    print(f"\n[START] Starting OCR operation on input: {input_path}")
    print(f"[CONFIG] Batch size: {args.batch_size} | Log path: {system.log_file_path}\n")

    result = system.operate(str(input_path))

    print("\n[COMPLETE] Operation finished successfully!")
    print(f"Processed files: {len(result.files)}")
    print(f"Total results: {len(result.respond) if isinstance(result.respond, list) else 1}")
    print(f"Log written to: {system.log_file_path.resolve()}")


if __name__ == "__main__":
    main()

