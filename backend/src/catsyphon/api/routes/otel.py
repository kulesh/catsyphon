"""
OpenTelemetry OTLP ingestion endpoints.

Accepts OTLP log exports from Codex/OpenTelemetry exporters and stores
normalized event records.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from catsyphon.api.auth import AuthContext, get_auth_context
from catsyphon.api.schemas import OtelStatsResponse
from catsyphon.config import settings
from catsyphon.db.connection import get_db
from catsyphon.db.repositories import OtelEventRepository
from catsyphon.otel import decode_otlp_request, normalize_logs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["otel"])


def _require_otel_access(token: str | None) -> None:
    if not settings.otel_ingest_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OTEL ingest is disabled",
        )
    if settings.otel_ingest_token and token != settings.otel_ingest_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTEL token",
        )


def _extract_token(authorization: str | None, x_otel_token: str | None) -> str | None:
    if x_otel_token:
        return x_otel_token
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


def _normalize_body_payload(value: Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}


@router.post("/v1/logs")
async def ingest_otel_logs(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
    content_type: str | None = Header(default=None, alias="Content-Type"),
    authorization: str | None = Header(default=None),
    x_catsyphon_otel_token: str | None = Header(
        default=None, alias="X-Catsyphon-Otel-Token"
    ),
) -> Response:
    """Ingest OTLP log records for a workspace."""
    token = _extract_token(authorization, x_catsyphon_otel_token)
    _require_otel_access(token)

    payload = await request.body()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty OTLP payload",
        )

    if len(payload) > settings.otel_ingest_max_payload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="OTLP payload exceeds max size",
        )

    try:
        export_request = decode_otlp_request(payload, content_type=content_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    normalized = normalize_logs(export_request)
    if not normalized:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    repo = OtelEventRepository(session)
    records = [
        {
            "workspace_id": auth.workspace_id,
            "source_conversation_id": event.source_conversation_id,
            "event_name": event.event_name,
            "event_timestamp": event.event_timestamp,
            "severity_text": event.severity_text,
            "severity_number": event.severity_number,
            "trace_id": event.trace_id,
            "span_id": event.span_id,
            "body": _normalize_body_payload(event.body),
            "attributes": event.attributes,
            "resource_attributes": event.resource_attributes,
            "scope_attributes": event.scope_attributes,
        }
        for event in normalized
    ]

    repo.bulk_create(records)
    logger.info(
        "Ingested %d OTEL events for workspace %s",
        len(records),
        auth.workspace_id,
    )

    return Response(status_code=status.HTTP_200_OK)


@router.get("/otel/stats", response_model=OtelStatsResponse)
async def get_otel_stats(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_db),
) -> OtelStatsResponse:
    """Get OTEL ingestion stats for a workspace."""
    repo = OtelEventRepository(session)
    return OtelStatsResponse(
        total_events=repo.count_by_workspace(auth.workspace_id),
        last_event_at=repo.last_event_time(auth.workspace_id),
    )
