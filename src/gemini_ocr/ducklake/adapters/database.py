"""
Upstream SourceAdapter for database_parser.
"""

from __future__ import annotations

from typing import Any

from ..config import LakehouseConfig
from ..models import BronzeEnvelope
from .base import hash_payload, iter_jsonl_records, iter_landing_records, make_envelope


class DatabaseAdapter:
    source_name = "database_parser"

    def _to_envelope(
        self,
        *,
        batch_id: str,
        ingested_at: str,
        origin: str,
        source_file: str,
        raw: dict[str, Any],
    ) -> BronzeEnvelope:
        payload = raw.get("data", raw) if isinstance(raw.get("data"), dict) else raw
        session_id = raw.get("session_id") or payload.get("session_id")
        if session_id:
            record_key = str(session_id)
        else:
            record_key = hash_payload(
                {
                    "database_name": payload.get("database_name"),
                    "export_source": payload.get("export_source"),
                    "total_rows": payload.get("total_rows"),
                }
            )
        is_test = payload.get("export_source") == "sales_database.sql"
        return make_envelope(
            batch_id=batch_id,
            ingested_at=ingested_at,
            source_name=self.source_name,
            source_origin_type=origin,  # type: ignore[arg-type]
            source_file=source_file,
            record_key=record_key,
            payload=payload,
            is_test_artifact=is_test,
        )

    def read_records(
        self,
        config: LakehouseConfig,
        batch_id: str,
        ingested_at: str,
    ) -> list[BronzeEnvelope]:
        assert config.logs_dir is not None and config.landing_dir is not None
        envelopes: list[BronzeEnvelope] = []
        log_path = config.logs_dir / "database_parser_log.jsonl"
        for _, obj in iter_jsonl_records(log_path):
            envelopes.append(
                self._to_envelope(
                    batch_id=batch_id,
                    ingested_at=ingested_at,
                    origin="jsonl",
                    source_file=log_path.name,
                    raw=obj,
                )
            )
        for rel_file, obj in iter_landing_records(config.landing_dir, self.source_name):
            envelopes.append(
                self._to_envelope(
                    batch_id=batch_id,
                    ingested_at=ingested_at,
                    origin="landing_json",
                    source_file=rel_file,
                    raw=obj,
                )
            )
        return envelopes
