# DuckLake Medallion Prototype

*   **Author:** MinnThikeTunn
*   **Status:** Approved
*   **Date:** 2026-11-26

--------------------------------------------------------------------------------

## Overview

The DuckLake Medallion Prototype adds a local Python analytics package (`src/ducklake/`) over the six existing ingestion services (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`, and `telemetry`) without modifying upstream parser code. It reads completed Extraction Runs and SQLite telemetry records into append-only Bronze Parquet partitions, normalizes and deduplicates Entity Records in Silver, routes invalid rows to Quarantine under a single-contract DuckDB SQL Quality Gate, and serves four Gold Marts through a CLI (`scripts/run_lakehouse.py`), a FastAPI router (`frontend/lakehouse_routes.py`), and a DuckLake tab in the web UI (`frontend/static/index.html`) for team review and iteration.

In this repository, "DuckLake" names this local Medallion package and storage directory rather than DuckDB's external `ducklake` catalog extension.

--------------------------------------------------------------------------------

## The Problem

Today, the six ingestion services store outputs in disconnected places with no cross-run deduplication, schema normalization, or quality checks:

1. **Fragmented persistence across services**: `gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, and `survey_extractor` append JSONL entries to `logs/*_log.jsonl`, while `telemetry` writes granular events (including Log Drain webhooks and Beacon events) to `logs/telemetry.db` and truncated 150-row summaries to `logs/telemetry_parser_log.jsonl`. Unused `logs/surveys.db` is not written by `frontend/app.py`.
2. **Duplicate runs and test pollution**: Uploading the same file multiple times or running `pytest` (`tests/test_frontend_api.py`, `tests/test_survey_extractor.py`, `tests/test_telemetry.py`) appends repeated entries into `logs/` (12–26 duplicate lines per log observed in current `logs/` files) and generates new random UUIDs in `logs/telemetry.db`, inflating counts.
3. **Schema mismatches and edge cases in upstream payloads**: Telegram exports include `Service Notice` entries with negative IDs (`id: -1`) and non-ISO dates (`"2 November 2026"`); `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place; YouTube Shorts have `duration_seconds: null`; `database_parser` handles arbitrary table schemas; and OCR logs omit `session_id` and reset `image_index` per batch.
4. **Heavyweight planned stack vs. v1 prototype scope**: `ducklake_medallion_pipeline_plan.md` proposed `dbt-duckdb`, Apache Airflow, Metabase Docker containers, `great-expectations`, and seven Gold Marts (including a Daily Activity Spine). That stack introduces heavy dependencies and Windows DuckDB single-writer file-locking risks before the team reviews Silver schemas.

The proposed solution introduces a standalone `src/ducklake/` module backed by atomic Parquet storage, short-lived `:memory:` DuckDB readers, content-hash watermarks, and a DuckDB SQL Quality Gate so the team can run, inspect, and iterate on validated analytical outputs locally.

--------------------------------------------------------------------------------

## Goals

*   **Zero upstream parser edits**: Keep all six existing packages in `src/` unchanged; consume `logs/*_log.jsonl`, `logs/telemetry.db`, and `lakehouse/landing/<source>/` strictly read-only.
*   **Single new Python dependency**: Add only `duckdb` to `pyproject.toml` and `requirements.txt`, avoiding `great-expectations`, `dbt-core`, and Docker container dependencies in v1.
*   **Lock-free concurrent reads and atomic writes**: Store committed Bronze, Silver, Quarantine, and Gold data as Parquet partitions tracked by `lakehouse/metadata/latest_manifest.json`, serialize Ingestion Batches under an OS-enforced single-writer lock, and serve FastAPI reads via short-lived `:memory:` DuckDB connections off the async event loop.
*   **Idempotent ingestion and deduplicated entities**: Track `(record_key, _payload_hash)` watermarks in Bronze (handling in-place rewrites in `telegram_parser_log.jsonl` and read-only SQLite snapshots of `logs/telemetry.db`), deduplicate Silver Entity Records by natural keys, and tag `_is_test_artifact` records with an explicit boolean flag without filtering them out.
*   **Single-contract Quality Gate with row-level Quarantine**: Run declarative DuckDB SQL validation rules once to route invalid rows to `lakehouse/quarantine/<entity>/` and compute per-entity status (`PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED`), keeping the previous verified Gold snapshot live per mart on `BLOCKED`.
*   **v1 prototype deliverables**: Publish four Gold Marts (`gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`), a CLI runner (`scripts/run_lakehouse.py`), `/api/lakehouse/*` FastAPI routes, a 3-panel DuckLake UI tab, and `tmp_path`-isolated `pytest` tests (including isolating existing API tests from `logs/`).

--------------------------------------------------------------------------------

## Non-Goals

*   **Containerized orchestration and BI deployment**: Docker Compose setup for Apache Airflow, Metabase, or DuckDB HTTP/Arrow servers (`Quack Protocol`) is out of scope for v1 (though an optional `.duckdb` snapshot export keeps future Metabase connection possible).
*   **`dbt-duckdb` scaffolding**: Creating a `dbt_project/` directory or Jinja-SQL macros is deferred.
*   **Runtime `great-expectations` dependency**: Installing GX Core in `requirements.txt` or `pyproject.toml` is deferred behind the `QualityGate` Python interface.
*   **Daily Activity Spine and remaining Gold Marts**: `gold_cross_channel_analytics_mart` (`Daily Activity Spine` requiring SCD Type 2 snapshot deltas), `gold_youtube_video_performance_mart`, `gold_ocr_quality_mart`, and `gold_survey_response_mart` are excluded from Gold in v1 (though all six sources land in Bronze and Silver).
*   **Arbitrary SQL execution in the web UI**: `/api/lakehouse/*` will only expose fixed, read-only Mart and Quarantine queries, never arbitrary user-supplied SQL strings.
*   **Unused `logs/surveys.db` ingestion**: Active ingestion reads `logs/survey_extractor_log.jsonl` rather than `logs/surveys.db`, which `frontend/app.py` does not write to.

--------------------------------------------------------------------------------

## Open Questions

None. Storage layout, adapter interfaces, Quality Gate rules, and API/UI contracts are specified in the Technical Plan below.

--------------------------------------------------------------------------------

## Critical User Journeys (CUJs)

### CUJ 1: Run Incremental Pipeline and Inspect Gold Marts in the UI

*   **Given**: Upstream Extraction Runs exist in `logs/*_log.jsonl`, `logs/telemetry.db`, or `lakehouse/landing/<source>/`, and the FastAPI server (`scripts/start_web.py`) is running.
*   **When**: An operator opens the `DuckLake` tab in `frontend/static/index.html` and triggers an Ingestion Batch (or runs `python scripts/run_lakehouse.py`).
*   **Then**: Bronze ingests only new or content-changed records using SHA-256 watermarks; Silver deduplicates all six sources; the Quality Gate writes invalid rows to `lakehouse/quarantine/<entity>/` and reports `PASSED` or `PASSED_WITH_QUARANTINE`; Gold Parquet partitions and `latest_manifest.json` update atomically; and the UI displays layer counts, gate status, and paginated previews of the four Gold Marts.

### CUJ 2: Quality Gate Blocks a Corrupt Entity Without Breaking Healthy Reads

*   **Given**: A verified Gold snapshot is already committed and referenced per mart in `latest_manifest.json`.
*   **When**: A new Ingestion Batch violates a dataset-level Quality Gate rule for a specific entity (for example, a non-conditional source with `> 0` pre-commit rows leaves `0` valid rows after Quarantine splitting, or a required schema constraint fails).
*   **Then**: The Quality Gate marks that entity `BLOCKED`, records failed rows with `_failure_reason` and `_rule_id` in `lakehouse/quarantine/<entity>/` plus the batch ledger, keeps `latest_manifest.json` pointing to the prior verified Gold snapshot for the affected mart so UI Mart previews stay online (without blocking unrelated healthy marts), and surfaces the `BLOCKED` status and Quarantine table in both CLI output and `/api/lakehouse/*`.

### CUJ 3: Concurrent UI Browsing During CLI Ingestion on Windows

*   **Given**: The FastAPI server is actively serving `/api/lakehouse/*` read requests in `frontend/app.py`.
*   **When**: A developer executes `scripts/run_lakehouse.py` from a separate terminal process at the same time.
*   **Then**: FastAPI read endpoints query committed Parquet files via short-lived `:memory:` DuckDB connections without holding a file lock on a shared `.duckdb` database, while the OS-enforced single-writer batch lock ensures no two Ingestion Batches overlap, preventing Windows DuckDB file-lock `IOException` errors.

### CUJ 4: Isolated Automated Testing Without Contaminating Live Logs

*   **Given**: A developer runs `pytest` locally against the full test suite.
*   **When**: `tests/test_frontend_api.py`, `tests/test_telemetry.py`, `tests/test_survey_extractor.py`, and the new `tests/test_ducklake*.py` execute.
*   **Then**: All log directories, SQLite databases, and lakehouse storage paths are injected into `tmp_path` fixtures so test runs verify end-to-end Bronze, Silver, Quarantine, and Gold behavior without appending test records into `logs/` or modifying `lakehouse/`.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### System Architecture & Data Flow

DuckLake operates as an isolated package (`src/ducklake/`) decoupled from upstream parsers (`src/*`), FastAPI middleware (`frontend/app.py`), and the browser UI. All persisted lakehouse data lives under `lakehouse/` as atomic Parquet datasets indexed by `lakehouse/metadata/latest_manifest.json`.

```text
Upstream Sources (Read-Only)
  ├── logs/*_log.jsonl (5 JSONL streams, copy-before-parse line streaming)
  ├── logs/telemetry.db (copied via sqlite3.Connection.backup())
  └── lakehouse/landing/<source>/*.json
          │
          ▼  [OS-Enforced Single-Writer Batch Lock]
  1. Bronze Adapters (src/ducklake/adapters/)
     • Uniform envelope: _ingest_id, _batch_id, _ingested_at, _source_name, _source_origin_type, _source_file, _record_key, _payload_hash, _is_test_artifact
     • Watermark check: (_record_key, _payload_hash) per source in lakehouse/metadata/watermarks.json
     • Output: lakehouse/bronze/<source>/batch_<batch_id>.parquet (manifest-fenced per source on commit)
          │
          ▼
  2. Single-Pass Silver Transforms & Quarantine Split (DuckDB SQL in :memory: session)
     • Reads only per-source committed_bronze_batches in latest_manifest.json plus each source's active batch
     • Natural-key deduplication (latest _ingested_at wins) + semantic splits (Telegram Service Notice, hybrid DB, EAV survey answers)
     • Evaluates declarative SQL rules once: writes validated Silver Parquet (silver/v_<batch_id>/) and invalid rows (quarantine/<entity>/v_<batch_id>/) in one pass
          │
          ▼
  3. Quality Gate Circuit-Breaker (DuckDBSQLQualityGate)
     • Evaluates dataset-level assertions per entity against pre-commit Silver + Quarantine summaries:
       - PASSED / PASSED_WITH_QUARANTINE -> build Gold mart, advance that source's watermarks + committed_bronze_batches + mart pointer
       - BLOCKED -> delete/unfence only the blocked source's Bronze batch, keep prior Gold mart pointer live, persist Quarantine + BatchRunReport
          │
          ▼
  4. Gold Marts & Optional Snapshot Export
     • Pre-commit & committed: lakehouse/gold/v_<batch_id>/<mart>.parquet
     • Optional export: lakehouse/ducklake.duckdb (materialized tables; temp write + os.replace; non-fatal if locked)
          │
          ▼  [Lock-Free :memory: DuckDB Readers]
  Consumers
     ├── scripts/run_lakehouse.py (CLI)
     └── frontend/lakehouse_routes.py (/api/lakehouse/*) ──▶ frontend/static/lakehouse.js
```

### Component Boundaries

1. **`src/ducklake/` (Core Lakehouse Package — zero FastAPI dependency)**:
   * `config.py`: `LakehouseConfig` holding `logs_dir`, `landing_dir`, `lakehouse_dir`, and `export_duckdb` flag, resolved explicitly from project root or dependency injection (no import-time relative `Path("logs")` globals).
   * `models.py`: Pydantic schemas for `BronzeEnvelope`, `BatchRunReport`, `QualityGateResult`, `QualityCheckResult`, `LayerCounts`, `ManifestState`, `QuarantinePage`, and `MartPreviewResponse`.
   * `adapters/`: `SourceAdapter` protocol (`base.py`), adapter registry (`__init__.py`), and six `SourceAdapter` implementations (`gemini_ocr.py`, `telegram.py`, `database.py`, `youtube.py`, `survey.py`, `telemetry.py`) normalizing varied upstream schemas into uniform Bronze records.
   * `bronze.py`: Manages per-source committed `(_record_key, _payload_hash)` watermarks (handling in-place rewrites in `logs/telegram_parser_log.jsonl` and `sqlite3.Connection.backup()` snapshots of `logs/telemetry.db`), copies and streams JSONL lines in Python to avoid DuckDB's 16 MB JSON object cap and tolerate trailing partial lines, and writes per-source manifest-fenced `batch_<batch_id>.parquet` files (deleting uncommitted Bronze files for any `BLOCKED` source or aborted batch).
   * `silver.py`: Executes DuckDB SQL over per-source committed Bronze Parquet files inside a short-lived `:memory:` DuckDB session to compute deduplicated Silver tables and feed single-pass Quality Gate + Quarantine materialization under `lakehouse/silver/v_<batch_id>/`.
   * `quality.py`: Defines the `QualityGate` protocol and `DuckDBSQLQualityGate` implementation. Evaluates declarative SQL check definitions in one pass alongside Silver transforms to emit `lakehouse/quarantine/<entity>/v_<batch_id>/quarantine.parquet` (with `_batch_id`, `_rule_id`, `_failure_reason`, `_quarantined_at`, `raw_payload_json`) and determine per-entity `PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED` (conditional empty tables with `0` input rows pass, while non-conditional entities with `> 0` pre-commit rows and `0` valid rows remaining trigger `BLOCKED` for that entity's Gold Mart).
   * `gold.py`: Builds the four v1 Gold Marts under `lakehouse/gold/v_<batch_id>/` from validated Silver data (including `_is_test_artifact` records so Gold Marts populate on test datasets) and optionally exports materialized tables to `lakehouse/ducklake.duckdb`.
   * `service.py`: `LakehouseService` facade shared by CLI and FastAPI. Acquires an exclusive cross-process OS file lock (`lakehouse/metadata/write.lock` via `msvcrt.locking` / `fcntl.flock`) for `run_batch()`, atomically commits per-source `watermarks.json`, `latest_manifest.json` (per-mart/entity pointers + per-source `committed_bronze_batches`), and `runs_history.jsonl`, pins active manifest versions during `keep_last=2` cleanup, and serves read queries (`get_status()`, `list_runs()`, `get_quarantine()`, `get_mart_preview()`) using short-lived `:memory:` DuckDB connections (skipping malformed lines when reading `runs_history.jsonl`).

2. **CLI & FastAPI Surface**:
   * `scripts/run_lakehouse.py`: Thin CLI entrypoint invoking `LakehouseService.run_batch()` and printing structured summaries (exit code `0` for `PASSED`/`PASSED_WITH_QUARANTINE`, `2` for `BLOCKED`, `1` for unexpected error).
   * `frontend/lakehouse_routes.py`: FastAPI `APIRouter` mounted into `frontend/app.py` at `/api/lakehouse/*`:
     * `POST /api/lakehouse/run`: Runs the blocking `run_batch()` call inside `asyncio.to_thread` under the single-writer lock, returning `200 OK` with `BatchRunReport` (or `409 Conflict` if another batch holds the lock).
     * `GET /api/lakehouse/status`: Returns current `ManifestState` (including `latest_status` and `layer_counts`; per-check `QualityGateResult` details are returned on `BatchRunReport` via `/run` and `/runs`).
     * `GET /api/lakehouse/runs`: Returns paginated `BatchRunReport` history.
     * `GET /api/lakehouse/quarantine`: Returns paginated quarantined rows filtered by allowlisted `entity` and regex-validated (`^[a-f0-9_-]+$`) `batch_id`.
     * `GET /api/lakehouse/marts/{mart_name}`: Returns paginated rows (`limit <= 200`, `offset`) and column metadata for the four allowed Gold Marts (`404` for unknown mart names; no arbitrary SQL input).

3. **Frontend UI (`frontend/static/`)**:
   * `frontend/static/index.html` & `frontend/static/style.css`: Updates header container (`min-h-16 py-2`) and switcher (`flex-wrap`), and adds `tabDuckLake` + `viewDuckLake` matching the `rounded-[32px]` / `font-black` styling of existing dashboard tabs without altering the existing six service views.
   * `frontend/static/lakehouse.js` + `frontend/static/app.js`: Hooks `"ducklake"` into `setupNavigation()`, `switchService()`, and `toggleActiveHistory()`, keeping all DuckLake fetch/render logic isolated in `lakehouse.js` with XSS-safe DOM rendering (`textContent` / HTML escaping) across three panels (Pipeline Trigger & Layer Counts, Quality Gate & Quarantine Inspector, Gold Mart Table Preview) plus the toggleable Run History section.

### Per-Source Silver Modeling, Deduplication Keys & Quality Rules

*   **`gemini_ocr` → `silver_ocr_extractions`**: Computes run-scoped `_record_key = SHA256(date, files, content)` and deduplicates within each Extraction Run on `(_record_key, filename, image_index)` after normalizing `filename` to basename (`Path(filename).name`), so distinct timed OCR runs remain preserved as separate audit records while repeated log scans collapse. Maps `text` and `confidence`; tags `content == 'Test OCR Prompt'` as `_is_test_artifact`; quarantines records containing an `"error"` key or `confidence` outside `[0.0, 1.0]`.
*   **`telegram_parser` → `silver_telegram_messages`, `silver_telegram_service_notices`, `silver_telegram_reactions`**: Separates `type == 'service'` entries (`Service Notice`, negative `id`, human-readable `date`) into `silver_telegram_service_notices` before message checks. Deduplicates user messages on `(chat_title, message_id)` and reactions in `silver_telegram_reactions` on `(chat_title, message_id, emoji)` storing `count` and `users_json`. Tags `export_source == 'messages.html'` with `chat_title == 'Min Thike Tun'` as `_is_test_artifact`; allows empty `text` on media messages; quarantines user messages with unparseable `date` or negative `reaction_count`.
*   **`database_parser` → Hybrid (`silver_database_tables` [key: `(database_name, table_name)`], `silver_database_rows` [key: `(database_name, table_name, _row_hash)`] + conditional `silver_sales_customers` [key: `customer_id`, fields: `customer_id`, `customer_name` via `COALESCE(name, customer_name)`, `segment` via `COALESCE(segment, 'unknown')`], `silver_sales_orders` [key: `order_id`, fields: `order_id`, `customer_id`, `order_date`, `total_amount` via `COALESCE(total_amount, order_amount)`])**: Always records table metadata and row JSON payloads. When exported tables match conforming sales schemas (`customers`; `sales_table`/`sales`/`orders` containing `order_id` and `total_amount`/`order_amount`), projects conformed `silver_sales_*` tables and quarantines rows with null `order_id` or `total_amount <= 0`. Tags `export_source == 'sales_database.sql'` runs as `_is_test_artifact`.
*   **`youtube_parser` → `silver_youtube_channels`, `silver_youtube_videos`**: Deduplicates channels by `COALESCE(channel_id, handle, channel_name)` and videos by `video_id`. Tags `channel_name == 'TechPulse Explains'` or `source == 'sample_channel.html'` as `_is_test_artifact`. Permits `NULL` `duration_seconds` and `view_count` (supporting Shorts and premieres); quarantines negative `duration_seconds < 0` or `view_count < 0`.
*   **`survey_extractor` → `silver_surveys` (`survey_id`), `silver_survey_questions` (`(survey_id, question_id)`), `silver_survey_responses` (`(survey_id, response_id)`), `silver_survey_answers` (`(survey_id, response_id, question_id)`)**: Reads `logs/survey_extractor_log.jsonl` (coalescing `data.responses` with fallback to legacy `data.sample_responses`) and normalizes `answers` into long-form Entity-Attribute-Value (EAV) rows. Tags `title == 'API Test Survey'` or `file_name == 'survey_test.csv'` as `_is_test_artifact`. Quarantines truncated survey Extraction Run records (captured responses `< metadata.valid_responses`, which flags truncated historical Extraction Runs) into `lakehouse/quarantine/survey_runs/` as `PASSED_WITH_QUARANTINE` so complete survey runs still promote.
*   **`telemetry` → `silver_telemetry_events`**: Snapshots `logs/telemetry.db` (`telemetry_events`) via `sqlite3.Connection.backup()`. Deduplicates on composite natural key `(site_id, timestamp, path, method, visitor_hash, session_id, status_code, latency_ms)` to collapse duplicate UUID re-uploads; tags `site_id IN ('upload_test', 'test_site', 'vercel_sample')` as `_is_test_artifact`; quarantines status codes outside `[100, 599]` or negative `latency_ms`.

### Gold Mart Definitions (v1)

1. **`gold_ingestion_overview`**: Per-source summary of raw Bronze records, deduplicated Silver Entity Records (using one representative entity per source: `ocr_extractions`, `telegram_messages`, `database_rows`, `youtube_videos`, `surveys`, `telemetry_events`), quarantined rows, `_is_test_artifact` count, and latest `_ingested_at` (`NULL` when empty).
2. **`gold_sales_kpi_mart`**: Daily (`order_date`) and customer-segment (`LEFT JOIN silver_sales_customers ON customer_id`, defaulting missing customers/segments to `'unknown'`) order count, gross revenue, and average order value computed from `silver_sales_orders` (returns an empty result set without error if no conforming sales tables exist).
3. **`gold_telegram_engagement_mart`**: Per-chat and per-sender (`COALESCE(NULLIF(from_name, ''), 'Unknown')`) message volume, reply count, media attachment count, and reaction totals (`SUM(reaction_count)`) computed strictly from non-`Service Notice` records.
4. **`gold_web_traffic_mart`**: Daily per-`site_id` pageviews, unique deduplicated `visitor_hash` count, `session_id` count, median/P95 latency (`quantile_cont` filtered to `source_mode != 'beacon'` so zero-latency client beacons do not skew server percentiles), and 4xx/5xx error rate from `silver_telemetry_events`.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Full Enterprise Stack (`dbt-duckdb` + Apache Airflow + Metabase Docker)

*   **Pros**: Provides scheduled DAG orchestration, built-in dbt lineage documentation, and standalone Metabase BI dashboards.
*   **Cons**: Requires Docker Compose runtime overhead, `dbt-core` transitive dependencies, and container setup before the team agrees on Silver schemas and Gold metrics.
*   **Reason for Rejection**: Rejected by author ([`docs/adr/0001-pure-duckdb-sql-over-dbt-and-docker.md`](../adr/0001-pure-duckdb-sql-over-dbt-and-docker.md)): for a v1 local prototype intended for local team review and iteration, pure DuckDB SQL and Parquet keep `pytest` and FastAPI dependencies minimal while remaining portable to `dbt-duckdb`, Airflow, and Metabase later.

### Alternative B: Persistent Shared Read/Write `lakehouse/ducklake.duckdb`

*   **Pros**: Stores Bronze, Silver, and Gold as native DuckDB tables in one file with persistent indexes and simpler SQL table updates.
*   **Cons**: DuckDB enforces exclusive single-writer file locking across OS processes on Windows, causing `IOException` lock errors whenever CLI Ingestion Batches (`scripts/run_lakehouse.py`) overlap with FastAPI `/api/lakehouse/*` queries.
*   **Reason for Rejection**: Rejected by author: compute-storage separation using atomic Parquet snapshots + `latest_manifest.json` + short-lived `:memory:` DuckDB readers eliminates cross-process file-lock collisions while still supporting an optional `.duckdb` snapshot export.

### Alternative C: Runtime `great-expectations` (GX Core) + Separate Row Splitter

*   **Pros**: Emits standardized GX Validation Results and Data Docs HTML artifacts.
*   **Cons**: `great-expectations` is not in `pyproject.toml`, pulls heavy runtime dependencies (`pandas`, `numpy`, `scipy`, `sqlalchemy`), and duplicates validation rules because invalid rows must already be split out in SQL/Python before GX validates validated Silver tables ([`docs/adr/0003-row-level-quarantine-before-gx-gate.md`](../adr/0003-row-level-quarantine-before-gx-gate.md)).
*   **Reason for Rejection**: Rejected by author: declarative DuckDB SQL assertions behind a narrow `QualityGate` protocol deliver row-level Quarantine and batch circuit-breaking in one pass with `duckdb` as the only new dependency; GX Core can be wired later behind the same interface.

### Alternative D: Intrusive Lakehouse Hooks Inside Existing `src/` Parsers

*   **Pros**: Upstream services could write directly to Bronze on each parse without scanning `logs/`.
*   **Cons**: Couples all six existing ingestion packages and `frontend/app.py` to lakehouse schemas and risks regressions in already-tested services.
*   **Reason for Rejection**: Rejected by author ([`docs/adr/0002-pull-logs-and-sqlite-without-modifying-parsers.md`](../adr/0002-pull-logs-and-sqlite-without-modifying-parsers.md)): pulling read-only from `logs/*_log.jsonl`, `logs/telemetry.db`, and `lakehouse/landing/<source>/` keeps all six upstream `src/` packages untouched.

### Alternative E: Byte-Offset / Line-Count Incremental Cursors for JSONL Logs

*   **Pros**: Avoids re-hashing unchanged JSONL prefix lines on append-only logs.
*   **Cons**: `POST /api/telegram/attach-photos` (`frontend/app.py`) rewrites `logs/telegram_parser_log.jsonl` in place, which breaks byte offsets and skips updated media URLs without error.
*   **Reason for Rejection**: Rejected by author: tracking `(_record_key, _payload_hash)` content hashes detects in-place file rewrites without missing updates and avoids external cursor state for local JSONL logs.

### Alternative F: Asynchronous `202 Accepted` Batch Execution with Polling

*   **Pros**: Prevents HTTP request timeouts if batches grow beyond 30–60 seconds.
*   **Cons**: Adds a background job state machine, stale-lock crash recovery, and polling logic in `frontend/static/lakehouse.js`.
*   **Reason for Rejection**: Rejected by author: running `run_batch()` inside `asyncio.to_thread` returning `BatchRunReport` matches the existing FastAPI service pattern and avoids background job state and polling logic for local datasets.

### Alternative G: Filter Out `_is_test_artifact` Rows from Domain Gold Marts by Default

*   **Pros**: Keeps business KPIs free of historical `pytest` fixtures sitting in `logs/`.
*   **Cons**: Domain Gold Marts would show zero rows by default when `logs/` contains only test runs unless the operator toggles a flag or wipes `logs/`, and heuristic test detection risks hiding real uploads that reuse sample names.
*   **Reason for Rejection**: Rejected by author: keeping `_is_test_artifact` explicitly tagged in `gold_ingestion_overview` while including all validated Silver records in domain Gold Marts displays non-empty Gold Marts without manual seed configuration while isolating `pytest` going forward.

### Alternative H: All Seven Gold Marts + Daily Activity Spine in v1

*   **Pros**: Covers every source-specific mart and cross-source timeline sketched in `ducklake_medallion_pipeline_plan.md`.
*   **Cons**: Current `logs/` spans disconnected years (2024 survey tests vs. 2026 chat/web tests), YouTube `view_count` is a cumulative snapshot rather than a daily event count, and wide survey pivoting adds unvalidated schema complexity before Silver schema sign-off.
*   **Reason for Rejection**: Rejected by author: trimming v1 Gold to `gold_ingestion_overview` plus three domain marts (`gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`) avoids misleading cross-channel numbers while preserving all six sources in Bronze and Silver.

### Alternative I: Incremental Partitioned Silver/Gold Merges vs. Full-Bronze Recomputation

*   **Pros**: Avoids re-scanning historical Bronze Parquet partitions on every Ingestion Batch when datasets scale into gigabytes.
*   **Cons**: Requires incremental CDC/upsert state per Silver table, complex late-arriving reaction/reply updates, and partial Gold recomputation logic.
*   **Reason for Rejection**: Rejected by author: at local prototype dataset sizes, stateless full-Bronze `:memory:` DuckDB SQL recomputation eliminates incremental state bugs and keeps Silver/Gold transforms simple to modify after team review.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Concurrency & Process Safety**: Write operations acquire an OS-enforced advisory file lock on `lakehouse/metadata/write.lock` (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX, failing fast with `409 Conflict` in FastAPI if held) and commit to new `v_<batch_id>` directories before atomically updating `latest_manifest.json` via temp-file `os.replace`. FastAPI read endpoints run in `asyncio.to_thread` (or sync `def` handlers) using short-lived `:memory:` DuckDB connections so the Uvicorn event loop never blocks.
*   **Performance & Memory Bounds**: JSONL ingestion copies and streams files line-by-line in Python to avoid DuckDB's 16 MB `read_json_auto` `maximum_object_size` limit and tolerate trailing partial lines; `/api/lakehouse/marts/{mart_name}` and `/api/lakehouse/quarantine` enforce pagination (`limit <= 200`, default `50`) to bound HTTP payload size and DOM row count.
*   **Security & Privacy**: No arbitrary SQL query endpoint is exposed; `mart_name` is validated against an allowlist (`gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`), `entity` and `batch_id` are strictly validated (allowlist + `^[a-f0-9_-]+$`), and read-only `sqlite3.Connection.backup()` snapshots avoid acquiring write locks on or mutating `logs/telemetry.db`.
*   **Rollout & Rollback**: Because each Silver/Quarantine/Gold batch writes to a new `v_<batch_id>` directory, rolling back a failed Ingestion Batch only requires pointing `latest_manifest.json` to the prior verified `batch_id` (and `BLOCKED` entities never advance their Gold mart pointer).

--------------------------------------------------------------------------------

## Risks & Mitigations

*   **Bronze vs. Watermark Split-Brain on `BLOCKED` or Mid-Batch Failure**:
    *   *Risk*: Writing Bronze Parquet before Silver/Quality Gate finishes could leave corrupt or duplicate uncommitted files in `lakehouse/bronze/` if a batch crashes or is `BLOCKED`.
    *   *Mitigation*: Silver scans only `committed_bronze_batches` registered in `latest_manifest.json` plus the active batch; uncommitted `batch_<batch_id>.parquet` files from `BLOCKED` or aborted runs are deleted/excluded, and `watermarks.json` + `latest_manifest.json` advance atomically only on successful commit.
*   **Stale `write.lock` & Windows Open-Handle Contention**:
    *   *Risk*: A crashed CLI process could leave a stale lockfile, or Windows could raise `PermissionError` when cleaning up `v_<batch_id>` directories or replacing `lakehouse/ducklake.duckdb` while read handles are open.
    *   *Mitigation*: `write.lock` uses OS-enforced non-blocking locks (`msvcrt.locking` / `fcntl.flock`) that auto-release on process exit; retention cleanup (`keep_last=2`) skips directories pinned by `latest_manifest.json` and catches transient Windows `PermissionError`s on old directories and optional `.duckdb` exports without failing the batch.
*   **Torn JSONL Reads During Concurrent `frontend/app.py` Writes**:
    *   *Risk*: `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place without locking, risking partial-line reads if `run_batch()` executes concurrently.
    *   *Mitigation*: Adapters copy each JSONL file into a temporary read buffer before line-by-line parsing and skip/retry trailing incomplete JSON lines instead of crashing.
*   **Local Scalability Limits & Synchronous HTTP Ceiling**:
    *   *Risk*: Full-Bronze recomputation in `:memory:` DuckDB and synchronous `POST /api/lakehouse/run` execution degrade once raw logs exceed hundreds of megabytes.
    *   *Mitigation*: Prototype bounds are documented as ~100 MB raw logs / ~500k events with DuckDB `memory_limit` configured explicitly; beyond this ceiling, move to incremental Silver merges (`Alternative I`) and async `202` runs (`Alternative F`).
*   **Local-Only Trust Boundary & Frontend XSS**:
    *   *Risk*: `frontend/app.py` permits `allow_origins=["*"]` with no auth, exposing `/api/lakehouse/*` triggers and user-supplied Quarantine strings to local origin requests or DOM injection.
    *   *Mitigation*: Document local-dev (`127.0.0.1`) runtime trust scope matching `frontend/app.py`, enforce single-writer `409` lock protection, validate all query parameters (`entity`, `batch_id`, `mart_name`), and render all dynamic values in `lakehouse.js` via `textContent` / HTML escaping.

--------------------------------------------------------------------------------

## Additional Resources

*   [`concepts_brief.md`](../../concepts_brief.md) — brainstorm synthesis and resolved contradictions
*   [`ducklake_medallion_pipeline_plan.md`](../../ducklake_medallion_pipeline_plan.md) — original enterprise Medallion blueprint (superseded for v1 by this prototype design)
*   [`CONTEXT-MAP.md`](../../CONTEXT-MAP.md), [`src/CONTEXT.md`](../../src/CONTEXT.md), [`src/ducklake/CONTEXT.md`](../../src/ducklake/CONTEXT.md) — bounded contexts and ubiquitous language
*   [`docs/adr/`](../adr) — Architecture Decision Records ([`0001`](../adr/0001-pure-duckdb-sql-over-dbt-and-docker.md), [`0002`](../adr/0002-pull-logs-and-sqlite-without-modifying-parsers.md), [`0003`](../adr/0003-row-level-quarantine-before-gx-gate.md)) covering pure DuckDB SQL, read-only log/SQLite pulling, and single-contract Quality Gate

--------------------------------------------------------------------------------

## Future Improvements

*   **Optional GX Core Adapter**: Implement `GreatExpectationsQualityGate` behind `QualityGate` if the team needs Data Docs HTML reports after schema sign-off.
*   **SCD Type 2 Daily Activity Spine**: Track daily deltas (`LAG()`) on cumulative sources (`youtube_parser`, `database_parser`) in Silver to enable accurate daily deltas for `gold_cross_channel_analytics_mart` (`Daily Activity Spine`).
*   **Additional Domain Gold Marts**: Add `gold_youtube_video_performance_mart`, `gold_ocr_quality_mart`, and `gold_survey_response_mart` once Silver schemas are signed off.
*   **Airflow & Metabase Integration**: Wrap `scripts/run_lakehouse.py --export-duckdb` in Dockerized Airflow DAGs and connect Metabase to the exported `lakehouse/ducklake.duckdb` snapshot.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

The implementation is partitioned into three incremental phases, each leaving the codebase buildable and verifiable before advancing.

### Phase 1: Packaging, Configuration, Models, Adapters & Bronze Ingestion

#### 1. [`pyproject.toml`](../../pyproject.toml) (Modify)

*   **Type / Scope**: Python packaging configuration.
*   **Proposed Changes & Rationale**: Add `"duckdb>=1.1.0"` to `dependencies`. Required so DuckLake executes Parquet reads/writes and SQL transforms locally without `great-expectations`, `dbt-core`, or container dependencies.

#### 2. [`requirements.txt`](../../requirements.txt) (Modify)

*   **Type / Scope**: Pip requirements list.
*   **Proposed Changes & Rationale**: Add `duckdb>=1.1.0` to stay aligned with `pyproject.toml`.

#### 3. [`.gitignore`](../../.gitignore) (Modify)

*   **Type / Scope**: Git ignore rules.
*   **Proposed Changes & Rationale**: Add `lakehouse/` so generated Bronze, Silver, Quarantine, Gold Parquet partitions, lock files, manifests, and `.duckdb` snapshots stay untracked like `logs/` and `frontend/uploads/`.

#### 4. [`src/ducklake/__init__.py`](../../src/ducklake/__init__.py) (Create)

*   **Type / Scope**: Python package entrypoint.
*   **Proposed Changes & Rationale**: Export `ALLOWED_MARTS`, `ALLOWED_SOURCES`, `BatchRunReport`, `LakehouseConfig`, `LakehouseLockError`, `LakehouseService`, `ManifestState`, `QualityGateResult`, and `QualityStatus` so CLI, FastAPI, and tests share one public package interface.

#### 5. [`src/ducklake/config.py`](../../src/ducklake/config.py) (Create)

*   **Type / Scope**: Frozen configuration dataclass.
*   **Proposed Changes & Rationale**: Define `@dataclass(frozen=True) class LakehouseConfig` with fields:
    *   `project_root: Path = Path(__file__).resolve().parents[2]`
    *   `logs_dir: Path | None = None` (defaults to `project_root / "logs"`)
    *   `landing_dir: Path | None = None` (defaults to `lakehouse_dir / "landing"`)
    *   `lakehouse_dir: Path | None = None` (defaults to `project_root / "lakehouse"`)
    *   `export_duckdb: bool = False`
    *   `memory_limit: str = "512MB"`
    *   `keep_last: int = 2`
    *   Properties: `bronze_dir`, `silver_dir`, `quarantine_dir`, `gold_dir`, `metadata_dir`, `manifest_path`, `watermarks_path`, `runs_history_path`, `write_lock_path`, `duckdb_snapshot_path`.

#### 6. [`src/ducklake/models.py`](../../src/ducklake/models.py) (Create)

*   **Type / Scope**: Pydantic v2 data contracts.
*   **Proposed Changes & Rationale**: Define exact schemas and constants:
    *   `ALLOWED_SOURCES: tuple[str, ...]` = `("gemini_ocr", "telegram_parser", "database_parser", "youtube_parser", "survey_extractor", "telemetry")`
    *   `ALLOWED_MARTS: tuple[str, ...]` = `("gold_ingestion_overview", "gold_sales_kpi_mart", "gold_telegram_engagement_mart", "gold_web_traffic_mart")`
    *   `QUARANTINE_ENTITIES: tuple[str, ...]` = `("ocr_extractions", "telegram_messages", "sales_orders", "youtube_videos", "survey_runs", "telemetry_events")`
    *   `QualityStatus(str, Enum)`: `"PASSED"`, `"PASSED_WITH_QUARANTINE"`, `"BLOCKED"`.
    *   `BronzeEnvelope`: `_ingest_id: str`, `_batch_id: str`, `_ingested_at: str` (UTC ISO), `_source_name: str`, `_source_origin_type: Literal["jsonl", "sqlite", "landing_json"]`, `_source_file: str` (filename relative to source root), `_record_key: str`, `_payload_hash: str`, `_is_test_artifact: bool`, `payload_json: str`.
    *   `SourceIngestSummary`: `source_name: str`, `scanned_count: int`, `ingested_count: int`, `skipped_unchanged_count: int`, `bronze_file: Optional[str] = None`.
    *   `QualityCheckResult`: `entity: str`, `_rule_id: str`, `status: QualityStatus`, `pre_commit_rows: int`, `valid_rows: int`, `quarantined_rows: int`, `message: str = ""`.
    *   `QualityGateResult`: `overall_status: QualityStatus`, `entity_statuses: dict[str, QualityStatus]`, `checks: list[QualityCheckResult]`, `total_quarantined: int`.
    *   `LayerCounts`: `bronze_by_source: dict[str, int]`, `silver_by_entity: dict[str, int]`, `quarantine_by_entity: dict[str, int]`, `gold_by_mart: dict[str, int]`.
    *   `MartPointer`: `mart_name: str`, `batch_id: str`, `parquet_path: str`, `row_count: int`, `updated_at: str`.
    *   `ManifestState`: `schema_version: int = 1`, `latest_batch_id: Optional[str] = None`, `latest_status: Optional[QualityStatus] = None`, `updated_at: Optional[str] = None`, `committed_bronze_batches: dict[str, list[str]]` (per source), `silver_versions: dict[str, str]` (entity -> `v_<batch_id>` dir), `quarantine_batches: dict[str, list[str]]` (entity -> batch paths), `marts: dict[str, MartPointer]`, `layer_counts: LayerCounts`.
    *   `BatchRunReport`: `batch_id: str` (lowercase `YYYYmmdd_HHMMSS_<8hex>`, matching `^[a-f0-9_-]+$`), `started_at: str`, `completed_at: str`, `full_refresh: bool`, `overall_status: QualityStatus`, `sources: list[SourceIngestSummary]`, `quality: QualityGateResult`, `layer_counts: LayerCounts`, `exported_duckdb_path: Optional[str] = None`, `warnings: list[str] = Field(default_factory=list)`.
    *   `RunBatchRequest`: `sources: Optional[list[str]] = None`, `full_refresh: bool = False`, `export_duckdb: Optional[bool] = None`.
    *   `QuarantinePage`: `total: int`, `limit: int`, `offset: int`, `entities: list[str]`, `rows: list[dict[str, Any]]`.
    *   `MartPreviewResponse`: `mart_name: str`, `batch_id: Optional[str]`, `total: int`, `limit: int`, `offset: int`, `columns: list[str]`, `rows: list[dict[str, Any]]`.

#### 7. [`src/ducklake/adapters/base.py`](../../src/ducklake/adapters/base.py) (Create)

*   **Type / Scope**: `SourceAdapter` protocol and streaming/hashing helpers.
*   **Proposed Changes & Rationale**:
    *   Define `SourceAdapter(Protocol)` with `source_name: str` and `read_records(config: LakehouseConfig, batch_id: str, ingested_at: str) -> list[BronzeEnvelope]`.
    *   Implement canonical SHA-256 hashing (`hash_payload(obj)` via `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`).
    *   Implement `iter_jsonl_records(path: Path)`: copies `path` bytes into a temporary memory buffer before splitting lines so concurrent `frontend/app.py` rewrites do not cause torn reads, parses lines in Python (supporting objects exceeding DuckDB's 16 MB `maximum_object_size`), and skips blank or trailing incomplete JSON lines while logging a warning.
    *   Implement `iter_landing_records(landing_dir: Path, source_name: str)`: reads `landing_dir / source_name / "*.json"`, unwrapping both single JSON objects and top-level JSON arrays; individual adapters unwrap `record.get("data", record)` (or `recent_events` for `telemetry`) where upstream CLI exports omit the log wrapper.

#### 8. [`src/ducklake/adapters/gemini_ocr.py`](../../src/ducklake/adapters/gemini_ocr.py) (Create)

*   **Type / Scope**: Upstream adapter for `gemini_ocr`.
*   **Proposed Changes & Rationale**: Read `logs/gemini_ocr_log.jsonl` (`_source_origin_type="jsonl"`) and `landing_dir/gemini_ocr/*.json` (`"landing_json"`). Compute `_record_key = sha256((date, files, content))` because `GeminiRespond` lacks `session_id`; normalize `filename` inside `respond[]` during Silver to `Path(filename).name`; tag `content == "Test OCR Prompt"` as `_is_test_artifact = True`.

#### 9. [`src/ducklake/adapters/telegram.py`](../../src/ducklake/adapters/telegram.py) (Create)

*   **Type / Scope**: Upstream adapter for `telegram_parser`.
*   **Proposed Changes & Rationale**: Read `logs/telegram_parser_log.jsonl` and `landing_dir/telegram_parser/*.json`. Key by `session_id` when present, falling back to `sha256((chat_title, export_source, len(messages)))` for standalone CLI outputs. Because `POST /api/telegram/attach-photos` rewrites `telegram_parser_log.jsonl` in place, updated media URLs change `_payload_hash` and re-ingest idempotently. Tag `export_source == "messages.html"` and `chat_title == "Min Thike Tun"` as `_is_test_artifact = True`.

#### 10. [`src/ducklake/adapters/database.py`](../../src/ducklake/adapters/database.py) (Create)

*   **Type / Scope**: Upstream adapter for `database_parser`.
*   **Proposed Changes & Rationale**: Read `logs/database_parser_log.jsonl` and `landing_dir/database_parser/*.json`, unwrapping `record.get("data", record)` to handle raw `DatabaseExportResult` CLI files. Key by `session_id`, falling back to `sha256((database_name, export_source, total_rows))`. Tag `export_source == "sales_database.sql"` as `_is_test_artifact = True`.

#### 11. [`src/ducklake/adapters/youtube.py`](../../src/ducklake/adapters/youtube.py) (Create)

*   **Type / Scope**: Upstream adapter for `youtube_parser`.
*   **Proposed Changes & Rationale**: Read `logs/youtube_parser_log.jsonl` and `landing_dir/youtube_parser/*.json`, unwrapping `record.get("data", record)` for standalone `YouTubeChannelExportResult` CLI outputs. Key by `session_id`, falling back to `COALESCE(channel_id, handle, channel_name)` concatenated with `scraped_at`. Tag `channel_info.channel_name == "TechPulse Explains"` or `source == "sample_channel.html"` as `_is_test_artifact = True`.

#### 12. [`src/ducklake/adapters/survey.py`](../../src/ducklake/adapters/survey.py) (Create)

*   **Type / Scope**: Upstream adapter for `survey_extractor`.
*   **Proposed Changes & Rationale**: Read `logs/survey_extractor_log.jsonl` and `landing_dir/survey_extractor/*.json` (omitting unused `logs/surveys.db`, which `frontend/app.py` does not write to). Unwrap `record.get("data", record)`; key by `(survey_id, timestamp)` falling back to `(survey_id, metadata.created_at)` for raw `SurveyExtractResult` landing files. Tag `metadata.title == "API Test Survey"` or `metadata.file_name == "survey_test.csv"` as `_is_test_artifact = True`.

#### 13. [`src/ducklake/adapters/telemetry.py`](../../src/ducklake/adapters/telemetry.py) (Create)

*   **Type / Scope**: Upstream adapter for `telemetry`.
*   **Proposed Changes & Rationale**: Snapshot `logs/telemetry.db` (`telemetry_events` table) using `sqlite3.connect(uri=True)` (`?mode=ro`) with `src_conn.backup(mem_conn)` into an `:memory:` SQLite connection (avoiding `SQLITE_BUSY` with FastAPI WAL writes), bypassing `logs/telemetry_parser_log.jsonl` to prevent 150-row truncation and double counting; also read optional `landing_dir/telemetry/*.json` (`TelemetryDashboardPayload.recent_events` or raw `TelemetryEvent` lists). Key each event by `_record_key = str(id)` with `_payload_hash` computed over all event columns, and tag `site_id in {"upload_test", "test_site", "vercel_sample"}` as `_is_test_artifact = True`.

#### 14. [`src/ducklake/adapters/__init__.py`](../../src/ducklake/adapters/__init__.py) (Create)

*   **Type / Scope**: Adapter registry.
*   **Proposed Changes & Rationale**: Export `ADAPTERS: dict[str, SourceAdapter]`, `get_adapter(name: str) -> SourceAdapter`, and `get_all_adapters() -> list[SourceAdapter]` covering all six services.

#### 15. [`src/ducklake/bronze.py`](../../src/ducklake/bronze.py) (Create)

*   **Type / Scope**: Bronze ingestion and per-source watermark manager.
*   **Proposed Changes & Rationale**:
    *   Metadata schemas: `watermarks.json` stores `{"sources": {"<source_name>": {"<_record_key>": "<_payload_hash>"}}}`.
    *   `stage_bronze_batch(config, adapters, batch_id, ingested_at, watermarks, full_refresh)`: collects `BronzeEnvelope`s; when `full_refresh=False`, filters out records whose `_record_key` already maps to the identical `_payload_hash` in `watermarks["sources"][source_name]`.
    *   If a source has `> 0` new/updated records, writes `lakehouse/bronze/<source>/batch_<batch_id>.parquet` via `:memory:` DuckDB; if `0` new records, writes no empty Parquet file (`bronze_file=None`). Returns per-source new watermark deltas without mutating `watermarks.json` until post-Quality Gate commit.

*   **Phase 1 Checkpoint**: `pip install -e . --no-deps`, verify `python -c "import duckdb, ducklake"`, and confirm Bronze unit tests ingesting isolated `tmp_path` fixtures write expected `BronzeEnvelope` Parquet files and skip unchanged records on repeat runs.

---

### Phase 2: Silver SQL, Single-Pass Quality Gate, Gold Marts, Orchestrator & Test Isolation

#### 16. [`src/ducklake/silver.py`](../../src/ducklake/silver.py) and [`src/ducklake/quality.py`](../../src/ducklake/quality.py) (Create)

*   **Type / Scope**: Single-pass Silver DuckDB SQL transformations, Quality Gate, and Quarantine writer.
*   **Proposed Changes & Rationale**:
    *   Define `QualityGate(Protocol)` and `DuckDBSQLQualityGate` in `quality.py`, executed inside the same short-lived `:memory:` DuckDB session (`SET memory_limit = ...`) as `silver.py` so each entity is classified and written to Parquet **once** (no double Silver rewrite).
    *   `silver.py` scans only `manifest.committed_bronze_batches[source]` plus that source's staged `batch_<batch_id>.parquet` to build typed `:memory:` TEMP tables, while `quality.py` materializes all Silver Parquet files (emitting empty 0-row typed Parquet files when a source has zero Bronze batches).
    *   Exact Silver column contracts and deduplication keys (latest `_ingested_at` wins via `ROW_NUMBER()`):
        *   `silver_ocr_extractions`: `(run_key VARCHAR, filename VARCHAR, image_index INTEGER, text VARCHAR, language VARCHAR, confidence DOUBLE, error_message VARCHAR, processed_at TIMESTAMPTZ, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `(run_key, filename, image_index)` with `filename = Path(f).name`.
        *   `silver_telegram_service_notices`: `(chat_title VARCHAR, message_id BIGINT, notice_date_text VARCHAR, notice_text VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — `type = 'service'` separated before message checks.
        *   `silver_telegram_messages`: `(chat_title VARCHAR, message_id BIGINT, from_name VARCHAR, message_ts TIMESTAMPTZ, reply_to_message_id BIGINT, forwarded_from VARCHAR, text VARCHAR, has_media BOOLEAN, media_type VARCHAR, media_path VARCHAR, reaction_count INTEGER, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `(chat_title, message_id)`.
        *   `silver_telegram_reactions`: `(chat_title VARCHAR, message_id BIGINT, emoji VARCHAR, reaction_count INTEGER, users_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ)` — key `(chat_title, message_id, emoji)`.
        *   `silver_database_tables`: `(database_name VARCHAR, table_name VARCHAR, format VARCHAR, row_count INTEGER, columns_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `(database_name, table_name)`.
        *   `silver_database_rows`: `(database_name VARCHAR, table_name VARCHAR, _row_hash VARCHAR, row_payload_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `(database_name, table_name, _row_hash)`.
        *   `silver_sales_customers` *(conditional)*: `(customer_id VARCHAR, customer_name VARCHAR, segment VARCHAR, email VARCHAR, city VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `customer_id`, projecting `COALESCE(name, customer_name)` and `COALESCE(segment, 'unknown')`.
        *   `silver_sales_orders` *(conditional)*: `(order_id VARCHAR, customer_id VARCHAR, order_date DATE, total_amount DOUBLE, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `COALESCE(order_id, '__null__' || CAST(rowid AS VARCHAR))`, projecting `COALESCE(total_amount, order_amount)`.
        *   `silver_youtube_channels`: `(channel_key VARCHAR, channel_id VARCHAR, channel_name VARCHAR, handle VARCHAR, subscriber_count BIGINT, total_videos_count INTEGER, is_verified BOOLEAN, custom_url VARCHAR, scraped_at TIMESTAMPTZ, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `COALESCE(channel_id, handle, channel_name)`.
        *   `silver_youtube_videos`: `(video_id VARCHAR, channel_key VARCHAR, title VARCHAR, url VARCHAR, duration_seconds INTEGER, view_count BIGINT, published_time_text VARCHAR, is_short BOOLEAN, thumbnail_url VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `video_id`.
        *   `silver_surveys`: `(survey_id VARCHAR, title VARCHAR, file_name VARCHAR, created_at TIMESTAMPTZ, total_questions INTEGER, total_responses INTEGER, valid_responses INTEGER, invalid_responses INTEGER, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — key `survey_id`.
        *   `silver_survey_questions`: `(survey_id VARCHAR, question_id VARCHAR, column_index INTEGER, question_text VARCHAR, field_type VARCHAR, detected_options_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ)` — key `(survey_id, question_id)`.
        *   `silver_survey_responses`: `(survey_id VARCHAR, response_id VARCHAR, row_number INTEGER, submitted_at VARCHAR, email VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ)` — key `(survey_id, response_id)`.
        *   `silver_survey_answers`: `(survey_id VARCHAR, response_id VARCHAR, question_id VARCHAR, answer_text VARCHAR, answer_list_json VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ)` — key `(survey_id, response_id, question_id)`.
        *   `silver_telemetry_events`: `(event_id VARCHAR, site_id VARCHAR, source_mode VARCHAR, event_ts TIMESTAMPTZ, timestamp_ms BIGINT, visitor_hash VARCHAR, session_id VARCHAR, path VARCHAR, method VARCHAR, status_code INTEGER, latency_ms DOUBLE, duration_seconds DOUBLE, referrer_domain VARCHAR, country_code VARCHAR, browser VARCHAR, os VARCHAR, device_type VARCHAR, _batch_id VARCHAR, _ingested_at TIMESTAMPTZ, _is_test_artifact BOOLEAN)` — deduplicated by `(site_id, timestamp_ms, path, method, visitor_hash, session_id, status_code, latency_ms)`.
    *   Quarantine & Quality Gate `_rule_id` contracts (written to `lakehouse/quarantine/<entity>/v_<batch_id>/quarantine.parquet` with `_batch_id`, `_rule_id`, `_failure_reason`, `_quarantined_at`, `raw_payload_json`):
        *   `ocr_extractions`: `OCR_ITEM_ERROR` (`error_message IS NOT NULL`), `OCR_CONFIDENCE_RANGE` (`confidence IS NULL OR confidence < 0.0 OR confidence > 1.0`).
        *   `telegram_messages`: `TG_INVALID_DATE` (`message_ts IS NULL`), `TG_NEGATIVE_REACTIONS` (`reaction_count IS NULL OR reaction_count < 0`).
        *   `sales_orders`: `DB_NULL_ORDER_ID` (`order_id IS NULL OR trim(order_id) = ''`), `DB_NON_POSITIVE_AMOUNT` (`total_amount IS NULL OR total_amount <= 0`).
        *   `youtube_videos`: `YT_NEGATIVE_DURATION` (`duration_seconds IS NOT NULL AND duration_seconds < 0`), `YT_NEGATIVE_VIEWS` (`view_count IS NOT NULL AND view_count < 0`).
        *   `survey_runs`: `SURVEY_TRUNCATED_RUN` (`captured_responses < valid_responses` — quarantines truncated Extraction Run metadata in `survey_runs` while keeping complete survey runs in `silver_surveys`/`responses`/`answers`).
        *   `telemetry_events`: `TELEMETRY_INVALID_STATUS` (`status_code IS NULL OR status_code < 100 OR status_code > 599`), `TELEMETRY_NEGATIVE_LATENCY` (`latency_ms IS NULL OR latency_ms < 0`).
    *   Dataset circuit-breaker rule per entity: `sales_customers` is materialized as a passthrough entity while `sales_orders` is conditional and passes with `0` rows when no conforming sales schema exists; non-conditional entities trigger `BLOCKED` if `pre_commit_rows > 0 AND valid_rows == 0` (`silver.py` normalizes into fixed typed TEMP schemas upfront). `survey_runs` is a Quarantine audit entity whose failures emit `PASSED_WITH_QUARANTINE` unless all survey runs in `silver_surveys` fail.

#### 17. [`src/ducklake/gold.py`](../../src/ducklake/gold.py) (Create)

*   **Type / Scope**: Gold Mart SQL materialization and `.duckdb` snapshot exporter.
*   **Proposed Changes & Rationale**: Materialize the four Gold Marts under `lakehouse/gold/v_<batch_id>/`:
    *   `gold_ingestion_overview.parquet`: `(source_name VARCHAR, bronze_records BIGINT, silver_entities BIGINT, quarantined_records BIGINT, test_artifact_records BIGINT, quality_status VARCHAR, latest_ingested_at TIMESTAMPTZ)` ordered by `source_name`.
    *   `gold_sales_kpi_mart.parquet`: `(order_date DATE, segment VARCHAR, order_count BIGINT, gross_revenue DOUBLE, avg_order_value DOUBLE)` via `LEFT JOIN silver_sales_customers ON customer_id` (`COALESCE(segment, 'unknown')`) ordered by `order_date DESC, gross_revenue DESC` (0-row typed Parquet when `silver_sales_orders` is empty).
    *   `gold_telegram_engagement_mart.parquet`: `(chat_title VARCHAR, sender_name VARCHAR, message_count BIGINT, reply_count BIGINT, media_count BIGINT, total_reactions BIGINT)` using `COALESCE(NULLIF(from_name, ''), 'Unknown')` and `SUM(reaction_count)` ordered by `message_count DESC`.
    *   `gold_web_traffic_mart.parquet`: `(traffic_date DATE, site_id VARCHAR, pageviews BIGINT, unique_visitors BIGINT, sessions BIGINT, p50_latency_ms DOUBLE, p95_latency_ms DOUBLE, error_rate_pct DOUBLE)` using `quantile_cont(latency_ms, 0.50) FILTER (WHERE source_mode != 'beacon')` (returns `NULL` if a day has only beacon events) and `ROUND(100.0 * COUNT(*) FILTER (WHERE status_code >= 400) / COUNT(*), 2)` ordered by `traffic_date DESC, pageviews DESC`.
    *   When `export_duckdb=True`, materialize **tables** inside schemas `silver`, `quarantine`, and `gold` in a temporary `.duckdb` file and atomically swap to `lakehouse/ducklake.duckdb` via `os.replace`, catching Windows `PermissionError` as a non-fatal warning in `BatchRunReport.warnings`.

#### 18. [`src/ducklake/service.py`](../../src/ducklake/service.py) (Create)

*   **Type / Scope**: Lakehouse orchestrator, lock manager, and read query facade.
*   **Proposed Changes & Rationale**:
    *   `LakehouseService(config: LakehouseConfig)`:
        *   **Cross-process OS lock**: Open `config.write_lock_path`, write/ensure 1 byte exists (`b"0"`) before acquiring non-blocking `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` on Windows (`os.name == "nt"`) or `fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)` on POSIX; raise `LakehouseLockError` immediately if held.
        *   **`run_batch(sources=None, full_refresh=False, export_duckdb=None)`**:
            *   If `full_refresh=True`: clears `watermarks`, `committed_bronze_batches`, and `bronze/<source>/` for selected `sources`; when all `ALLOWED_SOURCES` are refreshed, also resets `marts`, `silver_versions`, `quarantine_batches`, and `layer_counts` in `latest_manifest.json` (old `silver/v_*` and `gold/v_*` directories are cleaned up by `_prune_old_versions`, while up to 10 `quarantine/` directories remain on disk).
            *   When `sources` is a subset, Silver/Gold read committed Bronze batches for unselected sources so cross-source `gold_ingestion_overview` stays complete.
            *   Per-source/per-mart commit: for any source/entity whose Quality Gate status is `PASSED` or `PASSED_WITH_QUARANTINE`, register its new `batch_<batch_id>.parquet` in `committed_bronze_batches[source]`, update `watermarks[source]`, update `silver_versions[entity]`, and update `marts[mart_name]`. For any `BLOCKED` entity, delete that source's uncommitted `batch_<batch_id>.parquet`, keep its prior `watermarks[source]` and `marts[mart_name]` unchanged, and record `quarantine_batches[entity]` so `GET /api/lakehouse/quarantine` displays the `BLOCKED` failures immediately.
            *   Atomically write `watermarks.json` and `latest_manifest.json` via temp-file `os.replace`, append `BatchRunReport` JSON line to `runs_history.jsonl`, and prune `silver/` and `gold/` `v_<batch_id>` directories keeping `keep_last` plus any manifest-pinned directories (ignoring transient `PermissionError` on Windows). Quarantine directories retain `max(keep_last, 10)` batches so `BLOCKED` diagnostics survive consecutive runs.
        *   **Read methods** (`get_status()`, `list_runs(limit=20, offset=0)`, `get_quarantine(entity=None, batch_id=None, limit=50, offset=0)`, `get_mart_preview(mart_name, limit=50, offset=0)`): open short-lived `:memory:` DuckDB connections against committed manifest paths (`get_quarantine()` also reads `quarantine_batches` recorded for `BLOCKED` runs), skipping malformed lines in `runs_history.jsonl`.

#### 19. [`tests/conftest.py`](../../tests/conftest.py), [`tests/test_frontend_api.py`](../../tests/test_frontend_api.py), [`tests/test_survey_extractor.py`](../../tests/test_survey_extractor.py), [`tests/test_telemetry.py`](../../tests/test_telemetry.py) (Modify)

*   **Type / Scope**: Test isolation fixtures.
*   **Proposed Changes & Rationale**: Add an `autouse=True` `isolated_frontend_env` fixture in `tests/conftest.py` that monkeypatches `frontend.app.DEFAULT_LOG_DIR`, `frontend.app.UPLOADS_DIR`, all `*_LOG_FILE` paths, `frontend.app.TELEMETRY_DB_FILE`, `frontend.app.telemetry_service`, `frontend.app.OCRSystem` (wrapping it to pass `log_dir=tmp_logs_dir`, fixing `OCRSystem.__init__`'s import-time `DEFAULT_LOG_DIR` default binding without editing `src/gemini_ocr/`), and `frontend.app.app.state.lakehouse_service` into `tmp_path`. Update `test_survey_extractor.py::test_api_extract_endpoint` to accept the shared `client` fixture instead of constructing a raw `TestClient(app)` before fixture isolation if needed, and keep `logs/` and `frontend/uploads/` untouched during `pytest`.

#### 20. [`tests/test_ducklake_pipeline.py`](../../tests/test_ducklake_pipeline.py) (Create)

*   **Type / Scope**: Core DuckLake unit and integration tests (all in `tmp_path`).
*   **Proposed Changes & Rationale**: Include concrete test functions:
    *   `test_bronze_idempotency_and_telegram_inplace_rewrite`: ingests 6 sources, verifies second run yields `0` new Bronze records, simulates `attach-photos` rewrite in `telegram_parser_log.jsonl`, verifies new `_payload_hash` re-ingests cleanly.
    *   `test_jsonl_streaming_trailing_partial_line_and_large_payload`: tests torn trailing JSON line skip + >16 MB JSON line ingestion.
    *   `test_landing_json_unwrapping_and_empty_sources`: ingests raw CLI `DatabaseExportResult` / `YouTubeChannelExportResult` JSONs without `"data"` wrappers, and tests empty `logs/` initial batch emitting 0-row typed Silver/Gold Parquet.
    *   `test_silver_dedup_and_edge_cases`: verifies `gemini_ocr` basename normalization (`Path(f).name`), Telegram `Service Notice` separation (`id=-1`), `database_parser` hybrid routing + `customers` `COALESCE(name, customer_name)` + `'unknown'` segment, YouTube `NULL` Shorts duration, truncated `survey_extractor` (`SURVEY_TRUNCATED_RUN` in `survey_runs`), and `telemetry.db` composite-key deduplication over duplicate UUIDs + `beacon` latency `NULL` exclusion in `gold_web_traffic_mart`.
    *   `test_quality_gate_blocked_preserves_healthy_marts`: verifies a `BLOCKED` entity deletes its uncommitted Bronze file, preserves its prior verified Gold Mart pointer, still updates healthy marts, and surfaces `BLOCKED` rows via `get_quarantine()`.
    *   `test_full_refresh_runs_history_recovery_and_duckdb_export`: verifies `--full-refresh`, malformed `runs_history.jsonl` line skip, and `lakehouse/ducklake.duckdb` table export.

*   **Phase 2 Checkpoint**: Run `pytest` on all existing tests plus `tests/test_ducklake_pipeline.py`; assert all pass and `git status` / file mtimes confirm zero writes to workspace `logs/` or `lakehouse/`.

---

### Phase 3: CLI, FastAPI Router, SPA UI Tab, API Tests & Documentation

#### 21. [`scripts/run_lakehouse.py`](../../scripts/run_lakehouse.py) (Create)

*   **Type / Scope**: CLI runner script.
*   **Proposed Changes & Rationale**: Parse CLI flags via `argparse`: `--source` (`action="append"`, validated against `ALLOWED_SOURCES`, defaults to all sources), `--full-refresh` (`action="store_true"`), `--export-duckdb` (`action="store_true"`, default `False`), `--logs-dir`, `--landing-dir`, `--lakehouse-dir`, and `--json`. Invoke `LakehouseService.run_batch()`, print human-readable table counts or JSON report, and exit `0` on `PASSED` / `PASSED_WITH_QUARANTINE`, `2` on `BLOCKED`, and `1` on lock/runtime error.

#### 22. [`frontend/lakehouse_routes.py`](../../frontend/lakehouse_routes.py) (Create)

*   **Type / Scope**: FastAPI router module.
*   **Proposed Changes & Rationale**: Define `APIRouter(prefix="/api/lakehouse", tags=["lakehouse"])` using `get_lakehouse_service(request)`:
    *   `POST /api/lakehouse/run` (optional JSON body `RunBatchRequest`): runs `service.run_batch()` in `asyncio.to_thread`; returns `200` `BatchRunReport`, `422` for unknown source name, `409` on `LakehouseLockError`.
    *   `GET /api/lakehouse/status`: returns `ManifestState` (`200` even before first batch, with empty `marts`/`layer_counts`).
    *   `GET /api/lakehouse/runs`: query params `limit: int = Query(20, ge=1, le=200)`, `offset: int = Query(0, ge=0)`; returns `list[BatchRunReport]`.
    *   `GET /api/lakehouse/quarantine`: query params `entity: Optional[str] = None` (validated against `QUARANTINE_ENTITIES`, returning `422` if invalid), `batch_id: Optional[str] = Query(None, pattern=r"^[a-f0-9_-]+$")`, `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`; defaults to all committed/latest quarantined rows when `entity`/`batch_id` are omitted; returns `QuarantinePage`.
    *   `GET /api/lakehouse/marts/{mart_name}`: query params `limit: int = Query(50, ge=1, le=200)`, `offset: int = Query(0, ge=0)`; returns `404` for unknown `mart_name`, `200` empty `MartPreviewResponse` before first batch, or paginated rows.

#### 23. [`frontend/app.py`](../../frontend/app.py) (Modify)

*   **Type / Scope**: FastAPI application wiring.
*   **Proposed Changes & Rationale**: Include `lakehouse_router` from `frontend/lakehouse_routes.py` and initialize `app.state.lakehouse_service = LakehouseService(LakehouseConfig(project_root=BASE_DIR.parent))` without altering any of the existing six service routes.

#### 24. [`frontend/static/index.html`](../../frontend/static/index.html) (Modify)

*   **Type / Scope**: SPA HTML shell.
*   **Proposed Changes & Rationale**: Change the header container (`line 38`) from `h-16` to `min-h-16 py-2` and add `flex-wrap` to the segmented switcher (`line 53`) so seven tabs wrap without horizontal overflow or vertical clipping. Add `#tabDuckLake` and `#viewDuckLake` containing:
    *   Controls: `#ducklakeRunBtn`, `#ducklakeFullRefreshCheck`, `#ducklakeExportCheck`, `#ducklakeStatusBadge`.
    *   Layer cards container: `#ducklakeLayerCards`.
    *   Gold Mart explorer: `#ducklakeMartSelect`, `#ducklakeMartTable`, `#ducklakeMartPrev`, `#ducklakeMartNext`.
    *   Quarantine inspector: `#ducklakeQuarantineEntity`, `#ducklakeQuarantineTable`.
    *   History section: `#ducklakeHistorySection` (toggled via top-right `#btnToggleHistory`).
    *   Load `<script src="/static/lakehouse.js"></script>` immediately after `/static/app.js`.

#### 25. [`frontend/static/style.css`](../../frontend/static/style.css) (Modify)

*   **Type / Scope**: SPA styling.
*   **Proposed Changes & Rationale**: Add scoped badge classes (`.dl-badge-passed`, `.dl-badge-warn`, `.dl-badge-blocked`) and scrollable `.dl-table-wrap` container matching the existing dark theme.

#### 26. [`frontend/static/app.js`](../../frontend/static/app.js) (Modify)

*   **Type / Scope**: SPA tab routing glue.
*   **Proposed Changes & Rationale**: Register `tabDuckLake` and `viewDuckLake` inside `setupNavigation()` click listeners and the `switchService()` tab/view reset arrays; add `else if (serviceName === "ducklake")` branch updating `#historyBtnLabel` (`"Pipeline Runs"`), `#brandSubtitle`, and `#ocrStatusBadge`, calling `window.initDuckLakeTab?.()`; and handle `"ducklake"` in `toggleActiveHistory()` calling `window.toggleDuckLakeHistory?.()`.

#### 27. [`frontend/static/lakehouse.js`](../../frontend/static/lakehouse.js) (Create)

*   **Type / Scope**: Isolated DuckLake UI controller.
*   **Proposed Changes & Rationale**: Guard `window.initDuckLakeTab` with a one-time initialization flag (`_initialized`) to prevent duplicate event listeners on repeated tab switches; reuse `showToast` / `escapeHtml` (or local `textContent` DOM builders) to handle `/api/lakehouse/run`, `/status`, `/runs`, `/quarantine`, and `/marts/{mart_name}` without XSS risk.

#### 28. [`tests/test_ducklake_api.py`](../../tests/test_ducklake_api.py) (Create)

*   **Type / Scope**: FastAPI and CLI integration tests.
*   **Proposed Changes & Rationale**: Test `GET /api/lakehouse/status` before first batch (`200`), `POST /api/lakehouse/run` (`200` `BatchRunReport`), `POST /api/lakehouse/run` under simulated `LakehouseLockError` (`409`), `GET /api/lakehouse/marts/unknown` (`404`), `limit=201` validation (`422`), invalid `entity` / `batch_id` (`422`), paginated `QuarantinePage` & `MartPreviewResponse`, `GET /api/lakehouse/runs`, and `scripts/run_lakehouse.py` subprocess exit codes (`0` and `2`).

#### 29. [`README.md`](../../README.md) and [`ducklake_medallion_pipeline_plan.md`](../../ducklake_medallion_pipeline_plan.md) (Modify)

*   **Type / Scope**: Repository documentation alignment.
*   **Proposed Changes & Rationale**: Add a top banner note in `ducklake_medallion_pipeline_plan.md` pointing to this design doc and `docs/adr/0001`–`0003` for the v1 prototype architecture, and document `src/ducklake/`, `scripts/run_lakehouse.py`, and the DuckLake SPA tab in `README.md`.

*   **Phase 3 Checkpoint**: Run full `pytest`, CLI smoke check, and FastAPI/UI check below.

### Verification Plan

*   **Dependency & Import Verification**: `pip install -e . --no-deps` and verify `python -c "import duckdb, ducklake"` exits `0`.
*   **Unit & Integration Tests (`pytest`)**: Run `pytest` across the full existing test suite plus `tests/test_ducklake_pipeline.py` and `tests/test_ducklake_api.py`; verify zero new entries or timestamps are written to `logs/` or `lakehouse/` during `pytest`.
*   **CLI Smoke Check**: Run `python scripts/run_lakehouse.py --export-duckdb` against workspace `logs/` and verify `lakehouse/metadata/latest_manifest.json` reports `PASSED` or `PASSED_WITH_QUARANTINE`, Bronze/Silver/Gold Parquet files exist, `lakehouse/ducklake.duckdb` opens read-only with matching Gold row counts, and an immediate second run reports `0` newly ingested Bronze records.
*   **Web API & UI Check**: Start `python scripts/start_web.py`, open the `DuckLake` tab in the browser, verify header tabs wrap without clipping, trigger `POST /api/lakehouse/run`, verify all four Gold Marts and Quarantine rows render without console or lock errors, and verify concurrent `GET /api/lakehouse/status` returns `200` while a CLI `Ingestion Batch` runs.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
