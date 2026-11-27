# Stage 5: Initial Zoom Out & Inventive Catalyst Review Report

* **Target Document:** [`docs/designs/ducklake_medallion_prototype.md`](file:///D:/Data_in/docs/designs/ducklake_medallion_prototype.md)
* **Standard Applied:** [`zoom-out-standard.md`](file:///C:/Users/USER/.gemini/config/plugins/egm/resources/document_standards/zoom-out-standard.md)
* **Reviewers:** `egm-zoom-out`, `egm-inventive-catalyst`

---

## Part 1: Zoom Out Review (`egm-zoom-out`)

**Verdict: Needs Simplification (1 Blocker, 5 Major, 2 Nit)**

**Baseline Alignment:**
- Objective, constraints, ADRs (`0001`–`0003`), and non-goals are clearly defined.
- Core architectural decisions—zero edits to upstream `src/` packages, pure DuckDB SQL + Parquet instead of `dbt-duckdb`/Airflow/Docker/GX Core, ephemeral `:memory:` DuckDB readers to avoid Windows file locks, and `tmp_path` test isolation for `tests/`—align with the root problem and `README.md`.

### Findings

#### 1. [Blocker] Over-Built Package & File Footprint Relative to Actual Data and Meeting-Prototype Goal (YAGNI / Minimalist Data Flow)
* **Affected Scope:** `Overview` (lines 11–13), `Technical Plan` (lines 76–149), `Detailed Implementation Plan` Items 4–25 (lines 253–373).
* **Simplicity Rationale:** The stated objective is a lightweight local prototype so the team can review Silver schemas and four Gold Marts in a meeting (`The Problem` #4, line 22; `Alternatives Considered` A & H, lines 163, 205). The actual `logs/` files contain 13–26 lines per JSONL stream plus `logs/telemetry.db`. Yet the design prescribes 28 numbered items (~32 touched files), including 15 new Python files in `src/ducklake/`, 8 adapter files, 15 Silver tables, multi-layer `v_<batch_id>` directories with `keep_last=2` garbage collection, `latest_manifest.json` + `watermarks.json` + `runs_history.jsonl`, a `.duckdb` snapshot exporter, a 5-endpoint FastAPI router, and a 3-panel UI with a run-history drawer.
* **Concrete Simplification:** Collapse `src/ducklake/` from 15 files to 3–4 modules (e.g., config/models, ingest, SQL transforms + service) executing Bronze → Silver → Quality Gate → Gold in one DuckDB session, writing clean Parquet snapshots without multi-version retention GC or protocol hierarchies.

#### 2. [Major] Unnecessary `SourceAdapter` Protocol, 8-File Adapter Layer, and Speculative `lakehouse/landing/` Dropzone
* **Affected Scope:** `Component Boundaries` #1 (lines 121–122), `Detailed Implementation Plan` Items 7–13 (lines 268–302), `Goals`/`System Architecture` (lines 28, 84).
* **Simplicity Rationale:** Five of the six sources (`gemini_ocr`, `telegram_parser`, `database_parser`, `youtube_parser`, `survey_extractor`) are plain JSONL files in `logs/*_log.jsonl`. Defining a `SourceAdapter` `Protocol`, an `adapters/__init__.py` registry, and six separate Python modules duplicates file-reading and hashing boilerplate across 8 files. Every adapter also branches to support a speculative `lakehouse/landing/<source>/*.json` dropzone that does not exist and has no upstream producer in v1.
* **Concrete Simplification:** Replace `src/ducklake/adapters/` (8 files) with one table-driven JSONL reader parameterized by a small source config dict plus one helper reading `logs/telemetry.db` (`telemetry_events`). Drop `lakehouse/landing/` support until a producer exists.

#### 3. [Major] Speculative `QualityGate` Protocol for Deferred `great-expectations`
* **Affected Scope:** `Non-Goals` (line 39), `Component Boundaries` #1 (line 124), `Alternatives Considered` Alternative C (line 175), `Future Improvements` (line 227), `Detailed Implementation Plan` Items 16 & 18 (lines 319–322, 331).
* **Simplicity Rationale:** `QualityGate` is introduced as a `Protocol` injected into `LakehouseService(config, quality_gate=None)` solely to swap in `GreatExpectationsQualityGate` later, even though `Non-Goals` excludes GX Core from v1 and GX cannot implement row-level Quarantine splitting anyway.
* **Concrete Simplification:** Implement declarative SQL validation and Quarantine splitting directly in `quality.py`, removing the `QualityGate` `Protocol` and constructor injection.

#### 4. [Major] Redundant Bronze Watermarks + Full-Silver Recompute, Multi-Version `v_<batch_id>` Retention GC, and Speculative `--export-duckdb`
* **Affected Scope:** `Non-Goals` (line 37), `System Architecture & Data Flow` (lines 89–109), `Component Boundaries` (lines 122–127), `Detailed Implementation Plan` Items 14, 17, 18, 19 (lines 303–337).
* **Simplicity Rationale:**
  1. Bronze maintains `watermarks.json` to write incremental `batch_<batch_id>.parquet` files, yet Silver immediately scans all Bronze Parquet files every run and rebuilds every Silver table from scratch (line 311).
  2. Versioned directories across 3 layers (`silver/v_<batch_id>/`, `quarantine/<entity>/v_<batch_id>/`, `gold/v_<batch_id>/`), `latest_manifest.json`, `runs_history.jsonl`, and `keep_last=2` deletion add failure surface for a local prototype.
  3. `--export-duckdb` (`lakehouse/ducklake.duckdb`) is built solely for deferred Metabase integration.
* **Concrete Simplification:** Drop `--export-duckdb` / `ducklake.duckdb`, multi-version `v_<batch_id>` retention GC, and `runs_history.jsonl`. Stage outputs and atomically swap the active snapshot pointer while keeping Gold untouched on `BLOCKED`.

#### 5. [Major] 15 Silver Tables Materialized When v1 Gold Only Consumes 4
* **Affected Scope:** `Non-Goals` (line 40), `Per-Source Silver Modeling & Quality Rules` (lines 141–149), `Detailed Implementation Plan` Item 15 (lines 308–318).
* **Simplicity Rationale:** Silver materializes 15 distinct Parquet tables, including 4-table EAV survey normalization (`silver_surveys`, `silver_survey_questions`, `silver_survey_responses`, `silver_survey_answers`), generic database pass-through tables (`silver_database_tables`, `silver_database_rows`), and `silver_telegram_service_notices`, whereas v1 Gold only reads `silver_sales_orders`, `silver_sales_customers`, `silver_telegram_messages` + reactions, `silver_telemetry_events`, and ingestion counts.
* **Concrete Simplification:** Filter `type != 'service'` inline instead of materializing `silver_telegram_service_notices`. Defer 4-table EAV survey normalization and generic `silver_database_rows` JSON pass-through tables until a Gold Mart or team decision consumes them.

#### 6. [Major] Altitude Drops ("Weeds") in Architecture & Detailed Implementation Plan
* **Affected Scope:** `Component Boundaries` (lines 118–140), `Per-Source Silver Modeling & Quality Rules` (lines 141–149), `Detailed Implementation Plan` Items 1–28 (lines 234–388).
* **Simplicity Rationale:** High-level sections drop into internal filenames (`adapters/base.py`, `config.py`, `models.py`), 10 Pydantic model names, SQL `COALESCE` expressions, CSS class tweaks (`flex-wrap`), JS global hooks (`window.initDuckLakeTab?.()`), pagination caps (`limit <= 200`), retention constants (`keep_last=2`), and HTTP codes (`409 Conflict`, `404`).
* **Concrete Simplification:** Keep high-level design focused on boundaries, storage/concurrency model, source contracts, Quality Gate semantics, and API/UI capabilities; leave internal helper names, SQL expressions, and CSS/JS hooks out of the high-level spec.

#### 7. [Nit] Inaccurate DuckDB 16 MB JSON Limit Rationale & Under-Utilized Native Readers
* **Affected Scope:** `Component Boundaries` #1 (line 122), `Non-Functional Requirements` (line 212), `Detailed Implementation Plan` Item 7 (line 271).
* **Simplicity Rationale:** DuckDB's `read_json` / `read_ndjson` allows raising `maximum_object_size` well above 16 MB, and workspace JSONL lines are only ~9–12 KB.
* **Concrete Simplification:** Cite the real reasons if Python JSONL parsing is kept (malformed-line tolerance and key/hash extraction) rather than the 16 MB limit.

#### 8. [Nit] Unnecessary API & UI Surface (`runs_history`, Paginated `/runs` & `/quarantine`, Drawer) for v1 Prototype
* **Affected Scope:** `CLI & FastAPI Surface` (lines 129–139), `Detailed Implementation Plan` Items 20–25 (lines 339–373).
* **Simplicity Rationale:** Adding `runs_history.jsonl`, `GET /api/lakehouse/runs`, and a separate history drawer adds UI/API CRUD plumbing not needed to review the 4 Gold Marts and Quarantine errors in a meeting.
* **Concrete Simplification:** Keep `POST /api/lakehouse/run`, `GET /api/lakehouse/status` (layer counts, gate result, quarantine summary), and `GET /api/lakehouse/marts/{mart_name}` for v1.

---

## Part 2: Inventive Catalyst Review (`egm-inventive-catalyst`)

### 1. [Blocker] Global Batch `BLOCKED` Gate Couples Independent Sources & Muddles GX Portability
* **Affected Scope:** Quality Gate & Row-Level Quarantine (`#L99-L103`, `#L147`, `#L322`), `docs/adr/0003`.
* **Contradiction:** Preventing corrupt data from reaching Gold (`BLOCKED` if zero clean rows remain in any non-empty staged entity) vs. pipeline availability across 6 independent sources and future GX portability. Truncated legacy `survey_extractor_log.jsonl` lines (lines 1–2) or a single failed OCR upload would freeze unrelated healthy Gold Marts (`gold_web_traffic_mart`, `gold_telegram_engagement_mart`, `gold_sales_kpi_mart`). Coupling row-level Quarantine splitting inside `QualityGate` also breaks clean GX portability because GX only evaluates dataset assertions.
* **Inventive Resolution (`Extraction` + `Segmentation`):**
  1. Move row-level Quarantine classification into Silver SQL so `QualityGate` evaluates only dataset-level assertions on Silver + Quarantine summaries.
  2. Scope circuit-breaking per entity/mart, allowing `latest_manifest.json` to hold per-entity/per-mart version pointers rather than letting one source block all Gold Marts.
* **Secondary Liabilities:** `latest_manifest.json` tracks per-mart/entity pointers instead of one global `batch_id`.

### 2. [Major] Double-Materialized Silver & Three Parallel `v_<batch_id>` Trees Risk Quarantine Data Loss
* **Affected Scope:** `#L93-L108`, `silver.py`, `quality.py`, `service.py` (`#L311-L332`).
* **Contradiction:** Atomic snapshot rollback (`v_<batch_id>`) vs. single-pass efficiency and Quarantine retention safety. `silver.py` writes Silver Parquet, then `quality.py` reads it back and rewrites it without quarantined rows. Meanwhile, `keep_last=2` deletion across `silver/`, `quarantine/`, and `gold/` can prune the live Gold snapshot or wipe `BLOCKED` Quarantine evidence after two consecutive `BLOCKED` batches.
* **Inventive Resolution (`Preliminary Action` + `Segmentation`):**
  1. Run Silver deduplication and Quarantine classification inside the same `:memory:` DuckDB session and `COPY` clean Silver + Quarantine Parquet once.
  2. Store Quarantine append-only (`lakehouse/quarantine/<entity>/batch_<batch_id>.parquet`) outside `v_<batch_id>` retention, and pin all manifest-referenced directories before garbage collection.

### 3. [Major] Five Identical JSONL Adapters Inflate File Count
* **Affected Scope:** `src/ducklake/adapters/` (`#L268-L302`).
* **Contradiction:** Symmetric adapter isolation across 6 sources vs. minimalism. Five JSONL adapters share identical streaming mechanics, differing only in source config and key extraction.
* **Inventive Resolution:** Collapse the 5 JSONL adapters into one parameterized `JsonlSourceAdapter` driven by declarative `SourceSpec` configs, keeping only `telemetry.py` separate for SQLite backup.

### 4. [Major] Split-Brain Commit State Between `watermarks.json` and Bronze Parquet
* **Affected Scope:** `bronze.py`, `service.py`, `watermarks.json` (`#L89-L90`, `#L305-L306`, `#L332`).
* **Contradiction:** Fast incremental skipping vs. single-source-of-truth consistency. Updating `watermarks.json` and `latest_manifest.json` via two `os.replace` calls leaves a crash window and desyncs if `bronze/` is reset.
* **Inventive Resolution (`Self-Service`):** Either derive watermarks directly from committed Bronze Parquet (`arg_max(_payload_hash, _ingested_at)`) or fold watermarks into `latest_manifest.json` for a single atomic `os.replace`.

### 5. [Nit] Unspecified OS-Enforced Lock Semantics on `write.lock` & Brittle Test Monkeypatching
* **Affected Scope:** `#L211`, `#L374-L378`.
* **Contradiction:** Fast-fail `409 Conflict` locking vs. crash recovery. Without OS advisory file locking (`msvcrt.locking` on Windows / `fcntl.flock` on POSIX), a crashed CLI process leaves a stale `write.lock` file that permanently blocks `POST /api/lakehouse/run`.
* **Inventive Resolution:** Mandate OS-enforced non-blocking file locks so process teardown releases the lock automatically.
