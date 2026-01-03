/**
 * API client for CatSyphon backend.
 *
 * All requests use /api/* which is proxied to http://localhost:8000 in development.
 */

import type {
  CanonicalNarrativeResponse,
  ConversationDetail,
  ConversationFilters,
  ConversationListResponse,
  DetectionResponse,
  DeveloperResponse,
  HealthReportResponse,
  HealthResponse,
  IngestionJobFilters,
  IngestionJobResponse,
  IngestionStatsResponse,
  InsightsResponse,
  MessageResponse,
  OverviewStats,
  ProjectFileAggregation,
  ProjectInsightsResponse,
  ProjectListItem,
  ProjectSessionsResponse,
  ProjectStats,
  ProjectAnalytics,
  BenchmarkResultResponse,
  BenchmarkStatusResponse,
  ConversationRecapResponse,
  WeeklyDigestResponse,
  RecommendationListResponse,
  RecommendationResponse,
  RecommendationUpdate,
  UploadResponse,
  WatchConfigurationCreate,
  WatchConfigurationResponse,
  WatchConfigurationUpdate,
  WatchStatus,
} from '@/types/api';

// ===== Error Handling =====

export class ApiError extends Error {
  status: number;
  statusText: string;

  constructor(status: number, statusText: string, message?: string) {
    super(message || `API Error: ${status} ${statusText}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
  }
}

// ===== Workspace Header =====

const WORKSPACE_STORAGE_KEY = 'catsyphon_current_workspace_id';
const BENCHMARKS_TOKEN = import.meta.env.VITE_BENCHMARKS_TOKEN as string | undefined;

function getWorkspaceHeaders(): Record<string, string> {
  const workspaceId = localStorage.getItem(WORKSPACE_STORAGE_KEY);
  if (workspaceId) {
    return { 'X-Workspace-Id': workspaceId };
  }
  return {};
}

function getBenchmarkHeaders(): Record<string, string> {
  if (BENCHMARKS_TOKEN) {
    return { 'X-Benchmark-Token': BENCHMARKS_TOKEN };
  }
  return {};
}

// ===== Base Fetch Wrapper =====

async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `/api${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...getWorkspaceHeaders(),
        ...options?.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(
        response.status,
        response.statusText,
        await response.text()
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(`Network error: ${error}`);
  }
}

// ===== Conversation Endpoints =====

export async function getConversations(
  filters?: ConversationFilters
): Promise<ConversationListResponse> {
  const params = new URLSearchParams();

  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });
  }

