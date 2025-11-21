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

      expect(screen.getByText(/OBSERVATORY INIT/)).toBeInTheDocument();
      expect(screen.getByText(/Mission Control Setup Protocol/)).toBeInTheDocument();
      expect(screen.getByText(/Mission Parameters/)).toBeInTheDocument();
    });

    it('should display organization explanation', () => {
      render(<Setup />);

      expect(screen.getByText(/Your command center/)).toBeInTheDocument();
      expect(screen.getByText(/All operations and workspaces are managed/)).toBeInTheDocument();
    });

    it('should display workspace explanation', () => {
      render(<Setup />);

      expect(screen.getByText(/Isolated telemetry zones/)).toBeInTheDocument();
      expect(screen.getByText(/organizing agent conversations/)).toBeInTheDocument();
    });

    it('should navigate to organization step when INITIATE SETUP is clicked', async () => {
      const user = userEvent.setup();
      render(<Setup />);

      const getStartedButton = screen.getByText('INITIATE SETUP');
      await user.click(getStartedButton);

      expect(screen.getByText(/Configure your command center identity/)).toBeInTheDocument();
      expect(screen.getByText('STEP 1/2')).toBeInTheDocument();
    });
  });

  describe('Organization Step', () => {
    beforeEach(async () => {
      const user = userEvent.setup();
      render(<Setup />);
      const getStartedButton = screen.getByText('INITIATE SETUP');
      await user.click(getStartedButton);
    });

    it('should render organization form with all fields', () => {
      expect(screen.getByLabelText(/ORGANIZATION_NAME/)).toBeInTheDocument();
      expect(screen.getByLabelText(/URL_SLUG/)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/ACME Corporation/)).toBeInTheDocument();
    });

    it('should show helper text for organization name', () => {
      expect(screen.getByText(/Company, team, or personal identifier/)).toBeInTheDocument();
    });

    it('should show helper text for slug', () => {
      expect(screen.getByText(/lowercase-hyphenated-format/)).toBeInTheDocument();
    });

    it('should have Back button', () => {
      expect(screen.getByText(/BACK/)).toBeInTheDocument();
    });

    it('should navigate back to welcome when Back is clicked', async () => {
      const user = userEvent.setup();

      const backButton = screen.getByText(/BACK/);
      await user.click(backButton);

      expect(screen.getByText(/OBSERVATORY INIT/)).toBeInTheDocument();
    });

    it('should disable Continue button when name is empty', () => {
      const continueButton = screen.getByRole('button', { name: /CONTINUE/ });
      expect(continueButton).toBeDisabled();
    });

    it('should enable Continue button when name is filled', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/CONTINUE/);
      expect(continueButton).not.toBeDisabled();
    });

    it('should auto-generate slug when organization name is typed', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      await waitFor(() => {
        expect(apiSetup.generateSlug).toHaveBeenCalledWith('ACME Corporation');
      });
    });

    it('should allow manual slug editing', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const slugInput = screen.getByLabelText(/URL_SLUG/);
      await user.clear(slugInput);
      await user.type(slugInput, 'custom-slug');

      expect(slugInput).toHaveValue('custom-slug');
    });

    it('should disable Continue button when name is whitespace only', async () => {
      const user = userEvent.setup();

      // Type only whitespace
      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, '   ');

      // Button should be disabled because .trim() returns empty string
      const continueButton = screen.getByRole('button', { name: /CONTINUE/ });
      expect(continueButton).toBeDisabled();
    });

    it('should create organization and navigate to workspace step on success', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/CONTINUE/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(apiSetup.createOrganization).toHaveBeenCalledWith({
          name: 'ACME Corporation',
          slug: 'acme-corporation',
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/Configure telemetry zone/)).toBeInTheDocument();
        expect(screen.getByText('STEP 2/2')).toBeInTheDocument();
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

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/CONTINUE/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(screen.getByText('CREATING...')).toBeInTheDocument();
      });

      // Resolve the promise and wait for state updates
      if (resolvePromise) {
        resolvePromise(mockOrganization);
      }
      await waitFor(() => {
        expect(screen.queryByText('CREATING...')).not.toBeInTheDocument();
      });
    });

    it('should handle API errors', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockRejectedValue(
        new Error('Organization already exists')
      );

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const continueButton = screen.getByText(/CONTINUE/);
      await user.click(continueButton);

      await waitFor(() => {
        expect(screen.getByText('Organization already exists')).toBeInTheDocument();
      });
    });

    it('should send undefined slug if empty', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);

      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');

      const slugInput = screen.getByLabelText(/URL_SLUG/);
      await user.clear(slugInput);

      const continueButton = screen.getByText(/CONTINUE/);
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
      await user.click(screen.getByText('INITIATE SETUP'));

      // Fill and submit organization form
      const nameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(nameInput, 'ACME Corporation');
      await user.click(screen.getByText(/CONTINUE/));

      // Wait for workspace step
      await waitFor(() => {
        expect(screen.getByText(/Configure telemetry zone/)).toBeInTheDocument();
      });
    });

    it('should render workspace form with all fields', () => {
      expect(screen.getByLabelText(/WORKSPACE_NAME/)).toBeInTheDocument();
      expect(screen.getByLabelText(/URL_SLUG/)).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/Engineering/)).toBeInTheDocument();
    });

    it('should show organization name in description', () => {
      expect(screen.getByText(/PARENT:/)).toBeInTheDocument();
      expect(screen.getByText(mockOrganization.name)).toBeInTheDocument();
    });

    it('should show helper text for workspace name', () => {
      expect(screen.getByText(/Team, project, or environment identifier/)).toBeInTheDocument();
    });

    it('should navigate back to organization step when Back is clicked', async () => {
      const user = userEvent.setup();

      const backButton = screen.getByText(/BACK/);
      await user.click(backButton);

      expect(screen.getByText(/Configure your command center identity/)).toBeInTheDocument();
      expect(screen.getByText('STEP 1/2')).toBeInTheDocument();
    });

    it('should clear error when navigating back', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockRejectedValue(
        new Error('Workspace error')
      );

      // Try to submit with empty name to trigger error
      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Test');
      await user.click(screen.getByText(/FINALIZE SETUP/));

      await waitFor(() => {
        expect(screen.getByText('Workspace error')).toBeInTheDocument();
      });

      // Navigate back
      const backButton = screen.getByText(/BACK/);
      await user.click(backButton);

      // Error should be cleared
      expect(screen.queryByText('Workspace error')).not.toBeInTheDocument();
    });

    it('should disable Complete Setup button when name is empty', () => {
      const completeButton = screen.getByRole('button', { name: /FINALIZE SETUP/ });
      expect(completeButton).toBeDisabled();
    });

    it('should enable Complete Setup button when name is filled', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/FINALIZE SETUP/);
      expect(completeButton).not.toBeDisabled();
    });

    it('should auto-generate slug when workspace name is typed', async () => {
      const user = userEvent.setup();

      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Engineering Team');

      await waitFor(() => {
        expect(apiSetup.generateSlug).toHaveBeenCalledWith('Engineering Team');
      });
    });

    it('should create workspace and navigate to success step on success', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockResolvedValue(mockWorkspace);

      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/FINALIZE SETUP/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(apiSetup.createWorkspace).toHaveBeenCalledWith({
          organization_id: mockOrganization.id,
          name: 'Engineering',
          slug: 'engineering',
        });
      });

      await waitFor(() => {
        expect(screen.getByText(/INITIALIZATION COMPLETE/)).toBeInTheDocument();
      });
    });

    it('should show loading state while creating workspace', async () => {
      const user = userEvent.setup();
      let resolvePromise: ((value: typeof mockWorkspace) => void) | undefined;
      const promise = new Promise<typeof mockWorkspace>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(apiSetup.createWorkspace).mockReturnValue(promise);

      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/FINALIZE SETUP/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(screen.getByText('CREATING...')).toBeInTheDocument();
      });

      // Resolve the promise and wait for state updates
      if (resolvePromise) {
        resolvePromise(mockWorkspace);
      }
      await waitFor(() => {
        expect(screen.queryByText('CREATING...')).not.toBeInTheDocument();
      });
    });

    it('should handle API errors', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createWorkspace).mockRejectedValue(
        new Error('Workspace already exists')
      );

      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, 'Engineering');

      const completeButton = screen.getByText(/FINALIZE SETUP/);
      await user.click(completeButton);

      await waitFor(() => {
        expect(screen.getByText('Workspace already exists')).toBeInTheDocument();
      });
    });

    it('should disable Complete Setup button when name is whitespace only', async () => {
      const user = userEvent.setup();

      // Type only whitespace
      const nameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(nameInput, '   ');

      // Button should be disabled because .trim() returns empty string
      const completeButton = screen.getByRole('button', { name: /FINALIZE SETUP/ });
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
      await user.click(screen.getByText('INITIATE SETUP'));

      const orgNameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(orgNameInput, 'ACME Corporation');
      await user.click(screen.getByText(/CONTINUE/));

      await waitFor(() => {
        expect(screen.getByText(/Configure telemetry zone/)).toBeInTheDocument();
      });

      const wsNameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(wsNameInput, 'Engineering');
      await user.click(screen.getByText(/FINALIZE SETUP/));

      await waitFor(() => {
        expect(screen.getByText(/INITIALIZATION COMPLETE/)).toBeInTheDocument();
      });
    });

    it('should render success screen with checkmark', () => {
      expect(screen.getByText(/INITIALIZATION COMPLETE/)).toBeInTheDocument();
      expect(screen.getByText(/Observatory systems online/)).toBeInTheDocument();
    });

    it('should display what was created', () => {
      expect(screen.getByText(/CONFIGURATION:/)).toBeInTheDocument();
      expect(screen.getByText(/ORGANIZATION:/)).toBeInTheDocument();
      expect(screen.getByText(mockOrganization.name)).toBeInTheDocument();
      expect(screen.getByText(/WORKSPACE:/)).toBeInTheDocument();
      expect(screen.getByText(mockWorkspace.name)).toBeInTheDocument();
    });

    it('should navigate to ingestion when ENTER MISSION CONTROL is clicked', async () => {
      const user = userEvent.setup();

      const dashboardButton = screen.getByText('ENTER MISSION CONTROL');
      await user.click(dashboardButton);

      expect(mockNavigate).toHaveBeenCalledWith('/ingestion');
    });
  });

  describe('Full Flow', () => {
    it('should complete entire setup flow successfully', async () => {
      const user = userEvent.setup();
      vi.mocked(apiSetup.createOrganization).mockResolvedValue(mockOrganization);
      vi.mocked(apiSetup.createWorkspace).mockResolvedValue(mockWorkspace);

      render(<Setup />);

      // Welcome step
      expect(screen.getByText(/OBSERVATORY INIT/)).toBeInTheDocument();
      await user.click(screen.getByText('INITIATE SETUP'));

      // Organization step
      await waitFor(() => {
        expect(screen.getByText(/Configure your command center identity/)).toBeInTheDocument();
      });
      const orgNameInput = screen.getByLabelText(/ORGANIZATION_NAME/);
      await user.type(orgNameInput, 'ACME Corporation');
      await user.click(screen.getByText(/CONTINUE/));

      // Workspace step
      await waitFor(() => {
        expect(screen.getByText(/Configure telemetry zone/)).toBeInTheDocument();
      });
      const wsNameInput = screen.getByLabelText(/WORKSPACE_NAME/);
      await user.type(wsNameInput, 'Engineering');
      await user.click(screen.getByText(/FINALIZE SETUP/));

      // Success step
      await waitFor(() => {
        expect(screen.getByText(/INITIALIZATION COMPLETE/)).toBeInTheDocument();
      });
      await user.click(screen.getByText('ENTER MISSION CONTROL'));

      // Verify navigation
      expect(mockNavigate).toHaveBeenCalledWith('/ingestion');
    });

    it('should allow navigating back and forth between steps', async () => {
      const user = userEvent.setup();
      render(<Setup />);

      // Start flow
      await user.click(screen.getByText('INITIATE SETUP'));
      expect(screen.getByText(/Configure your command center identity/)).toBeInTheDocument();

      // Go back to welcome
      await user.click(screen.getByText(/BACK/));
      expect(screen.getByText(/OBSERVATORY INIT/)).toBeInTheDocument();

      // Go forward again
      await user.click(screen.getByText('INITIATE SETUP'));
      expect(screen.getByText(/Configure your command center identity/)).toBeInTheDocument();
    });
  });
});
