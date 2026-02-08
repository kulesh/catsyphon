/**
 * Live Activity tab for Ingestion.
 *
 * Real-time monitoring of watch directories and ingestion jobs with
 * auto-refreshing stats, pipeline performance metrics, and recent job feed.
 */

import { useQuery } from '@tanstack/react-query';
import {
  FolderSearch,
  Activity,
  CheckCircle,
  Loader2,
  Clock,
  RefreshCw,
  Zap,
  AlertCircle,
  FileCheck,
  Database,
} from 'lucide-react';
import {
  getWatchStatus,
  getIngestionJobs,
  getIngestionStats,
} from '@/lib/api';
import { Tooltip, Sparkline } from '@/components';
import IngestionJobCard from './IngestionJobCard';

export default function LiveActivityTab() {
  const { data: watchStatus, isLoading: isLoadingStatus } = useQuery({
    queryKey: ['watchStatus'],
    queryFn: getWatchStatus,
    refetchInterval: 5000,
    staleTime: 0,
  });

  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['ingestionStats'],
    queryFn: getIngestionStats,
    refetchInterval: 10000,
    staleTime: 0,
  });

  const { data: recentJobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ['recentIngestionJobs'],
    queryFn: () => getIngestionJobs({ page_size: 50 }),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const isLoading = isLoadingStatus || isLoadingStats || isLoadingJobs;

  if (isLoading && !watchStatus && !stats && !recentJobs) {
    return (
      <div className="text-center py-12">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">Loading live activity...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold mb-2">Live Activity</h2>
          <p className="text-muted-foreground">
            Real-time monitoring of watch directories and ingestion jobs
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Auto-refreshing
        </div>
      </div>

      {/* Stats Grid - Top Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Watch Status Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 rounded-lg">
              <FolderSearch className="h-5 w-5 text-primary" />
            </div>
            <h3 className="font-semibold">Watch Directories</h3>
          </div>
          {watchStatus ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Total number of configured watch directories">
                  <span className="text-sm text-muted-foreground">Total</span>
                </Tooltip>
                <span className="text-2xl font-bold">{watchStatus.total_configs}</span>
              </div>
              <div className="flex items-center justify-between">
                <Tooltip content="Watch directories currently monitoring for new log files">
                  <span className="text-sm text-muted-foreground">Active</span>
                </Tooltip>
                <span className="text-lg font-semibold text-green-600">
                  {watchStatus.active_count}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <Tooltip content="Watch directories that have been stopped">
                  <span className="text-sm text-muted-foreground">Inactive</span>
                </Tooltip>
                <span className="text-lg font-semibold text-gray-500">
                  {watchStatus.inactive_count}
                </span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Ingestion Stats Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <Database className="h-5 w-5 text-green-600" />
            </div>
            <h3 className="font-semibold">Total Jobs</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Total number of ingestion jobs ever processed">
                  <span className="text-sm text-muted-foreground">All Time</span>
                </Tooltip>
                <span className="text-2xl font-bold">{stats.total_jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Conversations successfully parsed and stored in database">
                  <span className="text-green-600">Success</span>
                </Tooltip>
                <span className="font-semibold">{stats.by_status.success || 0}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Ingestion attempts that encountered errors">
                  <span className="text-destructive">Failed</span>
                </Tooltip>
                <span className="font-semibold">{stats.by_status.failed || 0}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Files skipped because they were already ingested">
                  <span className="text-muted-foreground">Duplicate</span>
                </Tooltip>
                <span className="font-semibold">{stats.by_status.duplicate || 0}</span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Incremental Parsing Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-purple-600" />
            </div>
            <h3 className="font-semibold">Incremental Parsing</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Percentage of jobs using fast incremental parsing (10-106x faster)">
                  <span className="text-sm text-muted-foreground">Usage Rate</span>
                </Tooltip>
                <span className="text-2xl font-bold text-purple-600">
                  {stats.incremental_percentage
                    ? `${stats.incremental_percentage.toFixed(1)}%`
                    : '0%'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Jobs that only parsed new content appended to existing files">
                  <span className="text-muted-foreground">Incremental Jobs</span>
                </Tooltip>
                <span className="font-semibold">{stats.incremental_jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Jobs that parsed entire files from scratch">
                  <span className="text-muted-foreground">Full Parse Jobs</span>
                </Tooltip>
                <span className="font-semibold">{stats.total_jobs - stats.incremental_jobs}</span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Pipeline Performance Grid - Bottom Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Pipeline Performance Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Clock className="h-5 w-5 text-blue-600" />
            </div>
            <h3 className="font-semibold">Pipeline Performance</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Average total time to process one ingestion job">
                  <span className="text-sm text-muted-foreground">Total Avg</span>
                </Tooltip>
                <span className="text-2xl font-bold">
                  {stats.avg_processing_time_ms
                    ? `${stats.avg_processing_time_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Time to parse conversation log into structured data">
                  <span className="text-muted-foreground">Parsing</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.avg_parse_duration_ms
                    ? `${stats.avg_parse_duration_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Time to check if file was already ingested (hash + DB lookup)">
                  <span className="text-muted-foreground">Deduplication</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.avg_deduplication_check_ms
                    ? `${stats.avg_deduplication_check_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Time to insert conversation, messages, and file records into PostgreSQL">
                  <span className="text-muted-foreground">Database Ops</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.avg_database_operations_ms
                    ? `${stats.avg_database_operations_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Time for AI tagging (rule-based + LLM sentiment/intent analysis)">
                  <span className="text-muted-foreground">Tagging</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.avg_tagging_duration_ms
                    ? `${stats.avg_tagging_duration_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Error Breakdown Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <AlertCircle className="h-5 w-5 text-red-600" />
            </div>
            <h3 className="font-semibold">Error Breakdown</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Total number of ingestion jobs that failed with errors">
                  <span className="text-sm text-muted-foreground">Total Failed</span>
                </Tooltip>
                <span className="text-2xl font-bold text-destructive">
                  {stats.by_status.failed || 0}
                </span>
              </div>
              {Object.keys(stats.error_rates_by_stage || {}).length > 0 ? (
                Object.entries(stats.error_rates_by_stage).map(([stage, count]) => (
                  <div key={stage} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground capitalize">{stage}</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground mt-2">
                  {stats.by_status.failed === 0
                    ? 'No errors recorded'
                    : 'Stage-level error tracking coming soon'}
                </div>
              )}
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* LLM Usage Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-orange-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-orange-600" />
            </div>
            <h3 className="font-semibold">LLM Usage</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between">
                <Tooltip content="Total cumulative cost of all OpenAI API calls for tagging">
                  <span className="text-sm text-muted-foreground">Total Cost</span>
                </Tooltip>
                <span className="text-2xl font-bold">
                  {stats.total_llm_cost_usd
                    ? `$${stats.total_llm_cost_usd.toFixed(4)}`
                    : 'N/A'}
                </span>
              </div>
              <div className="space-y-2 pt-2 border-t border-border/50">
                <div className="flex items-center justify-between text-sm">
                  <Tooltip content="Average OpenAI API cost per ingestion job (gpt-4o-mini)">
                    <span className="text-muted-foreground">Avg Cost/Job</span>
                  </Tooltip>
                  <span className="font-semibold">
                    {stats.avg_llm_cost_usd
                      ? `$${stats.avg_llm_cost_usd.toFixed(5)}`
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <Tooltip content="Average total tokens (prompt + completion) per LLM tagging call">
                    <span className="text-muted-foreground">Avg Tokens</span>
                  </Tooltip>
                  <span className="font-semibold">
                    {stats.avg_llm_total_tokens
                      ? Math.round(stats.avg_llm_total_tokens)
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <Tooltip content="Percentage of tagging requests served from cache (reduces cost by 80-90%)">
                    <span className="text-muted-foreground">Cache Hit Rate</span>
                  </Tooltip>
                  <span className="font-semibold">
                    {stats.llm_cache_hit_rate !== null && stats.llm_cache_hit_rate !== undefined
                      ? `${(stats.llm_cache_hit_rate * 100).toFixed(1)}%`
                      : 'N/A'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <Tooltip content="Average time spent on OpenAI API call (excludes cache hits)">
                    <span className="text-muted-foreground">Avg Duration</span>
                  </Tooltip>
                  <span className="font-semibold">
                    {stats.avg_llm_tagging_ms
                      ? `${stats.avg_llm_tagging_ms.toFixed(0)}ms`
                      : 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Health Monitoring Grid - Third Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Recent Activity Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-cyan-500/10 rounded-lg">
              <Activity className="h-5 w-5 text-cyan-600" />
            </div>
            <h3 className="font-semibold">Recent Activity</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Number of ingestion jobs processed in the last hour">
                  <span className="text-sm text-muted-foreground">Last Hour</span>
                </Tooltip>
                <span className="text-2xl font-bold text-cyan-600">
                  {stats.jobs_last_hour}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Number of ingestion jobs processed in the last 24 hours">
                  <span className="text-muted-foreground">Last 24h</span>
                </Tooltip>
                <span className="font-semibold">{stats.jobs_last_24h}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Average number of jobs processed per minute (over last hour)">
                  <span className="text-muted-foreground">Processing Rate</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.processing_rate_per_minute.toFixed(2)} jobs/min
                </span>
              </div>
              {stats.timeseries_24h && stats.timeseries_24h.length > 0 && (
                <div className="pt-2 border-t border-border/50">
                  <div className="text-xs text-muted-foreground mb-1">24h Activity</div>
                  <Sparkline
                    data={stats.timeseries_24h.map((d) => d.job_count)}
                    width={200}
                    height={30}
                    color="#06b6d4"
                  />
                </div>
              )}
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Success Metrics Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <CheckCircle className="h-5 w-5 text-emerald-600" />
            </div>
            <h3 className="font-semibold">Success Metrics</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Percentage of jobs that completed successfully">
                  <span className="text-sm text-muted-foreground">Success Rate</span>
                </Tooltip>
                <span className="text-2xl font-bold text-emerald-600">
                  {stats.success_rate !== null
                    ? `${stats.success_rate.toFixed(1)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Percentage of jobs that failed with errors">
                  <span className="text-muted-foreground">Failure Rate</span>
                </Tooltip>
                <span className="font-semibold text-destructive">
                  {stats.failure_rate !== null
                    ? `${stats.failure_rate.toFixed(1)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="Time elapsed since the last failed ingestion job">
                  <span className="text-muted-foreground">Last Failure</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.time_since_last_failure_minutes !== null
                    ? stats.time_since_last_failure_minutes < 60
                      ? `${Math.floor(stats.time_since_last_failure_minutes)}m ago`
                      : `${Math.floor(stats.time_since_last_failure_minutes / 60)}h ago`
                    : 'Never'}
                </span>
              </div>
              {stats.timeseries_24h && stats.timeseries_24h.length > 0 && (
                <div className="pt-2 border-t border-border/50">
                  <div className="text-xs text-muted-foreground mb-1">24h Success Rate</div>
                  <Sparkline
                    data={stats.timeseries_24h.map((d) =>
                      d.job_count > 0 ? (d.success_count / d.job_count) * 100 : 0
                    )}
                    width={200}
                    height={30}
                    color="#10b981"
                  />
                </div>
              )}
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Performance Health Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-amber-600" />
            </div>
            <h3 className="font-semibold">Performance Health</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <Tooltip content="Median (p50) processing time - half of jobs are faster, half are slower">
                  <span className="text-sm text-muted-foreground">p50 Time</span>
                </Tooltip>
                <span className="text-2xl font-bold text-amber-600">
                  {stats.processing_time_percentiles.p50
                    ? `${stats.processing_time_percentiles.p50.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="90th percentile - 90% of jobs are faster than this">
                  <span className="text-muted-foreground">p90</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.processing_time_percentiles.p90
                    ? `${stats.processing_time_percentiles.p90.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="99th percentile - worst 1% of jobs">
                  <span className="text-muted-foreground">p99</span>
                </Tooltip>
                <span className="font-semibold">
                  {stats.processing_time_percentiles.p99
                    ? `${stats.processing_time_percentiles.p99.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <Tooltip content="How much faster incremental parsing is compared to full parsing">
                  <span className="text-muted-foreground">Incremental Speedup</span>
                </Tooltip>
                <span className="font-semibold text-purple-600">
                  {stats.incremental_speedup
                    ? `${stats.incremental_speedup.toFixed(1)}x`
                    : 'N/A'}
                </span>
              </div>
              {stats.timeseries_24h && stats.timeseries_24h.length > 0 && (
                <div className="pt-2 border-t border-border/50">
                  <div className="text-xs text-muted-foreground mb-1">24h Processing Time</div>
                  <Sparkline
                    data={stats.timeseries_24h.map((d) => d.avg_processing_time_ms || 0)}
                    width={200}
                    height={30}
                    color="#f59e0b"
                  />
                </div>
              )}
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Active Watch Configs */}
      {watchStatus && watchStatus.active_configs.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Active Watch Directories</h3>
          <div className="grid gap-3">
            {watchStatus.active_configs.map((config) => (
              <div
                key={config.id}
                className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <FolderSearch className="h-4 w-4 text-green-600" />
                  <span className="font-medium">{config.directory}</span>
                  {config.enable_tagging && (
                    <span className="ml-auto text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                      AI Tagging
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Jobs Feed */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Recent Ingestion Jobs</h3>
        {recentJobs && recentJobs.length > 0 ? (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {recentJobs.map((job) => (
              <IngestionJobCard key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 bg-card border border-border rounded-lg">
            <FileCheck className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-muted-foreground">No ingestion jobs yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Upload files or configure watch directories to get started
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
