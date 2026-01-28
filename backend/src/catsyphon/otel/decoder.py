"""
OTLP log decoding and normalization helpers.

Transforms OTLP ExportLogsServiceRequest payloads into normalized
Python objects suitable for storage.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence

from google.protobuf.json_format import Parse
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord
from opentelemetry.proto.resource.v1.resource_pb2 import Resource

logger = logging.getLogger(__name__)

OtelValue = (
    str
    | int
    | float
    | bool
    | None
    | list["OtelValue"]
    | dict[str, "OtelValue"]
)


@dataclass(frozen=True)
class NormalizedOtelEvent:
    """Normalized OTLP log record ready for persistence."""

    event_name: str
    event_timestamp: datetime
    severity_text: str | None
    severity_number: int | None
    body: OtelValue | None
    attributes: dict[str, OtelValue]
    resource_attributes: dict[str, OtelValue]
    scope_attributes: dict[str, OtelValue]
    source_conversation_id: str | None
    trace_id: str | None
    span_id: str | None


_CONVERSATION_ID_KEYS: tuple[str, ...] = (
    "conversation_id",
    "conversation.id",
    "session_id",
    "session.id",
    "codex.conversation_id",
    "codex.session_id",
    "codex.session",
    "codex.conversation",
)

_EVENT_NAME_KEYS: tuple[str, ...] = (
    "event.name",
    "event_name",
    "event",
    "name",
    "codex.event",
    "codex.event_name",
    "codex.event_type",
)


def decode_otlp_request(
    payload: bytes,
    *,
    content_type: str | None,
) -> ExportLogsServiceRequest:
    """Decode OTLP HTTP payload into an ExportLogsServiceRequest.

    Args:
        payload: Raw request body bytes.
        content_type: HTTP content-type header (may include charset).

    Returns:
        Parsed ExportLogsServiceRequest.

    Raises:
        ValueError: If payload cannot be parsed.
    """
    if not payload:
        raise ValueError("Empty OTLP payload")

    normalized = (content_type or "").split(";")[0].strip().lower()
    request = ExportLogsServiceRequest()

    try:
        if normalized == "application/json":
            Parse(payload.decode("utf-8"), request)
        else:
            request.ParseFromString(payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to parse OTLP payload: %s", exc)
        raise ValueError("Invalid OTLP payload") from exc

    return request


def normalize_logs(request: ExportLogsServiceRequest) -> list[NormalizedOtelEvent]:
    """Normalize OTLP log export request into internal events.

    Args:
        request: Parsed ExportLogsServiceRequest.

    Returns:
        List of normalized events.
    """
    events: list[NormalizedOtelEvent] = []

    for resource_logs in request.resource_logs:
        resource_attrs = _resource_attributes(resource_logs.resource)
        if resource_logs.schema_url:
            resource_attrs["resource.schema_url"] = resource_logs.schema_url

        for scope_logs in resource_logs.scope_logs:
            scope_attrs = _scope_attributes(scope_logs.scope)
            if scope_logs.schema_url:
                scope_attrs["scope.schema_url"] = scope_logs.schema_url

            for record in scope_logs.log_records:
                attributes = _attributes_to_dict(record.attributes)
                body = _any_value_to_python(record.body)
                event_name = _extract_event_name(body, attributes)
                source_conversation_id = _extract_conversation_id(
                    attributes, resource_attrs, scope_attrs, body
                )
                event_timestamp = _extract_timestamp(record)
                severity_text = record.severity_text or None
                severity_number = (
                    int(record.severity_number) if record.severity_number else None
                )

                events.append(
                    NormalizedOtelEvent(
                        event_name=event_name,
                        event_timestamp=event_timestamp,
                        severity_text=severity_text,
                        severity_number=severity_number,
                        body=body,
                        attributes=attributes,
                        resource_attributes=resource_attrs.copy(),
                        scope_attributes=scope_attrs.copy(),
                        source_conversation_id=source_conversation_id,
                        trace_id=_bytes_to_hex(record.trace_id),
                        span_id=_bytes_to_hex(record.span_id),
                    )
                )

    return events


def _extract_timestamp(record: LogRecord) -> datetime:
    timestamp_ns = record.time_unix_nano or record.observed_time_unix_nano
    if timestamp_ns:
        return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=UTC)
    return datetime.now(UTC)


def _resource_attributes(resource: Resource | None) -> dict[str, OtelValue]:
    if resource is None:
        return {}
    return _attributes_to_dict(resource.attributes)


def _scope_attributes(scope: Any | None) -> dict[str, OtelValue]:
    if scope is None:
        return {}
    scope_attrs = _attributes_to_dict(scope.attributes)
    if getattr(scope, "name", None):
        scope_attrs["scope.name"] = scope.name
    if getattr(scope, "version", None):
        scope_attrs["scope.version"] = scope.version
    return scope_attrs


def _attributes_to_dict(attributes: Sequence[KeyValue]) -> dict[str, OtelValue]:
    return {kv.key: _any_value_to_python(kv.value) for kv in attributes}


def _any_value_to_python(value: AnyValue) -> OtelValue:
    if value is None:
        return None
    if value.HasField("string_value"):
        return value.string_value
    if value.HasField("bool_value"):
        return value.bool_value
    if value.HasField("int_value"):
        return int(value.int_value)
    if value.HasField("double_value"):
        return float(value.double_value)
    if value.HasField("bytes_value"):
        return base64.b64encode(value.bytes_value).decode("ascii")
    if value.HasField("array_value"):
        return [_any_value_to_python(entry) for entry in value.array_value.values]
    if value.HasField("kvlist_value"):
        return {
            entry.key: _any_value_to_python(entry.value)
            for entry in value.kvlist_value.values
        }
    return None


def _extract_event_name(
    body: OtelValue | None,
    attributes: Mapping[str, OtelValue],
) -> str:
    for key in _EVENT_NAME_KEYS:
        value = attributes.get(key)
        if isinstance(value, str) and value:
            return value

    if isinstance(body, str) and body:
        return body

    if isinstance(body, dict):
        for key in _EVENT_NAME_KEYS:
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
        fallback = body.get("type")
        if isinstance(fallback, str) and fallback:
            return fallback

    return "otel.log"


def _extract_conversation_id(
    attributes: Mapping[str, OtelValue],
    resource_attributes: Mapping[str, OtelValue],
    scope_attributes: Mapping[str, OtelValue],
    body: OtelValue | None,
) -> str | None:
    for key in _CONVERSATION_ID_KEYS:
        value = attributes.get(key)
        if value is not None:
            return str(value)
        value = resource_attributes.get(key)
        if value is not None:
            return str(value)
        value = scope_attributes.get(key)
        if value is not None:
            return str(value)

    if isinstance(body, dict):
        for key in _CONVERSATION_ID_KEYS:
            value = body.get(key)
            if value is not None:
                return str(value)

    return None


def _bytes_to_hex(value: bytes) -> str | None:
    if not value:
        return None
    return value.hex()
