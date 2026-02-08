/**
 * Stats & Insights tab for ProjectDetail.
 *
 * Displays overview metrics, health report, pairing highlights,
 * sentiment timeline, tool usage, and insights.
 */

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { getProjectStats, getProjectAnalytics, getProjectHealthReport } from '@/lib/api';
import {
  Users,
  MessageSquare,
  FileText,
  Clock,
  TrendingUp,
  Activity,
  ArrowLeftRight,
  Brain,
  AlertTriangle,
  HeartPulse,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from 'lucide-react';
import { SentimentTimelineChart } from '@/components/SentimentTimelineChart';
import { ToolUsageChart } from '@/components/ToolUsageChart';
import type { PairingEffectivenessPair, RoleDynamicsSummary } from '@/types/api';

// ===== Helper Components =====

function getScoreQuality(score: number): { label: string; colorClass: string } {
  if (score >= 0.8) return { label: 'EXCELLENT', colorClass: 'text-emerald-400' };
  if (score >= 0.6) return { label: 'GOOD', colorClass: 'text-cyan-400' };
  if (score >= 0.4) return { label: 'FAIR', colorClass: 'text-amber-400' };
  return { label: 'NEEDS WORK', colorClass: 'text-red-400' };
}

function PairingHighlights({
  topPairings,
  bottomPairings,
}: {
  topPairings: PairingEffectivenessPair[];
  bottomPairings: PairingEffectivenessPair[];
}) {
  const renderMetricDots = (value: number | null, max: number, inverted = false) => {
    if (value === null) return <span className="text-muted-foreground text-xs">n/a</span>;
    const normalized = inverted ? Math.max(0, 1 - value / max) : Math.min(1, value / max);
    const filled = Math.round(normalized * 5);
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className={`w-1.5 h-1.5 rounded-full ${
              i <= filled
                ? normalized >= 0.6
                  ? 'bg-emerald-400'
                  : normalized >= 0.3
                    ? 'bg-amber-400'
                    : 'bg-red-400'
                : 'bg-slate-700'
            }`}
          />
        ))}
      </div>
    );
  };

  const renderPairingCard = (pair: PairingEffectivenessPair) => {
    const quality = getScoreQuality(pair.score);
    return (
      <div
        key={`${pair.developer}-${pair.agent_type}`}
        className="border border-border/50 rounded-lg px-4 py-3 bg-slate-900/30"
      >
        <div className="flex items-center justify-between mb-1">
          <div>
            <p className="font-semibold text-foreground">
              {pair.developer || 'Unassigned'} · {pair.agent_type}
            </p>
            <p className="text-xs text-muted-foreground">{pair.sessions} sessions</p>
          </div>
          <div className="text-right">
            <div className={`text-xl font-mono font-bold ${quality.colorClass}`}>
              {pair.score.toFixed(2)}
            </div>
            <div className={`text-xs font-semibold ${quality.colorClass}`}>{quality.label}</div>
          </div>
        </div>

        <div className="text-xs text-muted-foreground mb-3 pt-2 border-t border-border/30">
          Score = 60% Success + 30% Throughput + 10% Speed
        </div>

        <div className="space-y-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">
              Success rate <span className="text-slate-600">(target: &gt;70%)</span>
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono">
                {pair.success_rate !== null ? `${Math.round(pair.success_rate * 100)}%` : 'n/a'}
              </span>
              {renderMetricDots(pair.success_rate, 1)}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">
              LOC/hour <span className="text-slate-600">(target: 200)</span>
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono">
                {pair.lines_per_hour !== null ? Math.round(pair.lines_per_hour) : 'n/a'}
              </span>
              {renderMetricDots(pair.lines_per_hour, 200)}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">
              Time to change <span className="text-slate-600">(target: &lt;10m)</span>
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono">
                {pair.first_change_minutes !== null
                  ? `${pair.first_change_minutes.toFixed(1)}m`
                  : 'n/a'}
              </span>
              {renderMetricDots(pair.first_change_minutes, 10, true)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="observatory-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowLeftRight className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-mono font-semibold uppercase tracking-wider">
            Top Performers
          </h3>
        </div>
        {topPairings.length === 0 ? (
          <p className="text-muted-foreground text-sm">No pairing data yet.</p>
        ) : (
          <div className="space-y-3">
            {topPairings.map((pair) => renderPairingCard(pair))}
          </div>
        )}
      </div>

      <div className="observatory-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <ArrowLeftRight className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-mono font-semibold uppercase tracking-wider">
            Needs Attention
          </h3>
        </div>
        {bottomPairings.length === 0 ? (
          <p className="text-muted-foreground text-sm">No pairing data yet.</p>
        ) : (
          <div className="space-y-3">
            {bottomPairings.map((pair) => renderPairingCard(pair))}
          </div>
        )}
      </div>
    </div>
  );
}

function RoleDynamicsDonut({ dynamics }: { dynamics: RoleDynamicsSummary }) {
  const total = dynamics.agent_led + dynamics.dev_led + dynamics.co_pilot;
  if (total === 0) return null;

  const agentPct = (dynamics.agent_led / total) * 100;
  const devPct = (dynamics.dev_led / total) * 100;
  const coPilotPct = (dynamics.co_pilot / total) * 100;

  const gradient = `conic-gradient(
    #22d3ee 0% ${agentPct}%,
    #a855f7 ${agentPct}% ${agentPct + devPct}%,
    #34d399 ${agentPct + devPct}% 100%
  )`;

  return (
    <div className="observatory-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-purple-400" />
        <h3 className="text-sm font-mono font-semibold uppercase tracking-wider">
          Role Dynamics
        </h3>
      </div>
      <div className="flex items-center gap-8">
        <div
          className="w-24 h-24 rounded-full relative"
          style={{ background: gradient }}
        >
          <div className="absolute inset-3 bg-slate-950 rounded-full flex items-center justify-center">
            <span className="text-lg font-mono font-bold text-foreground">{total}</span>
          </div>
        </div>

        <div className="space-y-2 flex-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-cyan-400" />
              <span className="text-sm">Agent-led</span>
            </div>
            <span className="font-mono text-sm">
              {dynamics.agent_led} <span className="text-muted-foreground">({agentPct.toFixed(0)}%)</span>
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-purple-400" />
              <span className="text-sm">Dev-led</span>
            </div>
            <span className="font-mono text-sm">
              {dynamics.dev_led} <span className="text-muted-foreground">({devPct.toFixed(0)}%)</span>
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-400" />
              <span className="text-sm">Co-pilot</span>
            </div>
            <span className="font-mono text-sm">
              {dynamics.co_pilot} <span className="text-muted-foreground">({coPilotPct.toFixed(0)}%)</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function HealthReport({
  projectId,
  dateRange,
}: {
  projectId: string;
  dateRange: '7d' | '30d' | '90d' | 'all';
}) {
  const { data: report, isLoading, error } = useQuery({
    queryKey: ['projects', projectId, 'health-report', dateRange],
    queryFn: () => getProjectHealthReport(projectId, dateRange),
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="observatory-card p-6 animate-pulse">
        <div className="h-8 bg-muted rounded w-1/3 mb-4"></div>
        <div className="h-4 bg-muted rounded w-2/3 mb-6"></div>
        <div className="space-y-4">
          <div className="h-20 bg-muted rounded"></div>
          <div className="h-32 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="observatory-card p-6 border-destructive/30">
        <p className="text-destructive">Failed to load health report</p>
      </div>
    );
  }

  const scoreColorClass =
    report.score >= 0.8
      ? 'text-emerald-400'
      : report.score >= 0.6
        ? 'text-cyan-400'
        : report.score >= 0.4
          ? 'text-amber-400'
          : 'text-red-400';

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="observatory-card p-6">
        <div className="flex items-center gap-3 mb-4">
          <HeartPulse className={`w-6 h-6 ${scoreColorClass}`} />
          <h3 className="text-lg font-semibold">AI Collaboration Health</h3>
        </div>
        <div className="flex items-baseline gap-4 mb-3">
          <span className={`text-5xl font-mono font-bold ${scoreColorClass}`}>
            {(report.score * 100).toFixed(0)}%
          </span>
          <span className={`text-xl font-semibold uppercase ${scoreColorClass}`}>
            {report.label}
          </span>
        </div>
        <p className="text-muted-foreground">{report.summary}</p>
        <p className="text-xs text-muted-foreground mt-2">
          Based on {report.sessions_analyzed} sessions
        </p>
      </div>

      {/* Diagnosis Section */}
      <div className="observatory-card p-6">
        <h4 className="text-sm font-mono font-semibold uppercase tracking-wider mb-4">
          What's Driving Your Score
        </h4>

        {report.diagnosis.strengths.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-emerald-400 font-semibold uppercase mb-2">Strengths</p>
            <ul className="space-y-1">
              {report.diagnosis.strengths.map((s, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.diagnosis.gaps.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-amber-400 font-semibold uppercase mb-2">Gaps</p>
            <ul className="space-y-1">
              {report.diagnosis.gaps.map((g, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  <span>{g}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.diagnosis.primary_issue_detail && (
          <p className="text-sm text-muted-foreground border-t border-border/50 pt-4 mt-4">
            {report.diagnosis.primary_issue_detail}
          </p>
        )}
      </div>

      {/* Evidence Section */}
      {(report.evidence.success_example || report.evidence.failure_example) && (
        <div className="observatory-card p-6">
          <h4 className="text-sm font-mono font-semibold uppercase tracking-wider mb-4">
            Evidence From Your Sessions
          </h4>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {report.evidence.success_example && (
              <Link
                to={`/conversations/${report.evidence.success_example.session_id}`}
                className="border border-emerald-400/30 rounded-lg p-4 bg-emerald-400/5 hover:bg-emerald-400/10 hover:border-emerald-400/50 transition-colors block group"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-semibold text-emerald-400 uppercase">
                      Success Example
                    </span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="font-medium mb-1">{report.evidence.success_example.title}</p>
                <p className="text-xs text-muted-foreground mb-2">
                  {report.evidence.success_example.date} ·{' '}
                  {report.evidence.success_example.duration_minutes > 0
                    ? `${report.evidence.success_example.duration_minutes}m`
                    : 'In progress'}
                </p>
                {report.evidence.success_example.outcome && (
                  <p className="text-sm text-foreground/80 line-clamp-3">
                    {report.evidence.success_example.outcome}
                  </p>
                )}
                {report.evidence.success_example.explanation && (
                  <p className="text-sm text-emerald-400/80 mt-2">
                    {report.evidence.success_example.explanation}
                  </p>
                )}
              </Link>
            )}

            {report.evidence.failure_example && (
              <Link
                to={`/conversations/${report.evidence.failure_example.session_id}`}
                className="border border-red-400/30 rounded-lg p-4 bg-red-400/5 hover:bg-red-400/10 hover:border-red-400/50 transition-colors block group"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-semibold text-red-400 uppercase">
                      Failure Example
                    </span>
                  </div>
                  <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="font-medium mb-1">{report.evidence.failure_example.title}</p>
                <p className="text-xs text-muted-foreground mb-2">
                  {report.evidence.failure_example.date} ·{' '}
                  {report.evidence.failure_example.duration_minutes > 0
                    ? `${report.evidence.failure_example.duration_minutes}m`
                    : 'In progress'}
                </p>
                {report.evidence.failure_example.outcome && (
                  <p className="text-sm text-foreground/80 line-clamp-3">
                    {report.evidence.failure_example.outcome}
                  </p>
                )}
                {report.evidence.failure_example.explanation && (
                  <p className="text-sm text-red-400/80 mt-2">
                    {report.evidence.failure_example.explanation}
                  </p>
                )}
              </Link>
            )}
          </div>

          {report.evidence.patterns.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border/50">
              <p className="text-xs text-muted-foreground uppercase mb-2">Patterns Detected</p>
              {report.evidence.patterns.map((p, i) => (
                <p key={i} className="text-sm text-cyan-400">
                  {p.description}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Recommendations Section */}
      {report.recommendations.length > 0 && (
        <div className="observatory-card p-6">
          <h4 className="text-sm font-mono font-semibold uppercase tracking-wider mb-4">
            Recommendations
          </h4>
          <div className="space-y-4">
            {report.recommendations.map((rec, i) => (
              <div key={i} className="border-l-2 border-cyan-400 pl-4">
                <p className="font-medium">{rec.advice}</p>
                <p className="text-sm text-muted-foreground mt-1">{rec.evidence}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ===== Main StatsTab Component =====

type StatsSubTab = 'health' | 'details';

export default function StatsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('all');
  const [subTab, setSubTab] = useState<StatsSubTab>('health');

  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'stats', dateRange],
    queryFn: () => getProjectStats(projectId, dateRange),
    refetchInterval: 15000,
    staleTime: 0,
  });

  const { data: analytics } = useQuery({
    queryKey: ['projects', projectId, 'analytics', dateRange],
    queryFn: () => getProjectAnalytics(projectId, dateRange),
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="bg-card border border-border rounded-lg p-6 animate-pulse"
          >
            <div className="h-4 bg-muted rounded w-2/3 mb-4"></div>
            <div className="h-8 bg-muted rounded w-1/2 mb-2"></div>
            <div className="h-3 bg-muted rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load stats</p>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const avgDurationMinutes = stats.avg_session_duration_seconds
    ? Math.round(stats.avg_session_duration_seconds / 60)
    : null;

  const dateRangeLabels = {
    '7d': 'Last 7 days',
    '30d': 'Last 30 days',
    '90d': 'Last 90 days',
    'all': 'All time'
  };

  return (
    <div className="space-y-8">
      {/* Observatory Time Range Control */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">Time Range:</span>
          <div className="flex gap-2">
            {(['7d', '30d', '90d', 'all'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setDateRange(range)}
                className={`
                  px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider rounded-md transition-all duration-200
                  ${
                    dateRange === range
                      ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                      : 'border border-border/50 text-muted-foreground hover:text-foreground hover:bg-accent/30 hover:border-border'
                  }
                `}
              >
                {dateRangeLabels[range]}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isFetching ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-400/10 border border-cyan-400/30">
              <div className="w-1.5 h-1.5 bg-cyan-400 rounded-full pulse-dot" />
              <span className="text-xs font-mono text-cyan-400">SYNCING</span>
            </div>
          ) : dataUpdatedAt ? (
            <span className="text-xs font-mono text-muted-foreground">
              SYNC {formatDistanceToNow(dataUpdatedAt, { addSuffix: true }).toUpperCase()}
            </span>
          ) : null}
        </div>
      </div>

      {/* Observatory Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="observatory-card p-6 group hover:border-cyan-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Sessions
            </span>
            <Activity className="w-5 h-5 text-cyan-400/60 group-hover:text-cyan-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-cyan-400 glow-cyan mb-3">
            {stats.session_count.toLocaleString()}
          </p>
          <p className="text-xs font-mono text-muted-foreground">
            <span className="text-foreground/80">{stats.developer_count}</span> developer{stats.developer_count !== 1 ? 's' : ''}
          </p>
        </div>

        <div className="observatory-card p-6 group hover:border-emerald-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Messages
            </span>
            <MessageSquare className="w-5 h-5 text-emerald-400/60 group-hover:text-emerald-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-emerald-400 glow-emerald mb-3">
            {stats.total_messages.toLocaleString()}
          </p>
          <p className="text-xs font-mono text-muted-foreground">
            avg{' '}
            <span className="text-foreground/80">
              {stats.session_count > 0
                ? Math.round(stats.total_messages / stats.session_count).toLocaleString()
                : 'N/A'}
            </span>
            {' '}per session
          </p>
        </div>

        <div className="observatory-card p-6 group hover:border-amber-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Files Changed
            </span>
            <FileText className="w-5 h-5 text-amber-400/60 group-hover:text-amber-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-amber-400 glow-amber mb-3">
            {stats.total_files_changed.toLocaleString()}
          </p>
          <p className="text-xs font-mono text-muted-foreground">
            across all sessions
          </p>
        </div>

        <div className="observatory-card p-6 group hover:border-emerald-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Success Rate
            </span>
            <TrendingUp className="w-5 h-5 text-emerald-400/60 group-hover:text-emerald-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-emerald-400 glow-emerald mb-3">
            {stats.success_rate !== null
              ? `${Math.round(stats.success_rate * 100)}%`
              : 'N/A'}
          </p>
          {stats.success_rate !== null && (
            <div className="h-1.5 bg-slate-900/50 rounded-full overflow-hidden border border-border/30">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all"
                style={{ width: `${stats.success_rate * 100}%` }}
              />
            </div>
          )}
        </div>

        <div className="observatory-card p-6 group hover:border-purple-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Avg Duration
            </span>
            <Clock className="w-5 h-5 text-purple-400/60 group-hover:text-purple-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-purple-400 glow-purple mb-3">
            {avgDurationMinutes !== null ? `${avgDurationMinutes}m` : 'N/A'}
          </p>
          <p className="text-xs font-mono text-muted-foreground">
            per session
          </p>
        </div>

        <div className="observatory-card p-6 group hover:border-cyan-400/30 transition-all">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
              Developers
            </span>
            <Users className="w-5 h-5 text-cyan-400/60 group-hover:text-cyan-400 transition-colors" />
          </div>
          <p className="text-4xl font-mono font-bold text-cyan-400 glow-cyan mb-3">
            {stats.developer_count.toLocaleString()}
          </p>
          <p className="text-xs font-mono text-muted-foreground">
            active contributors
          </p>
        </div>
      </div>

      {/* Sub-tab Toggle */}
      <div className="flex items-center gap-4 border-b border-border/50 pb-4">
        <button
          onClick={() => setSubTab('health')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-md transition-all ${
            subTab === 'health'
              ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent/30'
          }`}
        >
          <HeartPulse className="w-4 h-4" />
          Health Report
        </button>
        <button
          onClick={() => setSubTab('details')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-md transition-all ${
            subTab === 'details'
              ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent/30'
          }`}
        >
          <ArrowLeftRight className="w-4 h-4" />
          Pairing Details
        </button>
      </div>

      {subTab === 'health' && <HealthReport projectId={projectId} dateRange={dateRange} />}

      {subTab === 'details' && (
        <>
          {analytics && (analytics.pairing_top.length > 0 || analytics.pairing_bottom.length > 0) && (
            <PairingHighlights
              topPairings={analytics.pairing_top.slice(0, 3)}
              bottomPairings={analytics.pairing_bottom.slice(0, 3)}
            />
          )}

          {analytics && (analytics.role_dynamics.agent_led > 0 || analytics.role_dynamics.dev_led > 0 || analytics.role_dynamics.co_pilot > 0) && (
            <RoleDynamicsDonut dynamics={analytics.role_dynamics} />
          )}
        </>
      )}

      {stats.sentiment_timeline && stats.sentiment_timeline.length > 0 && (
        <SentimentTimelineChart data={stats.sentiment_timeline} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {stats.top_features.length > 0 && (
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Top Features</h3>
            <div className="space-y-2">
              {stats.top_features.slice(0, 5).map((feature, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3 text-sm"
                >
                  <div className="w-1 h-6 bg-primary rounded-full" />
                  <span>{feature}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {stats.top_problems.length > 0 && (
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Top Problems</h3>
            <div className="space-y-2">
              {stats.top_problems.slice(0, 5).map((problem, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3 text-sm"
                >
                  <div className="w-1 h-6 bg-destructive rounded-full" />
                  <span>{problem}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {Object.keys(stats.tool_usage).length > 0 && (
        <ToolUsageChart toolUsage={stats.tool_usage} />
      )}
    </div>
  );
}
