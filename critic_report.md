# Stage 7: Critic Review Report (Round 1)

* **Target Document:** [`docs/designs/ducklake_medallion_prototype.md`](file:///D:/Data_in/docs/designs/ducklake_medallion_prototype.md) (`FeatureRange`: lines 1–233)
* **Standard Applied:** [`feature-spec-standard.md`](file:///C:/Users/USER/.gemini/config/plugins/egm/resources/document_standards/feature-spec-standard.md)
* **Reviewers:** `egm-design`, `egm-structural`, `egm-style`

---

## Summary Counts

* **Blockers:** 3 (`egm-design`: 3)
* **Majors:** 14 (`egm-design`: 3, `egm-structural`: 3, `egm-style`: 8)
* **Nits:** 23 (`egm-design`: 3, `egm-structural`: 3, `egm-style`: 17)

---

## Blocker Findings

### `design-1-1` [Blocker] Missing `Risks & Mitigations` Section and Bronze/Watermark Split-Brain on `BLOCKED` or Mid-Batch Failure (`egm-design`)
* **Affected Scope:** Lines 88–104, 122–126, 209–215 (vs. `feature-spec-standard.md` lines 23–27, 38).
* **Description & Rationale:** The spec lacks a `## Risks & Mitigations` section. In `Non-Functional Requirements`, rollback covers only `v_<batch_id>` via `latest_manifest.json`, leaving Bronze vs. `watermarks.json` split-brain unmitigated: writing `lakehouse/bronze/<source>/batch_<batch_id>.parquet` while deferring `watermarks.json` updates until commit either leaves a `BLOCKED` Bronze Parquet file on disk that re-triggers `BLOCKED` on every future Silver scan, or forces duplicate re-ingestion on the next run.
* **Recommendation:** Add `## Risks & Mitigations` and define two-phase staging/fencing for Bronze + `watermarks.json` (e.g., only read manifest-committed Bronze batches or stage Bronze writes atomically before updating watermarks).

### `design-1-2` [Blocker] Underspecified Quality Gate `BLOCKED` Semantics and Cross-Source Blast Radius (`egm-design`)
* **Affected Scope:** Lines 32, 59–60, 99–103, 124, 143–148.
* **Description & Rationale:** The spec lists row-level quarantine conditions per source and one example of `BLOCKED` (`zero valid rows remain`), but never specifies exact dataset-level assertions or whether `BLOCKED` is global across all six sources or scoped per entity/mart. In particular, line 147 flags truncated legacy `survey_extractor` log runs, leaving ambiguity over whether one failing source halts healthy Gold Marts (`gold_sales_kpi_mart`, `gold_telegram_engagement_mart`, `gold_web_traffic_mart`).
* **Recommendation:** Define exact dataset-level `BLOCKED` thresholds/assertions, scope `BLOCKED` per domain/mart (or clarify global vs. per-mart manifest updates), and specify how truncated legacy runs behave on initial bootstrap.

### `design-1-3` [Blocker] Concurrency, Torn Reads, and Windows File-Locking Failure Modes (`egm-design`)
* **Affected Scope:** Lines 30, 62–66, 82, 108, 122, 126, 131, 186, 192, 211 (cross-referenced with `frontend/app.py` lines 362–364).
* **Description & Rationale:**
  1. **Torn JSONL reads:** `POST /api/telegram/attach-photos` in `frontend/app.py` rewrites `logs/telegram_parser_log.jsonl` in place line-by-line without locking; concurrent `run_batch()` execution can read an empty or truncated file, with no defined snapshot-copy or malformed-line retry behavior.
  2. **Stale `write.lock` recovery:** `write.lock` has no specified OS advisory lock (`msvcrt.locking` / `fcntl.flock`) or lease-based stale-lock recovery if a CLI or FastAPI process crashes mid-batch.
  3. **Windows `os.replace` & snapshot retention:** No `v_<batch_id>` retention policy or Windows `PermissionError` handling is defined for overwriting `lakehouse/ducklake.duckdb` or `latest_manifest.json` while readers hold handles.
* **Recommendation:** Specify OS-enforced locks (`msvcrt.locking` / `fcntl.flock`), snapshot-copy or torn-line handling for JSONL inputs, retry/skip-if-locked behavior for `.duckdb` snapshot export, and a manifest-pinned retention policy.

---

## Major Findings

### Design Critic (`egm-design`)

* **`design-1-4` [Major] Missing Security Threat Model and Query-Parameter Validation on `/api/lakehouse/*`** (Lines 130–135, 139, 213; `frontend/app.py` lines 45–51)
  * `GET /api/lakehouse/quarantine` accepts `entity` and `batch_id` without specifying strict allowlist/regex validation to block path traversal or SQL string injection.
  * `frontend/app.py` uses `allow_origins=["*"]` with no auth; adding `POST /api/lakehouse/run` and raw Quarantine inspection increases local DoS (`409` lock starvation) and PII exposure unless localhost-only trust boundaries or origin/rate checks are documented.
  * `frontend/static/lakehouse.js` renders user-supplied Quarantine payloads without requiring HTML escaping / `textContent` DOM rendering to prevent XSS.

* **`design-1-5` [Major] Unaddressed Scalability Limits and Missing Alternative for Full-Scan Silver/Gold Recomputation** (Lines 87–110, 122–126, 157–206, 212)
  * Every `run_batch()` performs a full `telemetry.db` backup, hashes all JSONL lines, and scans all historical Bronze Parquet files in `:memory:` DuckDB to rebuild Silver and Gold. Neither `Alternatives Considered` nor `Non-Functional Requirements` evaluates incremental Silver/Gold updates vs. full recomputation or states local memory/row/timeout limits.

* **`design-1-6` [Major] Data Model, Deduplication Key, and `_is_test_artifact` Gaps Across Sources** (Lines 31, 54, 143–155, 198–199)
  * `database_parser`: No deduplication keys for `silver_database_tables`, `silver_database_rows`, `silver_sales_customers`, or `silver_sales_orders`, risking revenue double-counting on re-uploaded `sales_database.sql`; omits `gold_sales_kpi_mart` date/join columns and missing-customer fallback.
  * `survey_extractor`: No deduplication keys for the four survey Silver tables and unclear Quarantine target when `captured < valid_responses`.
  * `telegram_parser`: `silver_telegram_reactions` lacks schema/keys/quality rules; `gold_telegram_engagement_mart` omits null `sender_name` handling and reaction-total source.
  * `gemini_ocr`: Hashing `(date, files, content)` in `run_key` means re-running OCR on the same file never deduplicates across runs—contradicting *"Silver deduplicates all six sources"* (line 54).
  * `_is_test_artifact`: Exact classification criteria across all six sources are missing.

### Structural Critic (`egm-structural`)

* **`structural-1-1` [Major] Missing `## Risks & Mitigations` Section & Unmitigated Operational Limits** (Lines 209–214)
  * Overlaps with `design-1-1`, `design-1-3`, and `design-1-5`: `feature-spec-standard.md` expects an explicit Risks & Limits / Risks & Mitigations section covering stale `write.lock` recovery, Windows `v_<batch_id>` directory retention, and full-Bronze `:memory:` scan limits.

* **`structural-1-2` [Major] Mis-Nested Heading Hierarchy (`### Additional Resources`, `### Future Improvements`) & Inconsistent Dividers** (Lines 209–232)
  * Both headings sit at `###` under `## Non-Functional Requirements` (line 209) despite a horizontal divider (`---`, line 216), demoting top-level sections. Horizontal rules (`---`) also appear inconsistently across H2 sections.

* **`structural-1-3` [Major] Contradiction Between `BLOCKED` Zero-Valid-Rows Rule and Conditional Zero-Row Sales Tables** (Lines 59, 145, 153)
  * CUJ 2 states `BLOCKED` triggers when *"zero valid rows remain after Quarantine splitting"*, yet lines 145 and 153 allow `silver_sales_*` and `gold_sales_kpi_mart` to legitimately hold zero rows when no conforming sales tables exist. The spec must distinguish "source had no conforming rows" from "all staged rows failed Quality Gate checks."

### Style Critic (`egm-style`)

* **`style-1-1` [Major] Ubiquitous Language Drift (`Daily Activity Spine`)** (Lines 22, 40)
  * Uses `"cross-channel date spine"` (L22) and `"Cross-channel daily spine"` (L40) instead of canonical **`Daily Activity Spine`** (`src/ducklake/CONTEXT.md`).

* **`style-1-2` [Major] Avoid-List Terminology Violations** (Lines 19, 53, 101, 125, 143, 174, 199, 214)
  * Replace `"Beacon pings"` → `"Beacon events"`; `"pipeline run"` → `"Ingestion Batch"`; `"quarantines items"` → `"quarantines records"`; `"clean Silver ..."` → `"validated Silver ..."`; `"bad run"` → `"failed Ingestion Batch"`.

* **`style-1-3` [Major] Stale `Open Questions` Framing** (Line 46)
  * Line 46 defers finalization to *"the Technical Plan and Detailed Implementation Plan sections"* even though Technical Plan is already present at lines 74–155.

* **`style-1-4` [Major] Uncalibrated Performance Claim (`CALIBRATE`)** (Line 187)
  * Replace `"handles in-place file rewrites safely and stays fast at local JSONL file sizes"` with concrete behavior (detects in-place rewrites without missing updates and avoids external cursor state).

* **`style-1-5` [Major] Uncalibrated UX/Performance Claim (`CALIBRATE`)** (Line 212)
  * Replace `"so browser rendering stays responsive"` with `"to bound HTTP payload size and DOM row count"`.

* **`style-1-6` [Major] Overstated SQLite Safety Claim (`CALIBRATE`)** (Line 213)
  * Replace `"prevent write locks or corruption of logs/telemetry.db"` with `"avoid acquiring write locks on or mutating logs/telemetry.db"`.

* **`style-1-7` [Major] Uncalibrated Count & Crash Claims (`CALIBRATE`)** (Lines 20, 66, 168)
  * Qualify `12–26 duplicate lines per log` as observed in current `logs/` files, and replace `"file-lock crashes"` / `"IOException crashes"` with `"file-lock IOException errors"`.

* **`style-1-8` [Major] Mis-nested Heading Hierarchy** (Lines 218, 225)
  * Same as `structural-1-2`: promote `### Additional Resources` and `### Future Improvements` to `##`.

---

## Nit Findings

* **`design-1-7` [Nit] Stale `Open Questions` Deferral** (Lines 44–46) — Overlaps with `style-1-3` / `structural-1-4`.
* **`design-1-8` [Nit] Telemetry Beacon Latency Skew & `runs_history.jsonl` Durability** (Lines 126, 133, 148, 155; `src/telemetry/models.py`) — Beacon events default `latency_ms = 0.0`, which skews P50/P95 latency in `gold_web_traffic_mart` unless filtered (`source_mode != 'beacon'` or `latency_ms > 0`); `runs_history.jsonl` needs malformed-line skip rules.
* **`design-1-9` [Nit] Bare ADR Path References in `Alternatives Considered`** (Lines 163, 174, 181) — Link to full ADR filenames.
* **`structural-1-4` [Nit] Outdated `Open Questions` Wording** (Lines 44–46).
* **`structural-1-5` [Nit] Machine-Specific `file:///D:/Data_in/...` URIs & Unlinked ADRs** (Lines 163, 181, 220–223) — Use repo-relative links where appropriate.
* **`structural-1-6` [Nit] Metadata Column Naming Asymmetry & Avoid-List Echoes** (Lines 19, 31, 53, 88–89, 93, 96, 107, 122, 124, 147, 214) — Standardize `_rule_id` (leading underscore) and `_payload_hash` (vs. `payload_sha256`); replace `"staging"`/`"staged"` with `"pre-commit"`/`"uncommitted"`; tighten `"Quarantines runs"` to `"Quarantines survey Extraction Run records"`.
* **`style-1-9` to `style-1-25` [Nit] Prose Hygiene & Precision** (Lines 11, 19, 21–22, 24, 29–31, 33, 54, 60, 66, 72, 93, 121–122, 125–126, 131, 138, 147, 153, 161, 163, 168–169, 186, 193, 198–199, 204, 211, 214, 227–228):
  * Remove promotional/vague modifiers (`focused`, `lightweight`, `clean`, `transparently`, `safely`, `gracefully`, `straightforward`, `undistorted`, `rapid`, `speculative`, `real`).
  * Replace informal meeting/demo phrasing (`meeting prototype needs`, `reviewed Silver schemas in a meeting`, `team-demo alignment`, `demo populated charts`) with engineering scope phrasing (`v1 prototype scope`, `Silver schema sign-off`).
  * Standardize `"short-lived :memory: DuckDB connections"` (instead of mixing `"ephemeral"`), `"Ingestion Batches"`, `"exclusive cross-process file lock"`, `"Runs the blocking run_batch() call inside asyncio.to_thread"`, `"valid rows"` / `"invalid rows"` (instead of `"corrupt rows"`), `"Quarantine table"` (instead of `"Quarantine error table"`), and `"existing dashboard tabs"` (instead of `"newer tabs"`).
