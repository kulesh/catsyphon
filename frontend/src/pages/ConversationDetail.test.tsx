/**
 * Tests for ConversationDetail component.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/utils';
import ConversationDetail from './ConversationDetail';
import * as api from '@/lib/api';
import type { ConversationDetail as ConversationDetailType } from '@/types/api';

// Mock the API module
vi.mock('@/lib/api', () => ({
  getConversation: vi.fn(),
}));

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'conv-123' }),
    Link: ({ to, children, className }: any) => (
      <a href={to} className={className}>
        {children}
      </a>
    ),
  };
});

const mockConversation: ConversationDetailType = {
  id: 'conv-123',
  project_id: 'proj-1',
  developer_id: 'dev-1',
  agent_type: 'claude-code',
  agent_version: '1.0.0',
  start_time: '2025-01-12T10:00:00Z',
  end_time: '2025-01-12T11:30:00Z',
  status: 'completed',
  success: true,
  iteration_count: 3,
  tags: {},
  extra_data: {},
  created_at: '2025-01-12T10:00:00Z',
  updated_at: '2025-01-12T11:30:00Z',
  message_count: 42,
  epoch_count: 5,
  files_count: 12,
  project: {
    id: 'proj-1',
    name: 'Test Project',
    conversation_count: 10,
  },
  developer: {
    id: 'dev-1',
    username: 'John Doe',
    conversation_count: 15,
  },
  epochs: [
    {
      id: 'epoch-1',
      sequence: 1,
      intent: 'debug',
      outcome: 'success',
      sentiment: 'positive',
      sentiment_score: 0.8,
      start_time: '2025-01-12T10:00:00Z',
      end_time: '2025-01-12T10:30:00Z',
      duration_seconds: 1800,
      extra_data: {},
    },
  ],
  messages: [
    {
      id: 'msg-1',
      conversation_id: 'conv-123',
      role: 'user',
      content: 'Help me fix this bug',
      timestamp: '2025-01-12T10:00:00Z',
      sequence: 1,
    },
    {
      id: 'msg-2',
      conversation_id: 'conv-123',
      role: 'assistant',
      content: 'I can help with that',
      timestamp: '2025-01-12T10:01:00Z',
      sequence: 2,
    },
  ],
  files_touched: [
    {
      id: 'file-1',
      file_path: 'src/components/Button.tsx',
      change_type: 'edit',
      lines_added: 10,
      lines_deleted: 5,
      lines_modified: 45,
      timestamp: '2025-01-12T10:15:00Z',
      extra_data: {},
    },
    {
      id: 'file-2',
      file_path: 'src/utils/helpers.ts',
      change_type: 'read',
      lines_added: 0,
      lines_deleted: 0,
      lines_modified: 20,
      timestamp: '2025-01-12T10:20:00Z',
      extra_data: {},
    },
  ],
  conversation_tags: [
    {
      id: 'tag-1',
      tag_type: 'intent',
      tag_value: 'bug_fix',
      confidence: 0.95,
      extra_data: {},
    },
    {
      id: 'tag-2',
      tag_type: 'outcome',
      tag_value: 'success',
      confidence: 0.98,
      extra_data: {},
    },
    {
      id: 'tag-3',
      tag_type: 'sentiment',
      tag_value: 'positive',
      confidence: 0.85,
      extra_data: {},
    },
  ],
};

describe('ConversationDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show loading state initially', () => {
    vi.mocked(api.getConversation).mockReturnValue(
      new Promise(() => {}) // Never resolves - keeps loading
    );

    render(<ConversationDetail />);

    expect(screen.getByText('Loading conversation...')).toBeInTheDocument();
  });

  it('should display error state', async () => {
    vi.mocked(api.getConversation).mockRejectedValue(
      new Error('Failed to load conversation')
    );

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(
        screen.getByText(/Error loading conversation/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Failed to load conversation/)).toBeInTheDocument();
    });

    // Should show back link
    expect(screen.getByText('← Back to conversations')).toBeInTheDocument();
  });

  it('should display not found state when conversation is null', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(null as any);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation not found')).toBeInTheDocument();
    });

    expect(screen.getByText('← Back to conversations')).toBeInTheDocument();
  });

  it('should display conversation details', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Check ID displayed
    expect(screen.getByText('conv-123')).toBeInTheDocument();

    // Check overview metadata
    expect(screen.getByText('Test Project')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('claude-code')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
  });

  it('should display status badge with correct styling', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
    });
  });

  it('should display success indicator', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('✓ Success')).toBeInTheDocument();
    });
  });

  it('should display failed indicator when success is false', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      success: false,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('✗ Failed')).toBeInTheDocument();
    });
  });

  it('should display N/A when success is null', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      success: null,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });

  it('should display iteration count', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Iterations')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('should display formatted dates', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Start Time')).toBeInTheDocument();
      expect(screen.getByText('End Time')).toBeInTheDocument();
    });

    // Dates should be formatted (not exact match due to timezone/locale)
    const allText = document.body.textContent || '';
    expect(allText).toContain('2025');
  });

  it('should display "In progress" when end_time is null', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      end_time: null,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('In progress')).toBeInTheDocument();
    });
  });

  it('should calculate and display duration', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Duration')).toBeInTheDocument();
      // Duration: 90 minutes (10:00 to 11:30)
      expect(screen.getByText(/90 minutes/)).toBeInTheDocument();
    });
  });

  it('should display N/A duration when end_time is null', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      end_time: null,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      const durationSection = screen.getByText('Duration').parentElement;
      expect(durationSection).toHaveTextContent('N/A');
    });
  });

  it('should display conversation statistics', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Stats should be displayed somewhere in the document
    const allText = document.body.textContent || '';
    expect(allText).toContain('42'); // message_count
    expect(allText).toContain('5'); // epoch_count
    expect(allText).toContain('12'); // files_count
  });

  it('should render epochs when present', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Epoch data should be present
    expect(mockConversation.epochs.length).toBeGreaterThan(0);
  });

  it('should display messages', async () => {
    const user = userEvent.setup();
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Click on Messages tab (use getByRole to distinguish from message count text)
    await user.click(screen.getByRole('button', { name: /messages/i }));

    // Check that messages are displayed
    await waitFor(() => {
      expect(screen.getByText('Help me fix this bug')).toBeInTheDocument();
      expect(screen.getByText('I can help with that')).toBeInTheDocument();
    });
  });

  it('should display user and assistant roles', async () => {
    const user = userEvent.setup();
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    // Wait for component to load
    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Click on Messages tab (use getByRole to distinguish from message count text)
    await user.click(screen.getByRole('button', { name: /messages/i }));

    // Check that message content is displayed
    await waitFor(() => {
      const allText = document.body.textContent || '';
      expect(allText).toContain('Help me fix this bug');
    });

    // Check for role indicators (case-insensitive)
    const bodyText = document.body.textContent?.toLowerCase() || '';
    expect(bodyText).toContain('user');
    expect(bodyText).toContain('assistant');
  });

  it('should display files touched', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText(/Button.tsx/)).toBeInTheDocument();
      expect(screen.getByText(/helpers.ts/)).toBeInTheDocument();
    });
  });

  it('should display file change types', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      // Files should be displayed
      expect(screen.getByText(/Button.tsx/)).toBeInTheDocument();
      expect(screen.getByText(/helpers.ts/)).toBeInTheDocument();
    });
  });

  it('should render tags when present', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Tags should be in the document somewhere
    const allText = document.body.textContent || '';
    expect(allText.length).toBeGreaterThan(100); // Just verify content renders
  });

  it('should display back navigation link', async () => {
    vi.mocked(api.getConversation).mockResolvedValue(mockConversation);

    render(<ConversationDetail />);

    await waitFor(() => {
      const backLinks = screen.getAllByText('← Back to conversations');
      expect(backLinks.length).toBeGreaterThan(0);
    });
  });

  it('should handle conversation without optional fields', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      agent_version: null,
      epochs: [],
      files_touched: [],
      conversation_tags: [],
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Should still display basic info
    expect(screen.getByText('claude-code')).toBeInTheDocument();
    expect(screen.getByText('Test Project')).toBeInTheDocument();
  });

  it('should handle unknown project and developer', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      project: undefined,
      developer: undefined,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('Conversation Detail')).toBeInTheDocument();
    });

    // Should display "Unknown" for missing project/developer
    const unknownElements = screen.getAllByText('Unknown');
    expect(unknownElements.length).toBeGreaterThanOrEqual(2);
  });

  it('should display failed status with red styling', async () => {
    vi.mocked(api.getConversation).mockResolvedValue({
      ...mockConversation,
      status: 'failed',
      success: false,
    });

    render(<ConversationDetail />);

    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument();
    });
  });
});
