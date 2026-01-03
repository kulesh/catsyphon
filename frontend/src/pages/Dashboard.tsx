/**
 * Dashboard page - Observatory Mission Control.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { Activity, MessageSquare, FolderOpen, Users, TrendingUp, AlertTriangle, Terminal, Gauge, ClipboardCopy, Sparkles } from 'lucide-react';
import { ApiError, generateWeeklyDigest, getBenchmarkStatus, getLatestBenchmarkResults, getOverviewStats, getWeeklyDigest } from '@/lib/api';
import { useMemo, useState } from 'react';

export default function Dashboard() {
  const [benchmarksAvailable, setBenchmarksAvailable] = useState(true);
  const [digestPollEnabled, setDigestPollEnabled] = useState(true);
  const [digestMissing, setDigestMissing] = useState(false);

  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: () => getOverviewStats(),
    refetchInterval: 15000, // Auto-refresh every 15 seconds for live dashboard
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  const benchmarkStatusQuery = useQuery({
    queryKey: ['benchmarks', 'status'],
    queryFn: () => getBenchmarkStatus(),
    retry: false,
    enabled: benchmarksAvailable,
    refetchInterval: benchmarksAvailable ? 15000 : false,
    onError: (err) => {
      if (err instanceof ApiError && err.status === 403) {
        setBenchmarksAvailable(false);
      }
    },
  });

  const benchmarkResultsQuery = useQuery({
    queryKey: ['benchmarks', 'results', 'latest'],
    queryFn: () => getLatestBenchmarkResults(),
    enabled:
      benchmarksAvailable &&
      benchmarkStatusQuery.data?.status === 'completed',
    retry: false,
    refetchInterval: benchmarksAvailable ? 15000 : false,
  });

  const queryClient = useQueryClient();
  const digestWindow = useMemo(() => {
    const end = new Date();
    const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
    return {
      periodStart: start.toISOString(),
      periodEnd: end.toISOString(),
    };
  }, []);

  const digestQuery = useQuery({
    queryKey: ['digests', 'weekly', digestWindow.periodStart, digestWindow.periodEnd],
    queryFn: () => getWeeklyDigest(digestWindow.periodStart, digestWindow.periodEnd),
    retry: false,
    enabled: digestPollEnabled,
    refetchInterval: digestPollEnabled ? 60000 : false,
    onSuccess: () => {
      setDigestMissing(false);
      setDigestPollEnabled(true);
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 404) {
        setDigestMissing(true);
        setDigestPollEnabled(false);
      }
    },
  });

  const digestMutation = useMutation({
    mutationFn: ({ force }: { force: boolean }) =>
      generateWeeklyDigest(
        digestWindow.periodStart,
        digestWindow.periodEnd,
        force
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(
        ['digests', 'weekly', digestWindow.periodStart, digestWindow.periodEnd],
        data
      );
      setDigestMissing(false);
      setDigestPollEnabled(true);
    },
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center grid-pattern">
        <div className="text-center">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-2 border-transparent border-t-cyan-400 border-r-cyan-400 mx-auto mb-6 glow-cyan"></div>
            <div className="absolute inset-0 animate-ping rounded-full h-16 w-16 border border-cyan-400/20 mx-auto"></div>
          </div>
          <p className="text-sm font-mono text-muted-foreground tracking-wider">LOADING TELEMETRY DATA...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="observatory-card border-destructive/50 p-6">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-destructive" />
            <h3 className="font-heading text-lg text-destructive">System Error</h3>
          </div>
          <p className="font-mono text-sm text-destructive/80">
            {error.message}
          </p>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const benchmarkEnabled = benchmarksAvailable;

  const benchmarkStatus = benchmarkStatusQuery.data?.status;
  const benchmarkRunId = benchmarkStatusQuery.data?.run_id;
  const benchmarkResults = benchmarkResultsQuery.data;
  const digest = digestQuery.data;
  const digestMarkdown = digest
    ? [
        `# Weekly Digest`,
        ``,
        digest.summary,
        ``,
        digest.wins.length ? `## Wins` : ``,
        ...digest.wins.map((item) => `- ${item}`),
        digest.blockers.length ? `` : ``,
        digest.blockers.length ? `## Blockers` : ``,
        ...digest.blockers.map((item) => `- ${item}`),
        digest.highlights.length ? `` : ``,
        digest.highlights.length ? `## Highlights` : ``,
        ...digest.highlights.map((item) => `- ${item}`),
      ]
        .filter((line) => line !== '')
        .join('\n')
    : '';

  const handleCopyDigest = async () => {
    if (!digestMarkdown) return;
    try {
      await navigator.clipboard.writeText(digestMarkdown);
    } catch (err) {
      console.error('Failed to copy digest', err);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Mission Control Hero */}
      <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border-b border-border overflow-hidden">
        {/* Grid pattern background */}
        <div className="absolute inset-0 grid-pattern opacity-20" />

        {/* Scan line effect */}
        <div className="absolute inset-0 scan-line" />

        {/* Content */}
        <div className="container mx-auto px-6 py-12 relative z-10">
          <div className="flex items-start justify-between mb-8">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Activity className="w-8 h-8 text-cyan-400" />
                <h1 className="text-4xl font-display tracking-wide text-foreground">
                  MISSION CONTROL
                </h1>
              </div>
              <p className="text-muted-foreground font-mono text-sm tracking-wide">
                Observatory monitoring • Real-time telemetry • Agent activity analysis
              </p>
            </div>

            {/* Live status indicator */}
            <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-accent/30 border border-border backdrop-blur-sm">
              {isFetching && (
                <div className="w-2 h-2 bg-cyan-400 rounded-full pulse-dot" />
              )}
              {dataUpdatedAt && (
                <span className="text-xs font-mono text-muted-foreground">
                  SYNC {formatDistanceToNow(dataUpdatedAt, { addSuffix: true }).toUpperCase()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto p-6">

      {/* Observatory Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {/* Conversations Metric */}
        <div className="observatory-card p-6 group hover:border-cyan-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider">
              CONVERSATIONS
            </span>
            <MessageSquare className="w-5 h-5 text-cyan-400/60 group-hover:text-cyan-400 transition-colors" />
          </div>
          <div className="mb-3">
            <p className="text-4xl font-mono font-bold text-cyan-400 glow-cyan">
              {stats.total_conversations.toLocaleString()}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-mono text-muted-foreground">
              <span className="text-foreground/80">{stats.total_main_conversations}</span> main sessions
            </p>
            <p className="text-xs font-mono text-muted-foreground">
              <span className="text-foreground/80">{stats.total_agent_conversations}</span> agent spawns
            </p>
            <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/50">
              <div className="w-1 h-1 rounded-full bg-emerald-400 pulse-dot" />
              <p className="text-xs font-mono text-emerald-400">
                +{stats.recent_conversations} last 7d
              </p>
            </div>
          </div>
        </div>

        {/* Messages Metric */}
        <div className="observatory-card p-6 group hover:border-emerald-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider">
              MESSAGES
            </span>
            <Activity className="w-5 h-5 text-emerald-400/60 group-hover:text-emerald-400 transition-colors" />
          </div>
          <div className="mb-3">
            <p className="text-4xl font-mono font-bold text-emerald-400 glow-emerald">
              {stats.total_messages.toLocaleString()}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-mono text-muted-foreground">
              avg{' '}
              <span className="text-foreground/80">
                {stats.total_conversations > 0
                  ? Math.round(stats.total_messages / stats.total_conversations).toLocaleString()
                  : 'N/A'}
              </span>
              {' '}per session
            </p>
          </div>
        </div>

        {/* Projects Metric */}
        <div className="observatory-card p-6 group hover:border-amber-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider">
              PROJECTS
            </span>
            <FolderOpen className="w-5 h-5 text-amber-400/60 group-hover:text-amber-400 transition-colors" />
          </div>
          <div className="mb-3">
            <p className="text-4xl font-mono font-bold text-amber-400 glow-amber">
              {stats.total_projects.toLocaleString()}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-mono text-muted-foreground">
              tracked repositories
            </p>
          </div>
        </div>

        {/* Developers Metric */}
        <div className="observatory-card p-6 group hover:border-purple-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider">
              DEVELOPERS
            </span>
            <Users className="w-5 h-5 text-purple-400/60 group-hover:text-purple-400 transition-colors" />
          </div>
          <div className="mb-3">
            <p className="text-4xl font-mono font-bold text-purple-400 glow-purple">
              {stats.total_developers.toLocaleString()}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-mono text-muted-foreground">
              active contributors
            </p>
          </div>
        </div>
      </div>

      {/* Success Rate Observatory Panel */}
      {stats.success_rate !== null && (
        <div className="observatory-card p-6 mb-8">
          <div className="flex items-center gap-3 mb-6">
            <TrendingUp className="w-5 h-5 text-emerald-400" />
            <h2 className="text-xl font-heading font-semibold text-foreground">
              Mission Success Rate
            </h2>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex-1">
              <div className="relative h-6 bg-slate-900/50 rounded-full overflow-hidden border border-border/50">
                <div
                  className="absolute top-0 left-0 h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all glow-emerald"
                  style={{ width: `${stats.success_rate}%` }}
                />
              </div>
            </div>
            <div className="text-4xl font-mono font-bold text-emerald-400 glow-emerald min-w-[120px] text-right">
              {stats.success_rate.toFixed(1)}%
            </div>
          </div>
          <p className="text-xs font-mono text-muted-foreground mt-3">
            Success metric calculated from tagged conversation outcomes
          </p>
        </div>
      )}

      {/* Weekly Digest Panel */}
      <div className="observatory-card p-6 mb-8">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <div className="flex items-center gap-3">
            <Terminal className="w-5 h-5 text-emerald-400" />
            <h2 className="text-xl font-heading font-semibold text-foreground">
              Weekly Digest
            </h2>
          </div>
          <div className="flex items-center gap-2">
            {digest && (
              <button
                onClick={handleCopyDigest}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors text-sm"
              >
                <ClipboardCopy className="w-4 h-4" />
                Copy Markdown
              </button>
            )}
            <button
              onClick={() => digestMutation.mutate({ force: Boolean(digest) })}
              disabled={digestMutation.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
            >
              {digestMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {digest ? 'Regenerating...' : 'Generating...'}
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  {digest ? 'Regenerate' : 'Generate Digest'}
                </>
              )}
            </button>
          </div>
        </div>

        {digestQuery.isLoading && (
          <p className="text-sm font-mono text-muted-foreground">
            Loading digest...
          </p>
        )}

        {digestMissing && (
          <p className="text-sm font-mono text-muted-foreground">
            No digest yet for this week. Generate one to get a summary.
          </p>
        )}

        {digestQuery.isError && !digestMissing && (
          <p className="text-sm font-mono text-muted-foreground">
            {digestQuery.error?.message || 'Unable to load digest.'}
          </p>
        )}

        {digest && (
          <div className="space-y-4">
            <p className="text-sm text-foreground">{digest.summary}</p>
            {digest.wins.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2">Wins</h4>
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">
                  {digest.wins.map((item, idx) => (
                    <li key={`${item}-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {digest.blockers.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2">Blockers</h4>
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">
                  {digest.blockers.map((item, idx) => (
                    <li key={`${item}-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {digest.highlights.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2">Highlights</h4>
                <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">
                  {digest.highlights.map((item, idx) => (
                    <li key={`${item}-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="observatory-card p-6 mb-8">
        <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
          <div className="flex items-center gap-3">
            <Gauge className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-heading text-foreground">
              Performance Benchmarks
            </h2>
          </div>
          {benchmarkStatus && benchmarkEnabled && (
            <span className="text-xs font-mono text-muted-foreground">
              STATUS {benchmarkStatus.toUpperCase()}
            </span>
          )}
        </div>

        {!benchmarkEnabled && (
          <p className="text-sm font-mono text-muted-foreground">
            Benchmarks are disabled. Enable them in the backend settings to see results here.
          </p>
        )}

        {benchmarkEnabled && benchmarkStatusQuery.isLoading && (
          <p className="text-sm font-mono text-muted-foreground">
            Loading benchmark status...
          </p>
        )}

        {benchmarkEnabled && benchmarkStatusQuery.isError && (
          <p className="text-sm font-mono text-muted-foreground">
            {benchmarkStatusQuery.error?.message || 'Benchmarks unavailable'}
          </p>
        )}

        {benchmarkEnabled && benchmarkRunId && (
          <p className="text-xs font-mono text-muted-foreground mb-3">
            Latest run: {benchmarkRunId}
          </p>
        )}

        {benchmarkEnabled && benchmarkResults && (
          <div className="space-y-3">
            {benchmarkResults.benchmarks.map((benchmark) => (
              <div
                key={benchmark.name}
                className="rounded-lg border border-border/60 bg-card/60 p-3"
              >
                <div className="flex items-center justify-between gap-3 mb-2">
                  <span className="text-sm font-semibold text-foreground">
                    {benchmark.name}
                  </span>
                  <span className="text-xs font-mono text-muted-foreground">
                    {benchmark.status.toUpperCase()}
                  </span>
                </div>
                {benchmark.data?.overhead_ratio && (
                  <p className="text-xs font-mono text-muted-foreground">
                    Registry overhead:{' '}
                    {(benchmark.data.overhead_ratio * 100).toFixed(2)}%
                  </p>
                )}
                {benchmark.data?.reason && (
                  <p className="text-xs font-mono text-muted-foreground">
                    {benchmark.data.reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Observatory Data Analysis Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Status Breakdown */}
        <div className="observatory-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <Terminal className="w-5 h-5 text-cyan-400" />
            <h2 className="text-xl font-heading font-semibold text-foreground">
              Status Distribution
            </h2>
          </div>
          <div className="space-y-4">
            {Object.entries(stats.conversations_by_status)
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => {
                const percentage = (count / stats.total_conversations) * 100;
                const barColor =
                  status === 'completed' ? 'from-emerald-500 to-emerald-400' :
                  status === 'failed' ? 'from-rose-500 to-rose-400' :
                  status === 'in_progress' ? 'from-cyan-500 to-cyan-400' :
                  'from-amber-500 to-amber-400';

                return (
                  <div key={status}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-mono text-foreground/90 uppercase tracking-wide">
                        {status.replace('_', ' ')}
                      </span>
                      <span className="text-sm font-mono text-muted-foreground">
                        {count.toLocaleString()} <span className="text-xs">({percentage.toFixed(1)}%)</span>
                      </span>
                    </div>
                    <div className="relative h-2 bg-slate-900/50 rounded-full overflow-hidden border border-border/30">
                      <div
                        className={`absolute top-0 left-0 h-full bg-gradient-to-r ${barColor} transition-all`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Agent Type Breakdown */}
        <div className="observatory-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <Activity className="w-5 h-5 text-purple-400" />
            <h2 className="text-xl font-heading font-semibold text-foreground">
              Agent Distribution
            </h2>
          </div>
          <div className="space-y-4">
            {Object.entries(stats.conversations_by_agent)
              .sort(([, a], [, b]) => b - a)
              .map(([agent, count]) => {
                const percentage = (count / stats.total_conversations) * 100;
                return (
                  <div key={agent}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-mono text-foreground/90 uppercase tracking-wide">
                        {agent}
                      </span>
                      <span className="text-sm font-mono text-muted-foreground">
                        {count.toLocaleString()} <span className="text-xs">({percentage.toFixed(1)}%)</span>
                      </span>
                    </div>
                    <div className="relative h-2 bg-slate-900/50 rounded-full overflow-hidden border border-border/30">
                      <div
                        className="absolute top-0 left-0 h-full bg-gradient-to-r from-purple-500 to-purple-400 transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>

      {/* Command Center - Quick Actions */}
      <div className="observatory-card p-6">
        <div className="flex items-center gap-3 mb-6">
          <Terminal className="w-5 h-5 text-cyan-400" />
          <h2 className="text-xl font-heading font-semibold text-foreground">
            Command Center
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            to="/conversations"
            className="group relative p-5 border border-border/50 rounded-lg hover:border-cyan-400/50 transition-all overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-cyan-400/10 border border-cyan-400/30 flex items-center justify-center group-hover:glow-cyan transition-all">
                <MessageSquare className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <p className="font-mono text-sm font-semibold text-foreground mb-1">
                  BROWSE_SESSIONS
                </p>
                <p className="text-xs font-mono text-muted-foreground">
                  View and filter all conversations
                </p>
              </div>
            </div>
          </Link>

          <Link
            to="/failed-sessions"
            className="group relative p-5 border border-border/50 rounded-lg hover:border-rose-400/50 transition-all overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-rose-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-rose-400/10 border border-rose-400/30 flex items-center justify-center transition-all">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <p className="font-mono text-sm font-semibold text-foreground mb-1">
                  FAILED_SESSIONS
                </p>
                <p className="text-xs font-mono text-muted-foreground">
                  Review failed conversation logs
                </p>
              </div>
            </div>
          </Link>
        </div>
      </div>
    </div>
    </div>
  );
}
