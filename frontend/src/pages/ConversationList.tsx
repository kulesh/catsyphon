/**
 * Conversation List page - Paginated table with filters.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getConversations, getDevelopers, getProjects } from '@/lib/api';
import { format, formatDistanceToNow } from 'date-fns';
import type { ConversationFilters } from '@/types/api';
import { useRefreshCountdown } from '@/hooks/useRefreshCountdown';

export default function ConversationList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Track new items for highlighting
  const [newItemIds, setNewItemIds] = useState<Set<string>>(new Set());
  const [previousIds, setPreviousIds] = useState<Set<string>>(new Set());

  // Parse filters from URL
  const filters: ConversationFilters = {
    project_id: searchParams.get('project_id') || undefined,
    developer_id: searchParams.get('developer_id') || undefined,
    agent_type: searchParams.get('agent_type') || undefined,
    status: searchParams.get('status') || undefined,
    start_date: searchParams.get('start_date') || undefined,
    end_date: searchParams.get('end_date') || undefined,
    success:
      searchParams.get('success') === 'true'
        ? true
        : searchParams.get('success') === 'false'
          ? false
          : undefined,
    page: parseInt(searchParams.get('page') || '1'),
    page_size: parseInt(searchParams.get('page_size') || '20'),
  };

  // Fetch data
  const { data, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['conversations', filters],
    queryFn: () => getConversations(filters),
    placeholderData: (previousData) => previousData, // Show cached data while refetching
    refetchOnMount: false, // Don't refetch when navigating back to this page
    refetchInterval: 15000, // Auto-refresh every 15 seconds
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  const secondsUntilRefresh = useRefreshCountdown(15000, dataUpdatedAt);

  // Detect new items when data changes
  useEffect(() => {
    if (data?.items) {
      const currentIds = new Set(data.items.map((c) => c.id));

      // Find items that are in current but not in previous
      const newIds = new Set<string>();
      currentIds.forEach((id) => {
        if (previousIds.size > 0 && !previousIds.has(id)) {
          newIds.add(id);
        }
      });

      setNewItemIds(newIds);
      setPreviousIds(currentIds);

      // Clear highlights after 3 seconds
      if (newIds.size > 0) {
        const timer = setTimeout(() => {
          setNewItemIds(new Set());
        }, 3000);
        return () => clearTimeout(timer);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const { data: developers } = useQuery({
    queryKey: ['developers'],
    queryFn: getDevelopers,
  });

  // Update URL params
  const updateFilters = (updates: Partial<ConversationFilters>) => {
    const newParams = new URLSearchParams(searchParams);

    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') {
        newParams.delete(key);
      } else {
        newParams.set(key, String(value));
      }
    });

    // Reset to page 1 when filters change (unless explicitly setting page)
    if (!('page' in updates)) {
      newParams.set('page', '1');
    }

    setSearchParams(newParams);
  };

  const clearFilters = () => {
    setSearchParams(new URLSearchParams({ page: '1', page_size: '20' }));
  };

  return (
    <div className="container mx-auto p-6">
      {/* Header with freshness indicators */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">Conversations</h1>
        <div className="flex items-center gap-3">
          {isFetching && (
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <svg
                className="w-4 h-4 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Refreshing...
            </span>
          )}
          {!isFetching && dataUpdatedAt && (
            <span className="text-sm text-muted-foreground">
              Last updated {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}
            </span>
          )}
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            Auto-refresh: {secondsUntilRefresh}s
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-card border border-border rounded-lg p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {/* Project Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Project</label>
            <select
              value={filters.project_id || ''}
              onChange={(e) =>
                updateFilters({ project_id: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            >
              <option value="">All Projects</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {/* Developer Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Developer</label>
            <select
              value={filters.developer_id || ''}
              onChange={(e) =>
                updateFilters({ developer_id: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            >
              <option value="">All Developers</option>
              {developers?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.username}
                </option>
              ))}
            </select>
          </div>

          {/* Agent Type Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Agent Type</label>
            <input
              type="text"
              value={filters.agent_type || ''}
              onChange={(e) =>
                updateFilters({ agent_type: e.target.value || undefined })
              }
              placeholder="e.g., claude-code"
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            />
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Status</label>
            <select
              value={filters.status || ''}
              onChange={(e) =>
                updateFilters({ status: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            >
              <option value="">All Statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Start Date Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Start Date</label>
            <input
              type="date"
              value={
                filters.start_date
                  ? filters.start_date.split('T')[0]
                  : ''
              }
              onChange={(e) =>
                updateFilters({
                  start_date: e.target.value
                    ? `${e.target.value}T00:00:00Z`
                    : undefined,
                })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            />
          </div>

          {/* End Date Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">End Date</label>
            <input
              type="date"
              value={
                filters.end_date ? filters.end_date.split('T')[0] : ''
              }
              onChange={(e) =>
                updateFilters({
                  end_date: e.target.value
                    ? `${e.target.value}T23:59:59Z`
                    : undefined,
                })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            />
          </div>

          {/* Success Filter */}
          <div>
            <label className="block text-sm font-medium mb-1">Success</label>
            <select
              value={
                filters.success === undefined
                  ? ''
                  : filters.success
                    ? 'true'
                    : 'false'
              }
              onChange={(e) =>
                updateFilters({
                  success:
                    e.target.value === ''
                      ? undefined
                      : e.target.value === 'true',
                })
              }
              className="w-full px-3 py-2 border border-input rounded-md bg-background"
            >
              <option value="">All</option>
              <option value="true">Success</option>
              <option value="false">Failed</option>
            </select>
          </div>

          {/* Clear Filters Button */}
          <div className="flex items-end">
            <button
              onClick={clearFilters}
              className="w-full px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground border border-input rounded-md hover:bg-accent transition-colors"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading conversations...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4 mb-6">
          <p className="text-destructive">
            Error loading conversations: {error.message}
          </p>
        </div>
      )}

      {/* Table */}
      {data && (
        <>
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Start Time
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Last Activity
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Project
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Developer
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Agent Type
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Messages
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Success
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                      No conversations found
                    </td>
                  </tr>
                ) : (
                  data.items.map((conversation) => (
                    <tr
                      key={conversation.id}
                      onClick={() => navigate(`/conversations/${conversation.id}`)}
                      className={`border-t border-border hover:bg-accent cursor-pointer transition-all duration-500 ${
                        newItemIds.has(conversation.id)
                          ? 'bg-green-50 dark:bg-green-950/20 animate-pulse'
                          : ''
                      }`}
                    >
                      <td className="px-4 py-3 text-sm">
                        {format(new Date(conversation.start_time), 'PPp')}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {conversation.end_time
                          ? format(new Date(conversation.end_time), 'PPp')
                          : '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {conversation.project?.name || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {conversation.developer?.username || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex items-center gap-2">
                          {conversation.conversation_type === 'agent' && (
                            <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200" title="Agent conversation">
                              Agent
                            </span>
                          )}
                          <span className="font-mono text-xs">{conversation.agent_type}</span>
                          {conversation.children_count > 0 && (
                            <span className="text-xs text-muted-foreground" title={`${conversation.children_count} child conversation${conversation.children_count !== 1 ? 's' : ''}`}>
                              +{conversation.children_count}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <span
                          className={`inline-block px-2 py-1 rounded-full text-xs ${
                            conversation.status === 'completed'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : conversation.status === 'failed'
                                ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                                : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                          }`}
                        >
                          {conversation.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {conversation.message_count}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {conversation.success === null ? (
                          '-'
                        ) : conversation.success ? (
                          <span className="text-green-600 dark:text-green-400">
                            ✓
                          </span>
                        ) : (
                          <span className="text-red-600 dark:text-red-400">
                            ✗
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-muted-foreground">
              Showing {data.items.length === 0 ? 0 : (data.page - 1) * data.page_size + 1} to{' '}
              {Math.min(data.page * data.page_size, data.total)} of {data.total}{' '}
              conversations
            </p>

            <div className="flex gap-2">
              <button
                onClick={() => updateFilters({ page: filters.page! - 1 })}
                disabled={data.page === 1}
                className="px-3 py-1 text-sm border border-input rounded-md hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>

              <div className="flex items-center gap-2 px-3">
                <span className="text-sm">
                  Page {data.page} of {data.pages}
                </span>
              </div>

              <button
                onClick={() => updateFilters({ page: filters.page! + 1 })}
                disabled={data.page === data.pages}
                className="px-3 py-1 text-sm border border-input rounded-md hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
