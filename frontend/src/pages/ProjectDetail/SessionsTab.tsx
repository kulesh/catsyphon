/**
 * Sessions tab for ProjectDetail.
 *
 * Paginated, filterable, sortable list of all conversations for a project.
 */

import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { getProjectStats, getProjectSessions } from '@/lib/api';
import { Activity, RefreshCw } from 'lucide-react';
import { SessionTable, renderHelpers, type ColumnConfig } from '@/components/SessionTable';
import { SessionPagination } from '@/components/SessionPagination';
import type { ProjectSessionFilters } from '@/lib/api';

export default function SessionsTab({ projectId }: { projectId: string }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [developer, setDeveloper] = useState<string>('');
  const [outcome, setOutcome] = useState<'success' | 'failed' | 'partial' | ''>('');
  const [sortBy, setSortBy] = useState<'last_activity' | 'start_time' | 'message_count'>('last_activity');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const page = parseInt(searchParams.get('page') || '1');
  const pageSize = 20;

  const handleSort = (columnId: string) => {
    const sortByMap: Record<string, 'last_activity' | 'start_time' | 'message_count'> = {
      'last_activity': 'last_activity',
      'start_time': 'start_time',
      'messages': 'message_count',
    };
    const newSortBy = sortByMap[columnId];
    if (!newSortBy) return;

    if (newSortBy === sortBy) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(newSortBy);
      setSortOrder('desc');
    }
  };

  const { data: stats } = useQuery({
    queryKey: ['projects', projectId, 'stats'],
    queryFn: () => getProjectStats(projectId),
  });

  const filters: ProjectSessionFilters = {
    ...(developer && { developer }),
    ...(outcome && { outcome }),
    sort_by: sortBy,
    order: sortOrder,
  };

  const { data: sessions, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['projects', projectId, 'sessions', { page, pageSize, sortBy, sortOrder, developer, outcome }],
    queryFn: () => getProjectSessions(projectId, page, pageSize, filters),
    refetchInterval: 15000,
    staleTime: 0,
  });

  const handlePageChange = (newPage: number) => {
    setSearchParams({ page: String(newPage) });
  };

  const clearFilters = () => {
    setDeveloper('');
    setOutcome('');
  };

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
      sortable: true,
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

  const hasActiveFilters = developer || outcome;

  return (
    <div className="space-y-6">
      {/* Filters and Sorting */}
      <div className="observatory-card p-5">
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
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

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 text-xs font-mono font-semibold text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 transition-all uppercase tracking-wider"
            >
              Reset
            </button>
          )}
        </div>

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
      ) : sessions && sessions.items.length > 0 ? (
        <>
          <SessionTable
            sessions={sessions.items}
            columns={columns}
            onRowClick={(id) => navigate(`/conversations/${id}`)}
            variant="observatory"
            emptyMessage="No archive entries found"
            emptyHint="Sessions will appear here once you ingest conversation logs"
            sorting={{
              sortBy: sortBy === 'message_count' ? 'messages' : sortBy,
              order: sortOrder,
              onSort: handleSort,
            }}
          />

          <SessionPagination
            currentPage={page}
            pageSize={pageSize}
            currentPageItemCount={sessions.items.length}
            onPageChange={handlePageChange}
            variant="full"
            totalItems={sessions.total}
            totalPages={sessions.pages}
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
