"""Tests for OTLP decoding and normalization."""

from datetime import UTC, datetime

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from catsyphon.otel.decoder import normalize_logs


def test_normalize_logs_extracts_core_fields():
    request = ExportLogsServiceRequest()

    resource_logs = request.resource_logs.add()
    resource_logs.resource.attributes.extend(
        [
            KeyValue(
                key="service.name",
                value=AnyValue(string_value="codex"),
            )
        ]
    )

    scope_logs = resource_logs.scope_logs.add()
    scope_logs.scope.name = "codex"
    scope_logs.scope.version = "1.0"

    log_record = scope_logs.log_records.add()
    log_record.time_unix_nano = int(datetime(2026, 1, 28, tzinfo=UTC).timestamp() * 1e9)
    log_record.severity_text = "INFO"
    log_record.severity_number = 9
    log_record.body.string_value = "codex.api_request"
    log_record.attributes.extend(
        [
            KeyValue(
                key="event.name",
                value=AnyValue(string_value="codex.api_request"),
            ),
            KeyValue(
                key="conversation_id",
                value=AnyValue(string_value="conv-123"),
            ),
        ]
    )

    events = normalize_logs(request)

    assert len(events) == 1
    event = events[0]
    assert event.event_name == "codex.api_request"
    assert event.source_conversation_id == "conv-123"
    assert event.severity_text == "INFO"
    assert event.severity_number == 9
    assert event.resource_attributes["service.name"] == "codex"
    assert event.scope_attributes["scope.name"] == "codex"
