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
  MessageResponse,
  OverviewStats,
  ProjectResponse,
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

// ===== Metadata Endpoints =====

export async function getProjects(): Promise<ProjectResponse[]> {
  return apiFetch<ProjectResponse[]>('/projects');
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
