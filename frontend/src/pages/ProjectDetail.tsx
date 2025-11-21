/**
 * Project Detail page - Deep-dive analytics for a single project.
 *
 * Features three tabs:
 * - Stats: Overview metrics, insights, and tool usage
 * - Sessions: Paginated list of all conversations
 * - Files: Aggregated file modification statistics
 */

import { useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow, format } from 'date-fns';
import {
  getProjectStats,
  getProjectSessions,
  getProjectFiles,
  getProjects,
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
} from 'lucide-react';
import { SentimentTimelineChart } from '@/components/SentimentTimelineChart';
import { ToolUsageChart } from '@/components/ToolUsageChart';
import { SessionTable, renderHelpers, type ColumnConfig } from '@/components/SessionTable';
import { SessionPagination } from '@/components/SessionPagination';
import type { ProjectSessionFilters } from '@/lib/api';

type Tab = 'stats' | 'sessions' | 'files';

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
        {activeTab === 'sessions' && <SessionsTab projectId={id} />}
        {activeTab === 'files' && <FilesTab projectId={id} />}
      </div>
    </div>
  );
}

// ===== Stats Tab =====

function StatsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('all');

  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'stats', dateRange],
    queryFn: () => getProjectStats(projectId, dateRange),
    refetchInterval: 15000, // Auto-refresh every 15 seconds
    staleTime: 0, // Always fetch fresh data
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

// ===== Sessions Tab =====

function SessionsTab({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Filters and sorting
  const [developer, setDeveloper] = useState<string>('');
  const [outcome, setOutcome] = useState<'success' | 'failed' | 'partial' | ''>('');
  const [sortBy, setSortBy] = useState<'start_time' | 'duration' | 'messages'>('start_time');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

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
    sort_by: sortBy,
    order,
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

  const handleSort = (column: 'start_time' | 'duration' | 'messages') => {
    if (sortBy === column) {
      // Toggle order if clicking same column
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new column and default to desc
      setSortBy(column);
      setOrder('desc');
    }
  };

  const clearFilters = () => {
    setDeveloper('');
    setOutcome('');
    setSortBy('start_time');
    setOrder('desc');
  };

  // Define columns for SessionTable (Observatory theme to match ConversationList)
  const columns: ColumnConfig[] = [
    {
      id: 'start_time',
      label: 'Start Time',
      sortable: true,
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
      sortable: true,
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
      id: 'messages',
      label: 'Messages',
      align: 'right' as const,
      sortable: true,
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

  const hasActiveFilters = developer || outcome || sortBy !== 'start_time' || order !== 'desc';

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
            sorting={{
              sortBy,
              order,
              onSort: handleSort,
            }}
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
