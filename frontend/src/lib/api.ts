/**
 * API client for CatSyphon backend.
 *
 * All requests use /api/* which is proxied to http://localhost:8000 in development.
 */

import type {
  ConversationDetail,
  ConversationFilters,
  ConversationListResponse,
  DeveloperResponse,
  HealthResponse,
  IngestionJobFilters,
  IngestionJobResponse,
  IngestionStatsResponse,
  MessageResponse,
  OverviewStats,
  ProjectFileAggregation,
  ProjectListItem,
  ProjectResponse,
  ProjectSession,
  ProjectStats,
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
  });
}

export async function stopWatching(
  id: string
): Promise<WatchConfigurationResponse> {
  return apiFetch<WatchConfigurationResponse>(`/watch/configs/${id}/stop`, {
    method: 'POST',
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

export async function getProjectStats(projectId: string): Promise<ProjectStats> {
  return apiFetch<ProjectStats>(`/projects/${projectId}/stats`);
}

export async function getProjectSessions(
  projectId: string,
  page = 1,
  pageSize = 20
): Promise<ProjectSession[]> {
  return apiFetch<ProjectSession[]>(
    `/projects/${projectId}/sessions?page=${page}&page_size=${pageSize}`
  );
}

export async function getProjectFiles(
  projectId: string
): Promise<ProjectFileAggregation[]> {
  return apiFetch<ProjectFileAggregation[]>(`/projects/${projectId}/files`);
}
