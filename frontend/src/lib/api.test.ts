/**
 * Tests for API client.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  ApiError,
  getConversations,
  getConversation,
  getConversationMessages,
  getProjects,
  getDevelopers,
  getOverviewStats,
  getHealth,
  uploadConversationLogs,
  uploadSingleConversationLog,
} from './api';
import type {
  ConversationListResponse,
  ConversationDetail,
  MessageResponse,
  ProjectResponse,
  DeveloperResponse,
  OverviewStats,
  HealthResponse,
  UploadResponse,
} from '@/types/api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage for workspace header
const TEST_WORKSPACE_ID = 'test-workspace-123';
const localStorageMock = {
  getItem: vi.fn((key: string) => {
    if (key === 'catsyphon_current_workspace_id') {
      return TEST_WORKSPACE_ID;
    }
    return null;
  }),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn(),
};
Object.defineProperty(global, 'localStorage', { value: localStorageMock });

// Expected headers with workspace
const expectedHeaders = {
  'Content-Type': 'application/json',
  'X-Workspace-Id': TEST_WORKSPACE_ID,
};

describe('ApiError', () => {
  it('should create error with status and statusText', () => {
    const error = new ApiError(404, 'Not Found');

    expect(error).toBeInstanceOf(Error);
    expect(error.name).toBe('ApiError');
    expect(error.status).toBe(404);
    expect(error.statusText).toBe('Not Found');
    expect(error.message).toBe('API Error: 404 Not Found');
  });

  it('should use custom message if provided', () => {
    const error = new ApiError(500, 'Internal Server Error', 'Custom error message');

    expect(error.message).toBe('Custom error message');
    expect(error.status).toBe(500);
    expect(error.statusText).toBe('Internal Server Error');
  });
});

describe('getConversations', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch conversations without filters', async () => {
    const mockResponse: ConversationListResponse = {
      conversations: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await getConversations();

    expect(mockFetch).toHaveBeenCalledWith('/api/conversations', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockResponse);
  });

  it('should fetch conversations with filters', async () => {
    const mockResponse: ConversationListResponse = {
      conversations: [],
      total: 5,
      page: 1,
      page_size: 10,
      pages: 1,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    await getConversations({
      project_id: 'proj-123',
      developer_id: 'dev-456',
      page: 1,
      page_size: 10,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/conversations?project_id=proj-123&developer_id=dev-456&page=1&page_size=10',
      { headers: expectedHeaders }
    );
  });

  it('should skip undefined and null filter values', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ conversations: [], total: 0, page: 1, page_size: 20, pages: 0 }),
    });

    await getConversations({
      project_id: 'proj-123',
      developer_id: undefined,
      agent_type: null as any,
      page: 1,
    });

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/conversations?project_id=proj-123&page=1',
      { headers: expectedHeaders }
    );
  });

  it('should throw ApiError on HTTP error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Server error',
    });

    try {
      await getConversations();
      expect.fail('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).message).toBe('Server error');
    }
  });

  it('should throw network error on fetch failure', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network failure'));

    await expect(getConversations()).rejects.toThrow('Network error');
  });
});

describe('getConversation', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch single conversation by id', async () => {
    const mockConversation: ConversationDetail = {
      id: 'conv-123',
      project_id: 'proj-123',
      project_name: 'Test Project',
      developer_id: 'dev-123',
      developer_name: 'Test Developer',
      agent_type: 'claude-code',
      start_time: '2025-01-12T10:00:00Z',
      end_time: '2025-01-12T10:30:00Z',
      duration_seconds: 1800,
      status: 'completed',
      success: true,
      message_count: 10,
      epoch_count: 3,
      files_count: 5,
      intent: 'bug_fix',
      outcome: 'success',
      sentiment: 'positive',
      has_errors: false,
      tools_used: ['read', 'edit'],
      patterns: ['debugging'],
      features: [],
      problems: [],
      iterations: 1,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockConversation,
    });

    const result = await getConversation('conv-123');

    expect(mockFetch).toHaveBeenCalledWith('/api/conversations/conv-123', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockConversation);
  });

  it('should throw ApiError for not found conversation', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => 'Conversation not found',
    });

    await expect(getConversation('invalid-id')).rejects.toThrow(ApiError);
  });
});

describe('getConversationMessages', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch messages with default pagination', async () => {
    const mockMessages: MessageResponse[] = [
      {
        id: 'msg-1',
        conversation_id: 'conv-123',
        role: 'user',
        content: 'Hello',
        timestamp: '2025-01-12T10:00:00Z',
        sequence: 1,
      },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockMessages,
    });

    const result = await getConversationMessages('conv-123');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/conversations/conv-123/messages?page=1&page_size=50',
      { headers: expectedHeaders }
    );
    expect(result).toEqual(mockMessages);
  });

  it('should fetch messages with custom pagination', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    await getConversationMessages('conv-123', 2, 100);

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/conversations/conv-123/messages?page=2&page_size=100',
      { headers: expectedHeaders }
    );
  });
});

describe('getProjects', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch all projects', async () => {
    const mockProjects: ProjectResponse[] = [
      { id: 'proj-1', name: 'Project 1', conversation_count: 5 },
      { id: 'proj-2', name: 'Project 2', conversation_count: 10 },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockProjects,
    });

    const result = await getProjects();

    expect(mockFetch).toHaveBeenCalledWith('/api/projects', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockProjects);
  });
});

describe('getDevelopers', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch all developers', async () => {
    const mockDevelopers: DeveloperResponse[] = [
      { id: 'dev-1', name: 'Developer 1', conversation_count: 15 },
      { id: 'dev-2', name: 'Developer 2', conversation_count: 8 },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockDevelopers,
    });

    const result = await getDevelopers();

    expect(mockFetch).toHaveBeenCalledWith('/api/developers', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockDevelopers);
  });
});

describe('getOverviewStats', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch overview stats without date filters', async () => {
    const mockStats: OverviewStats = {
      total_conversations: 100,
      total_developers: 10,
      total_projects: 5,
      avg_conversation_duration: 1200,
      success_rate: 0.85,
      total_messages: 5000,
      avg_messages_per_conversation: 50,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStats,
    });

    const result = await getOverviewStats();

    expect(mockFetch).toHaveBeenCalledWith('/api/stats/overview', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockStats);
  });

  it('should fetch overview stats with date filters', async () => {
    const mockStats: OverviewStats = {
      total_conversations: 50,
      total_developers: 5,
      total_projects: 3,
      avg_conversation_duration: 1000,
      success_rate: 0.9,
      total_messages: 2500,
      avg_messages_per_conversation: 50,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockStats,
    });

    const result = await getOverviewStats('2025-01-01', '2025-01-31');

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/stats/overview?start_date=2025-01-01&end_date=2025-01-31',
      { headers: expectedHeaders }
    );
    expect(result).toEqual(mockStats);
  });

  it('should handle only start date', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_conversations: 0 }),
    });

    await getOverviewStats('2025-01-01');

    expect(mockFetch).toHaveBeenCalledWith('/api/stats/overview?start_date=2025-01-01', {
      headers: expectedHeaders,
    });
  });

  it('should handle only end date', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total_conversations: 0 }),
    });

    await getOverviewStats(undefined, '2025-01-31');

    expect(mockFetch).toHaveBeenCalledWith('/api/stats/overview?end_date=2025-01-31', {
      headers: expectedHeaders,
    });
  });
});

describe('getHealth', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch health status', async () => {
    const mockHealth: HealthResponse = {
      status: 'healthy',
      database: 'healthy',
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockHealth,
    });

    const result = await getHealth();

    expect(mockFetch).toHaveBeenCalledWith('/api/health', {
      headers: expectedHeaders,
    });
    expect(result).toEqual(mockHealth);
  });
});

describe('uploadConversationLogs', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should upload multiple files', async () => {
    const mockUploadResponse: UploadResponse = {
      success: true,
      conversations_created: 2,
      files_processed: 2,
      files_skipped: 0,
      errors: [],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUploadResponse,
    });

    const file1 = new File(['content1'], 'log1.jsonl', { type: 'application/jsonl' });
    const file2 = new File(['content2'], 'log2.jsonl', { type: 'application/jsonl' });

    const result = await uploadConversationLogs([file1, file2]);

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/upload/?update_mode=skip',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      })
    );

    // Verify FormData contains both files
    const call = mockFetch.mock.calls[0];
    const formData = call[1].body as FormData;
    expect(formData.getAll('files')).toHaveLength(2);

    expect(result).toEqual(mockUploadResponse);
  });

  it('should handle upload errors', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      text: async () => 'Invalid file format',
    });

    const file = new File(['content'], 'invalid.txt', { type: 'text/plain' });

    await expect(uploadConversationLogs([file])).rejects.toThrow(ApiError);
  });

  it('should handle network errors during upload', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network failure'));

    const file = new File(['content'], 'log.jsonl', { type: 'application/jsonl' });

    await expect(uploadConversationLogs([file])).rejects.toThrow('Network error');
  });
});

describe('uploadSingleConversationLog', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should upload single file', async () => {
    const mockUploadResponse: UploadResponse = {
      success: true,
      conversations_created: 1,
      files_processed: 1,
      files_skipped: 0,
      errors: [],
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUploadResponse,
    });

    const file = new File(['content'], 'log.jsonl', { type: 'application/jsonl' });

    const result = await uploadSingleConversationLog(file);

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/upload/?update_mode=skip',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      })
    );

    // Verify FormData contains single file
    const call = mockFetch.mock.calls[0];
    const formData = call[1].body as FormData;
    expect(formData.getAll('files')).toHaveLength(1);

    expect(result).toEqual(mockUploadResponse);
  });

  it('should throw ApiError on upload failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Upload failed',
    });

    const file = new File(['content'], 'log.jsonl', { type: 'application/jsonl' });

    await expect(uploadSingleConversationLog(file)).rejects.toThrow(ApiError);
  });
});

describe('Error handling edge cases', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should preserve ApiError when rethrowing', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      text: async () => 'Access denied',
    });

    try {
      await getConversations();
      expect.fail('Should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(403);
      expect((error as ApiError).statusText).toBe('Forbidden');
    }
  });

  it('should handle JSON parsing errors gracefully', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => {
        throw new Error('Invalid JSON');
      },
    });

    await expect(getConversations()).rejects.toThrow('Invalid JSON');
  });
});