  const query = params.toString();
  return apiFetch<ConversationListResponse>(
    `/conversations${query ? `?${query}` : ''}`
  );
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/conversations/${id}`);
}

export async function getConversationMessages(
  id: string,
  page = 1,
  pageSize = 50
): Promise<MessageResponse[]> {
  return apiFetch<MessageResponse[]>(
    `/conversations/${id}/messages?page=${page}&page_size=${pageSize}`
  );
}

export async function getCanonicalNarrative(
  conversationId: string,
  canonicalType: 'tagging' | 'insights' | 'export' = 'tagging',
  samplingStrategy: 'semantic' | 'epoch' | 'chronological' = 'chronological'
): Promise<CanonicalNarrativeResponse> {
  const params = new URLSearchParams({
    canonical_type: canonicalType,
    sampling_strategy: samplingStrategy,
  });

  return apiFetch<CanonicalNarrativeResponse>(
    `/conversations/${conversationId}/canonical/narrative?${params.toString()}`
  );
}

export async function tagConversation(
  id: string,
  force = false
): Promise<ConversationDetail> {
  const params = new URLSearchParams();
  if (force) params.append('force', 'true');

  const query = params.toString();
  return apiFetch<ConversationDetail>(
    `/conversations/${id}/tag${query ? `?${query}` : ''}`,
    { method: 'POST' }
  );
}

export async function getConversationInsights(
  id: string,
  forceRegenerate = false
): Promise<InsightsResponse> {
  const params = new URLSearchParams();
  if (forceRegenerate) params.append('force_regenerate', 'true');

  const query = params.toString();
  return apiFetch<InsightsResponse>(
    `/conversations/${id}/insights${query ? `?${query}` : ''}`
  );
}

// ===== Metadata Endpoints =====

export async function getProjects(): Promise<ProjectListItem[]> {
  return apiFetch<ProjectListItem[]>('/projects');
}

export async function getDevelopers(): Promise<DeveloperResponse[]> {
  return apiFetch<DeveloperResponse[]>('/developers');
}

// ===== Stats Endpoints =====

export async function getOverviewStats(
  startDate?: string,
  endDate?: string
): Promise<OverviewStats> {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);

  const query = params.toString();
  return apiFetch<OverviewStats>(`/stats/overview${query ? `?${query}` : ''}`);
}

// ===== Benchmark Endpoints =====

export async function getBenchmarkStatus(): Promise<BenchmarkStatusResponse> {
  return apiFetch<BenchmarkStatusResponse>('/benchmarks/status', {
    headers: getBenchmarkHeaders(),
  });
}

export async function runBenchmarks(): Promise<BenchmarkStatusResponse> {
  return apiFetch<BenchmarkStatusResponse>('/benchmarks/run', {
    method: 'POST',
    headers: getBenchmarkHeaders(),
  });
}

export async function getLatestBenchmarkResults(): Promise<BenchmarkResultResponse> {
  return apiFetch<BenchmarkResultResponse>('/benchmarks/results/latest', {
    headers: getBenchmarkHeaders(),
  });
}

// ===== Recap Endpoints =====

export async function getConversationRecap(
  id: string
): Promise<ConversationRecapResponse> {
  return apiFetch<ConversationRecapResponse>(`/conversations/${id}/recap`);
}

export async function generateConversationRecap(
  id: string,
  force = false
): Promise<ConversationRecapResponse> {
  const params = new URLSearchParams();
  if (force) params.append('force_regenerate', 'true');
  const query = params.toString();
  return apiFetch<ConversationRecapResponse>(
    `/conversations/${id}/recap${query ? `?${query}` : ''}`,
    { method: 'POST' }
  );
}

// ===== Digest Endpoints =====

export async function getWeeklyDigest(
  periodStart?: string,
  periodEnd?: string
): Promise<WeeklyDigestResponse> {
  const params = new URLSearchParams();
  if (periodStart) params.append('period_start', periodStart);
  if (periodEnd) params.append('period_end', periodEnd);
  const query = params.toString();
  return apiFetch<WeeklyDigestResponse>(
    `/digests/weekly${query ? `?${query}` : ''}`
  );
}

export async function generateWeeklyDigest(
  periodStart: string,
  periodEnd: string,
  force = false
): Promise<WeeklyDigestResponse> {
  const params = new URLSearchParams();
  if (force) params.append('force_regenerate', 'true');
  const query = params.toString();
  return apiFetch<WeeklyDigestResponse>(
    `/digests/weekly${query ? `?${query}` : ''}`,
    {
      method: 'POST',
      body: JSON.stringify({ period_start: periodStart, period_end: periodEnd }),
    }
  );
}

// ===== Health Endpoint =====

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

// ===== Upload Endpoint =====

export type UpdateMode = 'skip' | 'replace' | 'append';

export async function uploadConversationLogs(
  files: File[],
  updateMode: UpdateMode = 'skip'
): Promise<UploadResponse> {
  const formData = new FormData();

  // Append all files with the same field name (FastAPI expects list[UploadFile])
  files.forEach((file) => {
    formData.append('files', file);
  });

  // Add update_mode as query parameter
  const params = new URLSearchParams();
  params.append('update_mode', updateMode);

  const url = `/api/upload/?${params.toString()}`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header - browser will set it with boundary for multipart
      headers: getWorkspaceHeaders(),
    });

    if (!response.ok) {
      throw new ApiError(
        response.status,
        response.statusText,
        await response.text()
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(`Network error: ${error}`);
  }
}

export async function uploadSingleConversationLog(
  file: File,
  updateMode: UpdateMode = 'skip'
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('files', file);

  // Add update_mode as query parameter
  const params = new URLSearchParams();
  params.append('update_mode', updateMode);

  const url = `/api/upload/?${params.toString()}`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      headers: getWorkspaceHeaders(),
    });

    if (!response.ok) {
      throw new ApiError(
        response.status,
        response.statusText,
        await response.text()
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new Error(`Network error: ${error}`);
  }
}

// ===== Watch Configuration Endpoints =====

export async function getWatchConfigs(
  activeOnly = false
): Promise<WatchConfigurationResponse[]> {
  const params = new URLSearchParams();
  if (activeOnly) params.append('active_only', 'true');

  const query = params.toString();
  return apiFetch<WatchConfigurationResponse[]>(
    `/watch/configs${query ? `?${query}` : ''}`
  );
}

export async function getWatchConfig(
  id: string
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>(`/watch/configs/${id}`);
}

export interface SuggestedPath {
  path: string;
  name: string;
  description: string;
  project_count: number | null;
}

export interface PathValidationResponse {
  valid: boolean;
  expanded_path: string;
  exists: boolean;
  is_directory: boolean;
  is_readable: boolean;
}

export async function getSuggestedPaths(): Promise<SuggestedPath[]> {
  return apiFetch<SuggestedPath[]>('/watch/suggested-paths');
}

export async function validatePath(path: string): Promise<PathValidationResponse> {
  return apiFetch<PathValidationResponse>('/watch/validate-path', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function createWatchConfig(
  data: WatchConfigurationCreate
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>('/watch/configs', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateWatchConfig(
  id: string,
  data: WatchConfigurationUpdate
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>(`/watch/configs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteWatchConfig(id: string): Promise<void> {
  return apiFetch<void>(`/watch/configs/${id}`, {
    method: 'DELETE',
  });
}

export async function startWatching(
  id: string
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>(`/watch/configs/${id}/start`, {
    method: 'POST',
    body: JSON.stringify({}),  // Explicit empty body to ensure POST method
  });
}

export async function stopWatching(
  id: string
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>(`/watch/configs/${id}/stop`, {
    method: 'POST',
    body: JSON.stringify({}),  // Explicit empty body to ensure POST method
  });
}

export async function getWatchStatus(): Promise<WatchStatus> {
  return apiFetch<WatchStatus>('/watch/status');
}

// ===== Ingestion Job Endpoints =====

export async function getIngestionJobs(
  filters?: IngestionJobFilters
): Promise<IngestionJobResponse[]> {
  const params = new URLSearchParams();

  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });
  }

  const query = params.toString();
  return apiFetch<IngestionJobResponse[]>(
    `/ingestion/jobs${query ? `?${query}` : ''}`
  );
}

