/**
 * Bulk Upload tab for Ingestion.
 *
 * Drag-and-drop interface for uploading .jsonl conversation log files
 * with sequential processing and progress tracking.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload as UploadIcon,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
} from 'lucide-react';
import {
  uploadSingleConversationLog,
  type UpdateMode,
} from '@/lib/api';
import type { UploadResult } from '@/types/api';

interface FileUploadState {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  result?: UploadResult;
  error?: string;
}

export default function BulkUploadTab() {
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

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      handleFiles(files);
    }
  };

  const handleFiles = (files: File[]) => {
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

    const newFileStates: FileUploadState[] = jsonlFiles.map((file) => ({
      file,
      status: 'pending',
    }));

    setFileStates(newFileStates);
  };

  const handleUpload = async () => {
    if (fileStates.length === 0) return;

    setError(null);

    for (let i = 0; i < fileStates.length; i++) {
      setCurrentFileIndex(i);

      setFileStates((prev) =>
        prev.map((fs, idx) => (idx === i ? { ...fs, status: 'uploading' } : fs))
      );

      try {
        const response = await uploadSingleConversationLog(fileStates[i].file, updateMode);

        const result = response.results[0];

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

    if (fileStates.length === 1 && fileStates[0].result?.status === 'success') {
      const conversationId = fileStates[0].result.conversation_id;
      if (conversationId) {
        setTimeout(() => {
          navigate(`/conversations/${conversationId}`);
        }, 1500);
      }
    }
  };

  const removeFile = (index: number) => {
    setFileStates((prev) => prev.filter((_, i) => i !== index));
  };

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
          {isUploading && currentFileIndex !== null && (
            <div className="mb-4 p-4 bg-primary/10 border border-primary rounded-md">
              <p className="text-sm font-medium">
                Processing file {currentFileIndex + 1} of {fileStates.length}:{' '}
                {fileStates[currentFileIndex].file.name}
              </p>
            </div>
          )}

          {isComplete && (
            <div className="mb-4 p-4 bg-green-500/10 border border-green-500 rounded-md">
              <h3 className="text-lg font-semibold mb-2">Upload Complete</h3>
              <p className="text-sm">
                Successfully uploaded {successCount} of {fileStates.length} file(s)
                {failedCount > 0 && ` (${failedCount} failed)`}
              </p>
            </div>
          )}

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

                    <div className="flex-1">
                      <p className="text-sm font-medium">{fileState.file.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(fileState.file.size / 1024).toFixed(2)} KB
                      </p>

                      {fileState.status === 'success' && fileState.result && (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {fileState.result.message_count} messages,{' '}
                          {fileState.result.epoch_count} epoch(s)
                          {fileState.result.files_count > 0 &&
                            `, ${fileState.result.files_count} files touched`}
                        </div>
                      )}

                      {fileState.status === 'error' && (
                        <p className="mt-1 text-xs text-destructive">{fileState.error}</p>
                      )}

                      {fileState.status === 'uploading' && (
                        <p className="mt-1 text-xs text-primary">
                          Uploading and processing...
                        </p>
                      )}
                    </div>
                  </div>

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
