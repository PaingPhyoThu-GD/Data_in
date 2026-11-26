"""
Standalone CLI runner for the DuckLake Medallion pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ducklake import ALLOWED_SOURCES, LakehouseConfig, LakehouseLockError, LakehouseService, QualityStatus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DuckLake Medallion pipeline.")
    parser.add_argument(
        "--source",
        action="append",
        choices=ALLOWED_SOURCES,
        default=None,
        help="Target source(s) to ingest. Repeatable; defaults to all six sources.",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Reset watermarks and prior committed Bronze/Silver/Gold layers for selected sources.",
    )
    parser.add_argument(
        "--export-duckdb",
        action="store_true",
        default=False,
        help="Export materialized silver/quarantine/gold tables to lakehouse/ducklake.duckdb.",
    )
    parser.add_argument("--logs-dir", type=Path, default=None, help="Override upstream logs directory.")
    parser.add_argument("--landing-dir", type=Path, default=None, help="Override landing JSON directory.")
    parser.add_argument("--lakehouse-dir", type=Path, default=None, help="Override lakehouse output directory.")
    parser.add_argument("--json", action="store_true", help="Print full BatchRunReport as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = LakehouseConfig(
        project_root=PROJECT_ROOT,
        logs_dir=args.logs_dir,
        landing_dir=args.landing_dir,
        lakehouse_dir=args.lakehouse_dir,
        export_duckdb=bool(args.export_duckdb),
    )
    service = LakehouseService(config=config)

    try:
        report = service.run_batch(
            sources=args.source,
            full_refresh=bool(args.full_refresh),
            export_duckdb=bool(args.export_duckdb),
        )
    except LakehouseLockError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Pipeline failure: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(f"Batch: {report.batch_id} | Status: {report.overall_status.value}")
        for s in report.sources:
            print(
                f"  - {s.source_name}: scanned={s.scanned_count}, "
                f"ingested={s.ingested_count}, skipped={s.skipped_unchanged_count}"
            )
        print(f"Quarantined total: {report.quality.total_quarantined}")
        print(f"Gold Marts: {report.layer_counts.gold_by_mart}")
        for w in report.warnings:
            print(f"Warning: {w}", file=sys.stderr)

    return 2 if report.overall_status == QualityStatus.BLOCKED else 0


if __name__ == "__main__":
    raise SystemExit(main())
