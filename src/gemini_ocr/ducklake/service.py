"""
LakehouseService orchestrator, cross-process OS locking, atomic manifest commits, and read API.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

import duckdb

from .adapters import get_adapter, get_all_adapters
from .bronze import load_watermarks, save_watermarks_atomic, stage_bronze_batch
from .config import LakehouseConfig
from .gold import build_gold_marts, export_duckdb_snapshot
from .models import (
    ALLOWED_MARTS,
    ALLOWED_SILVER_ENTITIES,
    ALLOWED_SOURCES,
    BatchRunReport,
    LayerCounts,
    ManifestState,
    MartPointer,
    MartPreviewResponse,
    QUARANTINE_ENTITIES,
    QuarantinePage,
    QualityGateResult,
    QualityStatus,
    SilverPreviewResponse,
)
from .quality import DuckDBSQLQualityGate, ENTITY_TO_SOURCE, QualityGate
from .silver import build_silver_tables

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_BATCH_ID_RE = re.compile(r"^[a-f0-9_-]+$")


class LakehouseLockError(RuntimeError):
    """Raised when another process holds the exclusive write lock."""


def _generate_batch_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


class LakehouseService:
    """Facade coordinating Bronze/Silver/Quality/Gold execution and lock-free reads."""

    def __init__(
        self,
        config: LakehouseConfig | None = None,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self.config = config or LakehouseConfig()
        self.quality_gate: QualityGate = quality_gate or DuckDBSQLQualityGate()

    @contextmanager
    def _acquire_write_lock(self) -> Iterator[None]:
        lock_path = self.config.write_lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                if os.name == "nt":
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise LakehouseLockError("Another DuckLake Ingestion Batch is currently running.") from exc
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    if os.name == "nt":
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(fd)

    def _load_manifest(self) -> ManifestState:
        path = self.config.manifest_path
        if not path.exists():
            return ManifestState()
        try:
            return ManifestState.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return ManifestState()

    def _save_manifest_atomic(self, manifest: ManifestState) -> None:
        path = self.config.manifest_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp_path, path)

    def _append_run_history(self, report: BatchRunReport) -> None:
        path = self.config.runs_history_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(report.model_dump_json(by_alias=True) + "\n")

    def _prune_old_versions(self, manifest: ManifestState) -> None:
        keep_n = max(1, self.config.keep_last)
        pinned_silver = {v for v in manifest.silver_versions.values()}
        pinned_gold = {Path(mp.parquet_path).parent.name for mp in manifest.marts.values()}

        for base_dir, pinned in (
            (self.config.silver_dir, pinned_silver),
            (self.config.gold_dir, pinned_gold),
        ):
            if not base_dir.exists():
                continue
            dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("v_")], key=lambda d: d.name)
            if len(dirs) <= keep_n:
                continue
            for old_dir in dirs[:-keep_n]:
                if old_dir.name in pinned:
                    continue
                try:
                    shutil.rmtree(old_dir)
                except PermissionError:
                    pass

        # Retain up to max(keep_last, 10) quarantine batches per entity for diagnostics
        q_keep = max(keep_n, 10)
        if self.config.quarantine_dir.exists():
            for ent_dir in self.config.quarantine_dir.iterdir():
                if not ent_dir.is_dir():
                    continue
                q_dirs = sorted(
                    [d for d in ent_dir.iterdir() if d.is_dir() and d.name.startswith("v_")],
                    key=lambda d: d.name,
                )
                if len(q_dirs) <= q_keep:
                    continue
                for old_q in q_dirs[:-q_keep]:
                    try:
                        shutil.rmtree(old_q)
                    except PermissionError:
                        pass

    def _clear_for_full_refresh(
        self,
        selected_sources: list[str],
        manifest: ManifestState,
        watermarks: dict[str, dict[str, str]],
    ) -> None:
        for src in selected_sources:
            watermarks.pop(src, None)
            manifest.committed_bronze_batches.pop(src, None)
            src_bronze = self.config.bronze_dir / src
            if src_bronze.exists():
                shutil.rmtree(src_bronze, ignore_errors=True)
        if set(selected_sources) == set(ALLOWED_SOURCES):
            manifest.marts.clear()
            manifest.silver_versions.clear()
            manifest.quarantine_batches.clear()
            manifest.layer_counts = LayerCounts()

    def run_batch(
        self,
        sources: list[str] | None = None,
        full_refresh: bool = False,
        export_duckdb: bool | None = None,
    ) -> BatchRunReport:
        """Execute Bronze -> Silver -> Quality Gate -> Gold end-to-end under OS write lock."""
        selected_sources = list(sources) if sources else list(ALLOWED_SOURCES)
        for s in selected_sources:
            if s not in ALLOWED_SOURCES:
                raise ValueError(f"Unknown source: {s!r}")
        adapters = [get_adapter(s) for s in selected_sources] if sources else get_all_adapters()
        do_export = self.config.export_duckdb if export_duckdb is None else export_duckdb

        with self._acquire_write_lock():
            batch_id = _generate_batch_id()
            started_at = datetime.now(timezone.utc).isoformat()
            manifest = self._load_manifest()
            watermarks = load_watermarks(self.config.watermarks_path)

            if full_refresh:
                self._clear_for_full_refresh(selected_sources, manifest, watermarks)

            bronze_res = stage_bronze_batch(
                config=self.config,
                adapters=adapters,
                batch_id=batch_id,
                ingested_at=started_at,
                committed_watermarks=watermarks,
                full_refresh=full_refresh,
            )

            # Build list of committed + newly staged Bronze files per source
            assert self.config.lakehouse_dir is not None
            bronze_files_by_source: dict[str, list[Path]] = {}
            for src in ALLOWED_SOURCES:
                files: list[Path] = []
                for rel in manifest.committed_bronze_batches.get(src, []):
                    p = self.config.lakehouse_dir / rel
                    if p.exists():
                        files.append(p)
                if src in bronze_res.staged_files:
                    files.append(bronze_res.staged_files[src])
                bronze_files_by_source[src] = files

            conn = duckdb.connect(":memory:")
            try:
                conn.execute(f"SET memory_limit = '{self.config.memory_limit}'")
                build_silver_tables(conn, bronze_files_by_source)

                silver_v_dir = self.config.silver_dir / f"v_{batch_id}"
                gate_result, silver_paths, quarantine_paths, silver_counts, quarantine_counts = (
                    self.quality_gate.evaluate_and_materialize(
                        conn=conn,
                        batch_id=batch_id,
                        evaluated_at=started_at,
                        silver_out_dir=silver_v_dir,
                        quarantine_root=self.config.quarantine_dir,
                    )
                )

                # Determine per-source blocked flags before Gold overview so uncommitted Bronze counts are excluded
                blocked_sources = {
                    ENTITY_TO_SOURCE[ent]
                    for ent, st in gate_result.entity_statuses.items()
                    if st == QualityStatus.BLOCKED and ent in ENTITY_TO_SOURCE
                }

                # Compute total Bronze rows across committed + non-blocked staged files per source
                total_bronze_counts: dict[str, int] = {}
                for src, files in bronze_files_by_source.items():
                    active_files = [
                        p
                        for p in files
                        if not (src in blocked_sources and p == bronze_res.staged_files.get(src))
                    ]
                    if not active_files:
                        total_bronze_counts[src] = 0
                    else:
                        paths_sql = ", ".join(f"'{p.as_posix().replace(chr(39), chr(39)*2)}'" for p in active_files)
                        total_bronze_counts[src] = int(
                            conn.execute(f"SELECT COUNT(*) FROM read_parquet([{paths_sql}])").fetchone()[0]  # type: ignore[index]
                        )

                gold_v_dir = self.config.gold_dir / f"v_{batch_id}"
                gold_paths, gold_counts = build_gold_marts(
                    conn=conn,
                    gold_out_dir=gold_v_dir,
                    bronze_counts=total_bronze_counts,
                    silver_counts=silver_counts,
                    quarantine_counts=quarantine_counts,
                    gate_result=gate_result,
                    ingested_at=started_at,
                )
            finally:
                conn.close()

            for src in selected_sources:
                if src in blocked_sources:
                    # Delete uncommitted Bronze file for blocked source
                    staged = bronze_res.staged_files.get(src)
                    if staged and staged.exists():
                        staged.unlink(missing_ok=True)
                else:
                    watermarks[src] = bronze_res.pending_watermarks.get(src, watermarks.get(src, {}))
                    staged = bronze_res.staged_files.get(src)
                    if staged:
                        rel_bronze = staged.relative_to(self.config.lakehouse_dir).as_posix()
                        committed_list = list(manifest.committed_bronze_batches.get(src, []))
                        if rel_bronze not in committed_list:
                            committed_list.append(rel_bronze)
                        manifest.committed_bronze_batches[src] = committed_list

            # Update per-entity Silver & Quarantine pointers
            for ent, s_path in silver_paths.items():
                src = ENTITY_TO_SOURCE.get(ent)
                if src not in blocked_sources:
                    manifest.silver_versions[ent] = f"v_{batch_id}"
            for ent, q_path in quarantine_paths.items():
                rel_q = q_path.relative_to(self.config.lakehouse_dir).as_posix()
                q_list = list(manifest.quarantine_batches.get(ent, []))
                if rel_q not in q_list:
                    q_list.append(rel_q)
                manifest.quarantine_batches[ent] = q_list

            mart_source_deps: dict[str, str | None] = {
                "gold_ingestion_overview": None,
                "gold_sales_kpi_mart": "database_parser",
                "gold_telegram_engagement_mart": "telegram_parser",
                "gold_web_traffic_mart": "telemetry",
            }
            now_iso = datetime.now(timezone.utc).isoformat()
            for mart_name, m_path in gold_paths.items():
                dep_src = mart_source_deps.get(mart_name)
                if dep_src and dep_src in blocked_sources:
                    continue
                rel_mart = m_path.relative_to(self.config.lakehouse_dir).as_posix()
                manifest.marts[mart_name] = MartPointer(
                    mart_name=mart_name,
                    batch_id=batch_id,
                    parquet_path=rel_mart,
                    row_count=gold_counts.get(mart_name, 0),
                    updated_at=now_iso,
                )

            manifest.latest_batch_id = batch_id
            manifest.latest_status = gate_result.overall_status
            manifest.updated_at = now_iso
            manifest.layer_counts = LayerCounts(
                bronze_by_source=total_bronze_counts,
                silver_by_entity=silver_counts,
                quarantine_by_entity=quarantine_counts,
                gold_by_mart={m: mp.row_count for m, mp in manifest.marts.items()},
            )

            save_watermarks_atomic(self.config.watermarks_path, watermarks)
            self._save_manifest_atomic(manifest)
            self._prune_old_versions(manifest)

            warnings: list[str] = []
            exported_path_str: str | None = None
            if do_export:
                committed_silver_files: dict[str, Path] = {}
                for ent, ver in manifest.silver_versions.items():
                    for candidate in (self.config.silver_dir / ver).glob("*.parquet"):
                        # Map entity to its table file if present
                        if candidate.stem == f"silver_{ent}" or (
                            ent == "ocr_extractions" and candidate.stem == "silver_ocr_extractions"
                        ):
                            committed_silver_files[ent] = candidate
                committed_q_files = {
                    ent: [self.config.lakehouse_dir / p for p in paths]
                    for ent, paths in manifest.quarantine_batches.items()
                    if paths
                }
                committed_gold_files = {
                    m: self.config.lakehouse_dir / mp.parquet_path
                    for m, mp in manifest.marts.items()
                }
                ok, warn = export_duckdb_snapshot(
                    self.config.duckdb_snapshot_path,
                    committed_silver_files,
                    committed_q_files,
                    committed_gold_files,
                )
                if ok:
                    exported_path_str = str(self.config.duckdb_snapshot_path)
                elif warn:
                    warnings.append(warn)

            completed_at = datetime.now(timezone.utc).isoformat()
            report = BatchRunReport(
                batch_id=batch_id,
                started_at=started_at,
                completed_at=completed_at,
                full_refresh=full_refresh,
                overall_status=gate_result.overall_status,
                sources=bronze_res.summaries,
                quality=gate_result,
                layer_counts=manifest.layer_counts,
                exported_duckdb_path=exported_path_str,
                warnings=warnings,
            )
            self._append_run_history(report)
            return report

    def get_status(self) -> ManifestState:
        """Return current ManifestState (empty state if no Ingestion Batch has run yet)."""
        return self._load_manifest()

    def list_runs(self, limit: int = 20, offset: int = 0) -> list[BatchRunReport]:
        """Read paginated BatchRunReport history, skipping malformed JSONL lines."""
        path = self.config.runs_history_path
        if not path.exists():
            return []
        reports: list[BatchRunReport] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                reports.append(BatchRunReport.model_validate_json(stripped))
            except Exception:
                continue
        reports.reverse()
        return reports[offset : offset + limit]

    def get_quarantine(
        self,
        entity: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QuarantinePage:
        """Query Quarantine Parquet files via a short-lived :memory: DuckDB connection."""
        if entity is not None and entity not in QUARANTINE_ENTITIES:
            raise ValueError(f"Unknown quarantine entity: {entity!r}")
        if batch_id is not None and not _BATCH_ID_RE.match(batch_id):
            raise ValueError(f"Invalid batch_id format: {batch_id!r}")

        manifest = self._load_manifest()
        assert self.config.lakehouse_dir is not None
        target_entities = [entity] if entity else sorted(manifest.quarantine_batches.keys())
        parquet_files: list[tuple[str, Path]] = []
        for ent in target_entities:
            for rel in manifest.quarantine_batches.get(ent, []):
                p = self.config.lakehouse_dir / rel
                if p.exists():
                    if batch_id is None or f"v_{batch_id}" == p.parent.name:
                        parquet_files.append((ent, p))

        if not parquet_files:
            return QuarantinePage(total=0, limit=limit, offset=offset, entities=list(manifest.quarantine_batches.keys()), rows=[])

        conn = duckdb.connect(":memory:")
        try:
            unions = []
            for ent, fpath in parquet_files:
                esc = fpath.as_posix().replace("'", "''")
                unions.append(f"SELECT '{ent}' AS _entity, * FROM read_parquet('{esc}')")
            union_sql = " UNION ALL ".join(unions)
            total = int(conn.execute(f"SELECT COUNT(*) FROM ({union_sql})").fetchone()[0])  # type: ignore[index]
            cur = conn.execute(
                f"SELECT * FROM ({union_sql}) ORDER BY _quarantined_at DESC LIMIT ? OFFSET ?",
                [limit, offset],
            )
            cols = [desc[0] for desc in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return QuarantinePage(
                total=total,
                limit=limit,
                offset=offset,
                entities=list(manifest.quarantine_batches.keys()),
                rows=rows,
            )
        finally:
            conn.close()

    @staticmethod
    def _query_parquet_page(
        parquet_path: Path,
        limit: int,
        offset: int,
    ) -> tuple[int, list[str], list[dict[str, Any]]]:
        """Read a paginated slice of rows from a Parquet file via a short-lived :memory: DuckDB connection."""
        conn = duckdb.connect(":memory:")
        try:
            esc = parquet_path.as_posix().replace("'", "''")
            total = int(conn.execute(f"SELECT COUNT(*) FROM read_parquet('{esc}')").fetchone()[0])  # type: ignore[index]
            cur = conn.execute(f"SELECT * FROM read_parquet('{esc}') LIMIT ? OFFSET ?", [limit, offset])
            cols = [desc[0] for desc in cur.description]
            rows = [
                {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, rec)}
                for rec in cur.fetchall()
            ]
            return total, cols, rows
        finally:
            conn.close()

    def get_mart_preview(
        self,
        mart_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> MartPreviewResponse:
        """Query an allowlisted Gold Mart Parquet snapshot via a short-lived :memory: DuckDB connection."""
        if mart_name not in ALLOWED_MARTS:
            raise KeyError(f"Unknown Gold Mart: {mart_name!r}")

        manifest = self._load_manifest()
        pointer = manifest.marts.get(mart_name)
        assert self.config.lakehouse_dir is not None
        if pointer is None:
            return MartPreviewResponse(mart_name=mart_name, batch_id=None, total=0, limit=limit, offset=offset)

        parquet_path = self.config.lakehouse_dir / pointer.parquet_path
        if not parquet_path.exists():
            return MartPreviewResponse(mart_name=mart_name, batch_id=pointer.batch_id, total=0, limit=limit, offset=offset)

        total, cols, rows = self._query_parquet_page(parquet_path, limit, offset)
        return MartPreviewResponse(
            mart_name=mart_name,
            batch_id=pointer.batch_id,
            total=total,
            limit=limit,
            offset=offset,
            columns=cols,
            rows=rows,
        )

    def get_silver_preview(
        self,
        entity: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SilverPreviewResponse:
        """Query an allowlisted committed Silver entity Parquet snapshot via :memory: DuckDB."""
        if entity not in ALLOWED_SILVER_ENTITIES:
            raise KeyError(f"Unknown Silver entity: {entity!r}")

        manifest = self._load_manifest()
        ver = manifest.silver_versions.get(entity)
        assert self.config.silver_dir is not None
        if ver is None:
            return SilverPreviewResponse(entity=entity, version=None, total=0, limit=limit, offset=offset)

        parquet_path = self.config.silver_dir / ver / f"silver_{entity}.parquet"
        if not parquet_path.exists():
            return SilverPreviewResponse(entity=entity, version=ver, total=0, limit=limit, offset=offset)

        total, cols, rows = self._query_parquet_page(parquet_path, limit, offset)
        return SilverPreviewResponse(
            entity=entity,
            version=ver,
            total=total,
            limit=limit,
            offset=offset,
            columns=cols,
            rows=rows,
        )
