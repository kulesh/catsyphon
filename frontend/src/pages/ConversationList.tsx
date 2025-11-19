/**
 * Conversation List page - Observatory Session Archive.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getConversations, getDevelopers, getProjects } from '@/lib/api';
import { format, formatDistanceToNow } from 'date-fns';
import { Database, Filter, RefreshCw, AlertTriangle } from 'lucide-react';
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
      {/* Observatory Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <Database className="w-7 h-7 text-cyan-400" />
            <h1 className="text-3xl font-display tracking-wide text-foreground">
              SESSION ARCHIVE
            </h1>
          </div>
          <div className="flex items-center gap-3">
            {isFetching && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-cyan-400/10 border border-cyan-400/30">
                <RefreshCw className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                <span className="text-xs font-mono text-cyan-400">SYNCING</span>
              </div>
            )}
            {!isFetching && dataUpdatedAt && (
              <span className="text-xs font-mono text-muted-foreground">
                LAST SYNC {formatDistanceToNow(dataUpdatedAt, { addSuffix: true }).toUpperCase()}
              </span>
            )}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-400/10 border border-emerald-400/30">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot" />
              <span className="text-xs font-mono text-emerald-400">
                AUTO {secondsUntilRefresh}s
              </span>
            </div>
          </div>
        </div>
        <p className="text-sm font-mono text-muted-foreground">
          Archived conversation logs • Real-time monitoring • {data?.total.toLocaleString() || '---'} total entries
        </p>
      </div>

      {/* Observatory Filter Panel */}
      <div className="observatory-card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-mono text-foreground tracking-wider">FILTER PARAMETERS</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {/* Project Filter */}
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Project
            </label>
            <select
              value={filters.project_id || ''}
              onChange={(e) =>
                updateFilters({ project_id: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
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
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Developer
            </label>
            <select
              value={filters.developer_id || ''}
              onChange={(e) =>
                updateFilters({ developer_id: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
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
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Agent Type
            </label>
            <input
              type="text"
              value={filters.agent_type || ''}
              onChange={(e) =>
                updateFilters({ agent_type: e.target.value || undefined })
              }
              placeholder="claude-code"
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm placeholder:text-muted-foreground/40 focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
            />
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Status
            </label>
            <select
              value={filters.status || ''}
              onChange={(e) =>
                updateFilters({ status: e.target.value || undefined })
              }
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
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
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Start Date
            </label>
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
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all [color-scheme:dark]"
            />
          </div>

          {/* End Date Filter */}
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              End Date
            </label>
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
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all [color-scheme:dark]"
            />
          </div>

          {/* Success Filter */}
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1.5 uppercase tracking-wide">
              Success
            </label>
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
              className="w-full px-3 py-2 border border-border/50 rounded-md bg-slate-900/50 font-mono text-sm focus:border-cyan-400/50 focus:ring-1 focus:ring-cyan-400/20 transition-all"
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
              className="w-full px-4 py-2 text-xs font-mono font-semibold text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 transition-all uppercase tracking-wider"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="min-h-[400px] flex items-center justify-center grid-pattern">
          <div className="text-center">
            <div className="relative">
              <div className="animate-spin rounded-full h-16 w-16 border-2 border-transparent border-t-cyan-400 border-r-cyan-400 mx-auto mb-6 glow-cyan"></div>
              <div className="absolute inset-0 animate-ping rounded-full h-16 w-16 border border-cyan-400/20 mx-auto"></div>
            </div>
            <p className="text-sm font-mono text-muted-foreground tracking-wider">LOADING ARCHIVE DATA...</p>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="observatory-card border-destructive/50 p-6 mb-6">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-destructive" />
            <h3 className="font-heading text-lg text-destructive">Archive Error</h3>
          </div>
          <p className="font-mono text-sm text-destructive/80">
            {error.message}
          </p>
        </div>
      )}

      {/* Observatory Data Table */}
      {data && (
        <>
          <div className="observatory-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-900/50 border-b border-border/50">
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Start Time
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Last Activity
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Project
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Developer
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Agent Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Messages
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
                    Success
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center">
                      <p className="font-mono text-sm text-muted-foreground">NO ARCHIVE ENTRIES FOUND</p>
                      <p className="font-mono text-xs text-muted-foreground/60 mt-1">Adjust filter parameters</p>
                    </td>
                  </tr>
                ) : (
                  data.items.map((conversation) => (
                    <tr
                      key={conversation.id}
                      onClick={() => navigate(`/conversations/${conversation.id}`)}
                      className={`group cursor-pointer transition-all duration-300 hover:bg-cyan-400/5 ${
                        newItemIds.has(conversation.id)
                          ? 'bg-emerald-400/10 animate-pulse border-l-2 border-l-emerald-400'
                          : ''
                      }`}
                    >
                      <td className="px-4 py-3.5 font-mono text-xs text-foreground/90">
                        {format(new Date(conversation.start_time), 'MMM dd, yyyy HH:mm')}
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-muted-foreground">
                        {conversation.end_time
                          ? format(new Date(conversation.end_time), 'MMM dd, yyyy HH:mm')
                          : '---'}
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-foreground/80">
                        {conversation.project?.name || '---'}
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-cyan-400/90">
                        {conversation.developer?.username || '---'}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center gap-2">
                          {conversation.conversation_type === 'agent' && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-purple-400/10 border border-purple-400/30 text-[10px] font-mono text-purple-400 uppercase tracking-wide" title="Agent conversation">
                              Sub
                            </span>
                          )}
                          <span className="font-mono text-xs text-foreground/80">{conversation.agent_type}</span>
                          {conversation.children_count > 0 && (
                            <span className="font-mono text-[10px] text-amber-400" title={`${conversation.children_count} spawned agent${conversation.children_count !== 1 ? 's' : ''}`}>
                              +{conversation.children_count}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wide ${
                            conversation.status === 'completed'
                              ? 'bg-emerald-400/10 border border-emerald-400/30 text-emerald-400'
                              : conversation.status === 'failed'
                                ? 'bg-rose-400/10 border border-rose-400/30 text-rose-400'
                                : 'bg-cyan-400/10 border border-cyan-400/30 text-cyan-400'
                          }`}
                        >
                          {conversation.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 font-mono text-xs text-right text-foreground/90">
                        {conversation.message_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        {conversation.success === null ? (
                          <span className="font-mono text-xs text-muted-foreground">---</span>
                        ) : conversation.success ? (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-400/20 text-emerald-400 text-sm">
                            ✓
                          </span>
                        ) : (
                          <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-400/20 text-rose-400 text-sm">
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

          {/* Observatory Pagination Controls */}
          <div className="flex items-center justify-between mt-6">
            <div className="font-mono text-xs text-muted-foreground">
              <span className="text-foreground/90">
                {data.items.length === 0 ? 0 : ((data.page - 1) * data.page_size + 1).toLocaleString()}
              </span>
              {' - '}
              <span className="text-foreground/90">
                {Math.min(data.page * data.page_size, data.total).toLocaleString()}
              </span>
              {' of '}
              <span className="text-cyan-400">
                {data.total.toLocaleString()}
              </span>
              {' entries'}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => updateFilters({ page: filters.page! - 1 })}
                disabled={data.page === 1}
                className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-muted-foreground disabled:hover:border-border/50 disabled:hover:bg-transparent transition-all"
              >
                Prev
              </button>

              <div className="px-4 py-2 bg-slate-900/50 border border-border/50 rounded-md">
                <span className="font-mono text-xs text-foreground/90">
                  Page{' '}
                  <span className="text-cyan-400 font-semibold">{data.page}</span>
                  {' / '}
                  <span className="text-muted-foreground">{data.pages}</span>
                </span>
              </div>

              <button
                onClick={() => updateFilters({ page: filters.page! + 1 })}
                disabled={data.page === data.pages}
                className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-muted-foreground disabled:hover:border-border/50 disabled:hover:bg-transparent transition-all"
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
