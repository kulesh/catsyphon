/**
 * Tests for utility functions.
 */

import { describe, it, expect } from 'vitest';
import { cn, groupFilesByPath } from './utils';
import type { FileTouchedResponse } from '@/types/api';

describe('cn', () => {
  it('merges class names correctly', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('handles conditional classes', () => {
    const condition = false;
    expect(cn('foo', condition && 'bar', 'baz')).toBe('foo baz');
  });

  it('handles tailwind merge conflicts', () => {
    // twMerge should resolve conflicting classes
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });

  it('handles empty input', () => {
    expect(cn()).toBe('');
  });

  it('handles undefined and null values', () => {
    expect(cn('foo', undefined, null, 'bar')).toBe('foo bar');
  });
});

describe('groupFilesByPath', () => {
  it('groups files by path', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 2,
        lines_deleted: 1,
        lines_modified: 1,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(1);
    expect(result[0].file_path).toBe('src/app.ts');
    expect(result[0].total_operations).toBe(2);
    expect(result[0].total_lines_added).toBe(12);
    expect(result[0].total_lines_deleted).toBe(6);
    expect(result[0].total_lines_modified).toBe(4);
  });

  it('groups by change type within file', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'read',
        lines_added: 0,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(1);
    expect(result[0].operations).toHaveProperty('edit');
    expect(result[0].operations).toHaveProperty('read');
    expect(result[0].operations.edit.count).toBe(1);
    expect(result[0].operations.read.count).toBe(1);
  });

  it('handles null change_type by defaulting to read', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: null,
        lines_added: 0,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(1);
    expect(result[0].operations).toHaveProperty('read');
    expect(result[0].operations.read.count).toBe(1);
  });

  it('separates different file paths', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'src/utils.ts',
        change_type: 'edit',
        lines_added: 2,
        lines_deleted: 1,
        lines_modified: 1,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(2);
    expect(result[0].file_path).toBe('src/app.ts');
    expect(result[1].file_path).toBe('src/utils.ts');
  });

  it('sorts results by file path alphabetically', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'z/last.ts',
        change_type: 'edit',
        lines_added: 1,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'a/first.ts',
        change_type: 'edit',
        lines_added: 1,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result[0].file_path).toBe('a/first.ts');
    expect(result[1].file_path).toBe('z/last.ts');
  });

  it('accumulates statistics correctly for multiple operations', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 5,
        lines_deleted: 2,
        lines_modified: 1,
        extra_data: {},
      },
      {
        id: '3',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'read',
        lines_added: 0,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(1);
    expect(result[0].total_operations).toBe(3);
    expect(result[0].total_lines_added).toBe(15);
    expect(result[0].total_lines_deleted).toBe(7);
    expect(result[0].total_lines_modified).toBe(4);
    expect(result[0].operations.edit.count).toBe(2);
    expect(result[0].operations.edit.total_lines_added).toBe(15);
    expect(result[0].operations.read.count).toBe(1);
  });

  it('preserves modification details', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result[0].operations.edit.modifications).toHaveLength(1);
    expect(result[0].operations.edit.modifications[0]).toEqual(files[0]);
  });

  it('handles empty array', () => {
    const result = groupFilesByPath([]);

    expect(result).toEqual([]);
  });

  it('handles mixed change types for same file', () => {
    const files: FileTouchedResponse[] = [
      {
        id: '1',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'create',
        lines_added: 100,
        lines_deleted: 0,
        lines_modified: 0,
        extra_data: {},
      },
      {
        id: '2',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'edit',
        lines_added: 10,
        lines_deleted: 5,
        lines_modified: 3,
        extra_data: {},
      },
      {
        id: '3',
        conversation_id: 'conv-1',
        file_path: 'src/app.ts',
        change_type: 'delete',
        lines_added: 0,
        lines_deleted: 110,
        lines_modified: 0,
        extra_data: {},
      },
    ];

    const result = groupFilesByPath(files);

    expect(result).toHaveLength(1);
    expect(result[0].operations).toHaveProperty('create');
    expect(result[0].operations).toHaveProperty('edit');
    expect(result[0].operations).toHaveProperty('delete');
    expect(result[0].total_operations).toBe(3);
    expect(result[0].total_lines_added).toBe(110);
    expect(result[0].total_lines_deleted).toBe(115);
  });
});
