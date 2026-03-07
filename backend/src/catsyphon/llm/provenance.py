"""Helpers for analytics provenance bookkeeping."""

from __future__ import annotations

import hashlib
from typing import Any

from catsyphon.models.db import AnalysisRun


def stable_sha256(value: str) -> str:
    """Return a stable SHA256 hex digest for text inputs."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_to_provenance_dict(run: AnalysisRun) -> dict[str, Any]:
    """Serialize run fields used by API and UI provenance displays."""
    return {
        "run_id": str(run.id),
        "provider": run.provider,
        "model": run.model_id,
        "generated_at": run.completed_at or run.started_at,
        "prompt_version": run.prompt_version,
        "cost_usd": run.cost_usd,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "total_tokens": run.total_tokens,
        "latency_ms": run.latency_ms,
        "status": run.status,
    }

