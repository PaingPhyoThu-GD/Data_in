"""
Bronze layer ingestion, watermark checking, and Parquet batch writer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .adapters.base import SourceAdapter
from .config import LakehouseConfig
from .models import BronzeEnvelope, SourceIngestSummary


@dataclass
class StagedBronzeResult:
    """Result of staging Bronze Parquet files prior to Quality Gate commit."""

    summaries: list[SourceIngestSummary]
    staged_files: dict[str, Path]
    pending_watermarks: dict[str, dict[str, str]]
    row_counts_by_source: dict[str, int]


def load_watermarks(path: Path) -> dict[str, dict[str, str]]:
    """Load committed per-source watermarks from disk."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        sources = data.get("sources")
        if isinstance(sources, dict):
            return {
                str(src): {str(k): str(v) for k, v in mapping.items()}
                for src, mapping in sources.items()
                if isinstance(mapping, dict)
            }
    except Exception:
        pass
    return {}


def save_watermarks_atomic(path: Path, watermarks: dict[str, dict[str, str]]) -> None:
    """Atomically persist per-source watermarks via temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps({"sources": watermarks}, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp_path, path)


def _write_envelopes_parquet(envelopes: list[BronzeEnvelope], target_path: Path, memory_limit: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_parquet = target_path.with_suffix(".parquet.tmp")
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(f"SET memory_limit = '{memory_limit}'")
        conn.execute(
            """
            CREATE TABLE bronze_stage (
                _ingest_id VARCHAR,
                _batch_id VARCHAR,
                _ingested_at VARCHAR,
                _source_name VARCHAR,
                _source_origin_type VARCHAR,
                _source_file VARCHAR,
                _record_key VARCHAR,
                _payload_hash VARCHAR,
                _is_test_artifact BOOLEAN,
                payload_json VARCHAR
            )
            """
        )
        rows = [
            (
                env.ingest_id,
                env.batch_id,
                env.ingested_at,
                env.source_name,
                env.source_origin_type,
                env.source_file,
                env.record_key,
                env.payload_hash,
                env.is_test_artifact,
                env.payload_json,
            )
            for env in envelopes
        ]
        conn.executemany(
            "INSERT INTO bronze_stage VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        escaped = tmp_parquet.as_posix().replace("'", "''")
        conn.execute(f"COPY bronze_stage TO '{escaped}' (FORMAT PARQUET)")
    finally:
        conn.close()
    os.replace(tmp_parquet, target_path)


def stage_bronze_batch(
    config: LakehouseConfig,
    adapters: list[SourceAdapter],
    batch_id: str,
    ingested_at: str,
    committed_watermarks: dict[str, dict[str, str]],
    full_refresh: bool = False,
) -> StagedBronzeResult:
    """
    Scan all selected adapters, filter unchanged records against committed watermarks,
    and write new/changed records to lakehouse/bronze/<source>/batch_<batch_id>.parquet.
    """
    summaries: list[SourceIngestSummary] = []
    staged_files: dict[str, Path] = {}
    pending_watermarks: dict[str, dict[str, str]] = {}
    row_counts: dict[str, int] = {}

    for adapter in adapters:
        source_name = adapter.source_name
        existing_map = {} if full_refresh else dict(committed_watermarks.get(source_name, {}))
        records = adapter.read_records(config, batch_id=batch_id, ingested_at=ingested_at)

        # Collapse duplicate record_keys within the same scan, keeping latest occurrence
        dedup_in_scan: dict[str, BronzeEnvelope] = {}
        for env in records:
            dedup_in_scan[env.record_key] = env

        to_ingest: list[BronzeEnvelope] = []
        skipped = 0
        for rec_key, env in dedup_in_scan.items():
            if existing_map.get(rec_key) == env.payload_hash:
                skipped += 1
            else:
                to_ingest.append(env)

        bronze_file_str: str | None = None
        if to_ingest:
            out_path = config.bronze_dir / source_name / f"batch_{batch_id}.parquet"
            _write_envelopes_parquet(to_ingest, out_path, memory_limit=config.memory_limit)
            staged_files[source_name] = out_path
            bronze_file_str = out_path.relative_to(config.lakehouse_dir).as_posix()  # type: ignore[arg-type]
            updated_map = dict(existing_map)
            for env in to_ingest:
                updated_map[env.record_key] = env.payload_hash
            pending_watermarks[source_name] = updated_map
        else:
            pending_watermarks[source_name] = existing_map

        row_counts[source_name] = len(to_ingest)
        summaries.append(
            SourceIngestSummary(
                source_name=source_name,
                scanned_count=len(records),
                ingested_count=len(to_ingest),
                skipped_unchanged_count=skipped,
                bronze_file=bronze_file_str,
            )
        )

    return StagedBronzeResult(
        summaries=summaries,
        staged_files=staged_files,
        pending_watermarks=pending_watermarks,
        row_counts_by_source=row_counts,
    )
