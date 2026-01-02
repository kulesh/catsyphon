"""Tests for benchmark API endpoints."""

from datetime import UTC, datetime

from catsyphon.config import settings
from catsyphon.api.routes import benchmarks as benchmarks_route


class _ImmediateThread:
    """Thread stand-in that executes the target immediately."""

    def __init__(self, target, args=(), daemon=None):
        self._target = target
        self._args = args
        self._daemon = daemon

    def start(self) -> None:
        self._target(*self._args)


def test_benchmark_run_executes_runner(api_client, monkeypatch, tmp_path):
    """Ensure /benchmarks/run calls the runner and completes the status."""
    monkeypatch.setattr(settings, "benchmarks_enabled", True)
    monkeypatch.setattr(settings, "benchmarks_token", None)
    monkeypatch.setattr(settings, "benchmarks_output_dir", str(tmp_path))

    called = {}

    def fake_runner(run_id: str):
        called["run_id"] = run_id
        timestamp = datetime.now(UTC).isoformat()
        return {
            "run_id": run_id,
            "started_at": timestamp,
            "completed_at": timestamp,
            "benchmarks": [],
            "environment": {},
        }

    monkeypatch.setattr(benchmarks_route, "run_benchmarks_runner", fake_runner)
    monkeypatch.setattr(benchmarks_route.threading, "Thread", _ImmediateThread)

    response = api_client.post("/benchmarks/run")
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    assert called["run_id"] == run_id

    status_response = api_client.get("/benchmarks/status")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"

    results_response = api_client.get("/benchmarks/results/latest")
    assert results_response.status_code == 200
    assert results_response.json()["run_id"] == run_id
