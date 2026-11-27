"""
Base SourceAdapter protocol and shared read-only streaming/hashing utilities.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Iterator, Literal, Protocol

from ..config import LakehouseConfig
from ..models import BronzeEnvelope

logger = logging.getLogger(__name__)


class SourceAdapter(Protocol):
    """Contract implemented by each upstream ingestion adapter."""

    source_name: str

    def read_records(
        self,
        config: LakehouseConfig,
        batch_id: str,
        ingested_at: str,
    ) -> list[BronzeEnvelope]:
        ...


def hash_payload(obj: Any) -> str:
    """Compute canonical SHA-256 hex digest for a JSON-serializable object."""
    canonical = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_envelope(
    *,
    batch_id: str,
    ingested_at: str,
    source_name: str,
    source_origin_type: Literal["jsonl", "sqlite", "landing_json"],
    source_file: str,
    record_key: str,
    payload: Any,
    is_test_artifact: bool,
) -> BronzeEnvelope:
    """Wrap an unmodified upstream payload in a BronzeEnvelope."""
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    payload_hash = hash_payload(payload)
    return BronzeEnvelope(
        _ingest_id=uuid.uuid4().hex,
        _batch_id=batch_id,
        _ingested_at=ingested_at,
        _source_name=source_name,
        _source_origin_type=source_origin_type,
        _source_file=source_file,
        _record_key=record_key,
        _payload_hash=payload_hash,
        _is_test_artifact=is_test_artifact,
        payload_json=payload_json,
    )


def iter_jsonl_records(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """
    Copy a JSONL file into memory before parsing lines to avoid torn reads
    during concurrent in-place rewrites and skip trailing incomplete JSON lines.
    """
    if not path.exists():
        return

    raw_bytes = path.read_bytes()
    lines = raw_bytes.decode("utf-8", errors="replace").splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping malformed JSONL line %d in %s: %s", idx, path.name, exc)
            continue
        if isinstance(obj, dict):
            yield idx, obj


def iter_landing_records(landing_dir: Path, source_name: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """Read standalone JSON exports from lakehouse/landing/<source_name>/*.json."""
    source_dir = landing_dir / source_name
    if not source_dir.exists():
        return

    for file_path in sorted(source_dir.glob("*.json")):
        try:
            raw_obj = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Skipping invalid landing JSON %s: %s", file_path, exc)
            continue

        rel_name = f"landing/{source_name}/{file_path.name}"
        if isinstance(raw_obj, list):
            for item in raw_obj:
                if isinstance(item, dict):
                    yield rel_name, item
        elif isinstance(raw_obj, dict):
            yield rel_name, raw_obj