export async function getIngestionJob(
  id: string
): Promise<IngestionJobResponse> {
  return apiFetch<IngestionJobResponse>(`/ingestion/jobs/${id}`);
}

export async function getIngestionStats(): Promise<IngestionStatsResponse> {
  return apiFetch<IngestionStatsResponse>('/ingestion/stats');
}

export async function getConversationIngestionJobs(
  conversationId: string
): Promise<IngestionJobResponse[]> {
  return apiFetch<IngestionJobResponse[]>(
    `/ingestion/jobs/conversation/${conversationId}`
  );
}

export async function getWatchConfigIngestionJobs(
  configId: string,
  page = 1,
  pageSize = 50
): Promise<IngestionJobResponse[]> {
  return apiFetch<IngestionJobResponse[]>(
    `/ingestion/jobs/watch-config/${configId}?page=${page}&page_size=${pageSize}`
  );
}

// ===== Project Analytics Endpoints =====

export async function getProjectStats(
  projectId: string,
  dateRange?: '7d' | '30d' | '90d' | 'all'
): Promise<ProjectStats> {
  const params = dateRange ? `?date_range=${dateRange}` : '';
  return apiFetch<ProjectStats>(`/projects/${projectId}/stats${params}`);
}

export async function getProjectAnalytics(
  projectId: string,
  dateRange?: '7d' | '30d' | '90d' | 'all'
): Promise<ProjectAnalytics> {
  const params = dateRange ? `?date_range=${dateRange}` : '';
  return apiFetch<ProjectAnalytics>(`/projects/${projectId}/analytics${params}`);
}

