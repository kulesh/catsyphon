/**
 * Tests for Setup wizard component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/test/utils';
import Setup from './Setup';
import * as apiSetup from '@/lib/api-setup';

// Mock the api-setup module
vi.mock('@/lib/api-setup', () => ({
  createOrganization: vi.fn(),
  createWorkspace: vi.fn(),
  generateSlug: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockOrganization = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  name: 'ACME Corporation',
  slug: 'acme-corporation',
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
};

const mockWorkspace = {
  id: '223e4567-e89b-12d3-a456-426614174001',
  organization_id: '123e4567-e89b-12d3-a456-426614174000',
  name: 'Engineering',
  slug: 'engineering',
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
};

describe('Setup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Setup default generateSlug behavior
    vi.mocked(apiSetup.generateSlug).mockImplementation((name: string) =>
      name.toLowerCase().replace(/\s+/g, '-')
    );
  });

  describe('Welcome Step', () => {
    it('should render welcome screen with title and description', () => {
      render(<Setup />);

      expect(screen.getByText(/Welcome to CatSyphon!/)).toBeInTheDocument();
      expect(screen.getByText(/Let's get you set up/)).toBeInTheDocument();
      expect(screen.getByText(/What you'll create:/)).toBeInTheDocument();
    });

    it('should display organization explanation', () => {
      render(<Setup />);

      expect(screen.getByText('Organization')).toBeInTheDocument();
      expect(screen.getByText(/Your company, team, or personal account/)).toBeInTheDocument();
    });

    it('should display workspace explanation', () => {
      render(<Setup />);

      expect(screen.getByText('Workspace')).toBeInTheDocument();
      expect(screen.getByText(/Helps organize conversations by project/)).toBeInTheDocument();
    });

    it('should navigate to organization step when Get Started is clicked', async () => {
      const user = userEvent.setup();
      render(<Setup />);

      const getStartedButton = screen.getByText('Get Started');
      await user.click(getStartedButton);

      expect(screen.getByText('Create Organization')).toBeInTheDocument();
      expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
    });
  });

  describe('Organization Step', () => {
    beforeEach(async () => {
      const user = userEvent.setup();
      render(<Setup />);
      const getStartedButton = screen.getByText('Get Started');
      await user.click(getStartedButton);
    });

    it('should render organization form with all fields', () => {
      expect(screen.getByLabelText(/Organization Name/)).toBeInTheDocument();
      expect(screen.getByLabelText(/URL Slug/)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/e.g., ACME Corporation/)).toBeInTheDocument();
    });

    it('should show helper text for organization name', () => {
      expect(screen.getByText(/Your organization name/)).toBeInTheDocument();
    });

    it('should show helper text for slug', () => {
      expect(screen.getByText(/Used in URLs - lowercase, no spaces/)).toBeInTheDocument();
    });

    it('should have Back button', () => {
      expect(screen.getByText('← Back')).toBeInTheDocument();
    });

    it('should navigate back to welcome when Back is clicked', async () => {
      const user = userEvent.setup();

      const backButton = screen.getByText('← Back');
      await user.click(backButton);

      expect(screen.getByText(/Welcome to CatSyphon!/)).toBeInTheDocument();
    });

    it('should disable Continue button when name is empty', () => {
      const continueButton = screen.getByText(/Continue →/);
      expect(continueButton).toBeDisabled();
    });

    it('should enable Continue button when name is filled', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/Continue →/);
      expect(continueButton).not.toBeDisabled();
    });

    it('should auto-generate slug when organization name is typed', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      await waitFor(() => {
        expect(apiSetup.generateSlug).toHaveBeenCalledWith('ACME Corporation');
      });
    });

    it('should allow manual slug editing', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const slugInput = screen.getByLabelText(/URL Slug/);
      await user.clear(slugInput);
      await user.type(slugInput, 'custom-slug');

      expect(slugInput).toHaveValue('custom-slug');
    });

    it('should disable Continue button when name is whitespace only', async () => {
      const user = userEvent.setup();

      // Type only whitespace
      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, '   ');

      // Button should be disabled because .trim() returns empty string
      const continueButton = screen.getByText(/Continue →/);
      expect(continueButton).toBeDisabled();
    });

    it('should create organization and navigate to workspace step on success', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/Continue →/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(apiSetup.createOrganization).toHaveBeenCalledWith({
          name: 'ACME Corporation',
          slug: 'acme-corporation',
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Create Workspace')).toBeInTheDocument();
        expect(screen.getByText('Step 2 of 2')).toBeInTheDocument();
      });
    });

    it('should show loading state while creating organization', async () => {
      const user = userEvent.setup();
      // Create a promise we can control
      let resolvePromise: ((value: typeof mockOrganization) => void) | undefined;
      const promise = new Promise<typeof mockOrganization>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(apiSetup.createOrganization).mockReturnValue(promise);

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/Continue →/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(screen.getByText('Creating...')).toBeInTheDocument();
      });

      // Resolve the promise and wait for state updates
      if (resolvePromise) {
        resolvePromise(mockOrganization);
      }
      await waitFor(() => {
        expect(screen.queryByText('Creating...')).not.toBeInTheDocument();
      });
    });

    it('should handle API errors', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockRejectedValue(
        new Error('Organization already exists')
      );

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/Continue →/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(screen.getByText('Organization already exists')).toBeInTheDocument();
      });
    });

    it('should send undefined slug if empty', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);

      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');

      const slugInput = screen.getByLabelText(/URL Slug/);
      await user.clear(slugInput);

      const continueButton = screen.getByText(/Continue →/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(apiSetup.createOrganization).toHaveBeenCalledWith({
          name: 'ACME Corporation',
          slug: undefined,
        });
      });
    });
  });

  describe('Workspace Step', () => {
    beforeEach(async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);

      render(<Setup />);

      // Navigate to organization step
      await user.click(screen.getByText('Get Started'));

      // Fill and submit organization form
      const nameInput = screen.getByLabelText(/Organization Name/);
      await user.type(nameInput, 'ACME Corporation');
      await user.click(screen.getByText(/Continue →/));

      // Wait for workspace step
      await waitFor(() => {
        expect(screen.getByText('Create Workspace')).toBeInTheDocument();
      });
    });

    it('should render workspace form with all fields', () => {
      expect(screen.getByLabelText(/Workspace Name/)).toBeInTheDocument();
      expect(screen.getByLabelText(/URL Slug/)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/e.g., Engineering/)).toBeInTheDocument();
    });

    it('should show organization name in description', () => {
      expect(screen.getByText(/Creating workspace in:/)).toBeInTheDocument();
      expect(screen.getByText(mockOrganization.name)).toBeInTheDocument();
    });

    it('should show helper text for workspace name', () => {
      expect(screen.getByText(/Workspaces help organize conversations/)).toBeInTheDocument();
    });

    it('should navigate back to organization step when Back is clicked', async () => {
      const user = userEvent.setup();

      const backButton = screen.getByText('← Back');
      await user.click(backButton);

      expect(screen.getByText('Create Organization')).toBeInTheDocument();
      expect(screen.getByText('Step 1 of 2')).toBeInTheDocument();
    });

    it('should clear error when navigating back', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockRejectedValue(
        new Error('Workspace error')
      );

      // Try to submit with empty name to trigger error
      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Test');
      await user.click(screen.getByText(/Complete Setup →/));

      await waitFor(() => {
        expect(screen.getByText('Workspace error')).toBeInTheDocument();
      });

      // Navigate back
      const backButton = screen.getByText('← Back');
      await user.click(backButton);

      // Error should be cleared
      expect(screen.queryByText('Workspace error')).not.toBeInTheDocument();
    });

    it('should disable Complete Setup button when name is empty', () => {
      const completeButton = screen.getByText(/Complete Setup →/);
      expect(completeButton).toBeDisabled();
    });

    it('should enable Complete Setup button when name is filled', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/Complete Setup →/);
      expect(completeButton).not.toBeDisabled();
    });

    it('should auto-generate slug when workspace name is typed', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Engineering Team');

      await waitFor(() => {
        expect(apiSetup.generateSlug).toHaveBeenCalledWith('Engineering Team');
      });
    });

    it('should create workspace and navigate to success step on success', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockResolvedValue(mockWorkspace);

      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/Complete Setup →/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(apiSetup.createWorkspace).toHaveBeenCalledWith({
          organization_id: mockOrganization.id,
          name: 'Engineering',
          slug: 'engineering',
        });
      });

      await waitFor(() => {
        expect(screen.getByText('Setup Complete!')).toBeInTheDocument();
      });
    });

    it('should show loading state while creating workspace', async () => {
      const user = userEvent.setup();
      let resolvePromise: ((value: typeof mockWorkspace) => void) | undefined;
      const promise = new Promise<typeof mockWorkspace>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(apiSetup.createWorkspace).mockReturnValue(promise);

      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/Complete Setup →/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(screen.getByText('Creating...')).toBeInTheDocument();
      });

      // Resolve the promise and wait for state updates
      if (resolvePromise) {
        resolvePromise(mockWorkspace);
      }
      await waitFor(() => {
        expect(screen.queryByText('Creating...')).not.toBeInTheDocument();
      });
    });

    it('should handle API errors', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockRejectedValue(
        new Error('Workspace already exists')
      );

      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/Complete Setup →/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(screen.getByText('Workspace already exists')).toBeInTheDocument();
      });
    });

    it('should disable Complete Setup button when name is whitespace only', async () => {
      const user = userEvent.setup();

      // Type only whitespace
      const nameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(nameInput, '   ');

      // Button should be disabled because .trim() returns empty string
      const completeButton = screen.getByText(/Complete Setup →/);
      expect(completeButton).toBeDisabled();
    });
  });

  describe('Success Step', () => {
    beforeEach(async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);
      vi.mocked(apiSetup.createWorkspace).mockResolvedValue(mockWorkspace);

      render(<Setup />);

      // Complete full flow
      await user.click(screen.getByText('Get Started'));

      const orgNameInput = screen.getByLabelText(/Organization Name/);
      await user.type(orgNameInput, 'ACME Corporation');
      await user.click(screen.getByText(/Continue →/));

      await waitFor(() => {
        expect(screen.getByText('Create Workspace')).toBeInTheDocument();
      });

      const wsNameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(wsNameInput, 'Engineering');
      await user.click(screen.getByText(/Complete Setup →/));

      await waitFor(() => {
        expect(screen.getByText('Setup Complete!')).toBeInTheDocument();
      });
    });

    it('should render success screen with checkmark', () => {
      expect(screen.getByText('Setup Complete!')).toBeInTheDocument();
      expect(screen.getByText(/Your workspace is ready/)).toBeInTheDocument();
    });

    it('should display what was created', () => {
      expect(screen.getByText('What you created:')).toBeInTheDocument();
      expect(screen.getByText('Organization:')).toBeInTheDocument();
      expect(screen.getByText(mockOrganization.name)).toBeInTheDocument();
      expect(screen.getByText('Workspace:')).toBeInTheDocument();
      expect(screen.getByText(mockWorkspace.name)).toBeInTheDocument();
    });

    it('should navigate to dashboard when Go to Dashboard is clicked', async () => {
      const user = userEvent.setup();

      const dashboardButton = screen.getByText('Go to Dashboard');
      await user.click(dashboardButton);

      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  describe('Full Flow', () => {
    it('should complete entire setup flow successfully', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);
      vi.mocked(apiSetup.createWorkspace).mockResolvedValue(mockWorkspace);

      render(<Setup />);

      // Welcome step
      expect(screen.getByText(/Welcome to CatSyphon!/)).toBeInTheDocument();
      await user.click(screen.getByText('Get Started'));

      // Organization step
      await waitFor(() => {
        expect(screen.getByText('Create Organization')).toBeInTheDocument();
      });
      const orgNameInput = screen.getByLabelText(/Organization Name/);
      await user.type(orgNameInput, 'ACME Corporation');
      await user.click(screen.getByText(/Continue →/));

      // Workspace step
      await waitFor(() => {
        expect(screen.getByText('Create Workspace')).toBeInTheDocument();
      });
      const wsNameInput = screen.getByLabelText(/Workspace Name/);
      await user.type(wsNameInput, 'Engineering');
      await user.click(screen.getByText(/Complete Setup →/));

      // Success step
      await waitFor(() => {
        expect(screen.getByText('Setup Complete!')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Go to Dashboard'));

      // Verify navigation
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });

    it('should allow navigating back and forth between steps', async () => {
      const user = userEvent.setup();
      render(<Setup />);

      // Start flow
      await user.click(screen.getByText('Get Started'));
      expect(screen.getByText('Create Organization')).toBeInTheDocument();

      // Go back to welcome
      await user.click(screen.getByText('← Back'));
      expect(screen.getByText(/Welcome to CatSyphon!/)).toBeInTheDocument();

      // Go forward again
      await user.click(screen.getByText('Get Started'));
      expect(screen.getByText('Create Organization')).toBeInTheDocument();
    });
  });
});
