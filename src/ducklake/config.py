"""
Configuration for the DuckLake Medallion lakehouse package.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LakehouseConfig:
    """Immutable path and runtime configuration for DuckLake."""

    project_root: Path = Path(__file__).resolve().parents[2]
    logs_dir: Path | None = None
    landing_dir: Path | None = None
    lakehouse_dir: Path | None = None
    export_duckdb: bool = False
    memory_limit: str = "512MB"
    keep_last: int = 2

    def __post_init__(self) -> None:
        root = Path(self.project_root).resolve()
        lakehouse = Path(self.lakehouse_dir).resolve() if self.lakehouse_dir is not None else (root / "lakehouse")
        logs = Path(self.logs_dir).resolve() if self.logs_dir is not None else (root / "logs")
        landing = Path(self.landing_dir).resolve() if self.landing_dir is not None else (lakehouse / "landing")
        object.__setattr__(self, "project_root", root)
        object.__setattr__(self, "logs_dir", logs)
        object.__setattr__(self, "lakehouse_dir", lakehouse)
        object.__setattr__(self, "landing_dir", landing)

    @property
    def bronze_dir(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "bronze"

    @property
    def silver_dir(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "silver"

    @property
    def quarantine_dir(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "quarantine"

    @property
    def gold_dir(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "gold"

    @property
    def metadata_dir(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "metadata"

    @property
    def manifest_path(self) -> Path:
        return self.metadata_dir / "latest_manifest.json"

    @property
    def watermarks_path(self) -> Path:
        return self.metadata_dir / "watermarks.json"

    @property
    def runs_history_path(self) -> Path:
        return self.metadata_dir / "runs_history.jsonl"

    @property
    def write_lock_path(self) -> Path:
        return self.metadata_dir / "write.lock"

    @property
    def duckdb_snapshot_path(self) -> Path:
        assert self.lakehouse_dir is not None
        return self.lakehouse_dir / "ducklake.duckdb"
