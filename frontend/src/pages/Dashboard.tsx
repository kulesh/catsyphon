/**
 * Dashboard page - Overview statistics and metrics.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { getOverviewStats } from '@/lib/api';

export default function Dashboard() {
  const { data: stats, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: () => getOverviewStats(),
    refetchInterval: 15000, // Auto-refresh every 15 seconds for live dashboard
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
          <p className="text-destructive">
            Error loading dashboard: {error.message}
          </p>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">CatSyphon Dashboard</h1>
            <p className="text-muted-foreground">
              Overview of conversation logs and coding agent activity
            </p>
          </div>
          <div className="flex items-center gap-3">
            {isFetching && (
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
            {dataUpdatedAt && (
              <span className="text-xs text-muted-foreground">
                Updated {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Overview Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Conversations
            </p>
            <svg
              className="w-5 h-5 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold">{stats.total_conversations.toLocaleString()}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {stats.total_main_conversations} main, {stats.total_agent_conversations} agents
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {stats.recent_conversations} in last 7 days
          </p>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Total Messages
            </p>
            <svg
              className="w-5 h-5 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold">{stats.total_messages.toLocaleString()}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {stats.total_conversations > 0
              ? `${Math.round(stats.total_messages / stats.total_conversations)} avg per conversation`
              : 'N/A'}
          </p>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Projects
            </p>
            <svg
              className="w-5 h-5 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold">{stats.total_projects.toLocaleString()}</p>
          <p className="text-sm text-muted-foreground mt-1">
            Tracked projects
          </p>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Developers
            </p>
            <svg
              className="w-5 h-5 text-muted-foreground"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
          </div>
          <p className="text-3xl font-bold">{stats.total_developers.toLocaleString()}</p>
          <p className="text-sm text-muted-foreground mt-1">
            Active developers
          </p>
        </div>
      </div>

      {/* Success Rate */}
      {stats.success_rate !== null && (
        <div className="bg-card border border-border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">Success Rate</h2>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="relative h-8 bg-muted rounded-full overflow-hidden">
                <div
                  className="absolute top-0 left-0 h-full bg-green-500 transition-all"
                  style={{ width: `${stats.success_rate}%` }}
                />
              </div>
            </div>
            <div className="text-3xl font-bold">
              {stats.success_rate.toFixed(1)}%
            </div>
          </div>
          <p className="text-sm text-muted-foreground mt-2">
            Of conversations with success status recorded
          </p>
        </div>
      )}

      {/* Conversations by Status and Agent Type */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Status Breakdown */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">By Status</h2>
          <div className="space-y-3">
            {Object.entries(stats.conversations_by_status)
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => {
                const percentage = (count / stats.total_conversations) * 100;
                return (
                  <div key={status}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium capitalize">{status}</span>
                      <span className="text-sm text-muted-foreground">
                        {count} ({percentage.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`absolute top-0 left-0 h-full transition-all ${
                          status === 'completed'
                            ? 'bg-green-500'
                            : status === 'failed'
                              ? 'bg-red-500'
                              : status === 'in_progress'
                                ? 'bg-blue-500'
                                : 'bg-yellow-500'
                        }`}
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Agent Type Breakdown */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">By Agent Type</h2>
          <div className="space-y-3">
            {Object.entries(stats.conversations_by_agent)
              .sort(([, a], [, b]) => b - a)
              .map(([agent, count]) => {
                const percentage = (count / stats.total_conversations) * 100;
                return (
                  <div key={agent}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium font-mono">{agent}</span>
                      <span className="text-sm text-muted-foreground">
                        {count} ({percentage.toFixed(1)}%)
                      </span>
                    </div>
                    <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="absolute top-0 left-0 h-full bg-purple-500 transition-all"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            to="/conversations"
            className="flex items-center gap-3 p-4 border border-border rounded-md hover:bg-accent transition-colors"
          >
            <svg
              className="w-6 h-6 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
              />
            </svg>
            <div>
              <p className="font-medium">Browse Conversations</p>
              <p className="text-sm text-muted-foreground">
                View and filter all conversations
              </p>
            </div>
          </Link>

          <Link
            to="/conversations?status=failed"
            className="flex items-center gap-3 p-4 border border-border rounded-md hover:bg-accent transition-colors"
          >
            <svg
              className="w-6 h-6 text-destructive"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="font-medium">Failed Conversations</p>
              <p className="text-sm text-muted-foreground">
                Review conversations that failed
              </p>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
}
