/**
 * Benchmarks page - run and review performance benchmarks.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Activity, Gauge, AlertTriangle, Play, RefreshCw } from 'lucide-react';
import {
  ApiError,
  getBenchmarkAvailability,
  getBenchmarkStatus,
  getLatestBenchmarkResults,
  hasBenchmarkToken,
  runBenchmarks,
} from '@/lib/api';

export default function Benchmarks() {
  const [benchmarksAvailable, setBenchmarksAvailable] = useState(true);
  const availabilityQuery = useQuery({
    queryKey: ['benchmarks', 'availability'],
    queryFn: () => getBenchmarkAvailability(),
    retry: false,
    staleTime: 60000,
  });

  const benchmarkRequiresToken = availabilityQuery.data?.requires_token ?? false;
  const benchmarkEnabledByConfig = availabilityQuery.data?.enabled ?? true;
  const benchmarkHasToken = hasBenchmarkToken();
  const benchmarkEnabled =
    benchmarksAvailable &&
    benchmarkEnabledByConfig &&
    (!benchmarkRequiresToken || benchmarkHasToken);

  const statusQuery = useQuery({
    queryKey: ['benchmarks', 'status'],
    queryFn: () => getBenchmarkStatus(),
    enabled: benchmarkEnabled,
    retry: false,
    refetchInterval: (data) =>
      benchmarkEnabled ? (data?.status === 'running' ? 2000 : 10000) : false,
    onError: (err) => {
      if (err instanceof ApiError && err.status === 403) {
        setBenchmarksAvailable(false);
      }
    },
  });

  const resultsQuery = useQuery({
    queryKey: ['benchmarks', 'results', 'latest'],
    queryFn: () => getLatestBenchmarkResults(),
    enabled: benchmarkEnabled && statusQuery.data?.status === 'completed',
    retry: false,
  });

  const runMutation = useMutation({
    mutationFn: () => runBenchmarks(),
    onSuccess: () => {
      statusQuery.refetch();
    },
  });

  const status = statusQuery.data?.status || (benchmarkEnabled ? 'unknown' : 'disabled');
  const lastRunId = statusQuery.data?.run_id;

  const results = resultsQuery.data;

  const statusBadge = useMemo(() => {
    if (status === 'running') return 'bg-amber-500/20 text-amber-300';
    if (status === 'completed') return 'bg-emerald-500/20 text-emerald-300';
    if (status === 'failed') return 'bg-red-500/20 text-red-300';
    return 'bg-slate-500/20 text-slate-300';
  }, [status]);

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto p-6">
        <div className="observatory-card p-6 mb-6">
          <div className="flex items-center justify-between gap-6 flex-wrap">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Gauge className="w-5 h-5 text-cyan-400" />
                <h1 className="text-2xl font-heading text-foreground">
                  Benchmarks
                </h1>
              </div>
              <p className="text-sm text-muted-foreground font-mono">
                Run performance benchmarks and review the latest results.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span
                className={`px-3 py-1 rounded-full text-xs font-mono ${statusBadge}`}
              >
                {status.toUpperCase()}
              </span>
              <button
                onClick={() => runMutation.mutate()}
                disabled={
                  runMutation.isPending || status === 'running' || !benchmarkEnabled
                }
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-200 hover:bg-cyan-500/30 transition disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {status === 'running' ? 'Running…' : 'Run Benchmarks'}
              </button>
              <button
                onClick={() => statusQuery.refetch()}
                disabled={!benchmarkEnabled}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-accent/50 text-muted-foreground hover:text-foreground"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
          </div>

          {!benchmarkEnabledByConfig && (
            <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <div className="flex items-center gap-2 text-amber-300">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-mono">
                  Benchmarks are disabled. Enable them in the backend settings to use this page.
                </span>
              </div>
            </div>
          )}

          {benchmarkEnabledByConfig && benchmarkRequiresToken && !benchmarkHasToken && (
            <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <div className="flex items-center gap-2 text-amber-300">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-mono">
                  Benchmarks require a token. Set `VITE_BENCHMARKS_TOKEN` to access them.
                </span>
              </div>
            </div>
          )}

          {!benchmarksAvailable && (
            <div className="mt-4 p-4 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <div className="flex items-center gap-2 text-amber-300">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-mono">
                  Benchmarks are unavailable. Check your benchmark token or backend settings.
                </span>
              </div>
            </div>
          )}

          {statusQuery.isError && benchmarkEnabled && (
            <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 text-red-300">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-mono">
                  {statusQuery.error?.message || 'Failed to load benchmark status'}
                </span>
              </div>
            </div>
          )}

          {statusQuery.data?.error && (
            <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <div className="flex items-center gap-2 text-red-300">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm font-mono">
                  {statusQuery.data.error}
                </span>
              </div>
            </div>
          )}

          {lastRunId && (
            <div className="mt-4 text-xs font-mono text-muted-foreground">
              Last run: {lastRunId}
            </div>
          )}
        </div>

        <div className="observatory-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-4 h-4 text-emerald-400" />
            <h2 className="text-lg font-heading text-foreground">Latest Results</h2>
          </div>

          {status === 'running' && (
            <p className="text-sm font-mono text-muted-foreground">
              Benchmarks are running. Results will appear when complete.
            </p>
          )}

          {resultsQuery.isError && (
            <p className="text-sm font-mono text-muted-foreground">
              {resultsQuery.error?.message || 'No benchmark results available yet.'}
            </p>
          )}

          {!results && status !== 'running' && (
            <p className="text-sm font-mono text-muted-foreground">
              No benchmark results yet. Run the benchmarks to generate results.
            </p>
          )}

          {results && (
            <div className="space-y-4">
              <div className="text-xs font-mono text-muted-foreground">
                Run ID: {results.run_id}
              </div>
              {results.benchmarks.map((benchmark) => (
                <div
                  key={benchmark.name}
                  className="rounded-lg border border-border/60 bg-card/60 p-4"
                >
                  <div className="flex items-center justify-between gap-4 mb-2">
                    <h3 className="text-sm font-semibold text-foreground">
                      {benchmark.name}
                    </h3>
                    <span className="text-xs font-mono text-muted-foreground">
                      {benchmark.status.toUpperCase()}
                    </span>
                  </div>
                  {benchmark.error && (
                    <p className="text-xs text-red-300 font-mono">
                      {benchmark.error}
                    </p>
                  )}
                  <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                    {JSON.stringify(benchmark.data, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
