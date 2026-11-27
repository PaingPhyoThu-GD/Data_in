"""
Gold Mart SQL materializations and optional .duckdb snapshot export.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

from .models import ALLOWED_SOURCES, QualityGateResult, QualityStatus


def build_gold_marts(
    conn: duckdb.DuckDBPyConnection,
    gold_out_dir: Path,
    bronze_counts: dict[str, int],
    silver_counts: dict[str, int],
    quarantine_counts: dict[str, int],
    gate_result: QualityGateResult,
    ingested_at: str,
) -> tuple[dict[str, Path], dict[str, int]]:
    """
    Build the four v1 Gold Mart Parquet files from validated Silver tables in `conn`.
    Returns (mart_paths, mart_row_counts).
    """
    gold_out_dir.mkdir(parents=True, exist_ok=True)
    mart_paths: dict[str, Path] = {}
    mart_counts: dict[str, int] = {}

    # 1. gold_ingestion_overview
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE gold_ingestion_overview (
            source_name VARCHAR,
            bronze_records BIGINT,
            silver_entities BIGINT,
            quarantined_records BIGINT,
            test_artifact_records BIGINT,
            quality_status VARCHAR,
            latest_ingested_at TIMESTAMPTZ
        )
        """
    )
    source_silver_map: dict[str, tuple[str, ...]] = {
        "gemini_ocr": ("ocr_extractions",),
        "telegram_parser": ("telegram_messages",),
        "database_parser": ("database_rows",),
        "youtube_parser": ("youtube_videos",),
        "survey_extractor": ("surveys",),
        "telemetry": ("telemetry_events",),
    }
    source_test_table: dict[str, str] = {
        "gemini_ocr": "silver_ocr_extractions",
        "telegram_parser": "silver_telegram_messages",
        "database_parser": "silver_database_rows",
        "youtube_parser": "silver_youtube_videos",
        "survey_extractor": "silver_surveys",
        "telemetry": "silver_telemetry_events",
    }
    source_q_entity: dict[str, str] = {
        "gemini_ocr": "ocr_extractions",
        "telegram_parser": "telegram_messages",
        "database_parser": "sales_orders",
        "youtube_parser": "youtube_videos",
        "survey_extractor": "survey_runs",
        "telemetry": "telemetry_events",
    }

    for src in ALLOWED_SOURCES:
        b_cnt = bronze_counts.get(src, 0)
        s_cnt = sum(silver_counts.get(e, 0) for e in source_silver_map[src])
        q_ent = source_q_entity[src]
        q_cnt = quarantine_counts.get(q_ent, 0)
        tbl = source_test_table[src]
        test_cnt = int(
            conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE _is_test_artifact = TRUE").fetchone()[0]  # type: ignore[index]
        )
        max_ts = conn.execute(f"SELECT MAX(_ingested_at) FROM {tbl}").fetchone()[0]  # type: ignore[index]
        status_val = gate_result.entity_statuses.get(q_ent, QualityStatus.PASSED).value
        conn.execute(
            "INSERT INTO gold_ingestion_overview VALUES (?, ?, ?, ?, ?, ?, TRY_CAST(? AS TIMESTAMPTZ))",
            (src, b_cnt, s_cnt, q_cnt, test_cnt, status_val, max_ts),
        )

    overview_sorted = "SELECT * FROM gold_ingestion_overview ORDER BY source_name"
    conn.execute(f"CREATE OR REPLACE TEMP TABLE gold_ingestion_overview AS {overview_sorted}")

    # 2. gold_sales_kpi_mart
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE gold_sales_kpi_mart AS
        SELECT
            o.order_date AS order_date,
            COALESCE(c.segment, 'unknown') AS segment,
            COUNT(*)::BIGINT AS order_count,
            ROUND(SUM(o.total_amount), 2)::DOUBLE AS gross_revenue,
            ROUND(AVG(o.total_amount), 2)::DOUBLE AS avg_order_value
        FROM silver_sales_orders o
        LEFT JOIN silver_sales_customers c ON o.customer_id = c.customer_id
        GROUP BY o.order_date, COALESCE(c.segment, 'unknown')
        ORDER BY o.order_date DESC, gross_revenue DESC
        """
    )

    # 3. gold_telegram_engagement_mart
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE gold_telegram_engagement_mart AS
        SELECT
            chat_title,
            COALESCE(NULLIF(from_name, ''), 'Unknown') AS sender_name,
            COUNT(*)::BIGINT AS message_count,
            COUNT(*) FILTER (WHERE reply_to_message_id IS NOT NULL)::BIGINT AS reply_count,
            COUNT(*) FILTER (WHERE has_media)::BIGINT AS media_count,
            COALESCE(SUM(reaction_count), 0)::BIGINT AS total_reactions
        FROM silver_telegram_messages
        GROUP BY chat_title, COALESCE(NULLIF(from_name, ''), 'Unknown')
        ORDER BY message_count DESC
        """
    )

    # 4. gold_web_traffic_mart
    conn.execute(
        """
        CREATE OR REPLACE TEMP TABLE gold_web_traffic_mart AS
        SELECT
            CAST(event_ts AS DATE) AS traffic_date,
            site_id,
            COUNT(*)::BIGINT AS pageviews,
            COUNT(DISTINCT visitor_hash)::BIGINT AS unique_visitors,
            COUNT(DISTINCT session_id)::BIGINT AS sessions,
            ROUND(quantile_cont(latency_ms, 0.50) FILTER (WHERE source_mode != 'beacon'), 2)::DOUBLE AS p50_latency_ms,
            ROUND(quantile_cont(latency_ms, 0.95) FILTER (WHERE source_mode != 'beacon'), 2)::DOUBLE AS p95_latency_ms,
            ROUND(100.0 * COUNT(*) FILTER (WHERE status_code >= 400) / NULLIF(COUNT(*), 0), 2)::DOUBLE AS error_rate_pct
        FROM silver_telemetry_events
        GROUP BY CAST(event_ts AS DATE), site_id
        ORDER BY traffic_date DESC, pageviews DESC
        """
    )

    for mart_name in (
        "gold_ingestion_overview",
        "gold_sales_kpi_mart",
        "gold_telegram_engagement_mart",
        "gold_web_traffic_mart",
    ):
        out_file = gold_out_dir / f"{mart_name}.parquet"
        escaped = out_file.as_posix().replace("'", "''")
        conn.execute(f"COPY {mart_name} TO '{escaped}' (FORMAT PARQUET)")
        cnt = int(conn.execute(f"SELECT COUNT(*) FROM {mart_name}").fetchone()[0])  # type: ignore[index]
        mart_paths[mart_name] = out_file
        mart_counts[mart_name] = cnt

    return mart_paths, mart_counts


