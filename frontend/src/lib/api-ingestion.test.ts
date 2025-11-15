/**
 * Tests for Ingestion Job API client functions.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getIngestionJobs,
  getIngestionJob,
  getIngestionStats,
  getConversationIngestionJobs,
  getWatchConfigIngestionJobs,
  ApiError,
} from './api';
import type {
  IngestionJobResponse,
  IngestionStatsResponse,
  IngestionJobFilters,
} from '@/types/api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('Ingestion Job API', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('getIngestionJobs', () => {
    it('should fetch all jobs without filters', async () => {
      const mockJobs: IngestionJobResponse[] = [
        {
          id: 'job-1',
          conversation_id: 'conv-1',
          source_type: 'upload',
          source_config_id: null,
          file_path: '/path/to/file.jsonl',
          status: 'success',
          started_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:00:01Z',
          processing_time_ms: 1000,
          messages_added: 50,
          incremental: false,
          error_message: null,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJobs,
      });

      const result = await getIngestionJobs();

      expect(mockFetch).toHaveBeenCalledWith('/api/ingestion/jobs', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockJobs);
    });

    it('should fetch jobs with source_type filter', async () => {
      const filters: IngestionJobFilters = {
        source_type: 'watch',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getIngestionJobs(filters);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs?source_type=watch',
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    it('should fetch jobs with status filter', async () => {
      const filters: IngestionJobFilters = {
        status: 'failed',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getIngestionJobs(filters);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs?status=failed',
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    it('should fetch jobs with multiple filters', async () => {
      const filters: IngestionJobFilters = {
        source_type: 'cli',
        status: 'success',
        limit: 100,
        offset: 50,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getIngestionJobs(filters);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs?source_type=cli&status=success&limit=100&offset=50',
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    it('should skip undefined filter values', async () => {
      const filters: IngestionJobFilters = {
        source_type: 'upload',
        status: undefined,
        limit: 50,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getIngestionJobs(filters);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs?source_type=upload&limit=50',
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    it('should throw ApiError on HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Database error',
      });

      await expect(getIngestionJobs()).rejects.toThrow(ApiError);
    });
  });

  describe('getIngestionJob', () => {
    it('should fetch single ingestion job by id', async () => {
      const mockJob: IngestionJobResponse = {
        id: 'job-1',
        conversation_id: 'conv-1',
        source_type: 'watch',
        source_config_id: 'config-1',
        file_path: '/path/to/file.jsonl',
        status: 'success',
        started_at: '2025-01-01T00:00:00Z',
        completed_at: '2025-01-01T00:00:02Z',
        processing_time_ms: 2000,
        messages_added: 120,
        incremental: true,
        error_message: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      });

      const result = await getIngestionJob('job-1');

      expect(mockFetch).toHaveBeenCalledWith('/api/ingestion/jobs/job-1', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockJob);
    });

    it('should fetch failed job with error message', async () => {
      const mockJob: IngestionJobResponse = {
        id: 'job-2',
        conversation_id: 'conv-2',
        source_type: 'upload',
        source_config_id: null,
        file_path: '/path/to/broken.jsonl',
        status: 'failed',
        started_at: '2025-01-01T00:00:00Z',
        completed_at: '2025-01-01T00:00:01Z',
        processing_time_ms: 500,
        messages_added: 0,
        incremental: false,
        error_message: 'Invalid JSON format',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      });

      const result = await getIngestionJob('job-2');

      expect(result.status).toBe('failed');
      expect(result.error_message).toBe('Invalid JSON format');
    });

    it('should throw ApiError for not found job', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Job not found',
      });

      await expect(getIngestionJob('invalid-id')).rejects.toThrow(ApiError);
    });
  });

  describe('getIngestionStats', () => {
    it('should fetch ingestion stats', async () => {
      const mockStats: IngestionStatsResponse = {
        total_jobs: 150,
        by_source_type: {
          upload: 50,
          watch: 80,
          cli: 20,
        },
        by_status: {
          success: 130,
          failed: 15,
          duplicate: 5,
        },
        incremental_jobs: 60,
        incremental_percentage: 40.0,
        avg_processing_time_ms: 1500,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      });

      const result = await getIngestionStats();

      expect(mockFetch).toHaveBeenCalledWith('/api/ingestion/stats', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockStats);
    });

    it('should handle zero jobs', async () => {
      const mockStats: IngestionStatsResponse = {
        total_jobs: 0,
        by_source_type: {},
        by_status: {},
        incremental_jobs: 0,
        incremental_percentage: null,
        avg_processing_time_ms: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      });

      const result = await getIngestionStats();

      expect(result.total_jobs).toBe(0);
      expect(result.incremental_percentage).toBeNull();
      expect(result.avg_processing_time_ms).toBeNull();
    });

    it('should handle stats with all source types', async () => {
      const mockStats: IngestionStatsResponse = {
        total_jobs: 300,
        by_source_type: {
          upload: 100,
          watch: 150,
          cli: 50,
        },
        by_status: {
          success: 280,
          failed: 10,
          duplicate: 10,
        },
        incremental_jobs: 100,
        incremental_percentage: 33.33,
        avg_processing_time_ms: 2000,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      });

      const result = await getIngestionStats();

      expect(result.by_source_type.upload).toBe(100);
      expect(result.by_source_type.watch).toBe(150);
      expect(result.by_source_type.cli).toBe(50);
    });

    it('should throw ApiError on server error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Database error',
      });

      await expect(getIngestionStats()).rejects.toThrow(ApiError);
    });
  });

  describe('getConversationIngestionJobs', () => {
    it('should fetch jobs for a specific conversation', async () => {
      const mockJobs: IngestionJobResponse[] = [
        {
          id: 'job-1',
          conversation_id: 'conv-123',
          source_type: 'upload',
          source_config_id: null,
          file_path: '/path/to/file.jsonl',
          status: 'success',
          started_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:00:01Z',
          processing_time_ms: 1000,
          messages_added: 50,
          incremental: false,
          error_message: null,
        },
        {
          id: 'job-2',
          conversation_id: 'conv-123',
          source_type: 'watch',
          source_config_id: 'config-1',
          file_path: '/path/to/file.jsonl',
          status: 'success',
          started_at: '2025-01-01T01:00:00Z',
          completed_at: '2025-01-01T01:00:00Z',
          processing_time_ms: 200,
          messages_added: 10,
          incremental: true,
          error_message: null,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJobs,
      });

      const result = await getConversationIngestionJobs('conv-123');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs/conversation/conv-123',
        { headers: { 'Content-Type': 'application/json' } }
      );
      expect(result).toEqual(mockJobs);
      expect(result).toHaveLength(2);
      expect(result[0].conversation_id).toBe('conv-123');
      expect(result[1].conversation_id).toBe('conv-123');
    });

    it('should return empty array for conversation with no jobs', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      const result = await getConversationIngestionJobs('conv-no-jobs');

      expect(result).toEqual([]);
    });

    it('should throw ApiError for not found conversation', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Conversation not found',
      });

      await expect(
        getConversationIngestionJobs('invalid-id')
      ).rejects.toThrow(ApiError);
    });
  });

  describe('getWatchConfigIngestionJobs', () => {
    it('should fetch jobs for a specific watch config', async () => {
      const mockJobs: IngestionJobResponse[] = [
        {
          id: 'job-1',
          conversation_id: 'conv-1',
          source_type: 'watch',
          source_config_id: 'config-123',
          file_path: '/watched/dir/file1.jsonl',
          status: 'success',
          started_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:00:01Z',
          processing_time_ms: 1000,
          messages_added: 50,
          incremental: false,
          error_message: null,
        },
        {
          id: 'job-2',
          conversation_id: 'conv-1',
          source_type: 'watch',
          source_config_id: 'config-123',
          file_path: '/watched/dir/file1.jsonl',
          status: 'success',
          started_at: '2025-01-01T01:00:00Z',
          completed_at: '2025-01-01T01:00:00Z',
          processing_time_ms: 100,
          messages_added: 5,
          incremental: true,
          error_message: null,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJobs,
      });

      const result = await getWatchConfigIngestionJobs('config-123');

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs/watch-config/config-123?page=1&page_size=50',
        { headers: { 'Content-Type': 'application/json' } }
      );
      expect(result).toEqual(mockJobs);
      expect(result).toHaveLength(2);
      expect(result[0].source_config_id).toBe('config-123');
      expect(result[1].source_config_id).toBe('config-123');
    });

    it('should support custom pagination', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getWatchConfigIngestionJobs('config-123', 2, 100);

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/ingestion/jobs/watch-config/config-123?page=2&page_size=100',
        { headers: { 'Content-Type': 'application/json' } }
      );
    });

    it('should return empty array for config with no jobs', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      const result = await getWatchConfigIngestionJobs('config-no-jobs');

      expect(result).toEqual([]);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Watch configuration not found',
      });

      await expect(
        getWatchConfigIngestionJobs('invalid-id')
      ).rejects.toThrow(ApiError);
    });
  });

  describe('Error handling edge cases', () => {
    it('should preserve ApiError details when rethrowing', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        text: async () => 'Access denied',
      });

      try {
        await getIngestionJobs();
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(403);
        expect((error as ApiError).statusText).toBe('Forbidden');
      }
    });

    it('should handle network errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network failure'));

      await expect(getIngestionJobs()).rejects.toThrow('Network error');
    });

    it('should handle JSON parsing errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(getIngestionJobs()).rejects.toThrow('Invalid JSON');
    });
  });

  describe('Job status variations', () => {
    it('should handle processing status', async () => {
      const mockJob: IngestionJobResponse = {
        id: 'job-processing',
        conversation_id: 'conv-1',
        source_type: 'upload',
        source_config_id: null,
        file_path: '/path/to/file.jsonl',
        status: 'processing',
        started_at: '2025-01-01T00:00:00Z',
        completed_at: null,
        processing_time_ms: null,
        messages_added: 0,
        incremental: false,
        error_message: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      });

      const result = await getIngestionJob('job-processing');

      expect(result.status).toBe('processing');
      expect(result.completed_at).toBeNull();
      expect(result.processing_time_ms).toBeNull();
    });

    it('should handle duplicate status', async () => {
      const mockJob: IngestionJobResponse = {
        id: 'job-duplicate',
        conversation_id: 'conv-1',
        source_type: 'upload',
        source_config_id: null,
        file_path: '/path/to/duplicate.jsonl',
        status: 'duplicate',
        started_at: '2025-01-01T00:00:00Z',
        completed_at: '2025-01-01T00:00:00Z',
        processing_time_ms: 50,
        messages_added: 0,
        incremental: false,
        error_message: 'File already processed',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      });

      const result = await getIngestionJob('job-duplicate');

      expect(result.status).toBe('duplicate');
      expect(result.messages_added).toBe(0);
      expect(result.error_message).toBe('File already processed');
    });

    it('should handle skipped status', async () => {
      const mockJob: IngestionJobResponse = {
        id: 'job-skipped',
        conversation_id: 'conv-1',
        source_type: 'cli',
        source_config_id: null,
        file_path: '/path/to/skipped.jsonl',
        status: 'skipped',
        started_at: '2025-01-01T00:00:00Z',
        completed_at: '2025-01-01T00:00:00Z',
        processing_time_ms: 10,
        messages_added: 0,
        incremental: false,
        error_message: 'File unchanged',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockJob,
      });

      const result = await getIngestionJob('job-skipped');

      expect(result.status).toBe('skipped');
      expect(result.messages_added).toBe(0);
    });
  });
});
