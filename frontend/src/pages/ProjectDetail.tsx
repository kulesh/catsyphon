/**
 * Project Detail page - Deep-dive analytics for a single project.
 *
 * Features three tabs:
 * - Stats: Overview metrics, insights, and tool usage
 * - Sessions: Paginated list of all conversations
 * - Files: Aggregated file modification statistics
 */

import { useState } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow, format } from 'date-fns';
import {
  getProjectStats,
  getProjectSessions,
  getProjectFiles,
  getProjects,
  getProjectAnalytics,
  getProjectInsights,
  getProjectHealthReport,
} from '@/lib/api';
import {
  BarChart3,
  Users,
  MessageSquare,
  FileText,
  Clock,
  TrendingUp,
  Activity,
  Folder,
  RefreshCw,
  Network,
  ArrowLeftRight,
  Brain,
  Lightbulb,
  AlertTriangle,
  BookOpen,
  Sparkles,
  HeartPulse,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from 'lucide-react';
import { SentimentTimelineChart } from '@/components/SentimentTimelineChart';
import { ToolUsageChart } from '@/components/ToolUsageChart';
import { SessionTable, renderHelpers, type ColumnConfig } from '@/components/SessionTable';
import { SessionPagination } from '@/components/SessionPagination';
import type { ProjectSessionFilters } from '@/lib/api';
import type {
  ProjectAnalytics,
  PatternFrequency,
  TrendPoint,
  PairingEffectivenessPair,
  RoleDynamicsSummary,
} from '@/types/api';

type Tab = 'stats' | 'analytics' | 'insights' | 'sessions' | 'files';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('stats');

  // Fetch project metadata
  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const project = projects?.find((p) => p.id === id);

  if (!id) {
    return (
      <div className="container mx-auto px-6 py-8">
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
          <p className="text-destructive font-medium">Project ID is required</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'stats' as Tab, label: 'Stats & Insights', icon: BarChart3 },
    { id: 'analytics' as Tab, label: 'Pairing Analytics', icon: Brain },
    { id: 'insights' as Tab, label: 'AI Insights', icon: Lightbulb },
    { id: 'sessions' as Tab, label: 'Sessions', icon: Activity },
    { id: 'files' as Tab, label: 'Files', icon: FileText },
  ];

  return (
    <div className="container mx-auto px-6 py-8">
      {/* Observatory Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center glow-amber">
              <Folder className="w-6 h-6 text-slate-950" />
            </div>
            <div>
              <h1 className="text-3xl font-display tracking-wide text-foreground">
                {project?.name?.toUpperCase() || 'LOADING...'}
              </h1>
              {project?.description && (
                <p className="text-sm font-mono text-muted-foreground mt-1">
                  {project.description}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => navigate('/projects')}
            className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 transition-all"
          >
            ← Projects
          </button>
        </div>
      </div>

      {/* Observatory Tab Navigation */}
      <div className="mb-8">
        <nav className="flex gap-2 bg-slate-900/30 p-1 rounded-lg border border-border/50" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex-1 inline-flex items-center justify-center gap-2 py-3 px-4 rounded-md font-mono text-xs font-semibold uppercase tracking-wider
                  transition-all duration-200
                  ${
                    isActive
                      ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                      : 'text-muted-foreground hover:text-foreground hover:bg-accent/30'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="animate-in fade-in duration-300">
        {activeTab === 'stats' && <StatsTab projectId={id} />}
        {activeTab === 'analytics' && <AnalyticsTab projectId={id} />}
        {activeTab === 'insights' && <InsightsTab projectId={id} />}
        {activeTab === 'sessions' && <SessionsTab projectId={id} />}
        {activeTab === 'files' && <FilesTab projectId={id} />}
      </div>
    </div>
  );
}

// ===== Pairing Highlights Component =====

// Helper to get score quality label and color
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
  // Helper to render metric indicator dots (5 dots scale)
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
        {/* Header: Developer · Agent + Score with Quality Label */}
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

        {/* Formula explanation */}
        <div className="text-xs text-muted-foreground mb-3 pt-2 border-t border-border/30">
          Score = 60% Success + 30% Throughput + 10% Speed
        </div>

        {/* Metrics with benchmarks */}
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
      {/* Top Performers */}
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

      {/* Needs Attention */}
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

// ===== Role Dynamics Donut Component =====

function RoleDynamicsDonut({ dynamics }: { dynamics: RoleDynamicsSummary }) {
  const total = dynamics.agent_led + dynamics.dev_led + dynamics.co_pilot;
  if (total === 0) return null;

  const agentPct = (dynamics.agent_led / total) * 100;
  const devPct = (dynamics.dev_led / total) * 100;
  const coPilotPct = (dynamics.co_pilot / total) * 100;

  // CSS conic-gradient for donut chart
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
        {/* Donut Chart */}
        <div
          className="w-24 h-24 rounded-full relative"
          style={{ background: gradient }}
        >
          <div className="absolute inset-3 bg-slate-950 rounded-full flex items-center justify-center">
            <span className="text-lg font-mono font-bold text-foreground">{total}</span>
          </div>
        </div>

        {/* Legend */}
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

// ===== Health Report Component =====

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
    staleTime: 60000, // Cache for 1 minute
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

// ===== Stats Tab =====

type StatsSubTab = 'health' | 'details';

function StatsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('all');
  const [subTab, setSubTab] = useState<StatsSubTab>('health');

  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'stats', dateRange],
    queryFn: () => getProjectStats(projectId, dateRange),
    refetchInterval: 15000, // Auto-refresh every 15 seconds
    staleTime: 0, // Always fetch fresh data
  });

  // Fetch analytics data for pairing metrics
  const { data: analytics } = useQuery({
    queryKey: ['projects', projectId, 'analytics', dateRange],
    queryFn: () => getProjectAnalytics(projectId, dateRange),
    staleTime: 60000, // Analytics are less volatile
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
        {/* Date Range Buttons */}
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

        {/* Auto-refresh indicator */}
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
        {/* Total Sessions */}
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

        {/* Total Messages */}
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

        {/* Files Changed */}
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

        {/* Success Rate */}
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

        {/* Avg Session Duration */}
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

        {/* Developers */}
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

      {/* Sub-tab Toggle: Health Report vs Pairing Details */}
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

      {/* Health Report Tab Content */}
      {subTab === 'health' && <HealthReport projectId={projectId} dateRange={dateRange} />}

      {/* Pairing Details Tab Content */}
      {subTab === 'details' && (
        <>
          {/* Pairing Highlights */}
          {analytics && (analytics.pairing_top.length > 0 || analytics.pairing_bottom.length > 0) && (
            <PairingHighlights
              topPairings={analytics.pairing_top.slice(0, 3)}
              bottomPairings={analytics.pairing_bottom.slice(0, 3)}
            />
          )}

          {/* Role Dynamics */}
          {analytics && (analytics.role_dynamics.agent_led > 0 || analytics.role_dynamics.dev_led > 0 || analytics.role_dynamics.co_pilot > 0) && (
            <RoleDynamicsDonut dynamics={analytics.role_dynamics} />
          )}
        </>
      )}

      {/* Sentiment Timeline */}
      {stats.sentiment_timeline && stats.sentiment_timeline.length > 0 && (
        <SentimentTimelineChart data={stats.sentiment_timeline} />
      )}

      {/* Insights Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Features */}
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

        {/* Top Problems */}
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

      {/* Tool Usage */}
      {Object.keys(stats.tool_usage).length > 0 && (
        <ToolUsageChart toolUsage={stats.tool_usage} />
      )}
    </div>
  );
}

