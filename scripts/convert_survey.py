"""
CLI Runner: Extract Google Forms CSV exports into structured JSON (Pure In-Memory Extraction).
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from survey_extractor import GoogleFormsCSVParser


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Google Forms CSV export directly into structured JSON."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="sample_surveys/google_forms_sample.csv",
        help="Path to Google Forms CSV export file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for output JSON file (default: <filename>.json in same folder).",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Optional custom survey title.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[ERROR] Input file does not exist: {input_path}")
        sys.exit(1)

    print("\n=======================================================")
    print("  Google Forms Survey Data to JSON Extractor")
    print(f"  Input: {input_path}")
    print("=======================================================\n")

    parser_engine = GoogleFormsCSVParser()
    result = parser_engine.parse_file(
        file_path=input_path,
        survey_title=args.title,
    )

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}.json")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=args.indent)

    print("[SUCCESS] Survey extraction completed!")
    print(f"  Survey ID:        {result.survey_id}")
    print(f"  Title:            {result.metadata.title}")
    print(f"  Total Questions:  {result.metadata.total_questions}")
    print(f"  Total Responses:  {result.metadata.total_responses}")
    print(f"  Valid / Invalid:  {result.metadata.valid_responses} / {result.metadata.invalid_responses}")
    print(f"  Output JSON:      {output_path.resolve()}\n")

    print("Detected Questions:")
    for q in result.questions:
        opt_info = f" ({len(q.detected_options)} options detected)" if q.detected_options else ""
        print(f"  - [{q.field_type.value.upper()}] {q.question_text}{opt_info}")


if __name__ == "__main__":
    main()
