/**
 * Tests for Watch Configuration API client functions.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getWatchConfigs,
  getWatchConfig,
  createWatchConfig,
  updateWatchConfig,
  deleteWatchConfig,
  startWatching,
  stopWatching,
  getWatchStatus,
  ApiError,
} from './api';
import type {
  WatchConfigurationResponse,
  WatchConfigurationCreate,
  WatchConfigurationUpdate,
  WatchStatus,
} from '@/types/api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('Watch Configuration API', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('getWatchConfigs', () => {
    it('should fetch all watch configs without filters', async () => {
      const mockConfigs: WatchConfigurationResponse[] = [
        {
          id: 'config-1',
          directory: '/path/to/watch',
          project_id: 'proj-1',
          project_name: 'Test Project',
          developer_id: 'dev-1',
          developer_name: 'Test Developer',
          is_active: true,
          enable_tagging: false,
          created_at: '2025-01-01T00:00:00Z',
          last_started_at: '2025-01-01T00:00:00Z',
          last_stopped_at: null,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfigs,
      });

      const result = await getWatchConfigs();

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockConfigs);
    });

    it('should fetch active configs only when activeOnly=true', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      });

      await getWatchConfigs(true);

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs?active_only=true', {
        headers: { 'Content-Type': 'application/json' },
      });
    });

    it('should throw ApiError on HTTP error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Server error',
      });

      await expect(getWatchConfigs()).rejects.toThrow(ApiError);
    });
  });

  describe('getWatchConfig', () => {
    it('should fetch single watch config by id', async () => {
      const mockConfig: WatchConfigurationResponse = {
        id: 'config-1',
        directory: '/path/to/watch',
        project_id: 'proj-1',
        project_name: 'Test Project',
        developer_id: 'dev-1',
        developer_name: 'Test Developer',
        is_active: true,
        enable_tagging: false,
        created_at: '2025-01-01T00:00:00Z',
        last_started_at: '2025-01-01T00:00:00Z',
        last_stopped_at: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig,
      });

      const result = await getWatchConfig('config-1');

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs/config-1', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockConfig);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Configuration not found',
      });

      await expect(getWatchConfig('invalid-id')).rejects.toThrow(ApiError);
    });
  });

  describe('createWatchConfig', () => {
    it('should create watch config with valid data', async () => {
      const createData: WatchConfigurationCreate = {
        directory: '/path/to/watch',
        enable_tagging: false,
      };

      const mockResponse: WatchConfigurationResponse = {
        id: 'config-new',
        directory: '/path/to/watch',
        project_id: 'default-proj',
        project_name: 'Default Project',
        developer_id: 'default-dev',
        developer_name: 'Default Developer',
        is_active: false,
        enable_tagging: false,
        created_at: '2025-01-01T00:00:00Z',
        last_started_at: null,
        last_stopped_at: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createWatchConfig(createData);

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs', {
        method: 'POST',
        body: JSON.stringify(createData),
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should create watch config with tagging enabled', async () => {
      const createData: WatchConfigurationCreate = {
        directory: '/path/to/watch',
        enable_tagging: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 'config-new',
          directory: '/path/to/watch',
          enable_tagging: true,
        }),
      });

      await createWatchConfig(createData);

      const call = mockFetch.mock.calls[0];
      const body = JSON.parse(call[1].body);
      expect(body.enable_tagging).toBe(true);
    });

    it('should throw ApiError on duplicate directory', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        text: async () => 'Directory already being watched',
      });

      await expect(
        createWatchConfig({
          directory: '/existing/path',
          enable_tagging: false,
        })
      ).rejects.toThrow(ApiError);
    });
  });

  describe('updateWatchConfig', () => {
    it('should update watch config', async () => {
      const updateData: WatchConfigurationUpdate = {
        enable_tagging: true,
      };

      const mockResponse: WatchConfigurationResponse = {
        id: 'config-1',
        directory: '/path/to/watch',
        project_id: 'proj-1',
        project_name: 'Test Project',
        developer_id: 'dev-1',
        developer_name: 'Test Developer',
        is_active: false,
        enable_tagging: true,
        created_at: '2025-01-01T00:00:00Z',
        last_started_at: null,
        last_stopped_at: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await updateWatchConfig('config-1', updateData);

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs/config-1', {
        method: 'PUT',
        body: JSON.stringify(updateData),
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockResponse);
      expect(result.enable_tagging).toBe(true);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Configuration not found',
      });

      await expect(
        updateWatchConfig('invalid-id', { enable_tagging: true })
      ).rejects.toThrow(ApiError);
    });
  });

  describe('deleteWatchConfig', () => {
    it('should delete watch config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => undefined,
      });

      await deleteWatchConfig('config-1');

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs/config-1', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });
    });

    it('should throw ApiError when deleting active config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => 'Cannot delete active configuration',
      });

      await expect(deleteWatchConfig('active-config')).rejects.toThrow(ApiError);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Configuration not found',
      });

      await expect(deleteWatchConfig('invalid-id')).rejects.toThrow(ApiError);
    });
  });

  describe('startWatching', () => {
    it('should start watching for a config', async () => {
      const mockResponse: WatchConfigurationResponse = {
        id: 'config-1',
        directory: '/path/to/watch',
        project_id: 'proj-1',
        project_name: 'Test Project',
        developer_id: 'dev-1',
        developer_name: 'Test Developer',
        is_active: true,
        enable_tagging: false,
        created_at: '2025-01-01T00:00:00Z',
        last_started_at: '2025-01-01T10:00:00Z',
        last_stopped_at: null,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await startWatching('config-1');

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs/config-1/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockResponse);
      expect(result.is_active).toBe(true);
      expect(result.last_started_at).toBeTruthy();
    });

    it('should throw ApiError for already active config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => 'Configuration already active',
      });

      await expect(startWatching('already-active')).rejects.toThrow(ApiError);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Configuration not found',
      });

      await expect(startWatching('invalid-id')).rejects.toThrow(ApiError);
    });
  });

  describe('stopWatching', () => {
    it('should stop watching for a config', async () => {
      const mockResponse: WatchConfigurationResponse = {
        id: 'config-1',
        directory: '/path/to/watch',
        project_id: 'proj-1',
        project_name: 'Test Project',
        developer_id: 'dev-1',
        developer_name: 'Test Developer',
        is_active: false,
        enable_tagging: false,
        created_at: '2025-01-01T00:00:00Z',
        last_started_at: '2025-01-01T10:00:00Z',
        last_stopped_at: '2025-01-01T11:00:00Z',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await stopWatching('config-1');

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/configs/config-1/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockResponse);
      expect(result.is_active).toBe(false);
      expect(result.last_stopped_at).toBeTruthy();
    });

    it('should throw ApiError for inactive config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        text: async () => 'Configuration already inactive',
      });

      await expect(stopWatching('already-inactive')).rejects.toThrow(ApiError);
    });

    it('should throw ApiError for not found config', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        text: async () => 'Configuration not found',
      });

      await expect(stopWatching('invalid-id')).rejects.toThrow(ApiError);
    });
  });

  describe('getWatchStatus', () => {
    it('should fetch watch status', async () => {
      const mockStatus: WatchStatus = {
        total_configs: 5,
        active_count: 2,
        inactive_count: 3,
        active_configs: [
          {
            id: 'config-1',
            directory: '/path/one',
            project_id: 'proj-1',
            project_name: 'Project 1',
            developer_id: 'dev-1',
            developer_name: 'Developer 1',
            is_active: true,
            enable_tagging: false,
            created_at: '2025-01-01T00:00:00Z',
            last_started_at: '2025-01-01T10:00:00Z',
            last_stopped_at: null,
          },
          {
            id: 'config-2',
            directory: '/path/two',
            project_id: 'proj-2',
            project_name: 'Project 2',
            developer_id: 'dev-2',
            developer_name: 'Developer 2',
            is_active: true,
            enable_tagging: true,
            created_at: '2025-01-01T00:00:00Z',
            last_started_at: '2025-01-01T11:00:00Z',
            last_stopped_at: null,
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await getWatchStatus();

      expect(mockFetch).toHaveBeenCalledWith('/api/watch/status', {
        headers: { 'Content-Type': 'application/json' },
      });
      expect(result).toEqual(mockStatus);
      expect(result.total_configs).toBe(5);
      expect(result.active_count).toBe(2);
      expect(result.active_configs).toHaveLength(2);
    });

    it('should handle zero configs', async () => {
      const mockStatus: WatchStatus = {
        total_configs: 0,
        active_count: 0,
        inactive_count: 0,
        active_configs: [],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStatus,
      });

      const result = await getWatchStatus();

      expect(result.total_configs).toBe(0);
      expect(result.active_configs).toEqual([]);
    });

    it('should throw ApiError on server error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => 'Database error',
      });

      await expect(getWatchStatus()).rejects.toThrow(ApiError);
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
        await getWatchConfigs();
        expect.fail('Should have thrown');
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).status).toBe(403);
        expect((error as ApiError).statusText).toBe('Forbidden');
      }
    });

    it('should handle network errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network failure'));

      await expect(getWatchConfigs()).rejects.toThrow('Network error');
    });

    it('should handle JSON parsing errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      await expect(getWatchConfigs()).rejects.toThrow('Invalid JSON');
    });
  });
});
