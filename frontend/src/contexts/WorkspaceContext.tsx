/**
 * Workspace context provider.
 *
 * Manages the current workspace and provides workspace switching functionality.
 */

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { listWorkspaces, type Workspace } from '@/lib/api-setup';

interface WorkspaceContextType {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  setCurrentWorkspace: (workspace: Workspace) => void;
  isLoading: boolean;
  error: string | null;
  refreshWorkspaces: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

const WORKSPACE_STORAGE_KEY = 'catsyphon_current_workspace_id';

interface WorkspaceProviderProps {
  children: ReactNode;
}

export function WorkspaceProvider({ children }: WorkspaceProviderProps) {
  const [currentWorkspace, setCurrentWorkspaceState] = useState<Workspace | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load workspaces on mount
  useEffect(() => {
    loadWorkspaces();
  }, []);

  const loadWorkspaces = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const allWorkspaces = await listWorkspaces();
      setWorkspaces(allWorkspaces);

      // Try to restore from localStorage
      const savedWorkspaceId = localStorage.getItem(WORKSPACE_STORAGE_KEY);

      if (savedWorkspaceId) {
        const saved = allWorkspaces.find(ws => ws.id === savedWorkspaceId);
        if (saved) {
          setCurrentWorkspaceState(saved);
          return;
        }
      }

      // Default to first workspace
      if (allWorkspaces.length > 0) {
        setCurrentWorkspaceState(allWorkspaces[0]);
        localStorage.setItem(WORKSPACE_STORAGE_KEY, allWorkspaces[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces');
      console.error('Failed to load workspaces:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const setCurrentWorkspace = (workspace: Workspace) => {
    setCurrentWorkspaceState(workspace);
    localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace.id);
  };

  const refreshWorkspaces = async () => {
    await loadWorkspaces();
  };

  return (
    <WorkspaceContext.Provider
      value={{
        currentWorkspace,
        workspaces,
        setCurrentWorkspace,
        isLoading,
        error,
        refreshWorkspaces,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace() {
  const context = useContext(WorkspaceContext);

  if (context === undefined) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }

  return context;
}
