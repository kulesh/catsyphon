/**
 * Ingestion Job Card component.
 *
 * Displays a single ingestion job's status, metadata, and pipeline stage metrics.
 * Shared between LiveActivityTab and HistoryLogsTab.
 */

import {
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import type { IngestionJobResponse } from '@/types/api';

interface IngestionJobCardProps {
  job: IngestionJobResponse;
}

export default function IngestionJobCard({ job }: IngestionJobCardProps) {
  const jobIngestMode = (job.ingest_mode || job.metrics?.ingest_mode) as string | undefined;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return {
          bg: 'bg-green-500/10',
          text: 'text-green-600',
          border: 'border-green-500',
          icon: CheckCircle,
        };
      case 'failed':
        return {
          bg: 'bg-destructive/10',
          text: 'text-destructive',
          border: 'border-destructive',
          icon: XCircle,
        };
      case 'duplicate':
        return {
          bg: 'bg-yellow-500/10',
          text: 'text-yellow-600',
          border: 'border-yellow-500',
          icon: AlertCircle,
        };
      case 'processing':
        return {
          bg: 'bg-primary/10',
          text: 'text-primary',
          border: 'border-primary',
          icon: Loader2,
        };
      default:
        return {
          bg: 'bg-gray-500/10',
          text: 'text-gray-600',
          border: 'border-gray-500',
          icon: Clock,
        };
    }
  };

  const getSourceBadge = (sourceType: string) => {
    switch (sourceType) {
      case 'watch':
        return { bg: 'bg-blue-500/10', text: 'text-blue-600', label: 'Watch' };
      case 'upload':
        return { bg: 'bg-purple-500/10', text: 'text-purple-600', label: 'Upload' };
      case 'cli':
        return { bg: 'bg-orange-500/10', text: 'text-orange-600', label: 'CLI' };
      default:
        return { bg: 'bg-gray-500/10', text: 'text-gray-600', label: sourceType };
    }
  };

  const statusBadge = getStatusBadge(job.status);
  const sourceBadge = getSourceBadge(job.source_type);
  const StatusIcon = statusBadge.icon;

  const timeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${statusBadge.bg} ${statusBadge.border}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left side - Status and File */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <StatusIcon
            className={`h-5 w-5 mt-0.5 flex-shrink-0 ${statusBadge.text} ${
              job.status === 'processing' ? 'animate-spin' : ''
            }`}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`font-medium ${statusBadge.text}`}>
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </span>
              <span className="text-xs text-muted-foreground">•</span>
              <span className="text-xs text-muted-foreground">
                {timeAgo(job.started_at)}
              </span>
            </div>
            {job.file_path && (
              <p className="text-sm text-muted-foreground truncate" title={job.file_path}>
                {job.file_path.split('/').pop()}
              </p>
            )}
            {job.error_message && (
              <p className="text-xs text-destructive mt-1">{job.error_message}</p>
            )}
          </div>
        </div>

        {/* Right side - Metadata */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <span
            className={`px-2 py-1 text-xs font-medium rounded ${sourceBadge.bg} ${sourceBadge.text}`}
          >
            {sourceBadge.label}
          </span>

          {job.incremental && (
            <span className="px-2 py-1 text-xs font-medium rounded bg-purple-500/10 text-purple-600">
              ⚡ Incremental
            </span>
          )}

          {jobIngestMode && (
            <span className="px-2 py-1 text-xs font-medium rounded bg-secondary text-secondary-foreground">
              Mode: {jobIngestMode}
            </span>
          )}

          {job.processing_time_ms !== null && (
            <span className="text-xs text-muted-foreground">
              {job.processing_time_ms}ms
            </span>
          )}

          {job.messages_added > 0 && (
            <span className="text-xs text-muted-foreground">
              +{job.messages_added} msg
            </span>
          )}
        </div>
      </div>

      {/* Stage-level metrics */}
      {job.metrics && Object.keys(job.metrics).length > 0 && (
        <div className="mt-2 pt-2 border-t border-border/50">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="font-medium">Pipeline Stages:</span>
            {job.metrics.parse_duration_ms !== undefined && (
              <span>
                Parse: {job.metrics.parse_duration_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.deduplication_check_ms !== undefined && (
              <span>
                Dedup: {job.metrics.deduplication_check_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.database_operations_ms !== undefined && (
              <span>
                DB: {job.metrics.database_operations_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.total_ms !== undefined && (
              <span className="font-medium">
                Total: {job.metrics.total_ms.toFixed(0)}ms
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
