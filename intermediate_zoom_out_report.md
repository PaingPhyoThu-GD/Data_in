# Stage 8: Intermediate Zoom Out Review Report

* **Target Document:** [`docs/designs/ducklake_medallion_prototype.md`](file:///D:/Data_in/docs/designs/ducklake_medallion_prototype.md) (`FeatureRange: 1..276`, `DetailedRange: 277..443`)
* **Standard Applied:** [`zoom-out-standard.md`](file:///C:/Users/USER/.gemini/config/plugins/egm/resources/document_standards/zoom-out-standard.md)
* **Prior Stage 5 Report:** [`zoom_out_report.md`](file:///D:/Data_in/zoom_out_report.md)
* **Reviewer:** `egm-zoom-out`

**Verdict: Needs Simplification & Reconciliation (2 Blockers, 4 Majors, 2 Nits)**

Stage 7 Critic mitigations in `FeatureRange` resolved crash-safe lock release (`msvcrt.locking` / `fcntl.flock`) and torn JSONL reads, but left Stage 5's core over-engineering findings open and introduced structural contradictions between updated `FeatureRange` (`1..276`) and unedited `DetailedRange` (`277..443`).

---

## Findings

### 1. [Blocker] Contradictory Partial-Mart `BLOCKED` Semantics vs. Batch-Global Bronze Fencing (`FeatureRange` & `DetailedRange` Misalignment)
* **Affected Scope:** `Goals` (lines 34–36), `CUJ 2` (lines 68–70), `System Architecture` (lines 101–116), `Component Boundaries` (lines 135–139), `Risks & Mitigations` (lines 241–243), vs. `DetailedRange` Items 14, 15, 18 (lines 349, 354, 375).
* **Simplicity Rationale:** `FeatureRange` introduces per-entity `BLOCKED` status and per-mart pointers in `latest_manifest.json` so one bad entity does not freeze unrelated healthy marts (lines 70, 137). Simultaneously, lines 116 and 243 mandate deleting/unfencing the active Bronze `batch_<batch_id>.parquet` and withholding `watermarks.json` + `latest_manifest.json` updates when `BLOCKED` occurs—which is batch-global. Meanwhile, `DetailedRange` was not yet updated for Stage 7:
  * `service.py` (line 375) still commits `watermarks.json` and `latest_manifest.json` only when the whole batch is not `BLOCKED`.
  * `silver.py` (line 354) still reads `"all Bronze Parquet files for each source"`, bypassing `committed_bronze_batches` fencing (lines 106, 243).
  * `quality.py` (line 365) still reads and rewrites clean Silver Parquet after `silver.py` already wrote it, whereas `FeatureRange` specifies single-pass splitting.
* **Concrete Simplification:** Choose one consistent model for v1: either run and commit Bronze/Silver/Quarantine/Gold **per source/mart independently** (each source tracks its own committed Bronze snapshot/batches), **or** revert to batch-atomic `BLOCKED` (dropping per-mart manifest pinning and multi-version GC), and align `DetailedRange` (`silver.py`, `quality.py`, `service.py`) to match.

### 2. [Blocker] Incremental Bronze State (`watermarks.json` + Manifest Fencing + 3-Layer `v_<batch_id>` GC) Paired with Full Recomputation (`Alternative I`)
* **Affected Scope:** `System Architecture` (lines 101–121), `Component Boundaries` (lines 135–139), `Alternative I` (lines 222–226), `Risks & Mitigations` (lines 241–252), `DetailedRange` Items 14–18 (lines 346–376).
* **Simplicity Rationale:** `Alternative I` commits to stateless full-Bronze `:memory:` DuckDB SQL recomputation for Silver and Gold, yet the design retains incremental-pipeline machinery: `watermarks.json`, `committed_bronze_batches` manifest fencing, rollback deletion of uncommitted Bronze batches, three parallel `v_<batch_id>` trees (`silver/`, `quarantine/`, `gold/`), `runs_history.jsonl`, and `keep_last=2` garbage collection with manifest-pinning and Windows `PermissionError` suppression.
* **Concrete Simplification:** Eliminate `watermarks.json`, `committed_bronze_batches` fencing, `runs_history.jsonl`, and `keep_last=2` multi-version directory GC. Derive known `(_record_key, _payload_hash)` directly from existing committed Bronze Parquet when appending new Bronze batches, write Quarantine append-only (`quarantine/<entity>/batch_<batch_id>.parquet`), and swap active Silver/Gold snapshot paths on commit (or rebuild clean Bronze snapshots per run at <100 MB prototype scale).

### 3. [Major] Unaddressed Stage 5 Over-Built Footprint: 15-File `src/ducklake/`, 8-File `adapters/`, Speculative `lakehouse/landing/`, and `QualityGate` Protocol
* **Affected Scope:** `Goals` (lines 32–33), `Non-Goals` (line 45), `System Architecture` (line 96), `Component Boundaries` (lines 131–138), `Alternative C` (line 190), `DetailedRange` Items 4–16, 18 (lines 296–365, 375).
* **Simplicity Rationale:** Stage 5 Blocker #1 and Majors #2–#3 remain open:
  * 8 adapter files (`adapters/base.py`, `__init__.py`, and 6 source modules) for 5 JSONL files + 1 SQLite query, plus speculative `lakehouse/landing/<source>/*.json` branching with no upstream producer.
  * `QualityGate` `Protocol` + DI (`quality_gate=None`) solely for deferred `great-expectations`.
  * Speculative `--export-duckdb` (`lakehouse/ducklake.duckdb`) built only for deferred Metabase integration.
* **Concrete Simplification:** Collapse `src/ducklake/` into 4–5 modules (e.g., `config.py`, `ingest.py` with one table-driven JSONL reader + SQLite helper, `pipeline.py` for single-session DuckDB Silver/Quarantine/Gold SQL, `service.py`). Drop `lakehouse/landing/`, `QualityGate` `Protocol` injection, `--export-duckdb`, `runs_history.jsonl`, `/api/lakehouse/runs`, and the UI Run History drawer from v1.

### 4. [Major] Production `_is_test_artifact` String Heuristics Leak Test Fixtures into `src/ducklake/`
* **Affected Scope:** `Goals` (line 35), `Per-Source Silver Modeling` (lines 156–161), `Gold Mart Definitions` (line 165), `Alternative G` (lines 210–214), `DetailedRange` Items 7–13 (lines 314–344).
* **Simplicity Rationale:** `CUJ 4` / Item 26 already isolates `pytest` into `tmp_path`. Hardcoding 10 test-fixture literals (`'Test OCR Prompt'`, `'messages.html'`, `'sales_database.sql'`, `'TechPulse Explains'`, `'sample_channel.html'`, `'API Test Survey'`, `'survey_test.csv'`, `'upload_test'`, `'test_site'`, `'vercel_sample'`) into production adapters risks misclassifying real sample runs while domain Gold Marts include those rows anyway.
* **Concrete Simplification:** Remove `_is_test_artifact` heuristics from production `src/ducklake/` code and rely on `tmp_path` test isolation (`CUJ 4` / Item 26).

### 5. [Major] Speculative Silver Tables & EAV Modeling Unused by v1 Gold Marts
* **Affected Scope:** `Per-Source Silver Modeling` (lines 157–160), `DetailedRange` Item 15 (lines 356–359).
* **Simplicity Rationale:** Silver still materializes 15 tables including 4-table EAV survey normalization (`silver_surveys`, `silver_survey_questions`, `silver_survey_responses`, `silver_survey_answers`), generic `silver_database_tables` / `silver_database_rows`, and `silver_telegram_service_notices`, even though `Non-Goals` (line 46) defers survey/YouTube/OCR Gold Marts until after Silver schema sign-off.
* **Concrete Simplification:** Filter `type != 'service'` inline rather than materializing `silver_telegram_service_notices`; defer 4-table EAV survey splitting and `silver_database_rows` JSON pass-throughs until a downstream mart consumes them.

### 6. [Major] Remaining Altitude Drops ("Weeds") in `FeatureRange` & Schema/Naming Drift vs. `DetailedRange`
* **Affected Scope:** `Component Boundaries` (lines 131–152), `Per-Source Silver Modeling` (lines 156–161), `NFR` (lines 232–235), vs. `DetailedRange` (lines 309, 324, 355, 365, 425).
* **Simplicity Rationale:** `FeatureRange` includes internal filenames, Pydantic class names, regex literals (`^[a-f0-9_-]+$`), pagination caps (`limit <= 200`), HTTP codes (`409`, `404`), CSS classes (`flex-wrap`, `rounded-[32px]`), JS hooks (`switchService()`, `toggleActiveHistory()`), and SQL expressions (`COALESCE`, `quantile_cont`). Furthermore, `DetailedRange` diverges on field/entity names from `FeatureRange`:
  * `_payload_hash` (line 100) vs. `payload_sha256` (lines 324, 425).
  * `_rule_id` (line 137) vs. `rule_id` (line 365).
  * `(run_key, filename, image_index)` (line 156) vs. `(source_record_key, filename, image_index)` (line 355).
  * `BronzeEnvelope` in `DetailedRange` (line 309) includes `_source_name`, `_source_origin_type`, `_source_file` omitted in `FeatureRange` (line 100).
  * `lakehouse/quarantine/survey_runs/` (line 160) is unspecified in `DetailedRange` (line 365).
* **Concrete Simplification:** Trim implementation literals/CSS/JS hooks out of `FeatureRange` (`1..276`) and reconcile field/entity names across both ranges.

### 7. [Nit] Repeated Low-Level Security/Locking & Scalability Mechanics Across Multiple High-Level Sections
* **Affected Scope:** `Goals` (line 34), `Component Boundaries` (lines 139, 147), `Non-Functional Requirements` (lines 232–234), `Risks & Mitigations` (lines 244–255).
* **Simplicity Rationale:** `msvcrt.locking` / `fcntl.flock`, `^[a-f0-9_-]+$`, `limit <= 200`, and `textContent` escaping are repeated 3–4 times across `FeatureRange`. State architectural invariants once in `NFR` and keep implementation primitives in `DetailedRange`.

### 8. [Nit] `Open Questions: None` Overstates Readiness Given Unresolved Feature/Detail Tensions
* **Affected Scope:** `Open Questions` (lines 52–54).
* **Simplicity Rationale:** Claiming zero open questions while per-mart partial `BLOCKED` vs. batch-global Bronze commit remains contradictory across `FeatureRange` and `DetailedRange` masks an active architectural decision.
