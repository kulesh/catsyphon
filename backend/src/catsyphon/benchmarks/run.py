"""CLI entrypoint for running benchmarks."""

from __future__ import annotations

from catsyphon.benchmarks.runner import run_benchmarks, write_results


def main() -> None:
    results = run_benchmarks()
    run_id = results["run_id"]
    output_path = write_results(run_id, results)
    print(f"Benchmark run {run_id} written to {output_path}")


if __name__ == "__main__":
    main()
