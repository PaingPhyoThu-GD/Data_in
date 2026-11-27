# DuckLake Medallion Prototype

*   **Author:** MinnThikeTunn
*   **Status:** Proposed
*   **Date:** 2026-11-26

--------------------------------------------------------------------------------

## Overview

The DuckLake Medallion Prototype adds a local Python analytics package (`src/ducklake/`) over the six existing ingestion services (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`, and `telemetry`) without modifying upstream parser code. It extracts completed Extraction Runs and SQLite telemetry records into append-only Bronze Parquet partitions, normalizes and deduplicates Entity Records in Silver, routes invalid rows to Quarantine under a single-contract DuckDB SQL Quality Gate, and serves four focused Gold Marts through a CLI (`scripts/run_lakehouse.py`), a FastAPI router (`frontend/lakehouse_routes.py`), and a DuckLake tab in the web UI (`frontend/static/index.html`) for team review and iteration.

In this repository, "DuckLake" names this local Medallion package and storage directory rather than DuckDB's external `ducklake` catalog extension.

## The Problem

Today, the six ingestion services store outputs in disconnected places with no cross-run deduplication, schema normalization, or quality checks:

1. **Fragmented persistence across services**: `gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, and `survey_extractor` append JSONL entries to `logs/*_log.jsonl`, while `telemetry` writes granular events (including Log Drain webhooks and Beacon pings) to `logs/telemetry.db` and truncated 150-row summaries to `logs/telemetry_parser_log.jsonl`. Legacy `logs/surveys.db` is orphaned and not written by `frontend/app.py`.
2. **Duplicate runs and test pollution**: Uploading the same file multiple times or running `pytest` (`tests/test_frontend_api.py`, `tests/test_survey_extractor.py`, `tests/test_telemetry.py`) appends repeated entries into `logs/` (12–26 duplicate lines per log) and generates new random UUIDs in `logs/telemetry.db`, inflating counts.
3. **Incompatible edge cases in real payloads**: Telegram exports include `Service Notice` entries with negative IDs (`id: -1`) and non-ISO dates (`"2 November 2026"`); `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place; YouTube Shorts have `duration_seconds: null`; `database_parser` handles arbitrary table schemas; and OCR logs omit `session_id` and reset `image_index` per batch.
4. **Heavier planned stack vs. meeting prototype needs**: `ducklake_medallion_pipeline_plan.md` proposed `dbt-duckdb`, Apache Airflow, Metabase Docker containers, `great-expectations`, and seven Gold Marts (including a cross-channel date spine). That stack introduces heavy dependencies and Windows DuckDB single-writer file-locking risks before the team has reviewed Silver schemas in a meeting.

The proposed solution introduces a standalone `src/ducklake/` module backed by atomic Parquet storage, short-lived `:memory:` DuckDB readers, content-hash watermarks, and a DuckDB SQL Quality Gate so the team can run, inspect, and iterate on clean analytical outputs locally.

## Goals

*   **Zero upstream parser edits**: Keep all six existing packages in `src/` unchanged; consume `logs/*_log.jsonl`, `logs/telemetry.db`, and `lakehouse/landing/<source>/` strictly read-only.
*   **Lightweight local footprint**: Add only `duckdb` to `pyproject.toml` and `requirements.txt`, avoiding `great-expectations`, `dbt-core`, and Docker container dependencies in v1.
*   **Lock-free concurrent reads and atomic writes**: Store committed Bronze, Silver, Quarantine, and Gold data as Parquet partitions tracked by `lakehouse/metadata/latest_manifest.json`, serialize write batches under a single-writer lock, and serve FastAPI reads via ephemeral `:memory:` DuckDB connections off the async event loop.
*   **Idempotent ingestion and deduplicated entities**: Track `(record_key, payload_sha256)` watermarks in Bronze (handling in-place rewrites in `telegram_parser_log.jsonl` and read-only SQLite snapshots of `logs/telemetry.db`), deduplicate Silver Entity Records by natural keys, and tag `_is_test_artifact` records transparently.
*   **Single-contract Quality Gate with row-level Quarantine**: Run declarative DuckDB SQL validation rules once to route invalid rows to `lakehouse/quarantine/<entity>/` and compute batch status (`PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED`), keeping the previous verified Gold snapshot live on `BLOCKED`.
*   **Focused meeting deliverables**: Publish four Gold Marts (`gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`), a CLI runner (`scripts/run_lakehouse.py`), `/api/lakehouse/*` FastAPI routes, a 3-panel DuckLake UI tab, and `tmp_path`-isolated `pytest` tests (including isolating existing API tests from `logs/`).

## Non-Goals

*   **Containerized orchestration and BI deployment**: Docker Compose setup for Apache Airflow, Metabase, or DuckDB HTTP/Arrow servers (`Quack Protocol`) is out of scope for v1 (though an optional `.duckdb` snapshot export keeps future Metabase connection possible).
*   **`dbt-duckdb` scaffolding**: Creating a `dbt_project/` directory or Jinja-SQL macros is deferred.
*   **Runtime `great-expectations` dependency**: Installing GX Core in `requirements.txt` or `pyproject.toml` is deferred behind the `QualityGate` Python interface.
*   **Cross-channel daily spine and remaining Gold Marts**: `gold_cross_channel_analytics_mart` (`Daily Activity Spine` requiring SCD Type 2 snapshot deltas), `gold_youtube_video_performance_mart`, `gold_ocr_quality_mart`, and `gold_survey_response_mart` are excluded from Gold in v1 (though all six sources land in Bronze and Silver).
*   **Arbitrary SQL execution in the web UI**: `/api/lakehouse/*` will only expose fixed, read-only Mart and Quarantine queries, never arbitrary user-supplied SQL strings.
*   **Orphaned `logs/surveys.db` ingestion**: Active ingestion reads `logs/survey_extractor_log.jsonl` rather than `logs/surveys.db`, which `frontend/app.py` does not write to.

## Open Questions

None at the problem-definition stage; storage layout, adapter interfaces, Quality Gate rule semantics, and API/UI contracts will be finalized in the Technical Plan and Detailed Implementation Plan sections.

## Critical User Journeys (CUJs)

### CUJ 1: Run Incremental Pipeline and Inspect Gold Marts in the UI

*   **Given**: Upstream Extraction Runs exist in `logs/*_log.jsonl`, `logs/telemetry.db`, or `lakehouse/landing/<source>/`, and the FastAPI server (`scripts/start_web.py`) is running.
*   **When**: An operator opens the `DuckLake` tab in `frontend/static/index.html` and triggers a pipeline run (or runs `python scripts/run_lakehouse.py`).
*   **Then**: Bronze ingests only new or content-changed records using SHA-256 watermarks; Silver deduplicates all six sources; the Quality Gate writes any corrupt rows to `lakehouse/quarantine/<entity>/` and reports `PASSED` or `PASSED_WITH_QUARANTINE`; Gold Parquet partitions and `latest_manifest.json` update atomically; and the UI displays layer counts, gate status, and paginated previews of the four Gold Marts.

### CUJ 2: Quality Gate Blocks a Corrupt Batch Without Breaking Live Reads

*   **Given**: A verified Gold snapshot is already committed and referenced by `latest_manifest.json`.
*   **When**: A new Ingestion Batch violates a dataset-level Quality Gate rule (for example, zero valid rows remain after Quarantine splitting or a required schema constraint fails).
*   **Then**: The Quality Gate marks the batch `BLOCKED`, records the failed rows and `_failure_reason` in `lakehouse/quarantine/<entity>/` plus the batch ledger, keeps `latest_manifest.json` pointing to the prior verified Gold snapshot so UI Mart previews stay online, and surfaces the `BLOCKED` status and Quarantine error table in both CLI output and `/api/lakehouse/*`.

### CUJ 3: Concurrent UI Browsing During CLI Ingestion on Windows

*   **Given**: The FastAPI server is actively serving `/api/lakehouse/*` read requests in `frontend/app.py`.
*   **When**: A developer executes `scripts/run_lakehouse.py` from a separate terminal process at the same time.
*   **Then**: FastAPI read endpoints query committed Parquet files via ephemeral `:memory:` DuckDB connections without holding a file lock on a shared `.duckdb` database, while the single-writer batch lock ensures no two write batches overlap, avoiding Windows file-lock crashes.

### CUJ 4: Isolated Automated Testing Without Contaminating Live Logs

*   **Given**: A developer runs `pytest` locally against the full test suite.
*   **When**: `tests/test_frontend_api.py`, `tests/test_telemetry.py`, `tests/test_survey_extractor.py`, and the new `tests/test_ducklake*.py` execute.
*   **Then**: All log directories, SQLite databases, and lakehouse storage paths are injected into `tmp_path` fixtures so test runs verify real Bronze/Silver/Quarantine/Gold behavior without appending test records into `logs/` or modifying `lakehouse/`.

## Technical Plan (Architecture)

### System Architecture & Data Flow

DuckLake operates as an isolated package (`src/ducklake/`) decoupled from upstream parsers (`src/*`), FastAPI middleware (`frontend/app.py`), and the browser UI. All persisted lakehouse data lives under `lakehouse/` as atomic Parquet datasets indexed by `lakehouse/metadata/latest_manifest.json`.

```text
Upstream Sources (Read-Only)
  ├── logs/*_log.jsonl (5 JSONL streams, streamed line-by-line)
  ├── logs/telemetry.db (copied via sqlite3.Connection.backup())
  └── lakehouse/landing/<source>/*.json
          │
          ▼  [Single-Writer Batch Lock]
  1. Bronze Adapters (src/ducklake/adapters/)
     • Uniform envelope: _ingest_id, _batch_id, _ingested_at, _payload_hash, _is_test_artifact
     • Watermark check: (record_key, payload_sha256) in lakehouse/metadata/watermarks.json
     • Output: lakehouse/bronze/<source>/batch_<batch_id>.parquet (append-only)
          │
          ▼
  2. Silver Transforms (DuckDB SQL in :memory: staging)
     • Natural-key deduplication (latest _ingested_at wins)
     • Semantic splits (Telegram Service Notice, hybrid DB routing, EAV survey answers)
     • Output staged: lakehouse/silver/v_<batch_id>/<entity>.parquet
          │
          ▼
  3. Quality Gate & Row-Level Quarantine (DuckDBSQLQualityGate)
     • Single declarative rule set splits invalid rows -> lakehouse/quarantine/<entity>/v_<batch_id>/
     • Dataset assertions evaluate remaining clean Silver rows:
       - PASSED / PASSED_WITH_QUARANTINE -> build Gold & flip latest_manifest.json
       - BLOCKED -> keep previous latest_manifest.json live, persist Quarantine + BatchRunReport
          │
          ▼
  4. Gold Marts & Optional Snapshot Export
     • Staged & committed: lakehouse/gold/v_<batch_id>/<mart>.parquet
     • Optional export: lakehouse/ducklake.duckdb (copied via temp + os.replace)
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
   * `adapters/`: `SourceAdapter` protocol (`base.py`) plus six symmetric adapters (`gemini_ocr.py`, `telegram.py`, `database.py`, `youtube.py`, `survey.py`, `telemetry.py`) converting heterogeneous upstream shapes into uniform Bronze records.
   * `bronze.py`: Manages `(record_key, payload_sha256)` watermarks (handling in-place rewrites in `logs/telegram_parser_log.jsonl` and `sqlite3.Connection.backup()` snapshots of `logs/telemetry.db`), streams JSONL lines safely in Python to avoid DuckDB's 16 MB JSON object cap, and writes `batch_<batch_id>.parquet`.
   * `silver.py`: Executes DuckDB SQL over Bronze Parquet files inside an ephemeral `:memory:` DuckDB session to materialize deduplicated Silver Parquet files under `lakehouse/silver/v_<batch_id>/`.
   * `quality.py`: Defines the `QualityGate` protocol and `DuckDBSQLQualityGate` implementation. Evaluates declarative SQL check definitions once to split failing rows into `lakehouse/quarantine/<entity>/v_<batch_id>/` (with `_batch_id`, `rule_id`, `_failure_reason`, `_quarantined_at`) and determine `PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED`.
   * `gold.py`: Builds the four v1 Gold Marts under `lakehouse/gold/v_<batch_id>/` from clean Silver data (including `_is_test_artifact` records per team-demo alignment) and optionally exports `lakehouse/ducklake.duckdb`.
   * `service.py`: `LakehouseService` facade shared by CLI and FastAPI. Acquires an exclusive file/process lock (`lakehouse/metadata/write.lock`) for `run_batch()`, updates `lakehouse/metadata/latest_manifest.json` and `runs_history.jsonl`, and serves read queries (`get_status()`, `list_runs()`, `get_quarantine()`, `get_mart_preview()`) using short-lived `:memory:` DuckDB connections against committed manifest paths.

2. **CLI & FastAPI Surface**:
   * `scripts/run_lakehouse.py`: Thin CLI entrypoint invoking `LakehouseService.run_batch()` and printing structured summaries (exit code `0` for `PASSED`/`PASSED_WITH_QUARANTINE`, `2` for `BLOCKED`, `1` for unexpected error).
   * `frontend/lakehouse_routes.py`: FastAPI `APIRouter` mounted into `frontend/app.py` at `/api/lakehouse/*`:
     * `POST /api/lakehouse/run`: Executes synchronously in `asyncio.to_thread` under the single-writer lock, returning `200 OK` with `BatchRunReport` (or `409 Conflict` if another batch holds the lock).
     * `GET /api/lakehouse/status`: Returns current `ManifestState`, layer row counts, and latest Quality Gate summary.
     * `GET /api/lakehouse/runs`: Returns paginated `BatchRunReport` history.
     * `GET /api/lakehouse/quarantine`: Returns paginated quarantined rows filtered by optional `entity` or `batch_id`.
     * `GET /api/lakehouse/marts/{mart_name}`: Returns paginated rows (`limit <= 200`, `offset`) and column metadata for the four allowed Gold Marts (`404` for unknown mart names; no arbitrary SQL input).

3. **Frontend UI (`frontend/static/`)**:
   * `frontend/static/index.html` & `frontend/static/style.css`: Updates header tab bar to `flex-wrap` and adds `tabDuckLake` + `viewDuckLake` matching the `rounded-[32px]` / `font-black` aesthetic of the newer tabs without altering the existing six service views.
   * `frontend/static/lakehouse.js` + `frontend/static/app.js`: Hooks `"ducklake"` into `switchService()` and `toggleActiveHistory()`, keeping all DuckLake fetch/render logic isolated in `lakehouse.js` with three panels: Pipeline Trigger & Layer Counts, Quality Gate & Quarantine Inspector, and Gold Mart Table Preview.

### Per-Source Silver Modeling & Quality Rules

*   **`gemini_ocr` → `silver_ocr_extractions`**: Uses SHA-256 of `(date, files, content)` as synthetic run key and `(run_key, filename, image_index)` as Entity Record key. Maps `text` and `confidence`; quarantines items containing an `"error"` key or `confidence` outside `[0.0, 1.0]`.
*   **`telegram_parser` → `silver_telegram_messages`, `silver_telegram_service_notices`, `silver_telegram_reactions`**: Separates `type == 'service'` entries (`Service Notice`, negative `id`, human-readable `date`) into `silver_telegram_service_notices` before message checks. Deduplicates user messages on `(chat_title, id)`; allows empty `text` on media messages; quarantines user messages with unparseable `date` or negative `reaction_count`.
*   **`database_parser` → Hybrid (`silver_database_tables`, `silver_database_rows` + conditional `silver_sales_customers`, `silver_sales_orders`)**: Always records table metadata and row JSON payloads (`silver_database_tables`, `silver_database_rows`). When exported tables match conforming sales schemas (`customers`; `sales_table`/`sales`/`orders` containing `order_id` and `total_amount`/`order_amount`), projects conformed `silver_sales_*` tables and quarantines rows with null `order_id` or `amount <= 0`.
*   **`youtube_parser` → `silver_youtube_channels`, `silver_youtube_videos`**: Deduplicates channels by `COALESCE(channel_id, handle, channel_name)` and videos by `video_id`. Permits `NULL` `duration_seconds` and `view_count` (supporting Shorts and premieres); quarantines negative `duration_seconds < 0` or `view_count < 0`.
*   **`survey_extractor` → `silver_surveys`, `silver_survey_questions`, `silver_survey_responses`, `silver_survey_answers`**: Reads `logs/survey_extractor_log.jsonl` (coalescing `data.responses` with fallback to legacy `data.sample_responses`) and normalizes `answers` into long-form EAV rows (`response_id`, `question_id`, `answer_text`, `answer_list_json`). Quarantines runs where captured responses are fewer than `metadata.valid_responses` (flagging truncated legacy log lines 1–2).
*   **`telemetry` → `silver_telemetry_events`**: Snapshots `logs/telemetry.db` (`telemetry_events`) via `sqlite3.Connection.backup()`. Deduplicates on composite natural key `(site_id, timestamp, path, method, visitor_hash, session_id, status_code, latency_ms)` to collapse duplicate UUID re-uploads; quarantines status codes outside `[100, 599]` or negative `latency_ms`.

### Gold Mart Definitions (v1)

1. **`gold_ingestion_overview`**: Per-source summary of raw Bronze records, deduplicated Silver Entity Records, quarantined rows, `_is_test_artifact` count, and latest `_ingested_at`.
2. **`gold_sales_kpi_mart`**: Daily and customer-segment order count, gross revenue, and average order value computed from `silver_sales_orders` joined with `silver_sales_customers` when present (returns zero rows gracefully if no conforming sales tables exist).
3. **`gold_telegram_engagement_mart`**: Per-chat and per-sender message volume, reply count, media attachment count, and reaction totals computed strictly from non-`Service Notice` records.
4. **`gold_web_traffic_mart`**: Daily per-`site_id` pageviews, unique deduplicated `visitor_hash` count, `session_id` count, median/P95 latency (`quantile_cont`), and 4xx/5xx error rate from `silver_telemetry_events`.

## Alternatives Considered

### Alternative A: Full Enterprise Stack (`dbt-duckdb` + Apache Airflow + Metabase Docker)

*   **Pros**: Provides scheduled DAG orchestration, built-in dbt lineage documentation, and standalone Metabase BI dashboards out of the box.
*   **Cons**: Requires Docker Compose runtime overhead, `dbt-core` transitive dependencies, and container setup before the team has agreed on Silver schemas and Gold metrics.
*   **Reason for Rejection**: Rejected by author (`docs/adr/0001`): for a v1 local prototype intended for rapid team review and iteration, pure DuckDB SQL and Parquet keep `pytest` and FastAPI lightweight while remaining portable to `dbt-duckdb`, Airflow, and Metabase later.

### Alternative B: Persistent Shared Read/Write `lakehouse/ducklake.duckdb`

*   **Pros**: Stores Bronze, Silver, and Gold as native DuckDB tables in one file with persistent indexes and simpler SQL table updates.
*   **Cons**: DuckDB enforces exclusive single-writer file locking across OS processes on Windows, causing `IOException` crashes whenever CLI batch runs (`scripts/run_lakehouse.py`) overlap with FastAPI `/api/lakehouse/*` queries.
*   **Reason for Rejection**: Rejected by author: compute-storage separation using atomic Parquet snapshots + `latest_manifest.json` + short-lived `:memory:` DuckDB readers eliminates cross-process file-lock collisions while still supporting an optional `.duckdb` snapshot export.

### Alternative C: Runtime `great-expectations` (GX Core) + Separate Row Splitter

*   **Pros**: Emits standardized GX Validation Results and Data Docs HTML artifacts.
*   **Cons**: `great-expectations` is not in `pyproject.toml`, pulls heavy runtime dependencies (`pandas`, `numpy`, `scipy`, `sqlalchemy`), and duplicates validation rules because corrupt rows must already be split out in SQL/Python before GX validates clean Silver tables (`docs/adr/0003`).
*   **Reason for Rejection**: Rejected by author: declarative DuckDB SQL assertions behind a narrow `QualityGate` protocol deliver row-level Quarantine and batch circuit-breaking in one pass with `duckdb` as the only new dependency; GX Core can be wired later behind the same interface.

### Alternative D: Intrusive Lakehouse Hooks Inside Existing `src/` Parsers

*   **Pros**: Upstream services could write directly to Bronze on each parse without scanning `logs/`.
*   **Cons**: Couples all six existing ingestion packages and `frontend/app.py` to lakehouse schemas and risks regressions in already-tested services.
*   **Reason for Rejection**: Rejected by author (`docs/adr/0002`): pulling read-only from `logs/*_log.jsonl`, `logs/telemetry.db`, and `lakehouse/landing/<source>/` keeps all six upstream `src/` packages untouched.

### Alternative E: Byte-Offset / Line-Count Incremental Cursors for JSONL Logs

*   **Pros**: Avoids re-hashing unchanged JSONL prefix lines on append-only logs.
*   **Cons**: `POST /api/telegram/attach-photos` (`frontend/app.py`) rewrites `logs/telegram_parser_log.jsonl` in place, which breaks byte offsets and silently misses updated media URLs.
*   **Reason for Rejection**: Rejected by author: tracking `(record_key, payload_sha256)` content hashes handles in-place file rewrites safely and stays fast at local JSONL file sizes.

### Alternative F: Asynchronous `202 Accepted` Batch Execution with Polling

*   **Pros**: Prevents HTTP request timeouts if batches grow beyond 30–60 seconds.
*   **Cons**: Adds a background job state machine, stale-lock crash recovery, and polling logic in `frontend/static/lakehouse.js`.
*   **Reason for Rejection**: Rejected by author: synchronous execution inside `asyncio.to_thread` returning `BatchRunReport` matches the existing FastAPI service pattern and keeps the prototype straightforward for local datasets.

### Alternative G: Filter Out `_is_test_artifact` Rows from Domain Gold Marts by Default

*   **Pros**: Keeps business KPIs free of historical `pytest` fixtures sitting in `logs/`.
*   **Cons**: Domain Gold Marts would show zero rows out of the box when `logs/` contains only test runs unless the operator toggles a flag or wipes `logs/`, and heuristic test detection risks hiding real uploads that reuse sample names.
*   **Reason for Rejection**: Rejected by author: keeping `_is_test_artifact` tagged transparently in `gold_ingestion_overview` while including all clean Silver records in domain Gold Marts lets the team demo populated charts immediately while isolating `pytest` going forward.

### Alternative H: All Seven Gold Marts + Cross-Channel Daily Activity Spine in v1

*   **Pros**: Covers every source-specific mart and cross-source timeline sketched in `ducklake_medallion_pipeline_plan.md`.
*   **Cons**: Current `logs/` spans disconnected years (2024 survey tests vs. 2026 chat/web tests), YouTube `view_count` is a cumulative snapshot rather than a daily event count, and wide survey pivoting adds speculative complexity before meeting alignment.
*   **Reason for Rejection**: Rejected by author: trimming v1 Gold to `gold_ingestion_overview` plus three domain marts (`gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`) avoids misleading cross-channel numbers while preserving all six sources in Bronze and Silver.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Concurrency & Process Safety**: Write operations acquire `lakehouse/metadata/write.lock` (failing fast with `409 Conflict` in FastAPI if held) and commit to new `v_<batch_id>` directories before atomically updating `latest_manifest.json` via temp-file `os.replace`. FastAPI read endpoints run in `asyncio.to_thread` (or sync `def` handlers) using short-lived `:memory:` DuckDB connections so the Uvicorn event loop never blocks.
*   **Performance & Memory Bounds**: JSONL ingestion streams files line-by-line in Python to avoid DuckDB's 16 MB `read_json_auto` `maximum_object_size` limit; `/api/lakehouse/marts/{mart_name}` and `/api/lakehouse/quarantine` enforce pagination (`limit <= 200`, default `50`) so browser rendering stays responsive.
*   **Security & Privacy**: No arbitrary SQL query endpoint is exposed; `mart_name` is validated against an allowlist (`gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`), and read-only SQLite snapshots prevent write locks or corruption of `logs/telemetry.db`.
*   **Rollout & Rollback**: Because each Silver/Quarantine/Gold batch writes to a fresh `v_<batch_id>` folder, rolling back a bad run only requires pointing `latest_manifest.json` to the prior verified `batch_id` (and `BLOCKED` batches never advance the Gold pointer).

--------------------------------------------------------------------------------

### Additional Resources

*   [`concepts_brief.md`](file:///D:/Data_in/concepts_brief.md) — brainstorm synthesis and resolved contradictions
*   [`ducklake_medallion_pipeline_plan.md`](file:///D:/Data_in/ducklake_medallion_pipeline_plan.md) — original enterprise Medallion blueprint (superseded for v1 by this prototype design)
*   [`CONTEXT-MAP.md`](file:///D:/Data_in/CONTEXT-MAP.md), [`src/CONTEXT.md`](file:///D:/Data_in/src/CONTEXT.md), [`src/ducklake/CONTEXT.md`](file:///D:/Data_in/src/ducklake/CONTEXT.md) — bounded contexts and ubiquitous language
*   [`docs/adr/0001`–`0003`](file:///D:/Data_in/docs/adr) — Architecture Decision Records covering pure DuckDB SQL, read-only log/SQLite pulling, and single-contract Quality Gate

### Future Improvements

*   **Optional GX Core Adapter**: Implement `GreatExpectationsQualityGate` behind `QualityGate` if the team needs Data Docs HTML reports post-meeting.
*   **SCD Type 2 Cross-Channel Spine**: Track daily deltas (`LAG()`) on cumulative sources (`youtube_parser`, `database_parser`) in Silver to enable an undistorted `gold_cross_channel_analytics_mart` (`Daily Activity Spine`).
*   **Additional Domain Gold Marts**: Add `gold_youtube_video_performance_mart`, `gold_ocr_quality_mart`, and `gold_survey_response_mart` once Silver schemas are signed off.
*   **Airflow & Metabase Integration**: Wrap `scripts/run_lakehouse.py --export-duckdb` in Dockerized Airflow DAGs and connect Metabase to the exported `lakehouse/ducklake.duckdb` snapshot.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. [`pyproject.toml`](file:///D:/Data_in/pyproject.toml) (Modify)

*   **Type / Scope**: Python packaging configuration.
*   **Proposed Changes & Rationale**: Add `"duckdb>=1.1.0"` to `dependencies`. Required so DuckLake can execute Parquet reads/writes and SQL transforms locally without pulling `great-expectations`, `dbt-core`, or container dependencies.

#### 2. [`requirements.txt`](file:///D:/Data_in/requirements.txt) (Modify)

*   **Type / Scope**: Pip requirements list.
*   **Proposed Changes & Rationale**: Add `duckdb>=1.1.0` to stay aligned with `pyproject.toml`.

#### 3. [`.gitignore`](file:///D:/Data_in/.gitignore) (Modify)

*   **Type / Scope**: Git ignore rules.
*   **Proposed Changes & Rationale**: Add `lakehouse/` so generated Bronze/Silver/Quarantine/Gold Parquet files, lock files, manifests, and optional `.duckdb` snapshots stay untracked like `logs/` and `frontend/uploads/`.

#### 4. [`src/ducklake/__init__.py`](file:///D:/Data_in/src/ducklake/__init__.py) (Create)

*   **Type / Scope**: Python package entrypoint.
*   **Proposed Changes & Rationale**: Export `LakehouseConfig`, `LakehouseService`, `BatchRunReport`, `QualityGateResult`, and `ManifestState` so CLI, FastAPI, and tests share one public package interface.

#### 5. [`src/ducklake/config.py`](file:///D:/Data_in/src/ducklake/config.py) (Create)

*   **Type / Scope**: Configuration dataclass / Pydantic settings.
*   **Proposed Changes & Rationale**: Define `LakehouseConfig(project_root, logs_dir, landing_dir, lakehouse_dir, export_duckdb)` with deterministic path properties (`bronze_dir`, `silver_dir`, `quarantine_dir`, `gold_dir`, `metadata_dir`, `manifest_path`, `watermarks_path`, `runs_history_path`, `write_lock_path`, `duckdb_snapshot_path`). Resolves default paths from project root (avoiding CWD-relative `Path("logs")` bugs) while allowing `tmp_path` injection in tests.

#### 6. [`src/ducklake/models.py`](file:///D:/Data_in/src/ducklake/models.py) (Create)

*   **Type / Scope**: Pydantic data contracts.
*   **Proposed Changes & Rationale**: Define `QualityStatus` (`PASSED`, `PASSED_WITH_QUARANTINE`, `BLOCKED`), `BronzeEnvelope` (`_ingest_id`, `_batch_id`, `_ingested_at`, `_source_name`, `_source_origin_type`, `_source_file`, `_record_key`, `_payload_hash`, `_is_test_artifact`, `payload_json`), `SourceIngestSummary`, `QualityCheckResult`, `QualityGateResult`, `LayerCounts`, `ManifestState`, `BatchRunReport`, `QuarantinePage`, and `MartPreviewResponse` (with `ALLOWED_MARTS` allowlist).

#### 7. [`src/ducklake/adapters/base.py`](file:///D:/Data_in/src/ducklake/adapters/base.py) (Create)

*   **Type / Scope**: Source adapter protocol & shared utilities.
*   **Proposed Changes & Rationale**: Define `SourceAdapter` protocol (`source_name: str`, `read_records(config, batch_id, ingested_at) -> list[BronzeEnvelope]`), deterministic SHA-256 helper, test-artifact detection helper, and safe streaming JSONL reader (`_iter_jsonl_records`) that handles large single-line exports and malformed lines without hitting DuckDB's 16 MB JSON object limit.

#### 8. [`src/ducklake/adapters/gemini_ocr.py`](file:///D:/Data_in/src/ducklake/adapters/gemini_ocr.py) (Create)

*   **Type / Scope**: Upstream adapter for `gemini_ocr`.
*   **Proposed Changes & Rationale**: Read `logs/gemini_ocr_log.jsonl` and `lakehouse/landing/gemini_ocr/*.json`. Compute a synthetic `record_key` from SHA-256 of `(date, files, content)` because `GeminiRespond` lacks a `session_id`, tag `"Test OCR Prompt"` runs as `_is_test_artifact`, and preserve raw `respond` items (`text`, `confidence`, `language`, optional `error`) inside `payload_json`.

#### 9. [`src/ducklake/adapters/telegram.py`](file:///D:/Data_in/src/ducklake/adapters/telegram.py) (Create)

*   **Type / Scope**: Upstream adapter for `telegram_parser`.
*   **Proposed Changes & Rationale**: Read `logs/telegram_parser_log.jsonl` and `lakehouse/landing/telegram_parser/*.json`. Key each Extraction Run by `session_id` (or file hash for landing files) so in-place rewrites from `POST /api/telegram/attach-photos` produce a new `payload_sha256` and get re-ingested idempotently, and tag test runs matching `sample_chat` / known fixture signatures.

#### 10. [`src/ducklake/adapters/database.py`](file:///D:/Data_in/src/ducklake/adapters/database.py) (Create)

*   **Type / Scope**: Upstream adapter for `database_parser`.
*   **Proposed Changes & Rationale**: Read `logs/database_parser_log.jsonl` and `lakehouse/landing/database_parser/*.json`, normalizing `data` (`DatabaseExportResult`) with `session_id` record keys and `_is_test_artifact` tagging for `sales_database.sql` test fixtures.

#### 11. [`src/ducklake/adapters/youtube.py`](file:///D:/Data_in/src/ducklake/adapters/youtube.py) (Create)

*   **Type / Scope**: Upstream adapter for `youtube_parser`.
*   **Proposed Changes & Rationale**: Read `logs/youtube_parser_log.jsonl` and `lakehouse/landing/youtube_parser/*.json`, normalizing `data` (`YouTubeChannelExportResult`) with `session_id` / channel fallback keys.

#### 12. [`src/ducklake/adapters/survey.py`](file:///D:/Data_in/src/ducklake/adapters/survey.py) (Create)

*   **Type / Scope**: Upstream adapter for `survey_extractor`.
*   **Proposed Changes & Rationale**: Read `logs/survey_extractor_log.jsonl` and `lakehouse/landing/survey_extractor/*.json` (explicitly omitting orphaned `logs/surveys.db` per `ADR-0002` update). Key records by `(survey_id, timestamp)` and tag `"API Test Survey"` / `survey_test.csv` runs as `_is_test_artifact`.

#### 13. [`src/ducklake/adapters/telemetry.py`](file:///D:/Data_in/src/ducklake/adapters/telemetry.py) (Create)

*   **Type / Scope**: Upstream adapter for `telemetry` (and `src/ducklake/adapters/__init__.py` registry).
*   **Proposed Changes & Rationale**: Snapshot `logs/telemetry.db` (`telemetry_events`) using `sqlite3.Connection.backup()` into a temporary in-memory/temp file handle to avoid `SQLITE_BUSY` with FastAPI WAL writes (plus optional `lakehouse/landing/telemetry/*.json`), bypassing `logs/telemetry_parser_log.jsonl` to avoid 150-row truncation and double counting. Key each event by its SQLite `id` + full row payload hash and tag `"upload_test"` / `"test_site"` / `"vercel_sample"` as `_is_test_artifact`.

#### 14. [`src/ducklake/bronze.py`](file:///D:/Data_in/src/ducklake/bronze.py) (Create)

*   **Type / Scope**: Bronze ingestion and watermark manager.
*   **Proposed Changes & Rationale**: Load `lakehouse/metadata/watermarks.json`, invoke selected `SourceAdapter`s, filter out records whose `(source_name, record_key, payload_hash)` already matches the committed watermark (while allowing updated hashes such as rewritten Telegram logs), write new records to `lakehouse/bronze/<source>/batch_<batch_id>.parquet` via DuckDB, and return `SourceIngestSummary` counts without mutating watermarks until commit succeeds.

#### 15. [`src/ducklake/silver.py`](file:///D:/Data_in/src/ducklake/silver.py) (Create)

*   **Type / Scope**: Silver DuckDB SQL transformations and deduplication.
*   **Proposed Changes & Rationale**: Open an ephemeral `:memory:` DuckDB session reading all Bronze Parquet files for each source, flatten JSON payloads, and materialize staged Silver Parquet tables under `lakehouse/silver/v_<batch_id>/`:
    *   `silver_ocr_extractions`: flattens `respond[]`, maps `text`, `confidence`, `language`, `error_message`, deduplicates by `(source_record_key, filename, image_index)`.
    *   `silver_telegram_service_notices` & `silver_telegram_messages` & `silver_telegram_reactions`: separates `type == 'service'` rows before message checks; deduplicates messages by `(chat_title, message_id)` keeping latest `_ingested_at`.
    *   `silver_database_tables`, `silver_database_rows`, plus conditional `silver_sales_customers` and `silver_sales_orders`: implements hybrid routing (always writes generic table metadata and `row_payload_json`, and projects `silver_sales_*` when conforming `customers` / `sales_table` / `sales` / `orders` schemas appear).
    *   `silver_youtube_channels` & `silver_youtube_videos`: derives channel key `COALESCE(channel_id, handle, channel_name)`, deduplicates videos by `video_id`, permits nullable `duration_seconds` and `view_count`.
    *   `silver_surveys`, `silver_survey_questions`, `silver_survey_responses`, `silver_survey_answers`: coalesces `data.responses` with legacy `data.sample_responses`, expands dynamic `answers` into long-form EAV rows.
    *   `silver_telemetry_events`: deduplicates across re-uploaded CSV UUIDs using composite natural key `(site_id, timestamp, path, method, visitor_hash, session_id, status_code, latency_ms)`.

#### 16. [`src/ducklake/quality.py`](file:///D:/Data_in/src/ducklake/quality.py) (Create)

*   **Type / Scope**: Single-contract `QualityGate` protocol and Quarantine splitter.
*   **Proposed Changes & Rationale**: Define `QualityGate` protocol and `DuckDBSQLQualityGate`. In one pass per staged Silver entity, split invalid rows (`error` in OCR or `confidence` outside `[0, 1]`; unparseable timestamp or `reaction_count < 0` in non-service Telegram messages; `order_id IS NULL` or `amount <= 0` in `silver_sales_orders`; `duration_seconds < 0` or `view_count < 0` in YouTube; truncated legacy `survey_extractor` runs where captured rows `< valid_responses`; `status_code` outside `[100, 599]` or `latency_ms < 0` in telemetry) into `lakehouse/quarantine/<entity>/v_<batch_id>/quarantine.parquet` with `_batch_id`, `rule_id`, `_failure_reason`, `_quarantined_at`, and `raw_payload_json`, rewrite the clean Silver Parquet without quarantined rows, and evaluate circuit-breaker checks (`PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED` if zero clean rows remain in a non-empty staged entity or required schema constraints fail).

#### 17. [`src/ducklake/gold.py`](file:///D:/Data_in/src/ducklake/gold.py) (Create)

*   **Type / Scope**: Gold Mart SQL materialization and optional DuckDB export.
*   **Proposed Changes & Rationale**: Compute the four v1 Gold Marts from clean Silver Parquet files into `lakehouse/gold/v_<batch_id>/` (`gold_ingestion_overview.parquet`, `gold_sales_kpi_mart.parquet`, `gold_telegram_engagement_mart.parquet`, `gold_web_traffic_mart.parquet`) and, when `export_duckdb=True`, build a temporary `.duckdb` file containing `silver` / `quarantine` / `gold` views or tables and swap it atomically via `os.replace` to `lakehouse/ducklake.duckdb`.

#### 18. [`src/ducklake/service.py`](file:///D:/Data_in/src/ducklake/service.py) (Create)

*   **Type / Scope**: Lakehouse orchestrator and read query facade.
*   **Proposed Changes & Rationale**: Expose `LakehouseService(config, quality_gate=None)`. Acquire an exclusive cross-process file lock (`lakehouse/metadata/write.lock`) inside `run_batch(sources=None, full_refresh=False, export_duckdb=None)`; commit `watermarks.json` and `latest_manifest.json` atomically only when Quality Gate does not return `BLOCKED`; append every run (including `BLOCKED`) to `lakehouse/metadata/runs_history.jsonl`; clean up superseded `v_<batch_id>` directories outside retention (`keep_last=2`); and implement `get_status()`, `list_runs()`, `get_quarantine(entity, batch_id, limit, offset)`, and `get_mart_preview(mart_name, limit, offset)` via short-lived `:memory:` DuckDB connections reading committed manifest paths.

#### 19. [`scripts/run_lakehouse.py`](file:///D:/Data_in/scripts/run_lakehouse.py) (Create)

*   **Type / Scope**: CLI runner script.
*   **Proposed Changes & Rationale**: Parse `--source` (repeatable or `all`), `--full-refresh`, `--export-duckdb`, `--logs-dir`, `--landing-dir`, `--lakehouse-dir`, and `--json`, call `LakehouseService.run_batch()`, print structured status/counts/quarantine diagnostics, and exit `0` on `PASSED` / `PASSED_WITH_QUARANTINE`, `2` on `BLOCKED`, and `1` on runtime/lock error.

#### 20. [`frontend/lakehouse_routes.py`](file:///D:/Data_in/frontend/lakehouse_routes.py) (Create)

*   **Type / Scope**: FastAPI router module.
*   **Proposed Changes & Rationale**: Define an `APIRouter(prefix="/api/lakehouse", tags=["lakehouse"])` wired to a `get_lakehouse_service(request)` dependency (reading `app.state.lakehouse_service` when configured or default `LakehouseConfig`). Expose:
    *   `POST /api/lakehouse/run` (runs `service.run_batch` via `asyncio.to_thread`; returns `200` `BatchRunReport`, or `409` if locked).
    *   `GET /api/lakehouse/status` (returns `ManifestState` + latest counts).
    *   `GET /api/lakehouse/runs` (returns `runs_history.jsonl` entries).
    *   `GET /api/lakehouse/quarantine` (paginated `QuarantinePage` with `limit <= 200`).
    *   `GET /api/lakehouse/marts/{mart_name}` (allowlisted `MartPreviewResponse` with `limit <= 200`, `404` if invalid `mart_name`).

#### 21. [`frontend/app.py`](file:///D:/Data_in/frontend/app.py) (Modify)

*   **Type / Scope**: FastAPI application wiring.
*   **Proposed Changes & Rationale**: Include `lakehouse_router` from `frontend/lakehouse_routes.py` and initialize default `app.state.lakehouse_service` without touching any of the existing six service routes or logic.

#### 22. [`frontend/static/index.html`](file:///D:/Data_in/frontend/static/index.html) (Modify)

*   **Type / Scope**: SPA HTML shell.
*   **Proposed Changes & Rationale**: Add `flex-wrap` to the header segmented service switcher so seven tabs fit cleanly on narrower screens, add `tabDuckLake` button, add `viewDuckLake` container (three sections: Pipeline Trigger & Layer Health Cards, Quality Gate & Quarantine Inspector, Gold Mart Table Previewer + Run History drawer), and include `<script src="/static/lakehouse.js"></script>`.

#### 23. [`frontend/static/style.css`](file:///D:/Data_in/frontend/static/style.css) (Modify)

*   **Type / Scope**: SPA styling.
*   **Proposed Changes & Rationale**: Add minimal scoped styles for DuckLake status pills (`PASSED`, `PASSED_WITH_QUARANTINE`, `BLOCKED`) and responsive table scrolling matching the existing dark theme.

#### 24. [`frontend/static/app.js`](file:///D:/Data_in/frontend/static/app.js) (Modify)

*   **Type / Scope**: SPA tab routing glue.
*   **Proposed Changes & Rationale**: Register `tabDuckLake` and `viewDuckLake` inside `switchService("ducklake")` and `toggleActiveHistory()`, invoking `window.initDuckLakeTab?.()` / `window.toggleDuckLakeHistory?.()` in `lakehouse.js` while keeping all existing six tabs unchanged.

#### 25. [`frontend/static/lakehouse.js`](file:///D:/Data_in/frontend/static/lakehouse.js) (Create)

*   **Type / Scope**: Isolated DuckLake UI controller.
*   **Proposed Changes & Rationale**: Handle `/api/lakehouse/run`, `/status`, `/runs`, `/quarantine`, and `/marts/{mart_name}` fetch calls, render layer metrics, Quality Gate status badges, paginated Quarantine rows, and Gold Mart tables cleanly outside the 3,473-line `app.js`.

#### 26. [`tests/conftest.py`](file:///D:/Data_in/tests/conftest.py), [`tests/test_frontend_api.py`](file:///D:/Data_in/tests/test_frontend_api.py), [`tests/test_survey_extractor.py`](file:///D:/Data_in/tests/test_survey_extractor.py), [`tests/test_telemetry.py`](file:///D:/Data_in/tests/test_telemetry.py) (Modify)

*   **Type / Scope**: Test isolation fixtures.
*   **Proposed Changes & Rationale**: Add an `isolated_frontend_env` fixture in `tests/conftest.py` (used by `test_frontend_api.py`, `test_survey_extractor.py`, and `test_telemetry.py` when invoking `TestClient(app)`) that monkeypatches `frontend.app.DEFAULT_LOG_DIR`, `UPLOADS_DIR`, `*_LOG_FILE`, `TELEMETRY_DB_FILE`, `telemetry_service`, and `app.state.lakehouse_service` into `tmp_path` so running `pytest` no longer pollutes `logs/` or `frontend/uploads/`.

#### 27. [`tests/test_ducklake_pipeline.py`](file:///D:/Data_in/tests/test_ducklake_pipeline.py) and [`tests/test_ducklake_api.py`](file:///D:/Data_in/tests/test_ducklake_api.py) (Create)

*   **Type / Scope**: DuckLake unit, integration, and API tests.
*   **Proposed Changes & Rationale**: Test all six `SourceAdapter`s using isolated `tmp_path` fixtures (including Telegram in-place rewrites + `Service Notice` separation, `database_parser` hybrid routing, YouTube nullable Shorts durations, truncated legacy survey logs, SQLite `telemetry.db` backup + composite-key deduplication, `(record_key, payload_sha256)` idempotency, Quarantine splitting, `BLOCKED` manifest preservation, `.duckdb` snapshot export, CLI exit codes, and `/api/lakehouse/*` endpoints including `409` lock contention and `404` unknown mart handling).

#### 28. [`README.md`](file:///D:/Data_in/README.md) and [`ducklake_medallion_pipeline_plan.md`](file:///D:/Data_in/ducklake_medallion_pipeline_plan.md) (Modify)

*   **Type / Scope**: Repository documentation alignment.
*   **Proposed Changes & Rationale**: Add a top banner note in `ducklake_medallion_pipeline_plan.md` pointing readers to this design doc and `docs/adr/0001`–`0003` for the v1 prototype architecture, and document the DuckLake package, CLI command, and UI tab in `README.md`.

### Verification Plan

*   **Dependency & Import Verification**: `pip install -e . --no-deps` and verify `python -c "import duckdb, ducklake"` succeeds cleanly.
*   **Unit & Integration Tests (`pytest`)**: Run `pytest` across all existing 54 tests plus the new `tests/test_ducklake_pipeline.py` and `tests/test_ducklake_api.py`; verify zero new entries are written to `D:\Data_in\logs\` or `D:\Data_in\lakehouse\` during `pytest`.
*   **CLI Smoke Check**: Run `python scripts/run_lakehouse.py --export-duckdb` against workspace `logs/` and verify `lakehouse/metadata/latest_manifest.json`, Parquet outputs, `lakehouse/ducklake.duckdb`, Quarantine counts, and idempotency on an immediate second run (`0` new Bronze records).
*   **Web API & UI Check**: Start `python scripts/start_web.py`, open the `DuckLake` tab in the browser, trigger `POST /api/lakehouse/run`, verify `gold_ingestion_overview`, `gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`, and Quarantine tables render without console or lock errors, and verify concurrent `GET /api/lakehouse/status` succeeds during a CLI run.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
