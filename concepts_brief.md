# DuckLake Medallion Prototype

* **Author:** MinnThikeTunn
* **Date:** 2026-11-26

## Overview

The DuckLake Medallion Prototype adds a local Python analytics layer (`src/ducklake/`) on top of the six existing ingestion services (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`, and `telemetry`) without modifying upstream parser code. It pulls completed Extraction Runs and SQLite telemetry records into append-only Bronze Parquet partitions, conforms and deduplicates Entity Records in Silver, splits corrupt rows into Quarantine under a single-contract DuckDB SQL Quality Gate, and serves focused Gold Marts through a CLI (`scripts/run_lakehouse.py`), a FastAPI router (`frontend/lakehouse_routes.py`), and a DuckLake tab in `frontend/static/index.html` for team review and iteration.

Note: In this repository, "DuckLake" is the internal module name for this local Medallion layer, distinct from DuckDB's external `ducklake` catalog extension. This prototype brief supersedes [`ducklake_medallion_pipeline_plan.md`](file:///D:/Data_in/ducklake_medallion_pipeline_plan.md) for v1 local implementation.

## Analysis

Evaluating the prototype across architecture, codebase reality, minimalism, comprehension, structure, implementation readiness, and inventive problem-solving exposed five core contradictions and codebase mismatches, resolved as follows:

1. **DuckDB Single-Writer Locking vs. Concurrent CLI and Web Access**
   * *Contradiction*: Holding a single persistent `lakehouse/ducklake.duckdb` file open for both pipeline writes (`scripts/run_lakehouse.py` or `POST /api/lakehouse/run`) and web reads (`/api/lakehouse/*`) causes Windows file-lock errors and blocks the FastAPI event loop if run on async handlers.
   * *Resolution — Compute-Storage Separation & Single-Writer Lock*: Store committed Bronze, Silver, Quarantine, and Gold datasets as atomic Parquet files under `lakehouse/` tracked by `lakehouse/metadata/latest_manifest.json`. Guard write batches behind a single-writer lock and stage files before atomic promotion. Read endpoints run off the event loop (`asyncio.to_thread` or sync FastAPI routes) using short-lived `:memory:` DuckDB connections querying the last committed Parquet snapshot. A disposable `lakehouse/ducklake.duckdb` snapshot can optionally be exported after each batch for external tools such as Metabase.
   * *Trade-off*: Ephemeral `:memory:` readers incur small per-request view setup overhead rather than persistent DuckDB indexes, and Windows file-handle rules require keeping previous snapshot files briefly until active reads complete.

2. **Great Expectations Overhead vs. Fast Prototype Iteration**
   * *Contradiction*: `great-expectations` is absent from `pyproject.toml` and `requirements.txt`, pulls dozens of heavy transitive packages (`pandas`, `numpy`, `scipy`, `sqlalchemy`), and duplicates rule definitions because `docs/adr/0003` already splits corrupt rows into Quarantine before GX runs.
   * *Resolution — Single-Contract Quality Gate Port*: Express validation rules once as declarative DuckDB SQL checks behind a narrow `QualityGate` Python interface. A single evaluation pass routes failing rows to `lakehouse/quarantine/<entity>/` (`_batch_id`, `rule_id`, `_failure_reason`, `raw_payload`) and computes dataset-level circuit-breaker status (`PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED`) before promoting Silver to Gold. When a batch is `BLOCKED`, `latest_manifest.json` keeps pointing at the previous verified Gold snapshot (`stale-while-revalidate`) while surfacing Quarantine diagnostics. `great-expectations` stays deferred behind the `QualityGate` port as an optional post-meeting adapter.
   * *Trade-off*: Forfeits GX's generated Data Docs HTML UI in v1 in exchange for zero extra dependencies beyond `duckdb`, fast test execution, and single-source rule definitions.

3. **Pull-Source Realities & Upstream Schema Drift**
   * *Contradiction*: `docs/adr/0002` originally assumed surveys live in `logs/surveys.db` and logs are append-only JSONL files. Auditing the codebase surfaced five concrete mismatches:
     * **`surveys.db` is orphaned**: `frontend/app.py` writes surveys only to `logs/survey_extractor_log.jsonl`, and legacy lines 1–2 contain `sample_responses` without `responses`.
     * **`telemetry.db` is the system of record**: `logs/telemetry_parser_log.jsonl` omits `/sample`, `/drain`, and `/collect` beacon events and caps `recent_events` at 150. Three telemetry adapters also generate a fresh `uuid.uuid4()` `id` on every re-upload, so Silver must deduplicate on `(site_id, timestamp, path, method, visitor_hash, session_id, status_code, latency_ms)` rather than `id`, reading `logs/telemetry.db` via SQLite's online backup API (`sqlite3.Connection.backup()`) or `?mode=ro` to avoid `SQLITE_BUSY` with WAL writes.
     * **In-place JSONL rewrites**: `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place, breaking byte-offset cursors. Bronze must track `(record_key, payload_sha256)` watermarks in `lakehouse/metadata/` and stream JSONL lines in Python to avoid DuckDB's 16 MB object-size limit.
     * **Field & schema drift**: OCR logs use `confidence` and `text` (no `session_id`; batch `image_index` resets; failed items carry `"error"` + `confidence=0.0`); YouTube Shorts have `duration_seconds: null`; Telegram `Service Notice` entries have negative `id` and non-ISO dates (`"2 November 2026"`) and are separated before user-message engagement checks; `database_parser` parses arbitrary schemas (`sales_database.sql` uses `sales_table`, `order_id`, `total_amount` with no `products` table), requiring hybrid routing (conformed `silver_sales_*` when columns match + generic `silver_database_tables` / `silver_database_rows` JSON pass-through otherwise); surveys flatten into header + long-form answer rows (`silver_surveys`, `silver_survey_answers`).
     * **Test pollution & CWD paths**: `tests/test_frontend_api.py`, `tests/test_survey_extractor.py`, and `tests/test_telemetry.py` write test runs into `logs/` (12–26 duplicate lines per log), and `DEFAULT_LOG_DIR` defaults to relative `"logs"`. `src/ducklake/` must inject explicit `LakehouseConfig` paths, tag `_is_test_artifact` rows transparently, and isolate `tests/` into `tmp_path`.
   * *Resolution*: Implement one symmetric `SourceAdapter` interface across all 6 upstream services inside `src/ducklake/adapters/` with read-only access to `logs/` and `lakehouse/landing/<source>/`.

4. **Cumulative Snapshots vs. Daily Timeline (`Daily Activity Spine`)**
   * *Contradiction*: `youtube_parser` (`view_count`, `subscriber_count`) and `database_parser` exports capture cumulative state at scrape/export time, while `telegram_parser`, `telemetry`, `survey_extractor`, and `gemini_ocr` capture event timestamps—and current logs span disconnected years (2024 survey tests vs. 2026 chat/web logs) and relative strings (`"3 days ago"`). Mixing cumulative totals with daily event counts on a single calendar spine creates distorted numbers.
   * *Resolution — Lean Meeting Gold Scope*: For the v1 team-review prototype, keep all 6 sources flowing through Bronze and Silver, and publish a focused 4-mart Gold layer:
     1. `gold_ingestion_overview` (per-service Extraction Runs, deduplicated Entity Records, Quarantine counts, test-artifact vs. non-test breakdown, and latest run timestamp).
     2. `gold_sales_kpi_mart` (revenue and order KPIs derived conditionally from conforming `silver_sales_*` tables).
     3. `gold_telegram_engagement_mart` (participant activity, replies, media share, and reaction distributions excluding `Service Notice` rows).
     4. `gold_web_traffic_mart` (daily site pageviews, unique deduplicated visitors, P50/P95 latency, and error rates from `silver_telemetry_events`).
     Defer `gold_cross_channel_analytics_mart` (`Daily Activity Spine` with SCD Type 2 snapshot deltas), `gold_youtube_video_performance_mart`, `gold_ocr_quality_mart`, and `gold_survey_response_mart` until after the team validates Silver schemas in the meeting.

5. **Minimal Prototype UI & Middleware Boundaries**
   * *Contradiction*: `frontend/app.py` (911 lines), `frontend/static/index.html` (1,509 lines with 6 non-wrapping header tabs), and `frontend/static/app.js` (3,473 lines) are already dense. Adding DuckDB code inside `app.py` or building complex BI widgets before team alignment creates throwaway UI glue.
   * *Resolution*: Keep 100% of DuckLake logic inside `src/ducklake/`, mount thin routes via `frontend/lakehouse_routes.py`, reuse the same `LakehouseService` in `scripts/run_lakehouse.py`, wrap header navigation with `flex-wrap`, and keep DuckLake UI code in `frontend/static/lakehouse.js` with three focused views: Pipeline Trigger & Layer Counts, Quality Gate & Quarantine Inspector, and Gold Mart Table Preview.

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Add `duckdb` to `pyproject.toml` and `requirements.txt` (zero `great-expectations`, `dbt-core`, or container dependencies).
  * Build `src/ducklake/` with `LakehouseConfig`, symmetric `SourceAdapter`s for all 6 services, Parquet-first Bronze/Silver/Quarantine/Gold storage, watermark manifests, and an optional `.duckdb` snapshot export.
  * Implement Silver deduplication, Telegram `Service Notice` separation, hybrid `database_parser` routing, long-form survey answers, and composite-key telemetry deduplication.
  * Implement single-contract DuckDB SQL `QualityGate` with row-level Quarantine (`PASSED`, `PASSED_WITH_QUARANTINE`, `BLOCKED`) and 4 v1 Gold Marts.
  * Provide `scripts/run_lakehouse.py`, `frontend/lakehouse_routes.py` (`/api/lakehouse/*`), a lean DuckLake SPA tab (`frontend/static/lakehouse.js`), and `tmp_path`-isolated `pytest` coverage (including isolating `tests/test_frontend_api.py` from `logs/`).
* **Out-of-Scope Non-Goals:**
  * Docker Compose orchestration with Apache Airflow, Metabase, or DuckDB HTTP/Arrow servers (`Quack Protocol`) in v1.
  * `dbt-duckdb` project scaffolding (`dbt_project/`) in v1.
  * Installing `great-expectations` at runtime in v1 (deferred behind the `QualityGate` protocol).
  * Modifying upstream parser logic inside the 6 existing `src/` packages.
  * `gold_cross_channel_analytics_mart` (`Daily Activity Spine` with SCD2 deltas) and wide-pivoted survey/YouTube/OCR Gold Marts before post-meeting review.
  * Arbitrary user-entered SQL execution in `/api/lakehouse/*`.

## Alternatives Weighed

* **Full Enterprise Stack (`dbt-duckdb` + Airflow + Metabase Docker)**: Rejected for v1 (`docs/adr/0001`) because container orchestration and `dbt-core` slow local iteration before schema alignment; Parquet + DuckDB SQL stays portable to `dbt-duckdb` later.
* **Persistent Shared Read/Write `ducklake.duckdb`**: Rejected after Goldfish concurrency audit because concurrent FastAPI reads and CLI writes trigger Windows file-lock errors; replaced by atomic Parquet snapshots + ephemeral `:memory:` DuckDB readers (with optional `.duckdb` export).
* **Runtime `great-expectations` + Separate SQL Splitter**: Rejected for v1 (`docs/adr/0003` updated) because GX pulls heavy dependencies (`pandas`, `numpy`, `scipy`, `sqlalchemy`) and forces duplicate rule definitions; replaced by declarative DuckDB SQL behind a `QualityGate` interface.
* **Intrusive Upstream Hooks in `src/*` Parsers**: Rejected (`docs/adr/0002`) to preserve 100% isolation of existing service packages; replaced by read-only pulling from `logs/` and `lakehouse/landing/<source>/`.
* **Byte-Offset JSONL Cursors**: Rejected after codebase audit because `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place; replaced by `(record_key, payload_sha256)` watermarks.
* **All 7 Gold Marts + Cross-Channel Daily Spine in v1**: Deferred after codebase audit showed test logs span 2024–2026 and YouTube metrics are cumulative snapshots; trimmed to `gold_ingestion_overview` plus 3 clean domain marts for the meeting prototype.

## Key Decisions & Staging for Next Steps

* **Resolved Decisions Carried into `/egm-draft`:**
  1. **Storage & Concurrency (`ADR-0001` updated)**: Parquet-first atomic partitions + `latest_manifest.json` + single-writer batch lock + ephemeral `:memory:` DuckDB readers + optional `.duckdb` snapshot export.
  2. **Source Contracts (`ADR-0002` updated)**: Pull all 6 sources read-only from `logs/*_log.jsonl`, `logs/telemetry.db` (via online SQLite backup / `?mode=ro`), and `lakehouse/landing/<source>/` using content-hash watermarks; drop orphaned `logs/surveys.db` from active ingestion.
  3. **Quality Gate (`ADR-0003` updated)**: Single-contract DuckDB SQL `QualityGate` with row-level Quarantine and three-state status (`PASSED`, `PASSED_WITH_QUARANTINE`, `BLOCKED`); GX Core deferred behind the `QualityGate` port.
  4. **Prototype Gold Scope**: Ship 4 Gold Marts (`gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`) while keeping all 6 sources curated in Bronze and Silver.
* **Implementation Stages:**
  * **Stage 1**: Add `duckdb` dependency, `LakehouseConfig`, 6 `SourceAdapter`s, Bronze Parquet partitions, and watermark/manifest ledger.
  * **Stage 2**: Build Silver SQL transforms, single-contract `QualityGate` + Quarantine writer, and `tmp_path`-isolated `pytest` coverage (plus isolating existing API tests from `logs/`).
  * **Stage 3**: Build the 4 Gold Marts, `scripts/run_lakehouse.py`, `frontend/lakehouse_routes.py`, and the 3-panel DuckLake UI tab (`frontend/static/lakehouse.js`).
