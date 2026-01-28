"""OTEL ingestion helpers."""

from catsyphon.otel.decoder import (
    NormalizedOtelEvent,
    decode_otlp_request,
    normalize_logs,
)

__all__ = [
    "NormalizedOtelEvent",
    "decode_otlp_request",
    "normalize_logs",
]
