/**
 * Watch Directories tab for Ingestion.
 *
 * Configure directories for automatic conversation log monitoring and ingestion,
 * with quick-add suggestions, path validation, and daemon start/stop controls.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FolderSearch,
  Loader2,
  Play,
  Square,
  Trash2,
  Plus,
  FolderOpen,
  AlertCircle,
} from 'lucide-react';
import {
  getWatchConfigs,
  createWatchConfig,
  deleteWatchConfig,
  startWatching,
  stopWatching,
  getSuggestedPaths,
  validatePath,
} from '@/lib/api';
import type { WatchConfigurationResponse } from '@/types/api';
import { useWorkspace } from '@/contexts/WorkspaceContext';

// ===== Watch Config Card =====

interface WatchConfigCardProps {
  config: WatchConfigurationResponse;
  onStart: () => void;
  onStop: () => void;
  onDelete: () => void;
  isStarting: boolean;
  isStopping: boolean;
  isDeleting: boolean;
}

function WatchConfigCard({
  config,
  onStart,
  onStop,
  onDelete,
  isStarting,
  isStopping,
  isDeleting,
}: WatchConfigCardProps) {
  return (
    <div className="p-6 bg-card border border-border rounded-lg">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <FolderSearch className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">{config.directory}</h3>
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${
                config.is_active
                  ? 'bg-green-500/10 text-green-600 border border-green-500'
                  : 'bg-gray-500/10 text-gray-600 border border-gray-500'
              }`}
            >
              {config.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <div className="ml-8 space-y-1 text-sm text-muted-foreground">
            {config.enable_tagging && (
              <p>✓ AI tagging enabled</p>
            )}
            {config.extra_config?.use_api && (
              <p>✓ API mode enabled</p>
            )}
            {config.last_started_at && (
              <p>
                Last started:{' '}
                {new Date(config.last_started_at).toLocaleString()}
              </p>
            )}
            <p>ID: {config.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {config.is_active ? (
            <button
              onClick={onStop}
              disabled={isStopping}
              className="px-3 py-2 bg-destructive/10 text-destructive rounded-md hover:bg-destructive/20 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          ) : (
            <button
              onClick={onStart}
              disabled={isStarting}
              className="px-3 py-2 bg-green-500/10 text-green-600 rounded-md hover:bg-green-500/20 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              Start
            </button>
          )}
          <button
            onClick={onDelete}
            disabled={config.is_active || isDeleting}
            className="px-3 py-2 bg-destructive/10 text-destructive rounded-md hover:bg-destructive/20 transition-colors disabled:opacity-50"
            title={config.is_active ? 'Stop watching before deleting' : 'Delete configuration'}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ===== Main WatchDirectoriesTab =====

export default function WatchDirectoriesTab() {
  const queryClient = useQueryClient();
  const { currentWorkspace, isLoading: isWorkspaceLoading } = useWorkspace();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newDirectory, setNewDirectory] = useState('');
  const [enableTagging, setEnableTagging] = useState(false);
  const [useApiMode, setUseApiMode] = useState(false);
  const [pathError, setPathError] = useState<string | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['watchConfigs', currentWorkspace?.id],
    queryFn: () => getWatchConfigs(),
    enabled: !!currentWorkspace && !isWorkspaceLoading,
  });

  const { data: suggestions, isLoading: isLoadingSuggestions } = useQuery({
    queryKey: ['watchPathSuggestions', currentWorkspace?.id],
    queryFn: () => getSuggestedPaths(),
    enabled: !!currentWorkspace && !isWorkspaceLoading,
  });

  const createMutation = useMutation({
    mutationFn: createWatchConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
      setShowAddForm(false);
      setNewDirectory('');
      setEnableTagging(false);
      setUseApiMode(false);
      setPathError(null);
    },
    onError: (error) => {
      console.error('Failed to create watch config:', error);
      setPathError(error.message);
    },
  });

  const startMutation = useMutation({
    mutationFn: startWatching,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
    onError: (error) => {
      console.error('Failed to start watching:', error);
      alert(`Failed to start watching: ${error.message}`);
    },
  });

  const stopMutation = useMutation({
    mutationFn: stopWatching,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
    onError: (error) => {
      console.error('Failed to stop watching:', error);
      alert(`Failed to stop watching: ${error.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWatchConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
    onError: (error) => {
      console.error('Failed to delete watch config:', error);
      alert(`Failed to delete watch config: ${error.message}`);
    },
  });

  const handleCreateConfig = async () => {
    if (!newDirectory.trim()) return;

    setPathError(null);
    setIsValidating(true);

    try {
      const validation = await validatePath(newDirectory.trim());
      if (!validation.valid) {
        setPathError(
          validation.exists
            ? 'Path exists but is not a readable directory'
            : 'Directory does not exist'
        );
        setIsValidating(false);
        return;
      }

      createMutation.mutate({
        directory: validation.expanded_path,
        enable_tagging: enableTagging,
        extra_config: useApiMode ? { use_api: true } : undefined,
      });
    } catch {
      setPathError('Failed to validate path');
    } finally {
      setIsValidating(false);
    }
  };

  const handleQuickAdd = async (path: string) => {
    setPathError(null);

    try {
      const validation = await validatePath(path);
      if (!validation.valid) {
        alert(`Cannot add directory: ${path} is not a valid readable directory`);
        return;
      }

      const newConfig = await createWatchConfig({
        directory: validation.expanded_path,
        enable_tagging: true,
        extra_config: { use_api: true },
      });

      await startWatching(newConfig.id);

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['watchConfigs'] }),
        queryClient.invalidateQueries({ queryKey: ['watchPathSuggestions'] }),
      ]);
    } catch (err) {
      alert(`Failed to add directory: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  if (isLoading || isWorkspaceLoading || isLoadingSuggestions) {
    return (
      <div className="text-center py-12">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">Loading watch configurations...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
        <p className="text-destructive">
          Error loading watch configurations: {error.message}
        </p>
      </div>
    );
  }

  const availableSuggestions = suggestions?.filter(
    (s) => !configs?.some((c) => c.directory === s.path)
  );

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold mb-2">Watch Directories</h2>
          <p className="text-muted-foreground">
            Configure directories for automatic conversation log monitoring and ingestion.
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Directory
        </button>
      </div>

      {/* Quick Add Suggestions */}
      {availableSuggestions && availableSuggestions.length > 0 && !showAddForm && (
        <div className="mb-6 p-4 bg-muted/50 border border-border rounded-lg">
          <p className="text-sm font-medium mb-3">Quick Add:</p>
          <div className="flex flex-wrap gap-2">
            {availableSuggestions.map((s) => (
              <button
                key={s.path}
                onClick={() => handleQuickAdd(s.path)}
                className="px-3 py-1.5 bg-secondary text-secondary-foreground rounded-md text-sm hover:bg-secondary/80 transition-colors flex items-center gap-2"
              >
                <FolderOpen className="h-4 w-4" />
                {s.name}
                {s.project_count !== null && (
                  <span className="text-xs text-muted-foreground">
                    ({s.project_count} projects)
                  </span>
                )}
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Click to add and start watching automatically
          </p>
        </div>
      )}

      {/* Add New Config Form */}
      {showAddForm && (
        <div className="mb-6 p-6 bg-card border border-border rounded-lg">
          <h3 className="text-lg font-semibold mb-4">Add Watch Directory</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Directory Path <span className="text-destructive">*</span>
              </label>
              <input
                type="text"
                value={newDirectory}
                onChange={(e) => {
                  setNewDirectory(e.target.value);
                  setPathError(null);
                }}
                placeholder="~/.claude/projects or /path/to/watch"
                className={`w-full px-3 py-2 bg-background border rounded-md focus:outline-none focus:ring-2 focus:ring-primary ${
                  pathError ? 'border-destructive' : 'border-border'
                }`}
              />
              {pathError && (
                <p className="mt-1 text-sm text-destructive flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" />
                  {pathError}
                </p>
              )}
              {availableSuggestions && availableSuggestions.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-muted-foreground mb-1">Suggestions:</p>
                  <div className="flex flex-wrap gap-2">
                    {availableSuggestions.map((s) => (
                      <button
                        key={s.path}
                        type="button"
                        onClick={() => setNewDirectory(s.path)}
                        className="text-xs px-2 py-1 bg-muted rounded hover:bg-muted/80 transition-colors"
                      >
                        {s.path}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="enableTagging"
                checked={enableTagging}
                onChange={(e) => setEnableTagging(e.target.checked)}
                className="w-4 h-4 rounded border-border"
              />
              <label htmlFor="enableTagging" className="text-sm">
                Enable AI tagging (uses OpenAI API)
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="useApiMode"
                checked={useApiMode}
                onChange={(e) => setUseApiMode(e.target.checked)}
                className="w-4 h-4 rounded border-border"
              />
              <label htmlFor="useApiMode" className="text-sm">
                Use API mode (push events via Collector API)
              </label>
            </div>
            {useApiMode && (
              <p className="text-xs text-muted-foreground ml-6">
                API mode uses the built-in collector to push events via HTTP API.
                Credentials are managed automatically.
              </p>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleCreateConfig}
                disabled={createMutation.isPending || isValidating || !newDirectory.trim()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {isValidating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                    Validating...
                  </>
                ) : createMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin inline mr-2" />
                    Creating...
                  </>
                ) : (
                  'Create'
                )}
              </button>
              <button
                onClick={() => {
                  setShowAddForm(false);
                  setNewDirectory('');
                  setEnableTagging(false);
                  setUseApiMode(false);
                }}
                className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
              >
                Cancel
              </button>
            </div>
            {createMutation.isError && (
              <p className="text-sm text-destructive">
                Error: {createMutation.error.message}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Watch Configs List */}
      {configs && configs.length === 0 ? (
        <div className="text-center py-12 border-2 border-dashed border-border rounded-lg">
          <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Watch Directories</h3>
          <p className="text-muted-foreground mb-4">
            Add a directory to start automatic log ingestion
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            Add Your First Directory
          </button>
        </div>
      ) : (
        <div className="grid gap-4">
          {configs?.map((config) => (
            <WatchConfigCard
              key={config.id}
              config={config}
              onStart={() => startMutation.mutate(config.id)}
              onStop={() => stopMutation.mutate(config.id)}
              onDelete={() => {
                if (
                  confirm(
                    `Delete watch configuration for ${config.directory}?`
                  )
                ) {
                  deleteMutation.mutate(config.id);
                }
              }}
              isStarting={startMutation.isPending}
              isStopping={stopMutation.isPending}
              isDeleting={deleteMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}
