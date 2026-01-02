"""
Benchmark runner utilities.

Benchmarks are intentionally lightweight and produce JSON results suitable
for the web UI to display.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from catsyphon.config import settings
from catsyphon.parsers.claude_code import ClaudeCodeParser
from catsyphon.parsers.codex import CodexParser
from catsyphon.parsers.registry import ParserRegistry


@dataclass
class BenchmarkResult:
    name: str
    status: str
    data: dict[str, Any]
    error: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _benchmark_output_dir() -> Path:
    output_dir = Path(settings.benchmarks_output_dir)
    if not output_dir.is_absolute():
        output_dir = _repo_root() / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _time_call(func: Callable[[], Any], iterations: int) -> float:
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    return time.perf_counter() - start


def _fixture_paths() -> list[Path]:
    fixture_dir = _repo_root() / "backend/tests/test_parsers/fixtures"
    candidates = [
        "full_conversation.jsonl",
        "plan_conversation.jsonl",
        "agent_conversation.jsonl",
    ]
    paths = [fixture_dir / name for name in candidates]
    return [path for path in paths if path.exists()]


def benchmark_parser_registry_overhead() -> BenchmarkResult:
    fixtures = _fixture_paths()
    if not fixtures:
        return BenchmarkResult(
            name="parser_registry_overhead",
            status="skipped",
            data={
                "reason": "No parser fixtures found",
                "fixture_dir": str(_repo_root() / "backend/tests/test_parsers/fixtures"),
            },
        )

    iterations = max(1, settings.benchmarks_iterations)
    registry = ParserRegistry()
    registry.register(CodexParser())
    registry.register(ClaudeCodeParser())

    direct_parser = ClaudeCodeParser()
    cases: list[dict[str, Any]] = []
    direct_total = 0.0
    registry_total = 0.0

    for fixture in fixtures:
        try:
            direct_time = _time_call(lambda: direct_parser.parse(fixture), iterations)
            registry_time = _time_call(
                lambda: registry.parse_with_metadata(fixture), iterations
            )
        except Exception as exc:  # pragma: no cover - defensive
            return BenchmarkResult(
                name="parser_registry_overhead",
                status="failed",
                data={"fixture": str(fixture)},
                error=str(exc),
            )

        cases.append(
            {
                "fixture": fixture.name,
                "iterations": iterations,
                "direct_seconds": direct_time,
                "registry_seconds": registry_time,
                "overhead_ratio": (
                    registry_time / direct_time if direct_time > 0 else None
                ),
            }
        )
        direct_total += direct_time
        registry_total += registry_time

    overall_ratio = registry_total / direct_total if direct_total > 0 else None
    return BenchmarkResult(
        name="parser_registry_overhead",
        status="ok",
        data={
            "iterations": iterations,
            "cases": cases,
            "direct_total_seconds": direct_total,
            "registry_total_seconds": registry_total,
            "overhead_ratio": overall_ratio,
        },
    )


def benchmark_upload_streaming_vs_batch() -> BenchmarkResult:
    return BenchmarkResult(
        name="upload_streaming_vs_batch",
        status="skipped",
        data={
            "reason": "Requires streaming upload endpoint and a running server",
        },
    )


def benchmark_daemon_throughput() -> BenchmarkResult:
    return BenchmarkResult(
        name="daemon_throughput",
        status="skipped",
        data={
            "reason": "Requires async daemon implementation for comparison",
        },
    )


def run_benchmarks(run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or uuid4().hex
    started_at = datetime.now(UTC)

    benchmarks = [
        benchmark_parser_registry_overhead(),
        benchmark_upload_streaming_vs_batch(),
        benchmark_daemon_throughput(),
    ]

    completed_at = datetime.now(UTC)
    return {
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "benchmarks": [
            {
                "name": b.name,
                "status": b.status,
                "data": b.data,
                "error": b.error,
            }
            for b in benchmarks
        ],
        "environment": {
            "iterations": settings.benchmarks_iterations,
        },
    }


def write_results(run_id: str, results: dict[str, Any]) -> Path:
    output_dir = _benchmark_output_dir()
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return output_path