// ===== Analytics Tab =====

function AnalyticsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const {
    data: analytics,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['projects', projectId, 'analytics', dateRange],
    queryFn: () => getProjectAnalytics(projectId, dateRange),
    refetchInterval: 20000,
    staleTime: 0,
  });

  const rangeButtons: Array<{ label: string; value: '7d' | '30d' | '90d' | 'all' }> =
    [
      { label: '7D', value: '7d' },
      { label: '30D', value: '30d' },
      { label: '90D', value: '90d' },
      { label: 'All', value: 'all' },
    ];

  const loadingSkeleton = (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="bg-card border border-border rounded-lg p-6 animate-pulse h-44"
        >
          <div className="h-4 bg-muted rounded w-1/3 mb-4"></div>
          <div className="h-3 bg-muted rounded w-2/3 mb-2"></div>
          <div className="h-3 bg-muted rounded w-1/2"></div>
        </div>
      ))}
    </div>
  );

  if (isLoading) return loadingSkeleton;
  if (error || !analytics) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">
          Failed to load analytics
        </p>
      </div>
    );
  }

  const {
    pairing_top,
    pairing_bottom,
    role_dynamics,
    handoffs,
    impact,
    sentiment_by_agent,
    thinking_time,
  } = analytics;
  const { influence_flows, error_heatmap } = analytics;

  const renderPairList = (pairs: ProjectAnalytics['pairing_top'], tone: 'good' | 'bad') => (
    <div className="space-y-2">
      {pairs.length === 0 ? (
        <p className="text-muted-foreground text-sm">No data.</p>
      ) : (
        pairs.map((pair, idx) => (
          <div
            key={`${pair.developer}-${pair.agent_type}-${idx}`}
            className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
          >
            <div>
              <p className="font-semibold text-foreground">
                {pair.developer || 'Unassigned'} · {pair.agent_type}
              </p>
              <p className="text-xs text-muted-foreground">
                {pair.sessions} sessions · success{' '}
                {pair.success_rate !== null && pair.success_rate !== undefined
                  ? `${Math.round(pair.success_rate * 100)}%`
                  : '–'}
              </p>
            </div>
            <div className="text-right">
              <div
                className={`text-lg font-bold ${
                  tone === 'good' ? 'text-emerald-400' : 'text-amber-300'
                }`}
              >
                {pair.score.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground">
                {pair.lines_per_hour
                  ? `${pair.lines_per_hour.toFixed(0)} LOC/hr`
                  : 'LOC/hr n/a'}
              </p>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Pairing Analytics</h2>
        <div className="flex items-center gap-2">
          {rangeButtons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => setDateRange(btn.value)}
              className={`px-3 py-1 rounded-md text-xs font-semibold border transition-colors ${
                dateRange === btn.value
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-400/10'
                  : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent/30'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <ArrowLeftRight className="w-4 h-4 text-cyan-300" />
            <h3 className="text-lg font-semibold">Top Pairings</h3>
          </div>
          {renderPairList(pairing_top, 'good')}
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <ArrowLeftRight className="w-4 h-4 text-amber-300" />
            <h3 className="text-lg font-semibold">Pairs Needing Attention</h3>
          </div>
          {renderPairList(pairing_bottom, 'bad')}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-300" />
              <h3 className="text-lg font-semibold">Role Dynamics</h3>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent-led</span>
              <span className="font-semibold">{role_dynamics.agent_led}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Dev-led</span>
              <span className="font-semibold">{role_dynamics.dev_led}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Co-pilot</span>
              <span className="font-semibold">{role_dynamics.co_pilot}</span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <Network className="w-4 h-4 text-emerald-300" />
            <h3 className="text-lg font-semibold">Handoffs</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Count</span>
              <span className="font-semibold">{handoffs.handoff_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg response</span>
              <span className="font-semibold">
                {handoffs.avg_response_minutes !== null &&
                handoffs.avg_response_minutes !== undefined
                  ? `${handoffs.avg_response_minutes.toFixed(1)}m`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Success rate</span>
              <span className="font-semibold">
                {handoffs.success_rate !== null && handoffs.success_rate !== undefined
                  ? `${Math.round(handoffs.success_rate * 100)}%`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Clarifications</span>
              <span className="font-semibold">
                {handoffs.clarifications_avg !== null &&
                handoffs.clarifications_avg !== undefined
                  ? handoffs.clarifications_avg.toFixed(1)
                  : '–'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-cyan-300" />
            <h3 className="text-lg font-semibold">Impact</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg LOC/hour</span>
              <span className="font-semibold">
                {impact.avg_lines_per_hour !== null && impact.avg_lines_per_hour !== undefined
                  ? impact.avg_lines_per_hour.toFixed(0)
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Median time to first change</span>
              <span className="font-semibold">
                {impact.median_first_change_minutes !== null &&
                impact.median_first_change_minutes !== undefined
                  ? `${impact.median_first_change_minutes.toFixed(1)}m`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total lines changed</span>
              <span className="font-semibold">{impact.total_lines_changed}</span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-blue-300" />
            <h3 className="text-lg font-semibold">Thinking Time</h3>
          </div>
          {thinking_time ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Median</span>
                <span className="font-semibold">
                  {thinking_time.median_latency_seconds !== null &&
                  thinking_time.median_latency_seconds !== undefined
                    ? `${thinking_time.median_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">P95</span>
                <span className="font-semibold">
                  {thinking_time.p95_latency_seconds !== null &&
                  thinking_time.p95_latency_seconds !== undefined
                    ? `${thinking_time.p95_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max</span>
                <span className="font-semibold">
                  {thinking_time.max_latency_seconds !== null &&
                  thinking_time.max_latency_seconds !== undefined
                    ? `${thinking_time.max_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">% with thinking</span>
                <span className="font-semibold">
                  {thinking_time.pct_with_thinking !== null &&
                  thinking_time.pct_with_thinking !== undefined
                    ? `${Math.round(thinking_time.pct_with_thinking * 100)}%`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">% with tool calls</span>
                <span className="font-semibold">
                  {thinking_time.pct_with_tool_calls !== null &&
                  thinking_time.pct_with_tool_calls !== undefined
                    ? `${Math.round(thinking_time.pct_with_tool_calls * 100)}%`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Pairs</span>
                <span>{thinking_time.pair_count}</span>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No thinking-time data.</p>
          )}
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquare className="w-4 h-4 text-blue-300" />
          <h3 className="text-lg font-semibold">Sentiment by Agent</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sentiment_by_agent.length === 0 ? (
            <p className="text-muted-foreground text-sm col-span-full">
              No sentiment data.
            </p>
          ) : (
            sentiment_by_agent.map((s) => (
              <div
                key={s.agent_type}
                className="border border-border/50 rounded-md p-3 bg-slate-900/30"
              >
                <p className="font-semibold">{s.agent_type}</p>
                <p className="text-xs text-muted-foreground mb-1">
                  {s.sessions} sessions
                </p>
                <p className="text-lg font-bold">
                  {s.avg_sentiment !== null && s.avg_sentiment !== undefined
                    ? s.avg_sentiment.toFixed(2)
                    : '–'}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Only show these sections when there's data */}
      {(influence_flows.length > 0 || error_heatmap.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {influence_flows.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <ArrowLeftRight className="w-4 h-4 text-cyan-300" />
                <h3 className="text-lg font-semibold">Influence Flows</h3>
              </div>
              <div className="space-y-2">
                {influence_flows.map((flow) => (
                  <div
                    key={`${flow.source}-${flow.target}`}
                    className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
                  >
                    <div>
                      <p className="font-semibold text-foreground">
                        {flow.source} → {flow.target}
                      </p>
                    </div>
                    <p className="text-sm font-bold text-cyan-300">{flow.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error_heatmap.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <Network className="w-4 h-4 text-amber-300" />
                <h3 className="text-lg font-semibold">Error Heatmap</h3>
              </div>
              <div className="space-y-2">
                {error_heatmap.map((bucket) => (
                  <div
                    key={`${bucket.agent_type}-${bucket.category}`}
                    className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
                  >
                    <div>
                      <p className="font-semibold text-foreground">{bucket.agent_type}</p>
                      <p className="text-xs text-muted-foreground">{bucket.category}</p>
                    </div>
                    <p className="text-sm font-bold text-amber-300">{bucket.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ===== AI Insights Tab =====

function InsightsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const {
    data: insights,
    isLoading,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['projects', projectId, 'insights', dateRange],
    queryFn: () => getProjectInsights(projectId, dateRange, true, false),
    staleTime: 60000, // 1 minute - insights are expensive to generate
  });

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    setRegenerateError(null);
    try {
      // Fetch with force_regenerate=true
      const freshInsights = await getProjectInsights(projectId, dateRange, true, true);
      // Update the cache with fresh data
      queryClient.setQueryData(['projects', projectId, 'insights', dateRange], freshInsights);
    } catch (err) {
      console.error('Failed to regenerate insights:', err);
      setRegenerateError(err instanceof Error ? err.message : 'Failed to regenerate insights');
    } finally {
      setIsRegenerating(false);
    }
  };

  // Can only regenerate if there are conversations to analyze
  const canRegenerate = insights && insights.conversations_analyzed > 0;

  const dateRangeLabels = {
    '7d': 'Last 7 days',
    '30d': 'Last 30 days',
    '90d': 'Last 90 days',
    'all': 'All time',
  };

  // Calculate freshness - insights are stale if oldest insight is older than latest conversation
  const isStale = insights?.oldest_insight_at && insights?.latest_conversation_at
    ? new Date(insights.oldest_insight_at) < new Date(insights.latest_conversation_at)
    : false;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="observatory-card p-6">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin" />
            <div>
              <p className="text-sm font-medium">Analyzing conversations...</p>
              <p className="text-xs text-muted-foreground mt-1">
                First-time analysis may take 1-2 minutes for large projects
              </p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="observatory-card p-6 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/3 mb-4"></div>
              <div className="h-32 bg-muted rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load insights</p>
      </div>
    );
  }

  if (!insights) {
    return null;
  }

  const hasPatterns =
    insights.top_workflow_patterns.length > 0 ||
    insights.top_learning_opportunities.length > 0 ||
    insights.top_anti_patterns.length > 0;

  return (
    <div className="space-y-8">
      {/* Time Range Control */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Time Range:
          </span>
          <div className="flex gap-2">
            {(['7d', '30d', '90d', 'all'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setDateRange(range)}
                disabled={isFetching || isRegenerating}
                className={`
                  px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider rounded-md transition-all duration-200
                  ${
                    dateRange === range
                      ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                      : 'border border-border/50 text-muted-foreground hover:text-foreground hover:bg-accent/30 hover:border-border'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                {dateRangeLabels[range]}
              </button>
            ))}
          </div>
        </div>

        {/* Regenerate button */}
        <button
          onClick={handleRegenerate}
          disabled={isFetching || isRegenerating || !canRegenerate}
          title={!canRegenerate ? 'No conversations in selected date range' : undefined}
          className={`
            flex items-center gap-2 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider rounded-md
            border border-amber-400/30 text-amber-400 hover:bg-amber-400/10 transition-all
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
        >
          <RefreshCw className={`w-4 h-4 ${isRegenerating ? 'animate-spin' : ''}`} />
          {isRegenerating ? 'Regenerating...' : 'Regenerate'}
        </button>
      </div>

      {/* Regeneration in progress notice */}
      {isRegenerating && (
        <div className="observatory-card p-4 border-amber-400/30 bg-amber-400/5">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-amber-400 animate-spin" />
            <div>
              <p className="text-sm font-medium text-amber-400">Regenerating insights...</p>
              <p className="text-xs text-muted-foreground mt-1">
                This may take several minutes for projects with many conversations.
                Each conversation requires an LLM analysis call.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Regeneration error */}
      {regenerateError && (
        <div className="observatory-card p-4 border-red-400/30 bg-red-400/5">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <div>
              <p className="text-sm font-medium text-red-400">Regeneration failed</p>
              <p className="text-xs text-muted-foreground mt-1">{regenerateError}</p>
            </div>
          </div>
        </div>
      )}

      {/* Freshness Indicator */}
      {insights.oldest_insight_at && (
        <div className={`observatory-card p-4 ${isStale ? 'border-amber-400/30' : 'border-emerald-400/30'}`}>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              {isStale ? (
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              ) : (
                <Clock className="w-4 h-4 text-emerald-400" />
              )}
              <div>
                <span className="text-xs font-mono text-muted-foreground">
                  {isStale ? 'INSIGHTS MAY BE STALE' : 'INSIGHTS UP TO DATE'}
                </span>
                <p className="text-sm">
                  Oldest insight:{' '}
                  <span className={isStale ? 'text-amber-400' : 'text-foreground'}>
                    {formatDistanceToNow(new Date(insights.oldest_insight_at), { addSuffix: true })}
                  </span>
                  {insights.latest_conversation_at && (
                    <>
                      {' · Latest session: '}
                      <span className="text-foreground">
                        {formatDistanceToNow(new Date(insights.latest_conversation_at), { addSuffix: true })}
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
              <span>
                <span className="text-cyan-400">{insights.insights_cached}</span> cached
              </span>
              {insights.insights_generated > 0 && (
                <span>
                  <span className="text-emerald-400">{insights.insights_generated}</span> generated
                </span>
              )}
              {insights.insights_failed > 0 && (
                <span>
                  <span className="text-red-400">{insights.insights_failed}</span> failed
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Coverage Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Sessions Analyzed
          </span>
          <p className="text-2xl font-mono font-bold text-cyan-400 mt-1">
            {insights.conversations_analyzed}
          </p>
        </div>
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            With Insights
          </span>
          <p className="text-2xl font-mono font-bold text-emerald-400 mt-1">
            {insights.conversations_with_insights}
          </p>
        </div>
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Coverage
          </span>
          <p className="text-2xl font-mono font-bold text-purple-400 mt-1">
            {insights.conversations_analyzed > 0
              ? `${Math.round((insights.conversations_with_insights / insights.conversations_analyzed) * 100)}%`
              : 'N/A'}
          </p>
        </div>
      </div>

      {/* LLM Summary */}
      {insights.summary && (
        <div className="observatory-card p-6 border-l-4 border-l-cyan-400">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-cyan-400" />
            <h3 className="text-lg font-semibold">AI Summary</h3>
          </div>
          <div className="prose prose-sm prose-invert max-w-none">
            <p className="text-foreground/90 leading-relaxed whitespace-pre-wrap">
              {insights.summary}
            </p>
          </div>
        </div>
      )}

      {/* Score Averages */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ScoreCard
          title="Collaboration Quality"
          score={insights.avg_collaboration_quality}
          icon={<Users className="w-5 h-5" />}
          color="cyan"
          description="How well developers and AI work together"
        />
        <ScoreCard
          title="Agent Effectiveness"
          score={insights.avg_agent_effectiveness}
          icon={<Brain className="w-5 h-5" />}
          color="emerald"
          description="How well AI agents complete tasks"
        />
        <ScoreCard
          title="Scope Clarity"
          score={insights.avg_scope_clarity}
          icon={<FileText className="w-5 h-5" />}
          color="purple"
          description="How clear task requirements are"
        />
      </div>

      {/* Trends */}
      {(insights.collaboration_trend.length > 1 ||
        insights.effectiveness_trend.length > 1 ||
        insights.scope_clarity_trend.length > 1) && (
        <div className="observatory-card p-6">
          <h3 className="text-lg font-semibold mb-4">Weekly Trends</h3>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {insights.collaboration_trend.length > 1 && (
              <TrendMiniChart
                title="Collaboration"
                data={insights.collaboration_trend}
                color="cyan"
              />
            )}
            {insights.effectiveness_trend.length > 1 && (
              <TrendMiniChart
                title="Effectiveness"
                data={insights.effectiveness_trend}
                color="emerald"
              />
            )}
            {insights.scope_clarity_trend.length > 1 && (
              <TrendMiniChart
                title="Scope Clarity"
                data={insights.scope_clarity_trend}
                color="purple"
              />
            )}
          </div>
        </div>
      )}

      {/* Pattern Cards */}
      {hasPatterns && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Workflow Patterns */}
          {insights.top_workflow_patterns.length > 0 && (
            <PatternCard
              title="Top Workflow Patterns"
              icon={<Activity className="w-5 h-5 text-cyan-400" />}
              patterns={insights.top_workflow_patterns}
              color="cyan"
            />
          )}

          {/* Learning Opportunities */}
          {insights.top_learning_opportunities.length > 0 && (
            <PatternCard
              title="Learning Opportunities"
              icon={<BookOpen className="w-5 h-5 text-emerald-400" />}
              patterns={insights.top_learning_opportunities}
              color="emerald"
            />
          )}

          {/* Anti-Patterns */}
          {insights.top_anti_patterns.length > 0 && (
            <PatternCard
              title="Anti-Patterns"
              icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}
              patterns={insights.top_anti_patterns}
              color="amber"
            />
          )}

          {/* Technical Debt */}
          {insights.common_technical_debt.length > 0 && (
            <PatternCard
              title="Technical Debt Indicators"
              icon={<AlertTriangle className="w-5 h-5 text-red-400" />}
              patterns={insights.common_technical_debt}
              color="red"
            />
          )}
        </div>
      )}

      {/* Empty State */}
      {!hasPatterns && !insights.summary && (
        <div className="observatory-card p-12 text-center">
          <Lightbulb className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No Insights Yet</h3>
          {insights.conversations_analyzed === 0 ? (
            <div className="text-sm text-muted-foreground">
              <p className="mb-2">
                No conversations found in the selected time range ({dateRangeLabels[dateRange]}).
              </p>
              <p>
                Try selecting a longer time range like{' '}
                <button
                  onClick={() => setDateRange('all')}
                  className="text-cyan-400 hover:underline font-medium"
                >
                  All time
                </button>
                .
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Insights will appear here after analyzing conversation sessions.
              <br />
              Click <span className="text-amber-400 font-medium">Regenerate</span> to generate insights for all conversations.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ===== Insights Helper Components =====

function ScoreCard({
  title,
  score,
  icon,
  color,
  description,
}: {
  title: string;
  score: number;
  icon: React.ReactNode;
  color: 'cyan' | 'emerald' | 'purple';
  description: string;
}) {
  const colorClasses = {
    cyan: 'text-cyan-400 border-cyan-400/30 bg-cyan-400/5',
    emerald: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/5',
    purple: 'text-purple-400 border-purple-400/30 bg-purple-400/5',
  };

  const barColorClasses = {
    cyan: 'from-cyan-500 to-cyan-400',
    emerald: 'from-emerald-500 to-emerald-400',
    purple: 'from-purple-500 to-purple-400',
  };

  return (
    <div className={`observatory-card p-5 border ${colorClasses[color].split(' ')[1]} ${colorClasses[color].split(' ')[2]}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={colorClasses[color].split(' ')[0]}>{icon}</span>
        <h4 className="font-semibold text-sm">{title}</h4>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className={`text-3xl font-mono font-bold ${colorClasses[color].split(' ')[0]}`}>
          {score.toFixed(1)}
        </span>
        <span className="text-sm text-muted-foreground">/ 10</span>
      </div>
      <div className="h-1.5 bg-slate-900/50 rounded-full overflow-hidden border border-border/30 mb-2">
        <div
          className={`h-full bg-gradient-to-r ${barColorClasses[color]} transition-all`}
          style={{ width: `${(score / 10) * 100}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  );
}

function PatternCard({
  title,
  icon,
  patterns,
  color,
}: {
  title: string;
  icon: React.ReactNode;
  patterns: PatternFrequency[];
  color: 'cyan' | 'emerald' | 'amber' | 'red';
}) {
  const barColorClasses = {
    cyan: 'bg-cyan-400/80',
    emerald: 'bg-emerald-400/80',
    amber: 'bg-amber-400/80',
    red: 'bg-red-400/80',
  };

  return (
    <div className="observatory-card p-5">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h4 className="font-semibold">{title}</h4>
      </div>
      <div className="space-y-3">
        {patterns.slice(0, 5).map((pattern, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-foreground/90 truncate pr-2">{pattern.pattern}</span>
              <span className="text-muted-foreground font-mono text-xs whitespace-nowrap">
                {pattern.count} ({pattern.percentage}%)
              </span>
            </div>
            <div className="h-1 bg-slate-900/50 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColorClasses[color]} transition-all`}
                style={{ width: `${Math.min(pattern.percentage, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendMiniChart({
  title,
  data,
  color,
}: {
  title: string;
  data: TrendPoint[];
  color: 'cyan' | 'emerald' | 'purple';
}) {
  const colorClasses = {
    cyan: 'text-cyan-400',
    emerald: 'text-emerald-400',
    purple: 'text-purple-400',
  };

  const dotColorClasses = {
    cyan: 'bg-cyan-400',
    emerald: 'bg-emerald-400',
    purple: 'bg-purple-400',
  };

  // Calculate trend direction
  const firstScore = data[0]?.avg_score ?? 0;
  const lastScore = data[data.length - 1]?.avg_score ?? 0;
  const diff = lastScore - firstScore;
  const trendDirection = diff > 0.5 ? 'up' : diff < -0.5 ? 'down' : 'stable';

  // Normalize data for visualization
  const minScore = Math.min(...data.map((d) => d.avg_score));
  const maxScore = Math.max(...data.map((d) => d.avg_score));
  const range = maxScore - minScore || 1;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{title}</span>
        <span className={`text-sm font-mono ${colorClasses[color]}`}>
          {trendDirection === 'up' && '↑'}
          {trendDirection === 'down' && '↓'}
          {trendDirection === 'stable' && '→'}
          {lastScore.toFixed(1)}
        </span>
      </div>
      <div className="flex items-end gap-1 h-12">
        {data.map((point, idx) => {
          const height = ((point.avg_score - minScore) / range) * 100;
          return (
            <div
              key={idx}
              className={`flex-1 rounded-t ${dotColorClasses[color]} opacity-70 hover:opacity-100 transition-opacity`}
              style={{ height: `${Math.max(height, 10)}%` }}
              title={`${point.date}: ${point.avg_score.toFixed(1)} (${point.count} sessions)`}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-muted-foreground">{data[0]?.date?.slice(5)}</span>
        <span className="text-xs text-muted-foreground">{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}

// ===== Sessions Tab =====

function SessionsTab({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Filters and sorting
  const [developer, setDeveloper] = useState<string>('');
  const [outcome, setOutcome] = useState<'success' | 'failed' | 'partial' | ''>('');

  const page = parseInt(searchParams.get('page') || '1');
  const pageSize = 20;

  // Get stats to extract unique developers
  const { data: stats } = useQuery({
    queryKey: ['projects', projectId, 'stats'],
    queryFn: () => getProjectStats(projectId),
  });

  // Build filters object
  const filters: ProjectSessionFilters = {
    ...(developer && { developer }),
    ...(outcome && { outcome }),
  };

  const { data: sessions, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'sessions', { page, pageSize, filters }],
    queryFn: () => getProjectSessions(projectId, page, pageSize, filters),
    refetchInterval: 15000, // Auto-refresh
    staleTime: 0,
  });

  const handlePageChange = (newPage: number) => {
    setSearchParams({ page: String(newPage) });
  };

  const clearFilters = () => {
    setDeveloper('');
    setOutcome('');
  };

  // Define columns for SessionTable (Observatory theme to match ConversationList)
  const columns: ColumnConfig[] = [
    {
      id: 'start_time',
      label: 'Start Time',
      render: (session) => renderHelpers.startTime(session, 'observatory'),
    },
    {
      id: 'last_activity',
      label: 'Last Activity',
      render: renderHelpers.lastActivity,
    },
    {
      id: 'developer',
      label: 'Developer',
      render: renderHelpers.developerObservatory,
    },
    {
      id: 'agent_type',
      label: 'Agent Type',
      render: renderHelpers.agentType,
    },
    {
      id: 'status',
      label: 'Status',
      render: (session) => renderHelpers.status(session, 'observatory'),
    },
    {
      id: 'plan',
      label: 'Plan',
      align: 'center' as const,
      render: renderHelpers.planIndicator,
    },
    {
      id: 'messages',
      label: 'Messages',
      align: 'right' as const,
      render: (session) => renderHelpers.messageCount(session, 'observatory'),
    },
    {
      id: 'success',
      label: 'Success',
      align: 'center' as const,
      render: renderHelpers.successIndicator,
    },
  ];

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load sessions</p>
      </div>
    );
  }

  const hasActiveFilters = developer || outcome;

  return (
    <div className="space-y-6">
      {/* Filters and Sorting - Observatory Style */}
      <div className="observatory-card p-5">
        <div className="flex items-start justify-between gap-6">
          {/* Filter Controls */}
          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Developer Filter */}
            <div>
              <label htmlFor="developer-filter" className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
                Developer
              </label>
              <select
                id="developer-filter"
                value={developer}
                onChange={(e) => setDeveloper(e.target.value)}
                className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
              >
                <option value="">All Developers</option>
                {stats?.developers.map((dev) => (
                  <option key={dev} value={dev}>
                    {dev}
                  </option>
                ))}
              </select>
            </div>

            {/* Outcome Filter */}
            <div>
              <label htmlFor="outcome-filter" className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
                Outcome
              </label>
              <select
                id="outcome-filter"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value as typeof outcome)}
                className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
              >
                <option value="">All Outcomes</option>
                <option value="success">Success</option>
                <option value="partial">Partial</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>

          {/* Clear Filters Button */}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 text-xs font-mono font-semibold text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 transition-all uppercase tracking-wider"
            >
              Reset
            </button>
          )}
        </div>

        {/* Auto-refresh indicator - Observatory style */}
        <div className="flex items-center justify-end gap-3 mt-4">
          {isFetching && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-400/10 border border-cyan-400/30">
              <RefreshCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
              <span className="text-xs font-mono text-cyan-400">SYNCING</span>
            </div>
          )}
          {dataUpdatedAt && !isFetching && (
            <span className="text-xs font-mono text-muted-foreground">
              UPDATED {formatDistanceToNow(dataUpdatedAt, { addSuffix: true }).toUpperCase()}
            </span>
          )}
        </div>
      </div>

      {/* Sessions Table */}
      {isLoading ? (
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="animate-pulse space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-12 bg-muted rounded"></div>
            ))}
          </div>
        </div>
      ) : sessions && sessions.length > 0 ? (
        <>
          <SessionTable
            sessions={sessions}
            columns={columns}
            onRowClick={(id) => navigate(`/conversations/${id}`)}
            variant="observatory"
            emptyMessage="No archive entries found"
            emptyHint="Sessions will appear here once you ingest conversation logs"
          />

          <SessionPagination
            currentPage={page}
            pageSize={pageSize}
            currentPageItemCount={sessions.length}
            onPageChange={handlePageChange}
            variant="full"
            totalItems={sessions.length}
            totalPages={Math.ceil(sessions.length / pageSize)}
          />
        </>
      ) : (
        <div className="bg-card border border-border rounded-lg p-12 text-center">
          <Activity className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No sessions yet</h3>
          <p className="text-sm text-muted-foreground">
            Sessions will appear here once you ingest conversation logs
          </p>
        </div>
      )}
    </div>
  );
}

// ===== Files Tab =====

function FilesTab({ projectId }: { projectId: string }) {
  const { data: files, isLoading, error } = useQuery({
    queryKey: ['projects', projectId, 'files'],
    queryFn: () => getProjectFiles(projectId),
  });

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load files</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-muted rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (!files || files.length === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-12 text-center">
        <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-medium mb-2">No files modified</h3>
        <p className="text-sm text-muted-foreground">
          File modifications will appear here after ingesting sessions
        </p>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      <table className="min-w-full divide-y divide-border">
        <thead className="bg-muted/50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              File Path
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Modifications
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Lines Added
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Lines Deleted
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Last Modified
            </th>
          </tr>
        </thead>
        <tbody className="bg-card divide-y divide-border">
          {files.map((file, index) => (
            <tr key={index} className="hover:bg-accent transition-colors">
              <td className="px-6 py-4 text-sm font-mono max-w-md truncate">
                {file.file_path}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-mono">
                {file.modification_count}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-green-600">
                +{file.total_lines_added}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-red-600">
                -{file.total_lines_deleted}
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-sm">
                {format(new Date(file.last_modified_at), 'PPp')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ===== Helper Components =====
// (StatusBadge moved to shared components)
