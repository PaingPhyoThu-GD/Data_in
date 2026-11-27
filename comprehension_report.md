**What this proposes**
This document proposes adding a standalone local analytics package (`src/ducklake/`) over six existing ingestion services without modifying any upstream parser code. It reads existing JSONL logs, a SQLite telemetry database, and landing JSON files strictly read-only, persists append-only Bronze, deduplicated Silver, Quarantine, and Gold Parquet datasets under `lakehouse/` using content-hash watermarks and an exclusive write lock, and enforces a single-contract DuckDB SQL Quality Gate (`PASSED`, `PASSED_WITH_QUARANTINE`, or `BLOCKED`) that keeps the previous verified Gold snapshot live on `BLOCKED` batches. It also delivers four v1 Gold Marts, a CLI runner (`scripts/run_lakehouse.py`), read-only FastAPI endpoints (`/api/lakehouse/*`) served via ephemeral `:memory:` DuckDB connections, a new `DuckLake` tab in the web UI, and `tmp_path`-isolated `pytest` fixtures.

**How the existing system works, per this document**
Today, six existing services (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`, and `telemetry`) persist outputs across disconnected local stores with no deduplication or quality checks: five append JSONL entries to `logs/*_log.jsonl`, while `telemetry` writes granular events (including Log Drain webhooks and Beacon pings) to `logs/telemetry.db` and truncated 150-row summaries to `logs/telemetry_parser_log.jsonl`. A legacy `logs/surveys.db` file is orphaned and unused by `frontend/app.py`, and `POST /api/telegram/attach-photos` rewrites `logs/telegram_parser_log.jsonl` in place. The existing web UI (`frontend/static/index.html` and `app.js`) exposes six service tabs served by `frontend/app.py` (launched via `scripts/start_web.py`), and running the current 54 `pytest` tests pollutes `logs/` with duplicate lines and generates new random UUIDs in `logs/telemetry.db`.

---

### Findings

1. **Severity**: Major
   **Affected Scope**: Quarantine & `BLOCKED` batch visibility / Bronze cleanup (`CUJ 2` lines 56–60; `System Architecture` lines 88–104; `service.py` lines 126, 332; `bronze.py` line 306; `silver.py` line 311)
   **Discrepancy Description & Rationale**: Two internal lifecycle contradictions prevent a reader from tracing what happens during and after a `BLOCKED` batch:
   - **Quarantine read path**: Line 60 (`CUJ 2`) states that a `BLOCKED` batch keeps `latest_manifest.json` pointing to the prior verified Gold snapshot while surfacing "the `BLOCKED` status and Quarantine error table in both CLI output and `/api/lakehouse/*`." However, lines 126 and 332 state that `LakehouseService.get_quarantine()` reads "committed manifest paths" via `:memory:` DuckDB. If `latest_manifest.json` is not updated on `BLOCKED`, reading committed manifest paths will not return the `BLOCKED` batch's newly written `lakehouse/quarantine/<entity>/v_<batch_id>/quarantine.parquet`.
   - **Orphaned Bronze partitions on `BLOCKED`**: Line 306 states that `bronze.py` writes `lakehouse/bronze/<source>/batch_<batch_id>.parquet` and defers mutating `watermarks.json` until commit succeeds, while line 311 states `silver.py` reads "all Bronze Parquet files for each source." If a batch is `BLOCKED` and `watermarks.json` does not advance, the document does not specify deleting or ignoring the uncommitted `batch_<batch_id>.parquet` file—meaning the next run would both re-read that failed Bronze file and re-ingest the same records from the upstream source.

2. **Severity**: Major
   **Affected Scope**: `lakehouse/landing/<source>/` origin, schema, and `.gitignore` conflict (lines 28, 52, 84, 181, 251, 276–301)
   **Discrepancy Description & Rationale**: `lakehouse/landing/<source>/*.json` is listed alongside `logs/*_log.jsonl` and `logs/telemetry.db` as an upstream read-only source for all six adapters, yet "The Problem" (lines 17–23) never mentions `lakehouse/landing/`. A fresh reader has no context on what creates files in `lakehouse/landing/<source>/`, what JSON structure they use (single run object vs. array, raw upstream shape vs. wrapped log entry), or how adapters key them (only `telegram.py` on line 281 mentions "file hash for landing files"; the other five adapters do not). Additionally, line 251 adds `lakehouse/` to `.gitignore`, which hides any seed or landing files placed under `lakehouse/landing/`.

3. **Severity**: Major
   **Affected Scope**: Undefined `silver_telegram_reactions` and incomplete Silver/Gold schemas (`Per-Source Silver Modeling` lines 143–155; `silver.py` lines 312–317; `adapters/` lines 276–301)
   **Discrepancy Description & Rationale**: Several Silver tables, upstream payload structures, and Gold join columns are referenced without definitions:
   - **`silver_telegram_reactions`**: Listed as a target Silver table on lines 144 and 313, but its columns, source fields, deduplication key, quality rules, and relationship to `reaction_count` / `gold_telegram_engagement_mart` are never described anywhere in the document.
   - **`database_parser` & `gold_sales_kpi_mart`**: Lines 145 and 314 omit deduplication keys for all four tables (`silver_database_tables`, `silver_database_rows`, `silver_sales_customers`, `silver_sales_orders`), omit all column names for `silver_sales_customers`, and omit the order date column and customer join key required by `gold_sales_kpi_mart` (line 153: "Daily and customer-segment order count... joined with `silver_sales_customers`").
   - **`survey_extractor`**: Lines 147 and 316 omit deduplication keys and schemas for `silver_surveys`, `silver_survey_questions`, `silver_survey_responses`, and `silver_survey_answers`. Line 147 and line 322 state that truncated runs (`captured rows < valid_responses`) are quarantined, without specifying which of the four Silver tables holds those quarantined rows or whether a log containing only truncated legacy lines 1–2 triggers `BLOCKED` via the "zero clean rows remain" rule.
   - **`gemini_ocr` & `telemetry` upstream shapes**: Line 276 references `GeminiRespond` fields `(date, files, content)` alongside `respond` items (`text`, `confidence`, `language`, optional `error`), while lines 143 and 312 deduplicate by `(run_key, filename, image_index)` without explaining where `filename` and `image_index` live (`files` vs. `respond[]`) or what `content` represents. Line 286 (`DatabaseExportResult`) and line 291 (`YouTubeChannelExportResult`) name upstream schemas with no field summary. Similarly, lines 19–20, 148, and 301 reference `logs/telemetry.db` (`telemetry_events`), "Log Drain webhooks and Beacon pings," "new random UUIDs," SQLite `id`, and "re-uploaded CSV UUIDs" without explaining the table columns or how SQLite `id` relates to the random UUIDs.

4. **Severity**: Major
   **Affected Scope**: Unspecified `--full-refresh` behavior and `QualityGate` schema constraints (`quality.py` lines 59, 124, 322; `service.py` line 332; `scripts/run_lakehouse.py` line 337)
   **Discrepancy Description & Rationale**:
   - **`full_refresh` semantics**: `LakehouseService.run_batch(..., full_refresh=False)` (line 332) and `--full-refresh` (line 337) are never explained. Because Bronze is "append-only" (`batch_<batch_id>.parquet`, line 90) and Silver reads "all Bronze Parquet files" (line 311), the reader cannot tell whether `full_refresh=True` clears existing Bronze/Silver/Gold data first or merely ignores `watermarks.json` (which would duplicate raw Bronze row counts in `gold_ingestion_overview`).
   - **Schema constraints & retention**: Lines 59, 124, and 322 state a batch becomes `BLOCKED` if zero clean rows remain in a non-empty staged entity "or required schema constraints fail," without defining what those required schema constraints are. Likewise, `keep_last=2` cleanup for `v_<batch_id>` directories (line 332) does not clarify whether `BLOCKED` `v_<batch_id>` Quarantine directories count toward retention or how `ManifestState` tracks separate Silver/Quarantine/Gold versions.

5. **Severity**: Major
   **Affected Scope**: Unexplained `youtube.py` test-artifact rules and heuristic contradiction (`Alternative G` line 198; `adapters/` lines 271–301)
   **Discrepancy Description & Rationale**: Line 198 argues against filtering `_is_test_artifact` out of Gold Marts because "heuristic test detection risks hiding real uploads that reuse sample names," yet lines 276, 281, 286, 296, and 301 still implement sample-name heuristics (`"Test OCR Prompt"`, `sample_chat`, `sales_database.sql`, `"API Test Survey"`, `"upload_test"`/`"test_site"`/`"vercel_sample"`). Meanwhile, `youtube.py` (line 291) omits any `_is_test_artifact` tagging criteria altogether, leaving a reader unclear on how YouTube test runs are tagged.

6. **Severity**: Nit
   **Affected Scope**: Undefined project/external terms and acronyms (`Non-Goals` line 37; `Per-Source Silver Modeling` line 147; `Additional Resources` lines 220–223; `survey.py` line 296; Provenance lines 398–400)
   **Discrepancy Description & Rationale**:
   - `Quack Protocol` (line 37) and `EGM` (lines 398, 400) are used without definition or links.
   - `EAV` (lines 95, 147, 316) and `SCD Type 2` (lines 40, 228) are used without expansion on first mention.
   - Line 296 justifies omitting `logs/surveys.db` "per `ADR-0002` update" and lines 163, 174, 181 defer rationale to external ADRs (`docs/adr/0001`–`0003`) that a standalone reader cannot access.
   - Line 139 references existing JS functions (`switchService()`, `toggleActiveHistory()`) and "newer tabs" (`rounded-[32px]` / `font-black`) without brief context on how `frontend/static/app.js` structures tabs/history drawers, and line 33/139 calls the UI a "3-panel" tab while line 357 describes three sections "+ Run History drawer."

7. **Severity**: Nit
   **Affected Scope**: Field and CLI naming inconsistencies across sections (lines 31, 66, 88, 124, 143–145, 266, 306, 312–313, 322, 337)
   **Discrepancy Description & Rationale**: Minor naming drift across sections can confuse readers mapping data contracts:
   - `payload_sha256` (lines 31, 89, 122, 187, 281, 382) vs. `_payload_hash` (lines 88, 266) vs. `payload_hash` (line 306).
   - `record_key` / `_record_key` (lines 31, 266, 276) vs. `run_key` (line 143) vs. `source_record_key` (line 312).
   - `id` (line 144) vs. `message_id` (line 313) for Telegram deduplication.
   - `total_amount`/`order_amount` (line 145) vs. `amount` (line 322) in `silver_sales_orders` quality checks.
   - `rule_id` (lines 124, 322) omits the leading underscore used by all sibling system columns (`_batch_id`, `_failure_reason`, `_quarantined_at`, `_ingest_id`, `_ingested_at`, `_is_test_artifact`).
   - Line 337 says the CLI exits `1` on "runtime/lock error" (implying fail-fast on `write.lock`), whereas `CUJ 3` (line 66) does not clarify whether CLI fails fast or waits when the lock is held.
