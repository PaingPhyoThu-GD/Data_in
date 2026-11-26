"""
Upstream SourceAdapter for survey_extractor.
"""

from __future__ import annotations

from typing import Any

from ..config import LakehouseConfig
from ..models import BronzeEnvelope
from .base import iter_jsonl_records, iter_landing_records, make_envelope


class SurveyAdapter:
    source_name = "survey_extractor"

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
        meta = payload.get("metadata") or {}
        survey_id = raw.get("survey_id") or payload.get("survey_id") or meta.get("survey_id") or "unknown"
        ts = raw.get("timestamp") or meta.get("created_at") or ""
        record_key = f"{survey_id}|{ts}"

        title = raw.get("title") or meta.get("title")
        file_name = raw.get("file_name") or meta.get("file_name")
        is_test = title == "API Test Survey" or file_name == "survey_test.csv"
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
        # Reads survey_extractor_log.jsonl only; unused logs/surveys.db is omitted per ADR-0002.
        log_path = config.logs_dir / "survey_extractor_log.jsonl"
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
