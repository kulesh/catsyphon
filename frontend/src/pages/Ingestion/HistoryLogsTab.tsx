/**
 * History & Logs tab for Ingestion.
 *
 * Complete history of all ingestion jobs with filtering, pagination,
 * and summary statistics.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, Loader2 } from 'lucide-react';
import { getIngestionJobs, getIngestionStats } from '@/lib/api';
import type { IngestionJobFilters } from '@/types/api';
import IngestionJobCard from './IngestionJobCard';

export default function HistoryLogsTab() {
  const [filters, setFilters] = useState({
    source_type: '' as '' | 'watch' | 'upload' | 'cli',
    status: '' as '' | 'success' | 'failed' | 'duplicate' | 'skipped',
    page_size: 50,
  });
  const [page, setPage] = useState(1);

  const { data: jobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ['ingestionJobs', filters, page],
    queryFn: () => getIngestionJobs({
      source_type: filters.source_type || undefined,
      status: filters.status || undefined,
      page,
      page_size: filters.page_size,
    } satisfies IngestionJobFilters),
  });

  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['ingestionStats'],
    queryFn: getIngestionStats,
  });

  const isLoading = isLoadingJobs || isLoadingStats;

  const handleFilterChange = (key: string, value: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({ source_type: '', status: '', limit: 50 });
    setPage(1);
  };

  const hasActiveFilters = filters.source_type !== '' || filters.status !== '';

  if (isLoading && !stats && !jobs) {
    return (
      <div className="text-center py-12">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">Loading history...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold mb-2">History & Logs</h2>
          <p className="text-muted-foreground">
            Complete history of all ingestion jobs with filtering and pagination
          </p>
        </div>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-card border border-border rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Total Jobs</div>
            <div className="text-2xl font-bold">{stats.total_jobs}</div>
          </div>
          <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Success</div>
            <div className="text-2xl font-bold text-green-600">
              {stats.by_status.success || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.total_jobs > 0
                ? `${((stats.by_status.success || 0) / stats.total_jobs * 100).toFixed(1)}%`
                : '0%'}
            </div>
          </div>
          <div className="p-4 bg-destructive/5 border border-destructive/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Failed</div>
            <div className="text-2xl font-bold text-destructive">
              {stats.by_status.failed || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.total_jobs > 0
                ? `${((stats.by_status.failed || 0) / stats.total_jobs * 100).toFixed(1)}%`
                : '0%'}
            </div>
          </div>
          <div className="p-4 bg-purple-500/5 border border-purple-500/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Incremental</div>
            <div className="text-2xl font-bold text-purple-600">
              {stats.incremental_percentage ? `${stats.incremental_percentage.toFixed(1)}%` : '0%'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.incremental_jobs} jobs
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="p-4 bg-card border border-border rounded-lg">
        <div className="flex items-start justify-between mb-4">
          <h3 className="font-semibold">Filters</h3>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-primary hover:text-primary/80"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Source Type</label>
            <select
              value={filters.source_type}
              onChange={(e) => handleFilterChange('source_type', e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Sources</option>
              <option value="watch">Watch</option>
              <option value="upload">Upload</option>
              <option value="cli">CLI</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Statuses</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="duplicate">Duplicate</option>
              <option value="processing">Processing</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Results per page</label>
            <select
              value={filters.page_size}
              onChange={(e) => handleFilterChange('page_size', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results Info */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {jobs && jobs.length > 0 ? (
            <>
              Showing {(page - 1) * filters.page_size + 1} -{' '}
              {Math.min(page * filters.page_size, (page - 1) * filters.page_size + jobs.length)} of{' '}
              {stats?.total_jobs || 0} total jobs
              {hasActiveFilters && ' (filtered)'}
            </>
          ) : (
            'No jobs found'
          )}
        </div>
        {jobs && jobs.length >= filters.page_size && (
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="px-3 py-1 text-sm">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!jobs || jobs.length < filters.page_size}
              className="px-3 py-1 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Jobs List */}
      {jobs && jobs.length > 0 ? (
        <div className="space-y-2">
          {jobs.map((job) => (
            <IngestionJobCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-card border border-border rounded-lg">
          <History className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No jobs found</h3>
          <p className="text-muted-foreground mb-4">
            {hasActiveFilters
              ? 'Try adjusting your filters to see more results'
              : 'Upload files or configure watch directories to get started'}
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Clear Filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
