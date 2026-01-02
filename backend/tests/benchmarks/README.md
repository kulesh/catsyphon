# Benchmarks

Run the benchmark suite locally:

```bash
uv run python -m catsyphon.benchmarks.run
```

Notes:
- Configure via `CATSYPHON_BENCHMARKS_*` settings in `.env`.
- Web UI triggering is gated by `CATSYPHON_BENCHMARKS_ENABLED` and optional `CATSYPHON_BENCHMARKS_TOKEN`.
