"""
Standalone CLI tool to parse and convert Telemetry logs (NDJSON / CSV) into structured JSON.
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# Add src to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from telemetry import TelemetryConverter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest and analyze Vercel NDJSON/CSV telemetry logs into structured JSON."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input log file (.ndjson, .csv, .json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Optional path to output JSON file (defaults to stdout if omitted)",
    )
    parser.add_argument(
        "--site-id", "-s",
        default="default",
        help="Site or Project ID tag (defaults to 'default')",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation (default: 2)",
    )

    args = parser.parse_args()

    converter = TelemetryConverter()
    payload = converter.convert_file(
        input_file=args.input,
        output_file=args.output,
        site_id=args.site_id,
        indent=args.indent,
    )

    if not args.output:
        print(json.dumps(payload.model_dump(), ensure_ascii=False, indent=args.indent))
    else:
        print(f"Successfully processed {payload.total_records} events into {args.output}")


if __name__ == "__main__":
    main()
