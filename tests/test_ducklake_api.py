"""
Integration tests for /api/lakehouse/* FastAPI routes and scripts/run_lakehouse.py CLI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ducklake import LakehouseConfig, LakehouseLockError, LakehouseService
from frontend.app import app
from tests.test_ducklake_pipeline import _seed_all_sources


@pytest.fixture
def lakehouse_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, Path, Path]:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    svc = LakehouseService(LakehouseConfig(project_root=tmp_path, logs_dir=logs_dir, lakehouse_dir=lh_dir))
    monkeypatch.setattr(app.state, "lakehouse_service", svc, raising=False)
    return TestClient(app), logs_dir, lh_dir


def test_api_status_empty_before_first_batch(lakehouse_client: tuple[TestClient, Path, Path]) -> None:
    client, _, _ = lakehouse_client
    resp = client.get("/api/lakehouse/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["latest_batch_id"] is None
    assert data["marts"] == {}

    mart_resp = client.get("/api/lakehouse/marts/gold_ingestion_overview")
    assert mart_resp.status_code == 200
    assert mart_resp.json()["total"] == 0


def test_api_run_and_read_marts_quarantine_runs(lakehouse_client: tuple[TestClient, Path, Path]) -> None:
    client, _, _ = lakehouse_client
    run_resp = client.post("/api/lakehouse/run", json={"full_refresh": False, "export_duckdb": True})
    assert run_resp.status_code == 200
    report = run_resp.json()
    assert report["overall_status"] == "PASSED_WITH_QUARANTINE"
    assert report["exported_duckdb_path"] is not None

    runs_resp = client.get("/api/lakehouse/runs?limit=10&offset=0")
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) == 1

    q_resp = client.get("/api/lakehouse/quarantine?entity=ocr_extractions&limit=50&offset=0")
    assert q_resp.status_code == 200
    assert q_resp.json()["total"] == 1

    mart_resp = client.get("/api/lakehouse/marts/gold_ingestion_overview?limit=50&offset=0")
    assert mart_resp.status_code == 200
    assert mart_resp.json()["total"] == 6


def test_api_validation_errors_and_lock_conflict(lakehouse_client: tuple[TestClient, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = lakehouse_client

    assert client.get("/api/lakehouse/marts/unknown_mart").status_code == 404
    assert client.get("/api/lakehouse/marts/gold_ingestion_overview?limit=201").status_code == 422
    assert client.get("/api/lakehouse/quarantine?entity=invalid_entity").status_code == 422
    assert client.get("/api/lakehouse/quarantine?batch_id=../bad").status_code == 422
    assert client.post("/api/lakehouse/run", json={"sources": ["bad_source"]}).status_code == 422

    def _raise_lock(*args, **kwargs):
        raise LakehouseLockError("locked")

    monkeypatch.setattr(app.state.lakehouse_service, "run_batch", _raise_lock)
    assert client.post("/api/lakehouse/run", json={}).status_code == 409


def test_cli_exit_codes(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    lh_dir = tmp_path / "lakehouse"
    _seed_all_sources(logs_dir)
    script = Path(__file__).resolve().parent.parent / "scripts" / "run_lakehouse.py"

    ok_proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--logs-dir",
            str(logs_dir),
            "--lakehouse-dir",
            str(lh_dir),
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert ok_proc.returncode == 0
    parsed = json.loads(ok_proc.stdout)
    assert parsed["overall_status"] == "PASSED_WITH_QUARANTINE"

    # Corrupt 100% of telegram on a clean lakehouse -> exit code 2 (BLOCKED)
    bad_logs = tmp_path / "bad_logs"
    bad_lh = tmp_path / "bad_lh"
    bad_logs.mkdir()
    (bad_logs / "telegram_parser_log.jsonl").write_text(
        json.dumps(
            {
                "session_id": "s_bad",
                "timestamp": "2026-11-11T00:00:00",
                "chat_title": "Bad",
                "messages": [{"id": 1, "type": "message", "date": "bad", "text": "x", "reaction_count": -5}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    blocked_proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            "telegram_parser",
            "--logs-dir",
            str(bad_logs),
            "--lakehouse-dir",
            str(bad_lh),
        ],
        capture_output=True,
        text=True,
    )
    assert blocked_proc.returncode == 2
