/**
 * Ingestion page - Unified interface for managing conversation log ingestion.
 *
 * Combines bulk upload, watch directory configuration, live activity monitoring,
 * and ingestion history into a single tabbed interface.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Upload,
  FolderSearch,
  Activity,
  History,
  Upload as UploadIcon,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Play,
  Square,
  Trash2,
  Plus,
  FolderOpen,
  AlertCircle,
  FileCheck,
  Database,
  RefreshCw,
  Zap,
} from 'lucide-react';
import {
  uploadSingleConversationLog,
  getWatchConfigs,
  createWatchConfig,
  deleteWatchConfig,
  startWatching,
  stopWatching,
  getWatchStatus,
  getIngestionJobs,
  getIngestionStats,
  type UpdateMode,
} from '@/lib/api';
import type {
  UploadResult,
  WatchConfigurationResponse,
  IngestionJobResponse,
} from '@/types/api';

type Tab = 'upload' | 'watch' | 'activity' | 'history';

interface FileUploadState {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  result?: UploadResult;
  error?: string;
}

export default function Ingestion() {
  const [activeTab, setActiveTab] = useState<Tab>('upload');

  const tabs = [
    { id: 'upload' as Tab, label: 'Bulk Upload', icon: Upload },
    { id: 'watch' as Tab, label: 'Watch Directories', icon: FolderSearch },
    { id: 'activity' as Tab, label: 'Live Activity', icon: Activity },
    { id: 'history' as Tab, label: 'History & Logs', icon: History },
  ];

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Ingestion Management</h1>
        <p className="text-muted-foreground">
          Upload conversation logs, configure watch directories, and monitor ingestion activity
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-border mb-6">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm
                  transition-colors duration-200
                  ${
                    isActive
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon
                  className={`
                    -ml-0.5 mr-2 h-5 w-5
                    ${
                      isActive
                        ? 'text-primary'
                        : 'text-muted-foreground group-hover:text-foreground'
                    }
                  `}
                  aria-hidden="true"
                />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {activeTab === 'upload' && <BulkUploadTab />}
        {activeTab === 'watch' && <WatchDirectoriesTab />}
        {activeTab === 'activity' && <LiveActivityTab />}
        {activeTab === 'history' && <HistoryLogsTab />}
      </div>
    </div>
  );
}

// Tab components

function BulkUploadTab() {
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState(false);
  const [fileStates, setFileStates] = useState<FileUploadState[]>([]);
  const [currentFileIndex, setCurrentFileIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updateMode, setUpdateMode] = useState<UpdateMode>('skip');

  const isUploading = currentFileIndex !== null;
  const isComplete =
    fileStates.length > 0 &&
    fileStates.every((f) => f.status === 'success' || f.status === 'error');

  // Handle drag events
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  // Handle file selection from input
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      handleFiles(files);
    }
  };

  // Validate and set files
  const handleFiles = (files: File[]) => {
    // Filter for .jsonl files only
    const jsonlFiles = files.filter((file) => file.name.endsWith('.jsonl'));

    if (jsonlFiles.length === 0) {
      setError('Please select .jsonl files only');
      return;
    }

    if (jsonlFiles.length !== files.length) {
      setError(
        `Only .jsonl files are supported. ${files.length - jsonlFiles.length} file(s) ignored.`
      );
    } else {
      setError(null);
    }

    // Initialize file states
    const newFileStates: FileUploadState[] = jsonlFiles.map((file) => ({
      file,
      status: 'pending',
    }));

    setFileStates(newFileStates);
  };

  // Upload files sequentially
  const handleUpload = async () => {
    if (fileStates.length === 0) return;

    setError(null);

    for (let i = 0; i < fileStates.length; i++) {
      setCurrentFileIndex(i);

      // Update status to uploading
      setFileStates((prev) =>
        prev.map((fs, idx) => (idx === i ? { ...fs, status: 'uploading' } : fs))
      );

      try {
        const response = await uploadSingleConversationLog(fileStates[i].file, updateMode);

        // Response contains results array with one item
        const result = response.results[0];

        // Update with result
        setFileStates((prev) =>
          prev.map((fs, idx) =>
            idx === i
              ? {
                  ...fs,
                  status: result.status as 'success' | 'error',
                  result: result,
                  error: result.error,
                }
              : fs
          )
        );
      } catch (err) {
        // Update with error
        setFileStates((prev) =>
          prev.map((fs, idx) =>
            idx === i
              ? {
                  ...fs,
                  status: 'error',
                  error: err instanceof Error ? err.message : 'Upload failed',
                }
              : fs
          )
        );
      }
    }

    setCurrentFileIndex(null);

    // Redirect if only one file and it succeeded
    if (fileStates.length === 1 && fileStates[0].result?.status === 'success') {
      const conversationId = fileStates[0].result.conversation_id;
      if (conversationId) {
        setTimeout(() => {
          navigate(`/conversations/${conversationId}`);
        }, 1500);
      }
    }
  };

  // Remove a file
  const removeFile = (index: number) => {
    setFileStates((prev) => prev.filter((_, i) => i !== index));
  };

  // Reset form
  const reset = () => {
    setFileStates([]);
    setCurrentFileIndex(null);
    setError(null);
  };

  const successCount = fileStates.filter((f) => f.status === 'success').length;
  const failedCount = fileStates.filter((f) => f.status === 'error').length;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-semibold mb-2">Bulk Upload</h2>
        <p className="text-muted-foreground">
          Upload Claude Code conversation logs (.jsonl files) to analyze and explore your
          coding sessions.
        </p>
      </div>

      {/* Update Mode Selection */}
      <div className="mb-6 p-4 bg-card border rounded-md">
        <label className="text-sm font-medium mb-2 block">Update Mode</label>
        <p className="text-xs text-muted-foreground mb-3">
          How to handle existing conversations (matched by session ID)
        </p>
        <div className="space-y-2">
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="radio"
              name="updateMode"
              value="skip"
              checked={updateMode === 'skip'}
              onChange={(e) => setUpdateMode(e.target.value as UpdateMode)}
              className="mt-0.5"
              disabled={isUploading}
            />
            <div className="flex-1">
              <span className="text-sm font-medium">Skip existing</span>
              <p className="text-xs text-muted-foreground">
                Skip updates for existing conversations (default)
              </p>
            </div>
          </label>
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="radio"
              name="updateMode"
              value="replace"
              checked={updateMode === 'replace'}
              onChange={(e) => setUpdateMode(e.target.value as UpdateMode)}
              className="mt-0.5"
              disabled={isUploading}
            />
            <div className="flex-1">
              <span className="text-sm font-medium">Replace existing</span>
              <p className="text-xs text-muted-foreground">
                Delete and recreate existing conversations with new data
              </p>
            </div>
          </label>
          <label className="flex items-start space-x-3 cursor-pointer">
            <input
              type="radio"
              name="updateMode"
              value="append"
              checked={updateMode === 'append'}
              onChange={(e) => setUpdateMode(e.target.value as UpdateMode)}
              className="mt-0.5"
              disabled={isUploading}
            />
            <div className="flex-1">
              <span className="text-sm font-medium">Append to existing</span>
              <p className="text-xs text-muted-foreground">
                Append new messages to existing conversations (incremental update)
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Drag & Drop Zone */}
      {fileStates.length === 0 && (
        <div
          className={`
            border-2 border-dashed rounded-lg p-12 text-center transition-colors
            ${
              isDragging
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-border/80'
            }
          `}
          onDragEnter={handleDragEnter}
          onDragOver={handleDrag}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <UploadIcon className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          <p className="text-lg font-medium mb-2">Drag and drop .jsonl files here</p>
          <p className="text-sm text-muted-foreground mb-4">or</p>
          <label className="inline-block">
            <span className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 cursor-pointer transition-colors">
              Browse Files
            </span>
            <input
              type="file"
              className="hidden"
              accept=".jsonl"
              multiple
              onChange={handleFileInput}
            />
          </label>
          <p className="text-xs text-muted-foreground mt-4">
            Supports multiple .jsonl files
          </p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-destructive/10 border border-destructive rounded-md">
          <p className="text-destructive text-sm">{error}</p>
        </div>
      )}

      {/* Files List with Progress */}
      {fileStates.length > 0 && (
        <div className="mt-6">
          {/* Progress Header */}
          {isUploading && currentFileIndex !== null && (
            <div className="mb-4 p-4 bg-primary/10 border border-primary rounded-md">
              <p className="text-sm font-medium">
                Processing file {currentFileIndex + 1} of {fileStates.length}:{' '}
                {fileStates[currentFileIndex].file.name}
              </p>
            </div>
          )}

          {/* Completion Summary */}
          {isComplete && (
            <div className="mb-4 p-4 bg-green-500/10 border border-green-500 rounded-md">
              <h3 className="text-lg font-semibold mb-2">Upload Complete</h3>
              <p className="text-sm">
                Successfully uploaded {successCount} of {fileStates.length} file(s)
                {failedCount > 0 && ` (${failedCount} failed)`}
              </p>
            </div>
          )}

          {/* File List */}
          <div className="space-y-2">
            {fileStates.map((fileState, index) => (
              <div
                key={index}
                className={`
                  p-4 rounded-md border
                  ${
                    fileState.status === 'success'
                      ? 'bg-green-500/10 border-green-500'
                      : fileState.status === 'error'
                      ? 'bg-destructive/10 border-destructive'
                      : fileState.status === 'uploading'
                      ? 'bg-primary/10 border-primary'
                      : 'bg-card border-border'
                  }
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    {/* Status Icon */}
                    {fileState.status === 'success' && (
                      <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    )}
                    {fileState.status === 'error' && (
                      <XCircle className="h-5 w-5 text-destructive mt-0.5" />
                    )}
                    {fileState.status === 'uploading' && (
                      <Loader2 className="h-5 w-5 text-primary mt-0.5 animate-spin" />
                    )}
                    {fileState.status === 'pending' && (
                      <Clock className="h-5 w-5 text-muted-foreground mt-0.5" />
                    )}

                    {/* File Info */}
                    <div className="flex-1">
                      <p className="text-sm font-medium">{fileState.file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(fileState.file.size / 1024).toFixed(2)} KB
                      </p>

                      {/* Success Details */}
                      {fileState.status === 'success' && fileState.result && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {fileState.result.message_count} messages,{' '}
                          {fileState.result.epoch_count} epoch(s)
                          {fileState.result.files_count > 0 &&
                            `, ${fileState.result.files_count} files touched`}
                        </div>
                      )}

                      {/* Error Details */}
                      {fileState.status === 'error' && (
                        <p className="mt-1 text-xs text-destructive">{fileState.error}</p>
                      )}

                      {/* Uploading Status */}
                      {fileState.status === 'uploading' && (
                        <p className="mt-1 text-xs text-primary">
                          Uploading and processing...
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  {fileState.status === 'pending' && !isUploading && (
                    <button
                      onClick={() => removeFile(index)}
                      className="text-destructive hover:text-destructive/80 text-sm"
                    >
                      Remove
                    </button>
                  )}
                  {fileState.status === 'success' && fileState.result?.conversation_id && (
                    <button
                      onClick={() =>
                        navigate(`/conversations/${fileState.result!.conversation_id}`)
                      }
                      className="ml-4 text-sm text-primary hover:text-primary/80 whitespace-nowrap"
                    >
                      View →
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Action Buttons */}
          <div className="mt-6 flex space-x-3">
            {!isUploading && !isComplete && (
              <>
                <button
                  onClick={handleUpload}
                  className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
                >
                  Upload {fileStates.length}{' '}
                  {fileStates.length === 1 ? 'File' : 'Files'}
                </button>
                <button
                  onClick={reset}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
                >
                  Clear
                </button>
              </>
            )}
            {isComplete && (
              <>
                <button
                  onClick={reset}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
                >
                  Upload More Files
                </button>
                <button
                  onClick={() => navigate('/conversations')}
                  className="px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 transition-colors"
                >
                  View All Conversations
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function WatchDirectoriesTab() {
  const queryClient = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newDirectory, setNewDirectory] = useState('');
  const [enableTagging, setEnableTagging] = useState(false);

  // Fetch watch configs
  const { data: configs, isLoading, error } = useQuery({
    queryKey: ['watchConfigs'],
    queryFn: () => getWatchConfigs(),
  });

  // Create watch config mutation
  const createMutation = useMutation({
    mutationFn: createWatchConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
      setShowAddForm(false);
      setNewDirectory('');
      setEnableTagging(false);
    },
  });

  // Start watching mutation
  const startMutation = useMutation({
    mutationFn: startWatching,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
  });

  // Stop watching mutation
  const stopMutation = useMutation({
    mutationFn: stopWatching,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
  });

  // Delete watch config mutation
  const deleteMutation = useMutation({
    mutationFn: deleteWatchConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchConfigs'] });
    },
  });

  const handleCreateConfig = () => {
    if (!newDirectory.trim()) return;

    createMutation.mutate({
      directory: newDirectory.trim(),
      enable_tagging: enableTagging,
    });
  };

  if (isLoading) {
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
                onChange={(e) => setNewDirectory(e.target.value)}
                placeholder="/path/to/watch/directory"
                className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
              />
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
            <div className="flex gap-3">
              <button
                onClick={handleCreateConfig}
                disabled={createMutation.isPending || !newDirectory.trim()}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {createMutation.isPending ? (
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

// Watch Config Card Component
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

function LiveActivityTab() {
  // Fetch watch status with auto-refresh every 5 seconds
  const { data: watchStatus, isLoading: isLoadingStatus } = useQuery({
    queryKey: ['watchStatus'],
    queryFn: getWatchStatus,
    refetchInterval: 5000, // Auto-refresh every 5 seconds
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  // Fetch ingestion stats with auto-refresh every 10 seconds
  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['ingestionStats'],
    queryFn: getIngestionStats,
    refetchInterval: 10000,
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  // Fetch recent jobs with auto-refresh every 5 seconds
  const { data: recentJobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ['recentIngestionJobs'],
    queryFn: () => getIngestionJobs({ limit: 50 }),
    refetchInterval: 5000,
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
  });

  const isLoading = isLoadingStatus || isLoadingStats || isLoadingJobs;

  if (isLoading && !watchStatus && !stats && !recentJobs) {
    return (
      <div className="text-center py-12">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">Loading live activity...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold mb-2">Live Activity</h2>
          <p className="text-muted-foreground">
            Real-time monitoring of watch directories and ingestion jobs
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Auto-refreshing
        </div>
      </div>

      {/* Stats Grid - Top Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Watch Status Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 rounded-lg">
              <FolderSearch className="h-5 w-5 text-primary" />
            </div>
            <h3 className="font-semibold">Watch Directories</h3>
          </div>
          {watchStatus ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total</span>
                <span className="text-2xl font-bold">{watchStatus.total_configs}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Active</span>
                <span className="text-lg font-semibold text-green-600">
                  {watchStatus.active_count}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Inactive</span>
                <span className="text-lg font-semibold text-gray-500">
                  {watchStatus.inactive_count}
                </span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Ingestion Stats Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <Database className="h-5 w-5 text-green-600" />
            </div>
            <h3 className="font-semibold">Total Jobs</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">All Time</span>
                <span className="text-2xl font-bold">{stats.total_jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-green-600">Success</span>
                <span className="font-semibold">{stats.by_status.success || 0}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-destructive">Failed</span>
                <span className="font-semibold">{stats.by_status.failed || 0}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Duplicate</span>
                <span className="font-semibold">{stats.by_status.duplicate || 0}</span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Incremental Parsing Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-purple-600" />
            </div>
            <h3 className="font-semibold">Incremental Parsing</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Usage Rate</span>
                <span className="text-2xl font-bold text-purple-600">
                  {stats.incremental_percentage
                    ? `${stats.incremental_percentage.toFixed(1)}%`
                    : '0%'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Incremental Jobs</span>
                <span className="font-semibold">{stats.incremental_jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Full Parse Jobs</span>
                <span className="font-semibold">{stats.total_jobs - stats.incremental_jobs}</span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Pipeline Performance Grid - Bottom Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Pipeline Performance Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Clock className="h-5 w-5 text-blue-600" />
            </div>
            <h3 className="font-semibold">Pipeline Performance</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total Avg</span>
                <span className="text-2xl font-bold">
                  {stats.avg_processing_time_ms
                    ? `${stats.avg_processing_time_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Parsing</span>
                <span className="font-semibold">
                  {stats.avg_parse_duration_ms
                    ? `${stats.avg_parse_duration_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Deduplication</span>
                <span className="font-semibold">
                  {stats.avg_deduplication_check_ms
                    ? `${stats.avg_deduplication_check_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Database Ops</span>
                <span className="font-semibold">
                  {stats.avg_database_operations_ms
                    ? `${stats.avg_database_operations_ms.toFixed(0)}ms`
                    : 'N/A'}
                </span>
              </div>
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* Error Breakdown Card */}
        <div className="p-6 bg-card border border-border rounded-lg">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <AlertCircle className="h-5 w-5 text-red-600" />
            </div>
            <h3 className="font-semibold">Error Breakdown</h3>
          </div>
          {stats ? (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total Failed</span>
                <span className="text-2xl font-bold text-destructive">
                  {stats.by_status.failed || 0}
                </span>
              </div>
              {Object.keys(stats.error_rates_by_stage || {}).length > 0 ? (
                Object.entries(stats.error_rates_by_stage).map(([stage, count]) => (
                  <div key={stage} className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground capitalize">{stage}</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground mt-2">
                  {stats.by_status.failed === 0
                    ? 'No errors recorded'
                    : 'Stage-level error tracking coming soon'}
                </div>
              )}
            </div>
          ) : (
            <Loader2 className="h-6 w-6 animate-spin mt-4 text-muted-foreground" />
          )}
        </div>

        {/* LLM Usage Card (Placeholder) */}
        <div className="p-6 bg-card border border-border rounded-lg opacity-60">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-orange-500/10 rounded-lg">
              <Zap className="h-5 w-5 text-orange-600" />
            </div>
            <h3 className="font-semibold">LLM Usage</h3>
          </div>
          <div className="mt-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Coming Soon</span>
              <span className="text-2xl font-bold">-</span>
            </div>
            <div className="text-xs text-muted-foreground mt-2">
              Token usage, costs, and cache hit rates will be tracked here
            </div>
          </div>
        </div>
      </div>

      {/* Active Watch Configs */}
      {watchStatus && watchStatus.active_configs.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold mb-3">Active Watch Directories</h3>
          <div className="grid gap-3">
            {watchStatus.active_configs.map((config) => (
              <div
                key={config.id}
                className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <FolderSearch className="h-4 w-4 text-green-600" />
                  <span className="font-medium">{config.directory}</span>
                  {config.enable_tagging && (
                    <span className="ml-auto text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                      AI Tagging
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Jobs Feed */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Recent Ingestion Jobs</h3>
        {recentJobs && recentJobs.length > 0 ? (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {recentJobs.map((job) => (
              <IngestionJobCard key={job.id} job={job} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 bg-card border border-border rounded-lg">
            <FileCheck className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-muted-foreground">No ingestion jobs yet</p>
            <p className="text-sm text-muted-foreground mt-1">
              Upload files or configure watch directories to get started
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// Ingestion Job Card Component
interface IngestionJobCardProps {
  job: IngestionJobResponse;
}

function IngestionJobCard({ job }: IngestionJobCardProps) {
  // Status badge styling
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return {
          bg: 'bg-green-500/10',
          text: 'text-green-600',
          border: 'border-green-500',
          icon: CheckCircle,
        };
      case 'failed':
        return {
          bg: 'bg-destructive/10',
          text: 'text-destructive',
          border: 'border-destructive',
          icon: XCircle,
        };
      case 'duplicate':
        return {
          bg: 'bg-yellow-500/10',
          text: 'text-yellow-600',
          border: 'border-yellow-500',
          icon: AlertCircle,
        };
      case 'processing':
        return {
          bg: 'bg-primary/10',
          text: 'text-primary',
          border: 'border-primary',
          icon: Loader2,
        };
      default:
        return {
          bg: 'bg-gray-500/10',
          text: 'text-gray-600',
          border: 'border-gray-500',
          icon: Clock,
        };
    }
  };

  // Source type badge styling
  const getSourceBadge = (sourceType: string) => {
    switch (sourceType) {
      case 'watch':
        return { bg: 'bg-blue-500/10', text: 'text-blue-600', label: 'Watch' };
      case 'upload':
        return { bg: 'bg-purple-500/10', text: 'text-purple-600', label: 'Upload' };
      case 'cli':
        return { bg: 'bg-orange-500/10', text: 'text-orange-600', label: 'CLI' };
      default:
        return { bg: 'bg-gray-500/10', text: 'text-gray-600', label: sourceType };
    }
  };

  const statusBadge = getStatusBadge(job.status);
  const sourceBadge = getSourceBadge(job.source_type);
  const StatusIcon = statusBadge.icon;

  // Format timestamp
  const timeAgo = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div
      className={`p-4 rounded-lg border transition-colors ${statusBadge.bg} ${statusBadge.border}`}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Left side - Status and File */}
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <StatusIcon
            className={`h-5 w-5 mt-0.5 flex-shrink-0 ${statusBadge.text} ${
              job.status === 'processing' ? 'animate-spin' : ''
            }`}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`font-medium ${statusBadge.text}`}>
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </span>
              <span className="text-xs text-muted-foreground">•</span>
              <span className="text-xs text-muted-foreground">
                {timeAgo(job.started_at)}
              </span>
            </div>
            {job.file_path && (
              <p className="text-sm text-muted-foreground truncate" title={job.file_path}>
                {job.file_path.split('/').pop()}
              </p>
            )}
            {job.error_message && (
              <p className="text-xs text-destructive mt-1">{job.error_message}</p>
            )}
          </div>
        </div>

        {/* Right side - Metadata */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Source Type Badge */}
          <span
            className={`px-2 py-1 text-xs font-medium rounded ${sourceBadge.bg} ${sourceBadge.text}`}
          >
            {sourceBadge.label}
          </span>

          {/* Incremental Badge */}
          {job.incremental && (
            <span className="px-2 py-1 text-xs font-medium rounded bg-purple-500/10 text-purple-600">
              ⚡ Incremental
            </span>
          )}

          {/* Processing Time */}
          {job.processing_time_ms !== null && (
            <span className="text-xs text-muted-foreground">
              {job.processing_time_ms}ms
            </span>
          )}

          {/* Messages Added */}
          {job.messages_added > 0 && (
            <span className="text-xs text-muted-foreground">
              +{job.messages_added} msg
            </span>
          )}
        </div>
      </div>

      {/* Stage-level metrics (if available) */}
      {job.metrics && Object.keys(job.metrics).length > 0 && (
        <div className="mt-2 pt-2 border-t border-border/50">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="font-medium">Pipeline Stages:</span>
            {job.metrics.parse_duration_ms !== undefined && (
              <span>
                Parse: {job.metrics.parse_duration_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.deduplication_check_ms !== undefined && (
              <span>
                Dedup: {job.metrics.deduplication_check_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.database_operations_ms !== undefined && (
              <span>
                DB: {job.metrics.database_operations_ms.toFixed(0)}ms
              </span>
            )}
            {job.metrics.total_ms !== undefined && (
              <span className="font-medium">
                Total: {job.metrics.total_ms.toFixed(0)}ms
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryLogsTab() {
  const [filters, setFilters] = useState({
    source_type: '',
    status: '',
    limit: 50,
  });
  const [page, setPage] = useState(1);

  // Fetch jobs with filters
  const { data: jobs, isLoading: isLoadingJobs } = useQuery({
    queryKey: ['ingestionJobs', filters, page],
    queryFn: () => getIngestionJobs({
      source_type: filters.source_type || undefined,
      status: filters.status || undefined,
      limit: filters.limit,
      offset: (page - 1) * filters.limit,
    }),
  });

  // Fetch stats
  const { data: stats, isLoading: isLoadingStats } = useQuery({
    queryKey: ['ingestionStats'],
    queryFn: getIngestionStats,
  });

  const isLoading = isLoadingJobs || isLoadingStats;

  const handleFilterChange = (key: string, value: string | number) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1); // Reset to first page when filters change
  };

  const clearFilters = () => {
    setFilters({ source_type: '', status: '', limit: 50 });
    setPage(1);
  };

  const hasActiveFilters = filters.source_type !== '' || filters.status !== '';

  if (isLoading && !stats && !jobs) {
    return (
      <div className="text-center py-12">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
        <p className="mt-4 text-muted-foreground">Loading history...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-semibold mb-2">History & Logs</h2>
          <p className="text-muted-foreground">
            Complete history of all ingestion jobs with filtering and pagination
          </p>
        </div>
      </div>

      {/* Stats Summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-card border border-border rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Total Jobs</div>
            <div className="text-2xl font-bold">{stats.total_jobs}</div>
          </div>
          <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Success</div>
            <div className="text-2xl font-bold text-green-600">
              {stats.by_status.success || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.total_jobs > 0
                ? `${((stats.by_status.success || 0) / stats.total_jobs * 100).toFixed(1)}%`
                : '0%'}
            </div>
          </div>
          <div className="p-4 bg-destructive/5 border border-destructive/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Failed</div>
            <div className="text-2xl font-bold text-destructive">
              {stats.by_status.failed || 0}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.total_jobs > 0
                ? `${((stats.by_status.failed || 0) / stats.total_jobs * 100).toFixed(1)}%`
                : '0%'}
            </div>
          </div>
          <div className="p-4 bg-purple-500/5 border border-purple-500/20 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Incremental</div>
            <div className="text-2xl font-bold text-purple-600">
              {stats.incremental_percentage ? `${stats.incremental_percentage.toFixed(1)}%` : '0%'}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {stats.incremental_jobs} jobs
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="p-4 bg-card border border-border rounded-lg">
        <div className="flex items-start justify-between mb-4">
          <h3 className="font-semibold">Filters</h3>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-sm text-primary hover:text-primary/80"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Source Type Filter */}
          <div>
            <label className="block text-sm font-medium mb-2">Source Type</label>
            <select
              value={filters.source_type}
              onChange={(e) => handleFilterChange('source_type', e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Sources</option>
              <option value="watch">Watch</option>
              <option value="upload">Upload</option>
              <option value="cli">CLI</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium mb-2">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="">All Statuses</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="duplicate">Duplicate</option>
              <option value="processing">Processing</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>

          {/* Limit Filter */}
          <div>
            <label className="block text-sm font-medium mb-2">Results per page</label>
            <select
              value={filters.limit}
              onChange={(e) => handleFilterChange('limit', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-background border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results Info */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {jobs && jobs.length > 0 ? (
            <>
              Showing {(page - 1) * filters.limit + 1} -{' '}
              {Math.min(page * filters.limit, (page - 1) * filters.limit + jobs.length)} of{' '}
              {stats?.total_jobs || 0} total jobs
              {hasActiveFilters && ' (filtered)'}
            </>
          ) : (
            'No jobs found'
          )}
        </div>
        {jobs && jobs.length >= filters.limit && (
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="px-3 py-1 text-sm">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!jobs || jobs.length < filters.limit}
              className="px-3 py-1 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Jobs List */}
      {jobs && jobs.length > 0 ? (
        <div className="space-y-2">
          {jobs.map((job) => (
            <IngestionJobCard key={job.id} job={job} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-card border border-border rounded-lg">
          <History className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No jobs found</h3>
          <p className="text-muted-foreground mb-4">
            {hasActiveFilters
              ? 'Try adjusting your filters to see more results'
              : 'Upload files or configure watch directories to get started'}
          </p>
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
            >
              Clear Filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
