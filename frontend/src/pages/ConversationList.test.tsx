/**
 * Tests for ConversationList component.
 *
 * The ConversationList uses an "observatory" theme with uppercase labels,
 * SessionTable/SessionPagination components, and StatusBadge. Tests use
 * accessible queries and body text matching for resilience against
 * visual/theme changes.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/utils';
import ConversationList from './ConversationList';
import * as api from '@/lib/api';

// Mock the API module
vi.mock('@/lib/api', () => ({
  getConversations: vi.fn(),
  getProjects: vi.fn(),
  getDevelopers: vi.fn(),
}));

const mockConversations = {
  items: [
    {
      id: '1',
      start_time: '2025-01-01T10:00:00Z',
      end_time: '2025-01-01T11:00:00Z',
      updated_at: '2025-01-01T11:00:00Z',
      project: { id: 'proj-1', name: 'Test Project' },
      developer: { id: 'dev-1', username: 'testuser' },
      agent_type: 'claude-code',
      status: 'completed',
      message_count: 10,
      success: true,
    },
    {
      id: '2',
      start_time: '2025-01-02T10:00:00Z',
      end_time: null,
      updated_at: '2025-01-02T11:00:00Z',
      project: { id: 'proj-1', name: 'Test Project' },
      developer: { id: 'dev-2', username: 'otheruser' },
      agent_type: 'claude-code',
      status: 'in_progress',
      message_count: 5,
      success: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
  pages: 1,
};

const mockProjects = [
  { id: 'proj-1', name: 'Test Project' },
  { id: 'proj-2', name: 'Another Project' },
];

const mockDevelopers = [
  { id: 'dev-1', username: 'testuser' },
  { id: 'dev-2', username: 'otheruser' },
];

describe('ConversationList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getConversations).mockResolvedValue(mockConversations);
    vi.mocked(api.getProjects).mockResolvedValue(mockProjects);
    vi.mocked(api.getDevelopers).mockResolvedValue(mockDevelopers);
  });

  it('should render the page title', async () => {
    render(<ConversationList />);

    // Observatory theme uses "SESSION ARCHIVE" as heading
    await waitFor(() => {
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
      expect(heading.textContent).toContain('SESSION ARCHIVE');
    });
  });

  it('should display auto-refresh indicator', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // Observatory theme shows "AUTO Ns" format
      const bodyText = document.body.textContent || '';
      expect(bodyText).toMatch(/AUTO \d+s/);
    });
  });

  it('should display conversations in a table', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // Check that data appears (they appear in both dropdown and table)
      expect(screen.getAllByText('testuser').length).toBeGreaterThan(0);
      expect(screen.getAllByText('otheruser').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Test Project').length).toBeGreaterThan(0);
      // Check for agent type which only appears in table
      expect(screen.getAllByText('claude-code').length).toBe(2);
    });
  });

  it('should display entry count in pagination', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // SessionPagination (full variant) shows "N - M of T entries"
      const bodyText = document.body.textContent || '';
      expect(bodyText).toContain('entries');
      expect(bodyText).toContain('2'); // total count
    });
  });

  it('should render filter controls', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // Wait for data to load by checking for developer names in table
      expect(screen.getAllByText('testuser').length).toBeGreaterThan(0);
    });

    // Filter panel is rendered with "FILTER PARAMETERS" heading
    const bodyText = document.body.textContent || '';
    expect(bodyText).toContain('FILTER PARAMETERS');

    // Check filter dropdown options exist
    expect(screen.getByRole('option', { name: 'All Projects' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'All Developers' })).toBeInTheDocument();
  });

  it('should display reset button for filters', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // Observatory theme uses "Reset" button instead of "Clear Filters"
      expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
    });
  });

  it('should show message count for each conversation', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });
  });

  it('should show status badges for conversations', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      // StatusBadge in observatory mode replaces underscores with spaces
      // "completed" stays as "completed", "in_progress" becomes "in progress"
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('in progress')).toBeInTheDocument();
    });
  });

  it('should handle empty state when no conversations match', async () => {
    vi.mocked(api.getConversations).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      pages: 0,
    });

    render(<ConversationList />);

    await waitFor(() => {
      // SessionTable with observatory variant uppercases the empty message
      const bodyText = document.body.textContent || '';
      expect(bodyText).toContain('NO ARCHIVE ENTRIES FOUND');
    });
  });

  it('should handle API errors gracefully', async () => {
    vi.mocked(api.getConversations).mockRejectedValue(
      new Error('Failed to fetch conversations')
    );

    render(<ConversationList />);

    await waitFor(() => {
      // Error state shows "Archive Error" heading and the error message
      const bodyText = document.body.textContent || '';
      expect(bodyText).toContain('Archive Error');
      expect(bodyText).toContain('Failed to fetch conversations');
    });
  });

  it('should call getConversations with correct filters', async () => {
    render(<ConversationList />);

    await waitFor(() => {
      expect(api.getConversations).toHaveBeenCalledWith({
        project_id: undefined,
        developer_id: undefined,
        agent_type: undefined,
        status: undefined,
        start_date: undefined,
        end_date: undefined,
        success: undefined,
        page: 1,
        page_size: 20,
      });
    });
  });

  it('should display success indicators correctly', async () => {
    vi.mocked(api.getConversations).mockResolvedValue({
      items: [
        {
          id: '1',
          start_time: '2025-01-01T10:00:00Z',
          end_time: '2025-01-01T11:00:00Z',
          updated_at: '2025-01-01T11:00:00Z',
          project: { id: 'proj-1', name: 'Test Project' },
          developer: { id: 'dev-1', username: 'testuser' },
          agent_type: 'claude-code',
          status: 'completed',
          message_count: 10,
          success: true,
        },
        {
          id: '2',
          start_time: '2025-01-02T10:00:00Z',
          end_time: '2025-01-02T11:00:00Z',
          updated_at: '2025-01-02T11:00:00Z',
          project: { id: 'proj-1', name: 'Test Project' },
          developer: { id: 'dev-2', username: 'otheruser' },
          agent_type: 'claude-code',
          status: 'failed',
          message_count: 5,
          success: false,
        },
        {
          id: '3',
          start_time: '2025-01-03T10:00:00Z',
          end_time: null,
          updated_at: '2025-01-03T11:00:00Z',
          project: { id: 'proj-1', name: 'Test Project' },
          developer: { id: 'dev-3', username: 'thirduser' },
          agent_type: 'claude-code',
          status: 'in_progress',
          message_count: 2,
          success: null,
        },
      ],
      total: 3,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    render(<ConversationList />);

    await waitFor(() => {
      // Success checkmark (rendered by renderHelpers.successIndicator)
      const checkmark = screen.getByTitle('Session achieved its goal');
      expect(checkmark).toBeInTheDocument();
      expect(checkmark.textContent).toBe('✓');

      // Failure X mark
      const xmark = screen.getByTitle('Session failed to achieve its goal');
      expect(xmark).toBeInTheDocument();
      expect(xmark.textContent).toBe('✗');

      // Null success shows "---"
      const unknown = screen.getByTitle('Success status unknown or not yet determined');
      expect(unknown).toBeInTheDocument();
    });
  });

  it('should display failed status with correct styling', async () => {
    vi.mocked(api.getConversations).mockResolvedValue({
      items: [
        {
          id: '1',
          start_time: '2025-01-01T10:00:00Z',
          end_time: '2025-01-01T11:00:00Z',
          updated_at: '2025-01-01T11:00:00Z',
          project: { id: 'proj-1', name: 'Test Project' },
          developer: { id: 'dev-1', username: 'testuser' },
          agent_type: 'claude-code',
          status: 'failed',
          message_count: 10,
          success: false,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    });

    render(<ConversationList />);

    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument();
    });
  });
});
