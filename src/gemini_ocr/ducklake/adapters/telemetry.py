"""
Upstream SourceAdapter for telemetry (SQLite online backup + landing JSON).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config import LakehouseConfig
from ..models import BronzeEnvelope
from .base import hash_payload, iter_landing_records, make_envelope

_TEST_SITE_IDS = frozenset({"upload_test", "test_site", "vercel_sample"})


class TelemetryAdapter:
    source_name = "telemetry"

    def _event_to_envelope(
        self,
        *,
        batch_id: str,
        ingested_at: str,
        origin: str,
        source_file: str,
        event: dict[str, Any],
    ) -> BronzeEnvelope:
        event_id = str(event.get("id") or hash_payload(event))
        site_id = str(event.get("site_id") or "default")
        return make_envelope(
            batch_id=batch_id,
            ingested_at=ingested_at,
            source_name=self.source_name,
            source_origin_type=origin,  # type: ignore[arg-type]
            source_file=source_file,
            record_key=event_id,
            payload=event,
            is_test_artifact=site_id in _TEST_SITE_IDS,
        )

    def _read_sqlite_backup(self, db_path: Path) -> list[dict[str, Any]]:
        if not db_path.exists():
            return []
        uri = f"file:{db_path.as_posix()}?mode=ro"
        src_conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        mem_conn = sqlite3.connect(":memory:")
        try:
            src_conn.backup(mem_conn)
            mem_conn.row_factory = sqlite3.Row
            has_table = mem_conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='telemetry_events'"
            ).fetchone()
            if not has_table:
                return []
            rows = mem_conn.execute("SELECT * FROM telemetry_events").fetchall()
            return [dict(r) for r in rows]
        finally:
            mem_conn.close()
            src_conn.close()

    def read_records(
        self,
        config: LakehouseConfig,
        batch_id: str,
        ingested_at: str,
    ) -> list[BronzeEnvelope]:
        assert config.logs_dir is not None and config.landing_dir is not None
        envelopes: list[BronzeEnvelope] = []
        db_path = config.logs_dir / "telemetry.db"
        for event in self._read_sqlite_backup(db_path):
            envelopes.append(
                self._event_to_envelope(
                    batch_id=batch_id,
                    ingested_at=ingested_at,
                    origin="sqlite",
                    source_file=db_path.name,
                    event=event,
                )
            )
        for rel_file, obj in iter_landing_records(config.landing_dir, self.source_name):
            events = obj.get("recent_events") if isinstance(obj.get("recent_events"), list) else [obj]
            for ev in events:
                if isinstance(ev, dict):
                    envelopes.append(
                        self._event_to_envelope(
                            batch_id=batch_id,
                            ingested_at=ingested_at,
                            origin="landing_json",
                            source_file=rel_file,
                            event=ev,
                        )
                    )
        return envelopes
