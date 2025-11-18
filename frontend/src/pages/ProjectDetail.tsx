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
  ChevronLeft,
  ChevronRight,
  Folder,
} from 'lucide-react';

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
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-3">
          <Folder className="w-8 h-8 text-primary" />
          <h1 className="text-4xl font-bold">{project?.name || 'Loading...'}</h1>
        </div>
        {project?.description && (
          <p className="text-muted-foreground text-lg mb-2">
            {project.description}
          </p>
        )}
        <button
          onClick={() => navigate('/projects')}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Back to Projects
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border mb-8">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm
                  transition-all duration-200
                  ${
                    isActive
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon
                  className={`
                    -ml-0.5 mr-2 h-5 w-5 transition-colors
                    ${
                      isActive
                        ? 'text-primary'
                        : 'text-muted-foreground group-hover:text-foreground'
                    }
                  `}
                  aria-hidden="true"
                />
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
  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'stats'],
    queryFn: () => getProjectStats(projectId),
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

  return (
    <div className="space-y-8">
      {/* Auto-refresh indicator */}
      <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground">
        {isFetching && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span>Refreshing...</span>
          </div>
        )}
        {dataUpdatedAt && !isFetching && (
          <span>Updated {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}</span>
        )}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Total Sessions */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Sessions
            </p>
            <Activity className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {stats.session_count.toLocaleString()}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            {stats.developer_count} developer{stats.developer_count !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Total Messages */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Messages
            </p>
            <MessageSquare className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {stats.total_messages.toLocaleString()}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            {stats.session_count > 0
              ? `${Math.round(stats.total_messages / stats.session_count)} avg per session`
              : 'N/A'}
          </p>
        </div>

        {/* Files Changed */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Files Changed
            </p>
            <FileText className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {stats.total_files_changed.toLocaleString()}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Across all sessions
          </p>
        </div>

        {/* Success Rate */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Success Rate
            </p>
            <TrendingUp className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {stats.success_rate !== null
              ? `${Math.round(stats.success_rate * 100)}%`
              : 'N/A'}
          </p>
          {stats.success_rate !== null && (
            <div className="mt-3">
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full transition-all"
                  style={{ width: `${stats.success_rate * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Avg Session Duration */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Avg Duration
            </p>
            <Clock className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {avgDurationMinutes !== null ? `${avgDurationMinutes}m` : 'N/A'}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Per session
          </p>
        </div>

        {/* Developers */}
        <div className="bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Developers
            </p>
            <Users className="w-5 h-5 text-muted-foreground" />
          </div>
          <p className="text-4xl font-bold font-mono">
            {stats.developer_count}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Active contributors
          </p>
        </div>
      </div>

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
        <div className="bg-card border border-border rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Tool Usage</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {Object.entries(stats.tool_usage)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 8)
              .map(([tool, count]) => (
                <div
                  key={tool}
                  className="flex flex-col items-center justify-center p-4 bg-muted rounded-lg"
                >
                  <p className="text-2xl font-bold font-mono">{count}</p>
                  <p className="text-xs text-muted-foreground text-center mt-1">
                    {tool}
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ===== Sessions Tab =====

function SessionsTab({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parseInt(searchParams.get('page') || '1');
  const pageSize = 20;

  const { data: sessions, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'sessions', { page, pageSize }],
    queryFn: () => getProjectSessions(projectId, page, pageSize),
    refetchInterval: 15000, // Auto-refresh
    staleTime: 0,
  });

  const handlePageChange = (newPage: number) => {
    setSearchParams({ page: String(newPage) });
  };

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load sessions</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Auto-refresh indicator */}
      <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground">
        {isFetching && (
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span>Refreshing...</span>
          </div>
        )}
        {dataUpdatedAt && !isFetching && (
          <span>Updated {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}</span>
        )}
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
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Start Time
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Developer
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Messages
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Files
                  </th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {sessions.map((session) => (
                  <tr
                    key={session.id}
                    onClick={() => navigate(`/conversations/${session.id}`)}
                    className="hover:bg-accent cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {format(new Date(session.start_time), 'PPp')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono">
                      {session.duration_seconds
                        ? `${Math.round(session.duration_seconds / 60)}m`
                        : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge
                        status={session.status}
                        success={session.success}
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {session.developer || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono">
                      {session.message_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono">
                      {session.files_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Page {page}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
                className="px-4 py-2 bg-card border border-border rounded-lg text-sm hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={!sessions || sessions.length < pageSize}
                className="px-4 py-2 bg-card border border-border rounded-lg text-sm hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
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

function StatusBadge({ status, success }: { status: string; success: boolean | null }) {
  let colorClass = 'bg-muted/50 text-muted-foreground';

  if (success === true) {
    colorClass = 'bg-green-500/10 text-green-600 border-green-500/20';
  } else if (success === false) {
    colorClass = 'bg-destructive/10 text-destructive border-destructive/20';
  }

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}
    >
      {status}
    </span>
  );
}
