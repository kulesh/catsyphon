/**
 * Failed Sessions page - Display ingestion failures for troubleshooting.
 *
 * Shows all failed log ingestion attempts with error details, file paths,
 * and timestamps to help users debug parsing/ingestion issues.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, XCircle, Clock, FileX, Loader2, RefreshCw } from 'lucide-react';
import { getIngestionJobs } from '@/lib/api';
import type { IngestionJobResponse } from '@/types/api';

export default function FailedSessions() {
  const [page, setPage] = useState(1);
  const pageSize = 50;

  // Fetch failed ingestion jobs
  const { data: jobs, isLoading, error, refetch } = useQuery({
    queryKey: ['ingestion-jobs', 'failed', page, pageSize],
    queryFn: () => getIngestionJobs({ status: 'failed', page, page_size: pageSize }),
    refetchInterval: 15000, // Auto-refresh every 15s
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const formatDuration = (ms: number | null) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const getSourceBadgeColor = (source: string) => {
    switch (source) {
      case 'watch': return 'bg-blue-500/10 text-blue-600 border-blue-500/30';
      case 'upload': return 'bg-purple-500/10 text-purple-600 border-purple-500/30';
      case 'cli': return 'bg-green-500/10 text-green-600 border-green-500/30';
      default: return 'bg-gray-500/10 text-gray-600 border-gray-500/30';
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">Loading failed sessions...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <AlertTriangle className="h-12 w-12 mx-auto text-destructive mb-4" />
          <h3 className="text-lg font-semibold mb-2">Error Loading Failed Sessions</h3>
          <p className="text-muted-foreground mb-4">{error.message}</p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-rose-400/10 border border-rose-400/30 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-rose-400" />
            </div>
            Failed Sessions
          </h1>
          <p className="text-muted-foreground">
            Review failed log ingestion attempts and error details for troubleshooting
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-md hover:bg-accent transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats Summary */}
      <div className="mb-6 p-4 bg-destructive/5 border border-destructive/20 rounded-lg">
        <div className="flex items-center gap-3">
          <XCircle className="w-5 h-5 text-destructive" />
          <div>
            <div className="font-semibold text-destructive">
              {jobs?.length || 0} Failed Ingestion{jobs?.length !== 1 ? 's' : ''}
            </div>
            <div className="text-sm text-muted-foreground">
              These logs failed to parse or ingest into the database
            </div>
          </div>
        </div>
      </div>

      {/* Failed Jobs List */}
      {!jobs || jobs.length === 0 ? (
        <div className="text-center py-12 bg-card border border-border rounded-lg">
          <FileX className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Failed Sessions</h3>
          <p className="text-muted-foreground">
            All ingestion attempts have succeeded. Great job!
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job: IngestionJobResponse) => (
            <div
              key={job.id}
              className="p-5 bg-card border border-destructive/20 rounded-lg hover:border-destructive/40 transition-colors"
            >
              {/* Header Row */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-start gap-3 flex-1">
                  <div className="w-10 h-10 rounded-lg bg-destructive/10 border border-destructive/30 flex items-center justify-center flex-shrink-0">
                    <XCircle className="w-5 h-5 text-destructive" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm font-semibold mb-1 truncate">
                      {job.file_path || 'Unknown file'}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(job.started_at)}
                      </span>
                      <span>•</span>
                      <span>Duration: {formatDuration(job.processing_time_ms)}</span>
                      <span>•</span>
                      <span
                        className={`px-2 py-0.5 rounded-full border text-xs font-medium uppercase ${getSourceBadgeColor(job.source_type)}`}
                      >
                        {job.source_type}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error Message */}
              {job.error_message && (
                <div className="mt-3 p-3 bg-destructive/5 border border-destructive/20 rounded-md">
                  <div className="text-xs font-semibold text-destructive mb-1">ERROR</div>
                  <div className="font-mono text-sm text-foreground break-all">
                    {job.error_message}
                  </div>
                </div>
              )}

              {/* Additional Details */}
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <div className="text-muted-foreground mb-0.5">Job ID</div>
                  <div className="font-mono truncate" title={job.id}>
                    {job.id.split('-')[0]}...
                  </div>
                </div>
                {job.source_config_id && (
                  <div>
                    <div className="text-muted-foreground mb-0.5">Config ID</div>
                    <div className="font-mono truncate" title={job.source_config_id}>
                      {job.source_config_id.split('-')[0]}...
                    </div>
                  </div>
                )}
                <div>
                  <div className="text-muted-foreground mb-0.5">Status</div>
                  <div className="font-semibold text-destructive uppercase">FAILED</div>
                </div>
                {job.created_by && (
                  <div>
                    <div className="text-muted-foreground mb-0.5">Created By</div>
                    <div className="truncate">{job.created_by}</div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {jobs && jobs.length >= pageSize && (
        <div className="mt-6 flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 bg-card border border-border rounded-md hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="px-4 py-2 bg-card border border-border rounded-md">
            Page {page}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!jobs || jobs.length < pageSize}
            className="px-4 py-2 bg-card border border-border rounded-md hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
