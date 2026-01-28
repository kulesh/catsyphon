"""Tests for OTEL ingestion API."""

from datetime import UTC, datetime

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from catsyphon.config import settings
from catsyphon.models.db import OtelEvent


def _build_payload() -> bytes:
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
    log_record = scope_logs.log_records.add()
    log_record.time_unix_nano = int(datetime(2026, 1, 28, tzinfo=UTC).timestamp() * 1e9)
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
    return request.SerializeToString()


def test_otel_ingest_disabled(api_client, monkeypatch):
    monkeypatch.setattr(settings, "otel_ingest_enabled", False)
    response = api_client.post(
        "/v1/logs",
        content=_build_payload(),
        headers={"Content-Type": "application/x-protobuf"},
    )
    assert response.status_code == 403


def test_otel_ingest_requires_token(api_client, monkeypatch):
    monkeypatch.setattr(settings, "otel_ingest_enabled", True)
    monkeypatch.setattr(settings, "otel_ingest_token", "secret")

    response = api_client.post(
        "/v1/logs",
        content=_build_payload(),
        headers={"Content-Type": "application/x-protobuf"},
    )

    assert response.status_code == 401


def test_otel_ingest_persists_events(api_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "otel_ingest_enabled", True)
    monkeypatch.setattr(settings, "otel_ingest_token", "secret")

    response = api_client.post(
        "/v1/logs",
        content=_build_payload(),
        headers={
            "Content-Type": "application/x-protobuf",
            "X-Catsyphon-Otel-Token": "secret",
        },
    )

    assert response.status_code == 200

    events = db_session.query(OtelEvent).all()
    assert len(events) == 1
    assert events[0].event_name == "codex.api_request"
    assert events[0].source_conversation_id == "conv-123"


def test_otel_stats_returns_counts(api_client, monkeypatch):
    monkeypatch.setattr(settings, "otel_ingest_enabled", True)

    response = api_client.get("/otel/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 0
    assert payload["last_event_at"] is None
