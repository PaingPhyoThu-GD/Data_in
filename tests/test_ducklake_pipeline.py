"""
Unit and integration tests for the DuckLake Medallion pipeline.
All fixtures run in isolated tmp_path directories.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import duckdb
import pytest

from ducklake import LakehouseConfig, LakehouseService, QualityStatus


def _seed_all_sources(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)

    # 1. gemini_ocr_log.jsonl (1 valid + 1 error item with full Windows path)
    ocr_entry = {
        "content": "Test OCR Prompt",
        "date": "2026-11-10T03:10:00+00:00",
        "files": ["D:\\tmp\\sample.png", "D:\\tmp\\bad.png"],
        "respond": [
            {"image_index": 0, "filename": "sample.png", "text": "Hello Myanmar", "language": "mixed", "confidence": 0.98},
            {"image_index": 1, "filename": "D:\\tmp\\bad.png", "text": "", "language": "unknown", "confidence": 0.0, "error": "timeout"},
        ],
    }
    (logs_dir / "gemini_ocr_log.jsonl").write_text(json.dumps(ocr_entry) + "\n", encoding="utf-8")

    # 2. telegram_parser_log.jsonl (1 service notice + 2 messages with reactions)
    tg_entry = {
        "session_id": "tg_sess_1",
        "timestamp": "2026-11-10T09:40:01",
        "chat_title": "Min Thike Tun",
        "export_source": "messages.html",
        "messages": [
            {"id": -1, "type": "service", "date": "2 November 2026", "text": "2 November 2026", "reaction_count": 0, "reactions": []},
            {
                "id": 10,
                "type": "message",
                "date": "2026-11-02T14:36:02+06:30",
                "from_name": "Alice",
                "reply_to_message_id": None,
                "text": "Hi!",
                "media": None,
                "reaction_count": 2,
                "reactions": [{"emoji": "👍", "count": 2, "users": ["Bob", "Cara"]}],
            },
            {
                "id": 11,
                "type": "message",
                "date": "2026-11-02T14:37:00+06:30",
                "from_name": "",
                "reply_to_message_id": 10,
                "text": "",
                "media": {"type": "photo", "file_path": "photos/p1.jpg"},
                "reaction_count": 0,
                "reactions": [],
            },
        ],
    }
    (logs_dir / "telegram_parser_log.jsonl").write_text(json.dumps(tg_entry) + "\n", encoding="utf-8")

    # 3. database_parser_log.jsonl (customers with 'name' column only + sales_table with total_amount)
    db_entry = {
        "session_id": "db_sess_1",
        "timestamp": "2026-11-10T09:40:01",
        "database_name": "sales_database",
        "export_source": "sales_database.sql",
        "format": "sql_dump",
        "total_tables": 2,
        "total_rows": 3,
        "data": {
            "database_name": "sales_database",
            "export_source": "sales_database.sql",
            "format": "sql_dump",
            "tables": {
                "customers": {
                    "table_name": "customers",
                    "row_count": 1,
                    "columns": [{"name": "customer_id"}, {"name": "name"}],
                    "rows": [{"customer_id": "c1", "name": "Aung", "email": "a@example.com", "city": "Yangon"}],
                },
                "sales_table": {
                    "table_name": "sales_table",
                    "row_count": 2,
                    "columns": [{"name": "order_id"}, {"name": "customer_id"}, {"name": "order_date"}, {"name": "total_amount"}],
                    "rows": [
                        {"order_id": "o1", "customer_id": "c1", "order_date": "2026-11-01", "total_amount": 150.0},
                        {"order_id": "o2", "customer_id": "c_missing", "order_date": "2026-11-01", "total_amount": 50.0},
                    ],
                },
            },
        },
    }
    (logs_dir / "database_parser_log.jsonl").write_text(json.dumps(db_entry) + "\n", encoding="utf-8")

    # 4. youtube_parser_log.jsonl (with Short having duration_seconds=None)
    yt_entry = {
        "session_id": "yt_sess_1",
        "timestamp": "2026-11-10T09:40:01",
        "source": "sample_channel.html",
        "data": {
            "channel_info": {"channel_id": None, "channel_name": "TechPulse Explains", "handle": "@TechPulse", "is_verified": True},
            "videos": [
                {"video_id": "v1", "title": "Long", "url": "u1", "duration_seconds": 120, "view_count": 1000, "is_short": False},
                {"video_id": "v2", "title": "Short", "url": "u2", "duration_seconds": None, "view_count": 500, "is_short": True},
            ],
            "scraped_at": "2026-11-10T03:10:00+00:00",
        },
    }
    (logs_dir / "youtube_parser_log.jsonl").write_text(json.dumps(yt_entry) + "\n", encoding="utf-8")

    # 5. survey_extractor_log.jsonl (1 truncated legacy run + 1 complete run)
    srv_truncated = {
        "survey_id": "srv_trunc",
        "timestamp": "2026-11-10T09:50:00",
        "title": "API Test Survey",
        "file_name": "survey_test.csv",
        "data": {
            "survey_id": "srv_trunc",
            "metadata": {"survey_id": "srv_trunc", "title": "API Test Survey", "file_name": "survey_test.csv", "created_at": "2026-11-10T03:20:00+00:00", "total_questions": 1, "total_responses": 6, "valid_responses": 6, "invalid_responses": 0},
            "questions": [{"question_id": "q_0", "column_index": 0, "question_text": "Lang?", "field_type": "multi_select", "detected_options": ["Python"]}],
            "sample_responses": [{"response_id": "r1", "survey_id": "srv_trunc", "row_number": 1, "answers": {"q_0": ["Python"]}}],
        },
    }
    srv_full = {
        "survey_id": "srv_full",
        "timestamp": "2026-11-10T09:55:00",
        "title": "Real Survey",
        "file_name": "real.csv",
        "data": {
            "survey_id": "srv_full",
            "metadata": {"survey_id": "srv_full", "title": "Real Survey", "file_name": "real.csv", "created_at": "2026-11-10T03:25:00+00:00", "total_questions": 1, "total_responses": 1, "valid_responses": 1, "invalid_responses": 0},
            "questions": [{"question_id": "q_0", "column_index": 0, "question_text": "Lang?", "field_type": "multi_select", "detected_options": ["Python"]}],
            "responses": [{"response_id": "r_ok", "survey_id": "srv_full", "row_number": 1, "answers": {"q_0": ["Python", "SQL"]}}],
        },
    }
    (logs_dir / "survey_extractor_log.jsonl").write_text(
        json.dumps(srv_truncated) + "\n" + json.dumps(srv_full) + "\n", encoding="utf-8"
    )

    # 6. telemetry.db (duplicate UUID re-upload + beacon event with 0.0 latency)
    db_path = logs_dir / "telemetry.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_events (
            id TEXT PRIMARY KEY, site_id TEXT, source_mode TEXT, timestamp INTEGER,
            datetime_utc TEXT, visitor_hash TEXT, session_id TEXT, path TEXT, method TEXT,
            status_code INTEGER, latency_ms REAL, duration_seconds REAL, referrer TEXT,
            referrer_domain TEXT, country_code TEXT, city TEXT, browser TEXT, os TEXT, device_type TEXT
        )
        """
    )
    conn.execute("DELETE FROM telemetry_events")
    ev1 = ("uuid-1", "upload_test", "file_upload", 1762776000000, "2026-11-10T12:00:00Z", "vh1", "s1", "/home", "GET", 200, 45.0, 2.0, "", "direct", "MM", "", "Chrome", "Windows", "desktop")
    ev1_dup = ("uuid-2", "upload_test", "file_upload", 1762776000000, "2026-11-10T12:00:00Z", "vh1", "s1", "/home", "GET", 200, 45.0, 2.0, "", "direct", "MM", "", "Chrome", "Windows", "desktop")
    ev_beacon = ("uuid-3", "prod_site", "beacon", 1762776001000, "2026-11-10T12:00:01Z", "vh2", "s2", "/blog", "GET", 200, 0.0, 5.0, "", "direct", "MM", "", "Chrome", "Windows", "desktop")
    conn.executemany("INSERT INTO telemetry_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [ev1, ev1_dup, ev_beacon])
    conn.commit()
    conn.close()


def test_bronze_idempotency_and_telegram_inplace_rewrite(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))

    r1 = svc.run_batch()
    assert r1.overall_status == QualityStatus.PASSED_WITH_QUARANTINE
    assert all(s.ingested_count > 0 for s in r1.sources)

    # Immediate second run must ingest 0 new Bronze records
    r2 = svc.run_batch()
    assert all(s.ingested_count == 0 for s in r2.sources)

    # Simulate POST /api/telegram/attach-photos rewriting telegram_parser_log.jsonl in place
    tg_path = logs_dir / "telegram_parser_log.jsonl"
    obj = json.loads(tg_path.read_text(encoding="utf-8").strip())
    obj["messages"][2]["media"]["url"] = "/uploads/tg/p1.jpg"
    tg_path.write_text(json.dumps(obj) + "\n", encoding="utf-8")

    r3 = svc.run_batch()
    tg_summary = next(s for s in r3.sources if s.source_name == "telegram_parser")
    assert tg_summary.ingested_count == 1


