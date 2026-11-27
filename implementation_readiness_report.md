# Stage 9: Implementation Readiness Test Report (Round 1)

* **Target Document:** [`docs/designs/ducklake_medallion_prototype.md`](file:///D:/Data_in/docs/designs/ducklake_medallion_prototype.md) (`DetailedRange`: lines 277–443, cross-checked with `FeatureRange` lines 1–276 and codebase files)
* **Standard Applied:** [`implementation-readiness-standard.md`](C:/Users/USER/.gemini/config/plugins/egm/resources/document_standards/implementation-readiness-standard.md)
* **Reviewers:** `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`

**Overall Verdict: FAIL / NEEDS REVISION** — 8 Consolidated Blockers, 8 Consolidated Majors, and 7 Nits. An implementer cannot build `src/ducklake/`, `frontend/`, or `tests/` cleanly without guessing schemas, commit rules, or hitting runtime bugs against existing codebase behavior.

---

## Blocker Findings

### `readiness-1-1` [Blocker] `isolated_frontend_env` Fails to Isolate `OCRSystem` & Import-Time `logs/` Touches (`egm-implementation-readiness`, `egm-codebase-details`)
* **Affected Scope:** Lines 392–395 (`frontend/app.py`), lines 417–420 (`tests/conftest.py`, `test_frontend_api.py`, `test_survey_extractor.py`, `test_telemetry.py`), line 435 (`Verification Plan`).
* **Description & Rationale:** In `src/gemini_ocr/system.py` (lines 28–34), `OCRSystem.__init__` binds `log_dir = DEFAULT_LOG_DIR` at import time (`Path("logs")`), and `frontend/app.py` (line 127) calls `OCRSystem(mmen_ocr_component=...)` without passing `log_dir`. Monkeypatching `frontend.app.DEFAULT_LOG_DIR` alone will still append `"Test OCR Prompt"` entries into `logs/gemini_ocr_log.jsonl`. Additionally, `test_survey_extractor.py::test_api_extract_endpoint` instantiates `TestClient(app)` directly without a `client` fixture, and importing `frontend.app` runs `UPLOADS_DIR.mkdir` and `TelemetryService(TELEMETRY_DB_FILE)` before fixtures execute.
* **Recommendation:** Make `isolated_frontend_env` `autouse=True` (or patch `frontend.app.OCRSystem` / `OCRSystem.__init__` defaults, or pass `log_dir=DEFAULT_LOG_DIR` in `app.py` — wait: respecting zero upstream edits to `src/gemini_ocr/`, patching `frontend.app.OCRSystem` in `isolated_frontend_env` + updating `test_api_extract_endpoint` to use the shared fixture isolates all API tests cleanly).

### `readiness-1-2` [Blocker] Contradictory `database_parser` Silver Columns (`amount` vs. `total_amount`, Missing `customer_name`/`segment`) (`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`)
* **Affected Scope:** Lines 357, 365 vs. lines 158, 166, `sample_database/sales_database.sql`, and `logs/database_parser_log.jsonl`.
* **Description & Rationale:** Line 365 checks `amount <= 0` on `silver_sales_orders`, whereas `sales_database.sql` and line 158 define `total_amount` (causing a DuckDB `Binder Error`). Furthermore, actual `customers` in `sales_database.sql` has `(customer_id, name, email, city)`—neither `customer_name` nor `segment` exists—so lines 158, 166, and 357 need explicit coalescing rules (`COALESCE(name, customer_name)`, `COALESCE(segment, 'unknown')`).

### `readiness-1-3` [Blocker] Contradictory `BLOCKED` Commit, Manifest, and Watermark Semantics (`FeatureRange` vs. `DetailedRange`) (`egm-implementation-readiness`)
* **Affected Scope:** Line 375 (`service.py`), line 354 (`silver.py`), line 365 (`quality.py`) vs. lines 36, 70, 106, 113–116, 137, 139, 241–243.
* **Description & Rationale:** `FeatureRange` specifies per-entity `BLOCKED` isolation (per-mart pointers in `latest_manifest.json`), manifest-fenced Bronze batches (`committed_bronze_batches`), and single-pass Quarantine splitting, whereas `DetailedRange` still says: (1) `service.py` commits `watermarks.json` and `latest_manifest.json` only when the whole batch is not `BLOCKED`, (2) `silver.py` scans "all Bronze Parquet files", and (3) `quality.py` reads and rewrites clean Silver Parquet after `silver.py` wrote it. Both ranges must agree on one exact per-source/per-mart commit and fencing contract.

### `readiness-1-4` [Blocker] Missing Incremental Phasing & Checkpoints (`egm-implementation-readiness`, `egm-codebase-details`)
* **Affected Scope:** Lines 277–438 (`DetailedRange`) vs. `implementation-readiness-standard.md` lines 20–23.
* **Description & Rationale:** `DetailedRange` presents a flat 28-item list followed by one final `Verification Plan`, rather than partitioning the work into incremental buildable/testable phases with per-phase verification checkpoints.

### `readiness-1-5` [Blocker] Undefined Pydantic Models & Metadata File JSON Schemas (`egm-implementation-readiness`, `egm-codebase-details`)
* **Affected Scope:** Lines 306–310 (`models.py`), 346–350 (`bronze.py`), 372–376 (`service.py`).
* **Description & Rationale:** `SourceIngestSummary`, `QualityCheckResult`, `QualityGateResult`, `LayerCounts`, `ManifestState`, `BatchRunReport`, `QuarantinePage`, and `MartPreviewResponse` list no field names, types, or defaults, and `latest_manifest.json`, `watermarks.json`, and `runs_history.jsonl` have no defined JSON schemas.

### `readiness-1-6` [Blocker] Contradictory Column & Entity Names Across `DetailedRange` and `FeatureRange` (`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`)
* **Affected Scope:** Lines 309, 324, 349, 355–365, 425 vs. lines 35, 70, 100–101, 135, 137, 156–160.
* **Description & Rationale:** Naming drift across ranges blocks zero-decision implementation:
  * `_rule_id` (L70, L137) vs. `rule_id` (L365).
  * `_payload_hash` (L35, L100, L309) vs. `payload_sha256` (L324, L425) vs. `payload_hash` (L349).
  * `_record_key` (L309) / `record_key` (L349, L425) / `run_key` (L156) / `source_record_key` (L355).
  * `survey_runs` Quarantine entity (L160) missing from `DetailedRange` (L365) and `/api/lakehouse/quarantine` `entity` allowlist.

### `readiness-1-7` [Blocker] Zero SQL / Column Schemas for Silver Tables & Gold Marts + Undecided `.duckdb` Export (`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`)
* **Affected Scope:** Lines 351–370 (`silver.py`, `gold.py`).
* **Description & Rationale:** `silver.py` and `gold.py` omit exact column names, DuckDB types, nullability, timestamp parsing, 0-row empty-source schema emission, `gold_ingestion_overview` grain, `error_rate` scale (`0..1` vs `%`), and `ducklake.duckdb` export choice (`views` vs `tables`).

### `readiness-1-8` [Blocker] Underspecified Quality Gate Rules, `_rule_id` Contract, & Incomplete Adapter Unwrapping (`egm-implementation-readiness`, `egm-codebase-details`)
* **Affected Scope:** Lines 311–345 (`adapters/*.py`), lines 362–366 (`quality.py`).
* **Description & Rationale:**
  * `quality.py` omits exact `_rule_id` codes, `_failure_reason` strings, exact list of conditional entities allowed `0` rows without triggering `BLOCKED`, required schema checks, and whether truncated `survey_extractor` Extraction Runs exclude rows from `silver_surveys`/`responses`/`answers`.
  * `adapters/*.py` omit landing file unwrapping (`record.get("data", record)` when standalone CLI exports lack `"data"`, `session_id`, and `timestamp` wrappers), `_source_origin_type` enum (`"jsonl" | "sqlite" | "landing_json"`), canonical JSON hashing (`json.dumps(..., sort_keys=True)`), `gemini_ocr` basename normalization for error records, and `telemetry.py` exact `_record_key` format.

---

## Major Findings

* **`readiness-1-9` [Major] Target Scope Allowlist Gap for `src/ducklake/adapters/__init__.py`** (`egm-implementation-readiness`, `egm-codebase-details` — Line 343): `src/ducklake/adapters/__init__.py` is buried parenthetically inside Item 13 (`telemetry.py`) instead of having its own explicit Target File entry and registry API (`ADAPTERS`, `get_adapter`, `get_all_adapters`).
* **`readiness-1-10` [Major] Unspecified `batch_id` Format, `memory_limit`, `--full-refresh`, Retention Scope, and Windows 1-Byte Lock** (`egm-implementation-readiness`, `egm-style` — Lines 304, 349, 375, 380): `batch_id` generator must match `^[a-f0-9_-]+$` (lowercase); `config.py` omits `memory_limit` and `keep_last`; `bronze.py`/`service.py` omit empty-batch behavior, `--full-refresh` behavior, and Windows `msvcrt.locking` 1-byte file requirement.
* **`readiness-1-11` [Major] Incomplete CLI & FastAPI Request/Response Contracts** (`egm-implementation-readiness`, `egm-codebase-details`, `egm-style` — Lines 377–390): Missing `--source` parsing (`append` vs `nargs`), `--export-duckdb` default/negation, `POST /api/lakehouse/run` JSON body schema, `/runs` pagination shape, `/quarantine` defaults & `entity` allowlist (`400` vs `422`), and `/marts/{mart_name}` empty-state & `limit > 200` handling.
* **`readiness-1-12` [Major] Header `h-16` Clipping, Omitted `setupNavigation()` Hook, & Underspecified Frontend DOM/CSS IDs** (`egm-implementation-readiness`, `egm-codebase-details` — Lines 397–416): `frontend/static/index.html` line 38 uses fixed `h-16`, which clips wrapped tabs unless changed to `min-h-16 py-2`; `app.js` needs `setupNavigation()` click wiring, `switchService()` array resets + `#historyBtnLabel` / `#brandSubtitle` / `#ocrStatusBadge` updates; and exact DOM IDs/CSS classes/controls for `lakehouse.js` are missing.
* **`readiness-1-13` [Major] Missing Concrete Test Cases & Assertions in `Test Plan`** (`egm-implementation-readiness` — Lines 422–425): Item 27 lacks specific test case names, fixture inputs, and assertions (including truncated trailing JSONL line recovery, empty `logs/` initial batch, malformed `runs_history.jsonl` skip, `409` lock contention, invalid `batch_id`/`entity` rejection, and `limit > 200` handling).
* **`readiness-1-14` [Major] Ubiquitous-Language Violations (`staging`/`staged`, `clean`, `run`)** (`egm-style` — Lines 319, 324, 339, 354, 365, 370, 375, 425, 436, 437): Replace `staged` → `pre-commit`, `clean` → `validated`/`valid`, upstream `runs` → `Extraction Runs`, and lakehouse `run` → `Ingestion Batch`.
* **`readiness-1-15` [Major] Adapter & UI Drift vs. `FeatureRange` (`1..276`)** (`egm-style`, `egm-codebase-details` — Lines 324, 334, 356, 360, 388–389, 405): Replace `"sample_chat / known fixture signatures"` (no `sample_chat` exists; real fixture is `export_source == "messages.html"` and `chat_title == "Min Thike Tun"`), specify `youtube.py` `_is_test_artifact` criteria (`TechPulse Explains` / `sample_channel.html`), add `silver_telegram_reactions` key, widen `telemetry` description beyond CSV UUIDs, and align `style.css` / API param validation wording with `FeatureRange`.
* **`readiness-1-16` [Major] Run-on Sentences & Vague Modifiers** (`egm-style` — Lines 314, 344, 365, 375): Break up the 113-word (`quality.py`) and 70-word (`service.py`) sentences, remove `"temporary in-memory/temp"` redundancy, and replace `"safe"` / `"large"` with concrete mechanisms.

---

## Nit Findings

* **`readiness-1-17` [Nit] `src/ducklake/__init__.py` & `frontend/app.py` Root Resolution** (`egm-implementation-readiness` — Lines 296–300, 392–395): Export `QualityStatus` from `__init__.py` and state `LakehouseConfig(project_root=BASE_DIR.parent)` in `app.py`.
* **`readiness-1-18` [Nit] `gemini_ocr` Filename Normalization** (`egm-codebase-details` — Line 319): Normalize `filename` to basename (`Path(f).name`) on OCR error records to match success records.
* **`readiness-1-19` [Nit] Script Tag Ordering & Idempotent Listener Guard in `index.html` / `lakehouse.js`** (`egm-codebase-details` — Line 400): Place `<script src="/static/lakehouse.js"></script>` after `/static/app.js` if reusing helpers, and guard `initDuckLakeTab()` against duplicate listeners on repeated tab switches.
* **`readiness-1-20` [Nit] Prose Hygiene in `DetailedRange`** (`egm-style` — Lines 339, 356, 400, 405, 415, 435–437): Replace `"orphaned"` with `"unused"`, replace `"fit cleanly"` with `"wrap without horizontal overflow"`, remove `"minimal"` and brittle line/test counts (`3,473-line`, `54 tests`), use repo-relative `logs/` and `lakehouse/`, and write concrete CLI/UI pass criteria in Verification Plan.
