# OTEL Ingestion (Codex)

CatSyphon can ingest OpenTelemetry (OTLP) log events from Codex.
This is opt-in and disabled by default.

## Server Configuration

Set environment variables in `.env` (or your deployment environment):

```bash
CATSYPHON_OTEL_INGEST_ENABLED=true
# Optional shared secret for OTEL ingest
CATSYPHON_OTEL_INGEST_TOKEN=your-token-here
# Max OTLP payload size in bytes
CATSYPHON_OTEL_MAX_PAYLOAD_BYTES=5000000
```

## Codex Configuration

Codex supports OTLP HTTP export. Point it at CatSyphon and include headers for
workspace isolation (and optional token).

Example `~/.codex/config.toml`:

```toml
[otel]
exporter = { otlp-http = {
  endpoint = "http://localhost:8000/v1/logs",
  protocol = "binary",
  headers = {
    "x-workspace-id" = "<workspace-uuid>",
    "x-catsyphon-otel-token" = "your-token-here"
  }
}}
```

Notes:
- OTEL ingestion requires `X-Workspace-Id` for multi-tenant safety.
- If `CATSYPHON_OTEL_INGEST_TOKEN` is set, you must pass it via header.
- Codex redacts prompts by default unless `log_user_prompt` is enabled.

## Endpoint

- `POST /v1/logs` (OTLP HTTP) - Ingest OTLP log records
- `GET /otel/stats` - Basic ingestion stats per workspace

## Data Mapping

CatSyphon stores:
- Event name (from OTEL attributes or body)
- Timestamps, severity
- Attributes + resource/scope attributes (JSONB)
- Conversation/session IDs when present in OTEL attributes
