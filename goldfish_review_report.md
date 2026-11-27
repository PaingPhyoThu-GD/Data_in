# Goldfish Annotated Review Report

Status: resolved

**Target:** [`docs/designs/ducklake_medallion_prototype.md`](file:///D:/Data_in/docs/designs/ducklake_medallion_prototype.md) (`DetailedRange`: `277..443`, plus cross-range schema/manifest alignment in `1..276`)

## Prioritized Findings & AI Suggestions

### [Issue 1] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Blocker (`readiness-1-1`)
*   **Affected Scope:** Lines 392–395 (`frontend/app.py`), lines 417–420 (`tests/conftest.py`, API tests), line 435 (`Verification Plan`)
*   **Discrepancy Description:** `OCRSystem.__init__` binds `log_dir = DEFAULT_LOG_DIR` at import time (`Path("logs")`), and `frontend/app.py` calls `OCRSystem(mmen_ocr_component=...)` without passing `log_dir`. Monkeypatching `frontend.app.DEFAULT_LOG_DIR` alone leaves `POST /api/ocr` appending test records to `logs/gemini_ocr_log.jsonl`. Additionally, `test_survey_extractor.py::test_api_extract_endpoint` calls `TestClient(app)` directly without a fixture, and importing `frontend.app` touches `UPLOADS_DIR` and `TELEMETRY_DB_FILE` at import time.
*   **Rationale:** Test runs will continue polluting `logs/` unless `OCRSystem` and all FastAPI route clients are isolated into `tmp_path`.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Verified directly in `src/gemini_ocr/system.py` line 32 and `frontend/app.py` line 127.
*   ***Proposed Edit:***
    *   Location: Target File #26 (`tests/conftest.py` and existing test files).
    *   Change: Define an `autouse=True` `isolated_frontend_env` fixture in `tests/conftest.py` (or scoped fixture used by all API tests) that patches `frontend.app.OCRSystem` (injecting `log_dir=tmp_logs_dir`), `DEFAULT_LOG_DIR`, `UPLOADS_DIR`, all `*_LOG_FILE`, `TELEMETRY_DB_FILE`, `telemetry_service`, and `app.state.lakehouse_service` into `tmp_path`, and update `test_survey_extractor.py::test_api_extract_endpoint` to accept the shared `client` fixture.

### [Issue 2] [`egm-implementation-readiness` / `egm-codebase-details` / `egm-style`] - Severity: Blocker (`readiness-1-2`)
*   **Affected Scope:** Lines 357, 365 vs. lines 158, 166 (`database_parser` Silver & Quality Gate)
*   **Discrepancy Description:** Line 365 checks `amount <= 0` on `silver_sales_orders` (causing a DuckDB `Binder Error` against `total_amount`), and actual `customers` in `sample_database/sales_database.sql` has `(customer_id, name, email, city)` with no `customer_name` or `segment` columns.
*   **Rationale:** Exact column mapping and coalescing rules are required so Silver SQL and Quality Gate checks do not fail on the bundled `sales_database.sql` fixture.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Verified in `sample_database/sales_database.sql` lines 4–24.
*   ***Proposed Edit:***
    *   Location: `silver.py`, `quality.py`, and line 158 (`database_parser` Silver description).
    *   Change: Standardize `silver_sales_orders.total_amount` (coalescing `total_amount` and `order_amount`) and project `silver_sales_customers` using `COALESCE(name, customer_name) AS customer_name` and `COALESCE(segment, 'unknown') AS segment`.

### [Issue 3] [`egm-implementation-readiness`] - Severity: Blocker (`readiness-1-3`)
*   **Affected Scope:** Lines 354, 365, 375 vs. lines 36, 70, 106, 113–116, 137, 139, 241–243 (`BLOCKED` commit & single-pass fencing)
*   **Discrepancy Description:** `FeatureRange` specifies per-entity `BLOCKED` pointers, manifest-fenced Bronze batches, and single-pass Quarantine splitting, whereas `DetailedRange` specifies batch-global commits (`service.py`), scanning all Bronze files (`silver.py`), and rewriting Silver Parquet twice (`quality.py`).
*   **Rationale:** Implementers cannot build `bronze.py`, `silver.py`, `quality.py`, and `service.py` without one unified per-source/per-mart commit contract.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Directly resolves the `FeatureRange` vs. `DetailedRange` split flagged in both Stage 8 and Stage 9.
*   ***Proposed Edit:***
    *   Location: `bronze.py`, `silver.py`, `quality.py`, `service.py`, and `System Architecture` alignment.
    *   Change: Store `committed_bronze_batches: dict[str, list[str]]`, `watermarks: dict[str, dict[str, str]]`, and `marts: dict[str, MartPointer]` per source/mart; execute Silver deduplication and Quality Gate row splitting in a single `:memory:` DuckDB pass (`COPY` clean Silver + Quarantine once); on a `BLOCKED` entity, delete only that source's uncommitted Bronze batch file and withhold only that source's watermark + dependent mart pointer while healthy sources/marts commit atomically.

### [Issue 4] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Blocker (`readiness-1-4`)
*   **Affected Scope:** Lines 277–438 (`Detailed Implementation Plan`)
*   **Discrepancy Description:** `DetailedRange` lists 28 file items flatly with no incremental phases or intermediate verification checkpoints.
*   **Rationale:** `implementation-readiness-standard.md` requires partitioning implementation into incremental, buildable, testable phases.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Implementation Readiness Standard.
*   ***Proposed Edit:***
    *   Location: `## Detailed Implementation Plan`.
    *   Change: Partition target files into **Phase 1 (Dependencies, Config, Models, Adapters & Bronze)**, **Phase 2 (Silver SQL, Single-Pass Quality Gate, Quarantine, Gold Marts, Orchestrator & Test Isolation)**, and **Phase 3 (CLI, FastAPI Router, SPA DuckLake Tab, API Tests & Docs)**, each ending with an explicit verification checkpoint command.

### [Issue 5] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Blocker (`readiness-1-5`)
*   **Affected Scope:** Lines 306–310 (`models.py`), 346–350 (`bronze.py`), 372–376 (`service.py`)
*   **Discrepancy Description:** All Pydantic response/internal models (`SourceIngestSummary`, `QualityCheckResult`, `QualityGateResult`, `LayerCounts`, `ManifestState`, `BatchRunReport`, `QuarantinePage`, `MartPreviewResponse`) and metadata JSON files (`latest_manifest.json`, `watermarks.json`, `runs_history.jsonl`) omit field names, types, and defaults.
*   **Rationale:** Every downstream module (`service.py`, `lakehouse_routes.py`, `run_lakehouse.py`, `lakehouse.js`) depends on exact JSON keys.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Zero-Decision Rule.
*   ***Proposed Edit:***
    *   Location: `models.py`, `bronze.py`, and `service.py` target items.
    *   Change: Add explicit field-by-field Pydantic schema tables and JSON manifest/watermark/history record schemas.

### [Issue 6] [`egm-implementation-readiness` / `egm-codebase-details` / `egm-style`] - Severity: Blocker (`readiness-1-6`)
*   **Affected Scope:** Lines 309, 324, 349, 355–365, 425 vs. lines 35, 70, 100–101, 135, 137, 156–160
*   **Discrepancy Description:** Field and entity names drift across ranges (`rule_id` vs. `_rule_id`, `payload_sha256`/`payload_hash` vs. `_payload_hash`, `source_record_key`/`record_key` vs. `_record_key`/`run_key`, missing `survey_runs` Quarantine entity in `DetailedRange`).
*   **Rationale:** Implementers and tests must share one canonical set of column and entity identifiers.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Eliminates schema/test mismatch risk.
*   ***Proposed Edit:***
    *   Location: `DetailedRange` (lines 309–425) and `FeatureRange` cross-refs.
    *   Change: Standardize `_rule_id`, `_payload_hash`, `_record_key` (using `_record_key = run_key` for `gemini_ocr`), `total_amount`, and explicitly include `survey_runs` in `quality.py` and the `/api/lakehouse/quarantine` `entity` allowlist.

### [Issue 7] [`egm-implementation-readiness` / `egm-codebase-details` / `egm-style`] - Severity: Blocker (`readiness-1-7`)
*   **Affected Scope:** Lines 351–370 (`silver.py`, `gold.py`)
*   **Discrepancy Description:** Silver tables and Gold Marts omit column names, DuckDB types, nullability, empty-source 0-row Parquet handling, `error_rate` scale, `beacon`-only latency `NULL` handling, and `ducklake.duckdb` export format (`views` vs. `tables`).
*   **Rationale:** Leaves schema contracts and SQL logic completely open to guesswork.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Zero-Decision Rule.
*   ***Proposed Edit:***
    *   Location: `silver.py` and `gold.py` target items.
    *   Change: Specify complete column + DuckDB type contracts for all Silver tables and the four Gold Marts (including `error_rate_pct` on `0.0–100.0`, `NULL` latency quantiles when no non-beacon events exist, empty 0-row typed Parquet outputs when a source is empty, `answer_list_json VARCHAR` for multi-select answers, and exporting materialized `tables` under `silver`/`quarantine`/`gold` schemas inside `lakehouse/ducklake.duckdb`).

### [Issue 8] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Blocker (`readiness-1-8`)
*   **Affected Scope:** Lines 311–345 (`adapters/*.py`), lines 362–366 (`quality.py`)
*   **Discrepancy Description:** `quality.py` omits exact `_rule_id` codes, `_failure_reason` strings, conditional zero-row entity list, required schema checks, and survey truncation scoping; `adapters/*.py` omit landing JSON unwrapping (`record.get("data", record)` for raw CLI outputs), `_source_origin_type` values, canonical JSON serialization (`sort_keys=True`), and `telemetry` `_record_key` format.
*   **Rationale:** Standalone CLI outputs lack the `"data"`/`session_id`/`timestamp` wrapper present in `logs/*_log.jsonl`.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Zero-Decision Rule and verified against `scripts/convert_*.py` / `sample_youtube/sample_channel.json`.
*   ***Proposed Edit:***
    *   Location: `adapters/` and `quality.py` items.
    *   Change: Specify `_source_origin_type` (`"jsonl" | "sqlite" | "landing_json"`), `record.get("data", record)` + single/array unwrapping for `landing/`, `json.dumps(..., sort_keys=True, ensure_ascii=False)` hashing, exact fallback keys per adapter, explicit `_rule_id` table (`OCR_ITEM_ERROR`, `OCR_CONFIDENCE_RANGE`, `TG_INVALID_DATE`, `TG_NEGATIVE_REACTIONS`, `DB_NULL_ORDER_ID`, `DB_NON_POSITIVE_AMOUNT`, `YT_NEGATIVE_DURATION`, `YT_NEGATIVE_VIEWS`, `SURVEY_TRUNCATED_RUN`, `TELEMETRY_INVALID_STATUS`, `TELEMETRY_NEGATIVE_LATENCY`), conditional entities (`silver_sales_customers`, `silver_sales_orders`), and note that truncated `survey_runs` are quarantined while keeping `silver_surveys`/`responses`/`answers` populated from complete runs.

### [Issue 9] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Major (`readiness-1-9`)
*   **Affected Scope:** Line 343 (`adapters/telemetry.py` item #13)
*   **Discrepancy Description:** `src/ducklake/adapters/__init__.py` is nested inside Item #13 instead of listed as an explicit Target File with its registry API.
*   **Rationale:** Phase 5 file write allowlists require explicit entries for every created file.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Clean file enumeration requirement.
*   ***Proposed Edit:***
    *   Location: Target Files list (`src/ducklake/adapters/__init__.py`).
    *   Change: Add `src/ducklake/adapters/__init__.py` as its own numbered Target File defining `ADAPTERS`, `get_adapter(name)`, and `get_all_adapters()`.

### [Issue 10] [`egm-implementation-readiness` / `egm-style`] - Severity: Major (`readiness-1-10`)
*   **Affected Scope:** Lines 304, 349, 375, 380 (`config.py`, `bronze.py`, `service.py`, `run_lakehouse.py`)
*   **Discrepancy Description:** Unspecified config class type (`Frozen dataclass`), `memory_limit` (`512MB`), `keep_last` (`2`), lowercase `batch_id` format matching `^[a-f0-9_-]+$` (`YYYYmmdd_HHMMSS_<8hex>`), `--full-refresh` behavior, empty-batch handling, and Windows `msvcrt.locking` 1-byte lock file initialization.
*   **Rationale:** Eliminates guesswork on configuration, Windows lock behavior (`OSError` on 0-byte files), and incremental vs. full-refresh semantics.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Valid implementation-readiness requirement.
*   ***Proposed Edit:***
    *   Location: `config.py`, `bronze.py`, `service.py`, and `run_lakehouse.py`.
    *   Change: Specify frozen `dataclass` for `LakehouseConfig`, `memory_limit="512MB"`, `keep_last=2`, `batch_id` format `YYYYmmdd_HHMMSS_<8hex>`, empty-batch behavior (skip writing empty Bronze file; still materialize/update if `--full-refresh` or first run), `--full-refresh` behavior (reset watermarks & prior Bronze/Silver/Gold/Manifest for selected sources or full lakehouse), and ensuring `write.lock` holds at least 1 byte before `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`.

### [Issue 11] [`egm-implementation-readiness` / `egm-codebase-details` / `egm-style`] - Severity: Major (`readiness-1-11`)
*   **Affected Scope:** Lines 377–390 (`run_lakehouse.py`, `lakehouse_routes.py`)
*   **Discrepancy Description:** Missing CLI arg specs (`--source` `action="append"`, `--export-duckdb` default `False`) and FastAPI request/response details (`RunBatchRequest` body, `/runs` pagination, `/quarantine` defaults & `422` vs `400`, `/marts/{mart_name}` `limit > 200` `422` validation and empty-manifest `200` empty response).
*   **Rationale:** Prevents contract mismatch between backend routes, CLI, and `lakehouse.js`.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Zero-Decision Rule.
*   ***Proposed Edit:***
    *   Location: `scripts/run_lakehouse.py` and `frontend/lakehouse_routes.py`.
    *   Change: Define exact `argparse` options/defaults and FastAPI Pydantic request/query/response/error status contracts (`422` via FastAPI `Query(ge=1, le=200)` / allowlist `Literal` or `400`/`404`, `200` empty response before first batch).

### [Issue 12] [`egm-implementation-readiness` / `egm-codebase-details`] - Severity: Major (`readiness-1-12`)
*   **Affected Scope:** Lines 397–416 (`index.html`, `style.css`, `app.js`, `lakehouse.js`)
*   **Discrepancy Description:** `frontend/static/index.html` line 38 uses fixed `h-16` on the header container (which clips wrapped tabs); `app.js` omits `setupNavigation()` click wiring and `switchService()` tab/view array resets; and exact DOM IDs/CSS classes/controls for `lakehouse.js` are unspecified.
*   **Rationale:** Verified in `frontend/static/index.html#L38` and `frontend/static/app.js#L193-L279`.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Prevents header clipping bug and wiring omissions.
*   ***Proposed Edit:***
    *   Location: `frontend/static/index.html`, `style.css`, `app.js`, `lakehouse.js`.
    *   Change: Update header container from `h-16` to `min-h-16 py-2`, specify `setupNavigation()` and `switchService("ducklake")` array/label updates (`#historyBtnLabel`, `#brandSubtitle`, `#ocrStatusBadge`), and define exact DOM element IDs and CSS badge classes.

### [Issue 13] [`egm-implementation-readiness`] - Severity: Major (`readiness-1-13`)
*   **Affected Scope:** Lines 422–425 (`tests/test_ducklake_pipeline.py`, `tests/test_ducklake_api.py`)
*   **Discrepancy Description:** Item #27 lacks specific test case names, fixture inputs, and expected assertions (truncated trailing JSONL line recovery, `>16 MB` JSONL line streaming, empty `logs/` initial batch, malformed `runs_history.jsonl` skip, `limit > 200` / invalid `batch_id` rejection, `409` lock contention).
*   **Rationale:** `implementation-readiness-standard.md` requires enumerating happy-path and edge-case test cases explicitly.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Required by the Implementation Readiness Standard.
*   ***Proposed Edit:***
    *   Location: `tests/test_ducklake_pipeline.py` and `tests/test_ducklake_api.py`.
    *   Change: Enumerate named test functions and exact assertions covering every adapter, edge case, Quality Gate transition, CLI exit code, and FastAPI endpoint/error code.

### [Issue 14] [`egm-style`] - Severity: Major (`readiness-1-14`)
*   **Affected Scope:** Lines 319, 324, 339, 354, 365, 370, 375, 425, 436, 437
*   **Discrepancy Description:** Ubiquitous-language violations (`staged` vs. `pre-commit`, `clean` vs. `validated`/`valid`, upstream `runs` vs. `Extraction Runs`, lakehouse `run` vs. `Ingestion Batch`).
*   **Rationale:** Violates `src/CONTEXT.md` and `src/ducklake/CONTEXT.md` `_Avoid_` lists.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Maintains terminology alignment across the entire spec.
*   ***Proposed Edit:***
    *   Location: Cited lines in `DetailedRange`.
    *   Change: Replace `staged` → `pre-commit`, `clean` → `validated`/`valid`, upstream `runs` → `Extraction Runs`, and lakehouse `run` → `Ingestion Batch`.

### [Issue 15] [`egm-style` / `egm-codebase-details`] - Severity: Major (`readiness-1-15`)
*   **Affected Scope:** Lines 324, 334, 356, 360, 388–389, 405
*   **Discrepancy Description:** Adapter & UI drift vs. `FeatureRange` (`sample_chat` does not exist—actual test fixture is `export_source == "messages.html"` and `chat_title == "Min Thike Tun"`; missing `youtube.py` `_is_test_artifact` rule; missing `silver_telegram_reactions` key; telemetry description limited to CSV UUIDs; style/API param wording drift).
*   **Rationale:** Aligns `DetailedRange` with `FeatureRange` and actual codebase fixtures.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Verified in `tests/test_telegram_parser.py` and `logs/telegram_parser_log.jsonl`.
*   ***Proposed Edit:***
    *   Location: Cited lines in `DetailedRange`.
    *   Change: Apply exact fixture/contract alignments from `FeatureRange` (`1..276`).

### [Issue 16] [`egm-style`] - Severity: Major (`readiness-1-16`)
*   **Affected Scope:** Lines 314, 344, 365, 375
*   **Discrepancy Description:** Long run-on sentences (113 words in `quality.py`, 70+ words in `service.py`), synonym redundancy (`"temporary in-memory/temp"`), and vague modifiers (`"safe"`, `"large"`).
*   **Rationale:** Unreadable nested clauses create implementation ambiguity.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Splitting into bulleted specs improves implementer precision.
*   ***Proposed Edit:***
    *   Location: Lines 314, 344, 365, 375.
    *   Change: Rewrite into short bulleted clauses, commit `telemetry.py` backup target to an `:memory:` SQLite connection, and replace `"safe"`/`"large"` with concrete mechanisms.

### [Issue 17] [`egm-implementation-readiness`] - Severity: Nit (`readiness-1-17`)
*   **Affected Scope:** Lines 296–300 (`__init__.py`), 392–395 (`frontend/app.py`)
*   **Discrepancy Description:** `QualityStatus` omitted from `__init__.py` exports, and `app.py` does not explicitly state `LakehouseConfig(project_root=BASE_DIR.parent)`.
*   **Rationale:** Prevents minor import/path omissions.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Quick clarity fix.
*   ***Proposed Edit:***
    *   Location: Items #4 and #21.
    *   Change: Export `QualityStatus` in `__init__.py` and pass `project_root=BASE_DIR.parent` in `frontend/app.py`.

### [Issue 18] [`egm-codebase-details`] - Severity: Nit (`readiness-1-18`)
*   **Affected Scope:** Line 319 (`adapters/gemini_ocr.py`)
*   **Discrepancy Description:** `mmen_ocr.py` line 120 populates full path in `filename` on error items whereas success items use basename.
*   **Rationale:** Normalizing `Path(filename).name` ensures consistent keys across success and error rows.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Verified in `src/gemini_ocr/components/mmen_ocr.py` line 120.
*   ***Proposed Edit:***
    *   Location: `gemini_ocr.py` / `silver.py`.
    *   Change: Normalize `filename` to basename (`Path(filename).name`) during extraction.

### [Issue 19] [`egm-codebase-details`] - Severity: Nit (`readiness-1-19`)
*   **Affected Scope:** Lines 400, 415 (`index.html`, `lakehouse.js`)
*   **Discrepancy Description:** Script load order (`lakehouse.js` after `app.js` to reuse `escapeHtml`/`showToast`/`formatTime`) and idempotent listener guard in `initDuckLakeTab()` are unstated.
*   **Rationale:** Prevents duplicate API requests or undefined helper errors on tab switches.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Standard frontend lifecycle hygiene.
*   ***Proposed Edit:***
    *   Location: `index.html` and `lakehouse.js` items.
    *   Change: Place `<script src="/static/lakehouse.js"></script>` after `app.js` and guard `initDuckLakeTab()` with a one-time initialization flag.

### [Issue 20] [`egm-style`] - Severity: Nit (`readiness-1-20`)
*   **Affected Scope:** Lines 339, 356, 400, 405, 415, 435–437
*   **Discrepancy Description:** Minor prose hygiene (`"orphaned"`, `"fit cleanly"`, `"minimal"`, brittle `3,473-line`/`54 tests` counts, `D:\Data_in\` paths, uncalibrated verification checks).
*   **Rationale:** Repo-relative paths and observable pass criteria prevent stale references.
*   ***AI Suggestion:*** `PROPOSE FIX`
*   ***Justification:*** Clean final polish.
*   ***Proposed Edit:***
    *   Location: Cited lines in `DetailedRange` and `Verification Plan`.
    *   Change: Apply plain-English replacements, use repo-relative `logs/` and `lakehouse/`, and write concrete Verification Plan assertions.
