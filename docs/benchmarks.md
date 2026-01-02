# Benchmarks

This document describes how to run CatSyphon performance benchmarks from the
web UI or CLI and where results are stored.

## What is covered

- Parser registry overhead vs direct parser calls
- Upload streaming vs batch ingestion (placeholder until streaming upload exists)
- Daemon throughput (placeholder until async daemon exists)

## Web UI

Benchmarks are disabled by default and gated by environment settings.

Required:
- `CATSYPHON_BENCHMARKS_ENABLED=true`

Optional:
- `CATSYPHON_BENCHMARKS_TOKEN=...` (requires a matching header)

If you set a token, also set:
- `VITE_BENCHMARKS_TOKEN=...` (frontend build-time env var)

Then open `/benchmarks` in the web UI and click "Run Benchmarks".

## CLI

Run directly via the backend package:

```bash
uv run python -m catsyphon.benchmarks.run
```

## Results

Results are written to:

- `CATSYPHON_BENCHMARKS_OUTPUT_DIR` (default: `logs/benchmarks`)

Each run produces a JSON file named `{run_id}.json`, plus `status.json`
for the latest run status.

## API endpoints

- `GET /benchmarks/status`
- `POST /benchmarks/run`
- `GET /benchmarks/results/latest`
- `GET /benchmarks/results/{run_id}`

All endpoints require benchmarks to be enabled and will return 403 otherwise.
When a token is configured, clients must send `X-Benchmark-Token`.