export async function getProjectInsights(
  projectId: string,
  dateRange: '7d' | '30d' | '90d' | 'all' = '30d',
  includeSummary = true,
  forceRegenerate = false
): Promise<ProjectInsightsResponse> {
  const params = new URLSearchParams({
    date_range: dateRange,
    include_summary: String(includeSummary),
    force_regenerate: String(forceRegenerate),
  });
  return apiFetch<ProjectInsightsResponse>(
    `/projects/${projectId}/insights?${params.toString()}`
  );
}

export async function getProjectHealthReport(
  projectId: string,
  dateRange: '7d' | '30d' | '90d' | 'all' = '30d',
  developer?: string
): Promise<HealthReportResponse> {
  const params = new URLSearchParams({ date_range: dateRange });
  if (developer) {
    params.append('developer', developer);
  }
  return apiFetch<HealthReportResponse>(
    `/projects/${projectId}/health-report?${params.toString()}`
  );
}

export interface ProjectSessionFilters {
  developer?: string;
  outcome?: 'success' | 'failed' | 'partial';
  date_from?: string;
  date_to?: string;
  sort_by?: 'last_activity' | 'start_time' | 'message_count';
  order?: 'asc' | 'desc';
}

export async function getProjectSessions(
  projectId: string,
  page = 1,
  pageSize = 20,
  filters?: ProjectSessionFilters
): Promise<ProjectSessionsResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (filters) {
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });
  }

  return apiFetch<ProjectSessionsResponse>(
    `/projects/${projectId}/sessions?${params.toString()}`
  );
}

export async function getProjectFiles(
  projectId: string
): Promise<ProjectFileAggregation[]> {
  return apiFetch<ProjectFileAggregation[]>(`/projects/${projectId}/files`);
}

// ===== Recommendation Endpoints =====

export async function getConversationRecommendations(
  conversationId: string,
  status?: string,
  recommendationType?: string
): Promise<RecommendationListResponse> {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (recommendationType) params.append('recommendation_type', recommendationType);

  const query = params.toString();
  return apiFetch<RecommendationListResponse>(
    `/conversations/${conversationId}/recommendations${query ? `?${query}` : ''}`
  );
}

export async function detectRecommendations(
  conversationId: string,
  forceRegenerate = false
): Promise<DetectionResponse> {
  return apiFetch<DetectionResponse>(
    `/conversations/${conversationId}/recommendations/detect`,
    {
      method: 'POST',
      body: JSON.stringify({ force_regenerate: forceRegenerate }),
    }
  );
}

export async function detectMCPRecommendations(
  conversationId: string,
  forceRegenerate = false
): Promise<DetectionResponse> {
  return apiFetch<DetectionResponse>(
    `/conversations/${conversationId}/recommendations/detect-mcp`,
    {
      method: 'POST',
      body: JSON.stringify({ force_regenerate: forceRegenerate }),
    }
  );
}

export async function updateRecommendation(
  recommendationId: string,
  update: RecommendationUpdate
): Promise<RecommendationResponse> {
  return apiFetch<RecommendationResponse>(
    `/recommendations/${recommendationId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(update),
    }
  );
}