def test_jsonl_streaming_trailing_partial_line_and_large_payload(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    logs_dir.mkdir(parents=True, exist_ok=True)

    big_text = "x" * (17 * 1024 * 1024)  # > 16 MB single JSON line
    valid_ocr = {
        "content": "Large Doc",
        "date": "2026-11-10T03:10:00+00:00",
        "files": ["big.png"],
        "respond": [{"image_index": 0, "filename": "big.png", "text": big_text, "language": "en", "confidence": 0.99}],
    }
    (logs_dir / "gemini_ocr_log.jsonl").write_text(
        json.dumps(valid_ocr) + "\n" + '{"content": "torn_line',
        encoding="utf-8",
    )

    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))
    report = svc.run_batch(sources=["gemini_ocr"])
    assert report.overall_status == QualityStatus.PASSED
    assert report.layer_counts.silver_by_entity["ocr_extractions"] == 1


def test_landing_json_unwrapping_and_empty_sources(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    logs_dir.mkdir(parents=True, exist_ok=True)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))

    # Empty logs initial batch should succeed cleanly with 0-row typed Parquet files
    empty_report = svc.run_batch()
    assert empty_report.overall_status == QualityStatus.PASSED
    assert svc.get_mart_preview("gold_sales_kpi_mart").total == 0

    # Add raw unwrapped CLI exports to landing/
    db_landing = lh_dir / "landing" / "database_parser"
    yt_landing = lh_dir / "landing" / "youtube_parser"
    db_landing.mkdir(parents=True, exist_ok=True)
    yt_landing.mkdir(parents=True, exist_ok=True)
    (db_landing / "raw_db.json").write_text(
        json.dumps(
            {
                "database_name": "cli_db",
                "export_source": "cli.csv",
                "format": "csv",
                "total_rows": 1,
                "tables": {"orders": {"table_name": "orders", "rows": [{"order_id": "cli_1", "total_amount": 99.5, "order_date": "2026-11-05"}]}},
            }
        ),
        encoding="utf-8",
    )
    (yt_landing / "raw_yt.json").write_text(
        json.dumps(
            {
                "channel_info": {"channel_id": "UC_CLI", "channel_name": "CLI Channel"},
                "videos": [{"video_id": "vid_cli", "title": "CLI Video", "url": "https://yt/1", "duration_seconds": 30, "view_count": 10}],
                "scraped_at": "2026-11-11T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    r2 = svc.run_batch()
    assert r2.overall_status == QualityStatus.PASSED
    sales = svc.get_mart_preview("gold_sales_kpi_mart")
    assert sales.total == 1
    assert sales.rows[0]["segment"] == "unknown"


def test_silver_dedup_and_edge_cases(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))
    report = svc.run_batch()

    # OCR: 1 valid + 1 quarantined (with basename normalized)
    assert report.layer_counts.silver_by_entity["ocr_extractions"] == 1
    assert report.layer_counts.quarantine_by_entity["ocr_extractions"] == 1
    q_ocr = svc.get_quarantine(entity="ocr_extractions")
    assert q_ocr.total == 1
    assert q_ocr.rows[0]["_rule_id"] == "OCR_ITEM_ERROR"
    assert json.loads(q_ocr.rows[0]["raw_payload_json"])["filename"] == "bad.png"

    # Telegram: 1 service notice separated, 2 valid messages, 'Unknown' sender fallback in Gold
    assert report.layer_counts.silver_by_entity["telegram_service_notices"] == 1
    assert report.layer_counts.silver_by_entity["telegram_messages"] == 2
    tg_mart = svc.get_mart_preview("gold_telegram_engagement_mart")
    assert {r["sender_name"] for r in tg_mart.rows} == {"Alice", "Unknown"}

    # Sales KPI: customer_name coalesced, missing customer falls back to 'unknown' segment
    sales_mart = svc.get_mart_preview("gold_sales_kpi_mart")
    assert sales_mart.total == 1
    assert sales_mart.rows[0]["gross_revenue"] == 200.0

    # Survey: truncated legacy run quarantined in survey_runs while complete survey promotes
    assert report.layer_counts.quarantine_by_entity["survey_runs"] == 1
    assert report.layer_counts.silver_by_entity["surveys"] == 2

    # Telemetry: duplicate UUIDs collapsed (2 unique events total), beacon-only site has NULL p50 latency
    assert report.layer_counts.silver_by_entity["telemetry_events"] == 2
    web_mart = svc.get_mart_preview("gold_web_traffic_mart")
    by_site = {r["site_id"]: r for r in web_mart.rows}
    assert by_site["upload_test"]["pageviews"] == 1
    assert by_site["upload_test"]["p50_latency_ms"] == 45.0
    assert by_site["prod_site"]["p50_latency_ms"] is None


def test_quality_gate_blocked_preserves_healthy_marts(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))
    first = svc.run_batch()
    assert first.overall_status == QualityStatus.PASSED_WITH_QUARANTINE
    initial_tg_batch = svc.get_status().marts["gold_telegram_engagement_mart"].batch_id

    # Full-refresh telegram with 100% invalid messages alongside a new telemetry event -> BLOCKED for telegram only
    bad_tg = {
        "session_id": "tg_bad",
        "timestamp": "2026-11-11T00:00:00",
        "chat_title": "Broken",
        "messages": [{"id": 99, "type": "message", "date": "not-a-date", "from_name": "X", "text": "hi", "reaction_count": -1}],
    }
    (logs_dir / "telegram_parser_log.jsonl").write_text(json.dumps(bad_tg) + "\n", encoding="utf-8")
    # Clear telegram's prior committed bronze & watermark to simulate a 100% invalid staged source
    wm = json.loads(svc.config.watermarks_path.read_text(encoding="utf-8"))
    wm["sources"].pop("telegram_parser", None)
    svc.config.watermarks_path.write_text(json.dumps(wm), encoding="utf-8")
    mf = json.loads(svc.config.manifest_path.read_text(encoding="utf-8"))
    mf["committed_bronze_batches"].pop("telegram_parser", None)
    svc.config.manifest_path.write_text(json.dumps(mf), encoding="utf-8")

    # Add a valid new telemetry event -> should still advance gold_web_traffic_mart
    conn = sqlite3.connect(str(logs_dir / "telemetry.db"))
    conn.execute(
        "INSERT INTO telemetry_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("uuid-new", "prod_site", "file_upload", 1762776002000, "2026-11-10T12:00:02Z", "vh3", "s3", "/pricing", "GET", 200, 12.0, 1.0, "", "direct", "MM", "", "Chrome", "Windows", "desktop"),
    )
    conn.commit()
    conn.close()

    second = svc.run_batch()
    assert second.overall_status == QualityStatus.BLOCKED
    assert second.quality.entity_statuses["telegram_messages"] == QualityStatus.BLOCKED

    # Telegram Gold Mart pointer stays pinned to prior valid batch; uncommitted Bronze file was deleted
    status_after = svc.get_status()
    assert status_after.marts["gold_telegram_engagement_mart"].batch_id == initial_tg_batch
    assert not (lh_dir / "bronze" / "telegram_parser" / f"batch_{second.batch_id}.parquet").exists()

    # Healthy web traffic mart advanced to new batch
    assert status_after.marts["gold_web_traffic_mart"].batch_id == second.batch_id
    # Quarantine for blocked batch is queryable
    q_tg = svc.get_quarantine(entity="telegram_messages", batch_id=second.batch_id)
    assert q_tg.total >= 1


def test_full_refresh_runs_history_recovery_and_duckdb_export(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir, export_duckdb=True))

    r1 = svc.run_batch()
    assert r1.exported_duckdb_path is not None
    snap = Path(r1.exported_duckdb_path)
    assert snap.exists()

    dconn = duckdb.connect(str(snap), read_only=True)
    try:
        cnt = dconn.execute("SELECT COUNT(*) FROM gold.gold_web_traffic_mart").fetchone()[0]
        assert cnt == 2
    finally:
        dconn.close()

    # Inject malformed line into runs_history.jsonl and verify list_runs skips it
    with open(svc.config.runs_history_path, "a", encoding="utf-8") as fh:
        fh.write("{corrupt json line\n")
    runs = svc.list_runs()
    assert len(runs) == 1

    # Full refresh re-ingests all records cleanly
    r2 = svc.run_batch(full_refresh=True)
    assert sum(s.ingested_count for s in r2.sources) > 0