def export_duckdb_snapshot(
    snapshot_path: Path,
    silver_files: dict[str, Path],
    quarantine_files: dict[str, Path | list[Path]],
    gold_files: dict[str, Path],
) -> tuple[bool, str | None]:
    """
    Export materialized silver, quarantine, and gold tables into a standalone .duckdb snapshot.
    Returns (success, warning_message_if_failed).
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = snapshot_path.with_suffix(".duckdb.tmp")
    if tmp_db.exists():
        try:
            tmp_db.unlink()
        except OSError:
            pass

    conn = duckdb.connect(str(tmp_db))
    try:
        conn.execute("CREATE SCHEMA IF NOT EXISTS silver")
        conn.execute("CREATE SCHEMA IF NOT EXISTS quarantine")
        conn.execute("CREATE SCHEMA IF NOT EXISTS gold")

        for ent, fpath in silver_files.items():
            if fpath.exists():
                tbl = fpath.stem
                esc = fpath.as_posix().replace("'", "''")
                conn.execute(f"CREATE OR REPLACE TABLE silver.{tbl} AS SELECT * FROM read_parquet('{esc}')")

        for ent, fpaths in quarantine_files.items():
            paths_list = [fpaths] if isinstance(fpaths, Path) else list(fpaths)
            existing = [p for p in paths_list if p.exists()]
            if existing:
                paths_sql = ", ".join(f"'{p.as_posix().replace(chr(39), chr(39)*2)}'" for p in existing)
                conn.execute(f"CREATE OR REPLACE TABLE quarantine.{ent} AS SELECT * FROM read_parquet([{paths_sql}])")

        for mart_name, fpath in gold_files.items():
            if fpath.exists():
                esc = fpath.as_posix().replace("'", "''")
                conn.execute(f"CREATE OR REPLACE TABLE gold.{mart_name} AS SELECT * FROM read_parquet('{esc}')")
    finally:
        conn.close()

    try:
        os.replace(tmp_db, snapshot_path)
        return True, None
    except PermissionError as exc:
        try:
            tmp_db.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"Skipped .duckdb export because target is locked by another process: {exc}"
