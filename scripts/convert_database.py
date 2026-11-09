"""
CLI Runner: Convert Database exports (SQL dump, SQLite .db, CSV/TSV, Excel .xlsx) to structured JSON.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Ensure src is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from database_parser import DatabaseConverter, DatabaseParser


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert database export files (SQL, SQLite, CSV, XLSX) to JSON.")
    parser.add_argument(
        "--input",
        type=str,
        default="sample_database/sales_database.sql",
        help="Path to database export file (.sql, .db, .sqlite, .csv, .tsv, .xlsx).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path for output JSON file (default: <filename>.json in same folder).",
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

    db_parser = DatabaseParser()
    converter = DatabaseConverter(parser=db_parser)

    print("\n=======================================================")
    print("  Database Export to JSON Converter")
    print(f"  Input: {input_path}")
    print("=======================================================\n")

    result = converter.convert(
        input_file_path=input_path,
        output_json_path=args.output,
        indent=args.indent,
    )

    out_file = Path(args.output) if args.output else input_path.with_name(f"{input_path.stem}.json")

    print("[SUCCESS] Conversion completed!")
    print(f"  Format:           {result.format}")
    print(f"  Database Name:    {result.database_name}")
    print(f"  Total Tables:     {result.total_tables}")
    print(f"  Total Rows:       {result.total_rows}")
    for tbl_name, tbl in result.tables.items():
        print(f"    - Table '{tbl_name}': {len(tbl.columns)} cols, {tbl.row_count} rows")
    print(f"  Output File:      {out_file.resolve()}\n")


if __name__ == "__main__":
    main()
