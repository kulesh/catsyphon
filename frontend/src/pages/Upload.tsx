import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { uploadConversationLogs } from '@/lib/api';
import type { UploadResponse } from '@/types/api';

export default function Upload() {
  const navigate = useNavigate();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      setError(`Only .jsonl files are supported. ${files.length - jsonlFiles.length} file(s) ignored.`);
    } else {
      setError(null);
    }

    setSelectedFiles(jsonlFiles);
    setUploadResult(null);
  };

  // Upload files
  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setIsUploading(true);
    setError(null);
    setUploadResult(null);

    try {
      const result = await uploadConversationLogs(selectedFiles);
      setUploadResult(result);

      // Redirect to conversation detail if only one file was uploaded successfully
      if (result.success_count === 1 && result.results.length === 1) {
        const conversationId = result.results[0].conversation_id;
        if (conversationId) {
          // Wait a moment to show success, then redirect
          setTimeout(() => {
            navigate(`/conversations/${conversationId}`);
          }, 1500);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  // Remove a selected file
  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Reset form
  const reset = () => {
    setSelectedFiles([]);
    setUploadResult(null);
    setError(null);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Conversation Logs</h1>
        <p className="text-gray-600">
          Upload Claude Code conversation logs (.jsonl files) to analyze and explore your coding sessions.
        </p>
      </div>

      {/* Drag & Drop Zone */}
      {!uploadResult && (
        <div
          className={`
            border-2 border-dashed rounded-lg p-12 text-center transition-colors
            ${
              isDragging
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }
          `}
          onDragEnter={handleDragEnter}
          onDragOver={handleDrag}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <UploadIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <p className="text-lg font-medium text-gray-700 mb-2">
            Drag and drop .jsonl files here
          </p>
          <p className="text-sm text-gray-500 mb-4">or</p>
          <label className="inline-block">
            <span className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer transition-colors">
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
          <p className="text-xs text-gray-500 mt-4">
            Supports multiple .jsonl files
          </p>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-800 text-sm">{error}</p>
        </div>
      )}

      {/* Selected Files List */}
      {selectedFiles.length > 0 && !uploadResult && (
        <div className="mt-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Selected Files ({selectedFiles.length})
          </h2>
          <div className="space-y-2">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-md"
              >
                <div className="flex items-center space-x-3">
                  <FileText className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">{file.name}</p>
                    <p className="text-xs text-gray-500">
                      {(file.size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="text-red-600 hover:text-red-800 text-sm"
                  disabled={isUploading}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>

          {/* Upload Button */}
          <div className="mt-6 flex space-x-3">
            <button
              onClick={handleUpload}
              disabled={isUploading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
            >
              {isUploading ? (
                <>
                  <Loader2 className="animate-spin h-5 w-5 mr-2" />
                  Uploading...
                </>
              ) : (
                `Upload ${selectedFiles.length} ${selectedFiles.length === 1 ? 'File' : 'Files'}`
              )}
            </button>
            <button
              onClick={reset}
              disabled={isUploading}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 disabled:bg-gray-100 disabled:cursor-not-allowed transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Upload Results */}
      {uploadResult && (
        <div className="mt-6">
          <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-md">
            <h2 className="text-lg font-semibold text-green-900 mb-2">
              Upload Complete
            </h2>
            <p className="text-sm text-green-700">
              Successfully uploaded {uploadResult.success_count} of{' '}
              {uploadResult.success_count + uploadResult.failed_count} file(s)
            </p>
          </div>

          {/* Results List */}
          <div className="space-y-2">
            {uploadResult.results.map((result, index) => (
              <div
                key={index}
                className={`
                  p-4 rounded-md border
                  ${
                    result.status === 'success'
                      ? 'bg-green-50 border-green-200'
                      : 'bg-red-50 border-red-200'
                  }
                `}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    {result.status === 'success' ? (
                      <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-600 mt-0.5" />
                    )}
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">
                        {result.filename}
                      </p>
                      {result.status === 'success' ? (
                        <div className="mt-1 text-xs text-gray-600">
                          {result.message_count} messages, {result.epoch_count} epoch(s)
                          {result.files_count > 0 && `, ${result.files_count} files touched`}
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-red-700">{result.error}</p>
                      )}
                    </div>
                  </div>
                  {result.status === 'success' && result.conversation_id && (
                    <button
                      onClick={() => navigate(`/conversations/${result.conversation_id}`)}
                      className="ml-4 text-sm text-blue-600 hover:text-blue-800 whitespace-nowrap"
                    >
                      View →
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="mt-6 flex space-x-3">
            <button
              onClick={reset}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Upload More Files
            </button>
            <button
              onClick={() => navigate('/conversations')}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
            >
              View All Conversations
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
