"""Benchmark control endpoints."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from catsyphon.api.schemas import BenchmarkResultResponse, BenchmarkStatusResponse
from catsyphon.benchmarks.runner import (
    run_benchmarks as run_benchmarks_runner,
    write_results,
)
from catsyphon.config import settings

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

_status_lock = threading.Lock()


def _output_dir() -> Path:
    output_dir = Path(settings.benchmarks_output_dir)
    if not output_dir.is_absolute():
        output_dir = Path(__file__).resolve().parents[4] / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _status_path() -> Path:
    return _output_dir() / "status.json"


def _load_status() -> dict[str, Any]:
    path = _status_path()
    if not path.exists():
        return {"status": "idle"}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_status(payload: dict[str, Any]) -> None:
    path = _status_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _require_benchmark_access(token: str | None) -> None:
    if not settings.benchmarks_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Benchmarks are disabled",
        )
    if settings.benchmarks_token and token != settings.benchmarks_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid benchmark token",
        )


def _run_benchmarks_async(run_id: str) -> None:
    try:
        results = run_benchmarks_runner(run_id)
        output_path = write_results(run_id, results)
        _write_status(
            {
                "status": "completed",
                "run_id": run_id,
                "started_at": results["started_at"],
                "completed_at": results["completed_at"],
                "result_path": str(output_path),
            }
        )
    except Exception as exc:  # pragma: no cover - defensive
        _write_status(
            {
                "status": "failed",
                "run_id": run_id,
                "error": str(exc),
                "completed_at": datetime.now(UTC).isoformat(),
            }
        )


@router.get("/status", response_model=BenchmarkStatusResponse)
async def get_benchmark_status(
    x_benchmark_token: str | None = Header(default=None),
) -> BenchmarkStatusResponse:
    _require_benchmark_access(x_benchmark_token)
    status_data = _load_status()
    return BenchmarkStatusResponse(
        status=status_data.get("status", "idle"),
        run_id=status_data.get("run_id"),
        started_at=_parse_datetime(status_data.get("started_at")),
        completed_at=_parse_datetime(status_data.get("completed_at")),
        error=status_data.get("error"),
    )


@router.post("/run", response_model=BenchmarkStatusResponse)
async def run_benchmark_suite(
    x_benchmark_token: str | None = Header(default=None),
) -> BenchmarkStatusResponse:
    _require_benchmark_access(x_benchmark_token)

    with _status_lock:
        status_data = _load_status()
        if status_data.get("status") == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Benchmarks already running",
            )

        run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        started_at = datetime.now(UTC).isoformat()
        _write_status(
            {
                "status": "running",
                "run_id": run_id,
                "started_at": started_at,
            }
        )

        thread = threading.Thread(
            target=_run_benchmarks_async, args=(run_id,), daemon=True
        )
        thread.start()

    return BenchmarkStatusResponse(
        status="running",
        run_id=run_id,
        started_at=_parse_datetime(started_at),
    )


@router.get("/results/latest", response_model=BenchmarkResultResponse)
async def get_latest_benchmark_results(
    x_benchmark_token: str | None = Header(default=None),
) -> BenchmarkResultResponse:
    _require_benchmark_access(x_benchmark_token)
    status_data = _load_status()
    result_path = status_data.get("result_path")
    if not result_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No benchmark results found",
        )
    results = json.loads(Path(result_path).read_text(encoding="utf-8"))
    return BenchmarkResultResponse(**results)


@router.get("/results/{run_id}", response_model=BenchmarkResultResponse)
async def get_benchmark_results(
    run_id: str,
    x_benchmark_token: str | None = Header(default=None),
) -> BenchmarkResultResponse:
    _require_benchmark_access(x_benchmark_token)
    result_path = _output_dir() / f"{run_id}.json"
    if not result_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Benchmark results not found",
        )
    results = json.loads(result_path.read_text(encoding="utf-8"))
    return BenchmarkResultResponse(**results)
