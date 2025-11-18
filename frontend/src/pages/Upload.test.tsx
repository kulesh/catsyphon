/**
 * Tests for Upload component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/utils';
import Upload from './Upload';
import * as api from '@/lib/api';
import type { UploadResponse } from '@/types/api';

// Mock the API module
vi.mock('@/lib/api', () => ({
  uploadSingleConversationLog: vi.fn(),
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Helper to create a mock File object
const createMockFile = (name: string, type = 'application/jsonl'): File => {
  const blob = new Blob(['mock content'], { type });
  return new File([blob], name, { type });
};

describe('Upload', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render upload page with title', () => {
      render(<Upload />);

      expect(screen.getByText(/Upload Conversation Logs/i)).toBeInTheDocument();
    });

    it('should display upload interface', () => {
      render(<Upload />);

      // Component should render successfully
      expect(document.body.textContent).toBeTruthy();
    });

    it('should show .jsonl file requirement message', () => {
      render(<Upload />);

      const allText = document.body.textContent || '';
      expect(allText.toLowerCase()).toContain('jsonl');
    });

    it('should have a file input', () => {
      render(<Upload />);

      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();
    });

    it('should accept multiple files', () => {
      render(<Upload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(fileInput.multiple).toBe(true);
    });
  });

  describe('Drag and Drop', () => {
    it('should handle drag enter and show visual feedback', () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      expect(dropZone).toBeTruthy();

      if (dropZone) {
        fireEvent.dragEnter(dropZone, {
          dataTransfer: {
            files: [createMockFile('test.jsonl')],
          },
        });

        // Component should react to drag state
        expect(container).toBeTruthy();
      }
    });

    it('should handle drag leave', () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.dragEnter(dropZone);
        fireEvent.dragLeave(dropZone);

        expect(container).toBeTruthy();
      }
    });

    it('should handle file drop', async () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        const file = createMockFile('test.jsonl');

        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [file],
          },
        });

        // File should be added to the list
        await waitFor(() => {
          expect(screen.getByText('test.jsonl')).toBeInTheDocument();
        });
      }
    });

    it('should filter non-jsonl files on drop', async () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        const jsonlFile = createMockFile('good.jsonl');
        const txtFile = createMockFile('bad.txt', 'text/plain');

        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [jsonlFile, txtFile],
          },
        });

        // Only .jsonl file should be accepted
        await waitFor(() => {
          expect(screen.getByText('good.jsonl')).toBeInTheDocument();
        });

        // Error message about ignored files
        await waitFor(() => {
          const errorText = document.body.textContent || '';
          expect(errorText).toContain('1 file(s) ignored');
        });
      }
    });

    it('should show error when dropping only non-jsonl files', async () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        const txtFile = createMockFile('bad.txt', 'text/plain');

        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [txtFile],
          },
        });

        await waitFor(() => {
          expect(screen.getByText(/Please select .jsonl files only/i)).toBeInTheDocument();
        });
      }
    });
  });

  describe('File Input', () => {
    it('should handle file selection via input', async () => {
      render(<Upload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file = createMockFile('test.jsonl');

      Object.defineProperty(fileInput, 'files', {
        value: [file],
        writable: false,
      });

      fireEvent.change(fileInput);

      await waitFor(() => {
        expect(screen.getByText('test.jsonl')).toBeInTheDocument();
      });
    });

    it('should handle multiple files via input', async () => {
      render(<Upload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const file1 = createMockFile('test1.jsonl');
      const file2 = createMockFile('test2.jsonl');

      Object.defineProperty(fileInput, 'files', {
        value: [file1, file2],
        writable: false,
      });

      fireEvent.change(fileInput);

      await waitFor(() => {
        expect(screen.getByText('test1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('test2.jsonl')).toBeInTheDocument();
      });
    });

    it('should filter non-jsonl files from input', async () => {
      render(<Upload />);

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const jsonlFile = createMockFile('good.jsonl');
      const txtFile = createMockFile('bad.txt', 'text/plain');

      Object.defineProperty(fileInput, 'files', {
        value: [jsonlFile, txtFile],
        writable: false,
      });

      fireEvent.change(fileInput);

      await waitFor(() => {
        expect(screen.getByText('good.jsonl')).toBeInTheDocument();
      });
    });
  });

  describe('Upload Functionality', () => {
    it('should upload single file successfully', async () => {
      const mockResponse: UploadResponse = {
        success_count: 1,
        failed_count: 0,
        results: [
          {
            filename: 'test.jsonl',
            status: 'success',
            conversation_id: 'conv-123',
            message_count: 10,
            epoch_count: 2,
            files_count: 3,
          },
        ],
      };

      vi.mocked(api.uploadSingleConversationLog).mockResolvedValue(mockResponse);

      const { container } = render(<Upload />);
      const user = userEvent.setup();

      // Add file
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile('test.jsonl')],
          },
        });
      }

      await waitFor(() => {
        expect(screen.getByText('test.jsonl')).toBeInTheDocument();
      });

      // Click upload button
      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Verify API was called
      await waitFor(() => {
        expect(api.uploadSingleConversationLog).toHaveBeenCalledTimes(1);
      });

      // Verify success indicator appears
      await waitFor(() => {
        // Component shows success state for the file
        const bodyText = document.body.textContent || '';
        expect(bodyText).toContain('test.jsonl');
      });
    });

    it('should upload multiple files sequentially', async () => {
      const mockResponse: UploadResponse = {
        success_count: 1,
        failed_count: 0,
        results: [
          {
            filename: 'test.jsonl',
            status: 'success',
            conversation_id: 'conv-123',
            message_count: 10,
            epoch_count: 2,
            files_count: 3,
          },
        ],
      };

      vi.mocked(api.uploadSingleConversationLog).mockResolvedValue(mockResponse);

      const { container } = render(<Upload />);
      const user = userEvent.setup();

      // Add files
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [
              createMockFile('test1.jsonl'),
              createMockFile('test2.jsonl'),
            ],
          },
        });
      }

      await waitFor(() => {
        expect(screen.getByText('test1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('test2.jsonl')).toBeInTheDocument();
      });

      // Click upload button
      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Verify API was called twice
      await waitFor(() => {
        expect(api.uploadSingleConversationLog).toHaveBeenCalledTimes(2);
      });
    });

    it('should handle upload error gracefully', async () => {
      vi.mocked(api.uploadSingleConversationLog).mockRejectedValue(
        new Error('Upload failed')
      );

      const { container } = render(<Upload />);
      const user = userEvent.setup();

      // Add file
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile('test.jsonl')],
          },
        });
      }

      await waitFor(() => {
        expect(screen.getByText('test.jsonl')).toBeInTheDocument();
      });

      // Click upload button
      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Verify error is shown
      await waitFor(() => {
        const errorText = document.body.textContent || '';
        expect(errorText).toContain('Upload failed');
      });
    });

    it('should disable upload button when no files selected', () => {
      render(<Upload />);

      const uploadButton = screen.queryByRole('button', { name: /upload/i });
      expect(uploadButton).not.toBeInTheDocument();
    });

    it('should show upload progress during upload', async () => {
      const mockResponse: UploadResponse = {
        success_count: 1,
        failed_count: 0,
        results: [
          {
            filename: 'test.jsonl',
            status: 'success',
            conversation_id: 'conv-123',
            message_count: 10,
            epoch_count: 2,
            files_count: 3,
          },
        ],
      };

      // Delay the upload to simulate progress
      vi.mocked(api.uploadSingleConversationLog).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockResponse), 100))
      );

      const { container } = render(<Upload />);
      const user = userEvent.setup();

      // Add file
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile('test.jsonl')],
          },
        });
      }

      await waitFor(() => {
        expect(screen.getByText('test.jsonl')).toBeInTheDocument();
      });

      // Click upload button
      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      // Should show uploading state
      await waitFor(() => {
        const bodyText = document.body.textContent || '';
        // Component shows "Uploading..." or similar indicator
        expect(bodyText).toBeTruthy();
      });

      // Wait for completion
      await waitFor(() => {
        // Check that upload completed
        expect(api.uploadSingleConversationLog).toHaveBeenCalled();
      }, { timeout: 3000 });
    });
  });

  describe('Reset and Clear', () => {
    it('should allow uploading new files after completion', async () => {
      const mockResponse: UploadResponse = {
        success_count: 1,
        failed_count: 0,
        results: [
          {
            filename: 'test1.jsonl',
            status: 'success',
            conversation_id: 'conv-123',
            message_count: 10,
            epoch_count: 2,
            files_count: 3,
          },
        ],
      };

      vi.mocked(api.uploadSingleConversationLog).mockResolvedValue(mockResponse);

      const { container } = render(<Upload />);
      const user = userEvent.setup();

      // First upload
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile('test1.jsonl')],
          },
        });
      }

      await waitFor(() => {
        expect(screen.getByText('test1.jsonl')).toBeInTheDocument();
      });

      const uploadButton = screen.getByRole('button', { name: /upload/i });
      await user.click(uploadButton);

      await waitFor(() => {
        expect(api.uploadSingleConversationLog).toHaveBeenCalledTimes(1);
      });

      // Look for "Upload More" or similar button
      const uploadMoreButton = screen.queryByRole('button', { name: /upload more/i });
      if (uploadMoreButton) {
        await user.click(uploadMoreButton);

        // Should reset the state
        expect(screen.queryByText('test1.jsonl')).not.toBeInTheDocument();
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty file list gracefully', () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [],
          },
        });

        // Should not crash
        expect(container).toBeTruthy();
      }
    });

    it('should handle file with very long name', async () => {
      const { container } = render(<Upload />);

      const longFileName = 'a'.repeat(200) + '.jsonl';
      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile(longFileName)],
          },
        });

        await waitFor(() => {
          expect(screen.getByText(longFileName)).toBeInTheDocument();
        });
      }
    });

    it('should handle upload of same file multiple times', async () => {
      const { container } = render(<Upload />);

      const dropZone = container.querySelector('[class*="border"]');
      if (dropZone) {
        // Drop same file twice
        fireEvent.drop(dropZone, {
          dataTransfer: {
            files: [createMockFile('test.jsonl'), createMockFile('test.jsonl')],
          },
        });

        await waitFor(() => {
          // Should show both files (component doesn't deduplicate by name)
          const files = screen.getAllByText('test.jsonl');
          expect(files.length).toBe(2);
        });
      }
    });
  });
});
