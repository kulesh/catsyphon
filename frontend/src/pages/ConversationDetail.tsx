/**
 * Conversation Detail page - Full conversation with messages.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { getConversation } from '@/lib/api';
import { groupFilesByPath } from '@/lib/utils';
import { format, formatDistanceToNow } from 'date-fns';
import { useRefreshCountdown } from '@/hooks/useRefreshCountdown';

export default function ConversationDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: conversation, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => getConversation(id!),
    enabled: !!id,
    refetchInterval: 15000, // Auto-refresh every 15 seconds
    placeholderData: (previousData) => previousData, // Show cached data while refetching
  });

  const secondsUntilRefresh = useRefreshCountdown(15000, dataUpdatedAt);

  // Group files by path for collapsible display
  const groupedFiles = useMemo(() => {
    if (!conversation?.files_touched) return [];
    return groupFilesByPath(conversation.files_touched);
  }, [conversation?.files_touched]);

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading conversation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
          <p className="text-destructive">
            Error loading conversation: {error.message}
          </p>
        </div>
        <Link
          to="/conversations"
          className="inline-block mt-4 text-primary hover:underline"
        >
          ← Back to conversations
        </Link>
      </div>
    );
  }

  if (!conversation) {
    return (
      <div className="container mx-auto p-6">
        <p>Conversation not found</p>
        <Link
          to="/conversations"
          className="inline-block mt-4 text-primary hover:underline"
        >
          ← Back to conversations
        </Link>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-6xl">
      {/* Back button */}
      <Link
        to="/conversations"
        className="inline-block mb-4 text-sm text-primary hover:underline"
      >
        ← Back to conversations
      </Link>

      {/* Header with auto-refresh indicator */}
      <div className="mb-6">
        <div className="flex items-start justify-between mb-2">
          <h1 className="text-3xl font-bold">Conversation Detail</h1>
          <div className="flex items-center gap-3">
            {isFetching && (
              <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <svg
                  className="w-4 h-4 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Refreshing...
              </span>
            )}
            {!isFetching && dataUpdatedAt && (
              <span className="text-sm text-muted-foreground">
                Last updated {formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}
              </span>
            )}
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
              Auto-refresh: {secondsUntilRefresh}s
            </span>
          </div>
        </div>
        <p className="text-sm text-muted-foreground font-mono">{conversation.id}</p>
      </div>

      {/* Metadata Card */}
      <div className="bg-card border border-border rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Overview</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <p className="text-sm text-muted-foreground mb-1">Project</p>
            <p className="font-medium">
              {conversation.project?.name || 'Unknown'}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Developer</p>
            <p className="font-medium">
              {conversation.developer?.username || 'Unknown'}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Agent</p>
            <p className="font-medium font-mono text-sm">
              {conversation.agent_type}
              {conversation.agent_version && (
                <span className="text-muted-foreground ml-1">
                  v{conversation.agent_version}
                </span>
              )}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Status</p>
            <span
              className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                conversation.status === 'completed'
                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                  : conversation.status === 'failed'
                    ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
              }`}
            >
              {conversation.status}
            </span>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Success</p>
            <p className="font-medium">
              {conversation.success === null ? (
                'N/A'
              ) : conversation.success ? (
                <span className="text-green-600 dark:text-green-400">✓ Success</span>
              ) : (
                <span className="text-red-600 dark:text-red-400">✗ Failed</span>
              )}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Iterations</p>
            <p className="font-medium">{conversation.iteration_count}</p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Start Time</p>
            <p className="font-medium">
              {format(new Date(conversation.start_time), 'PPp')}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">End Time</p>
            <p className="font-medium">
              {conversation.end_time
                ? format(new Date(conversation.end_time), 'PPp')
                : 'In progress'}
            </p>
          </div>

          <div>
            <p className="text-sm text-muted-foreground mb-1">Duration</p>
            <p className="font-medium">
              {conversation.end_time
                ? `${Math.round(
                    (new Date(conversation.end_time).getTime() -
                      new Date(conversation.start_time).getTime()) /
                      60000
                  )} minutes`
                : 'N/A'}
            </p>
          </div>
        </div>

        {/* Stats Row */}
        <div className="mt-6 pt-6 border-t border-border">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold">{conversation.message_count}</p>
              <p className="text-sm text-muted-foreground">Messages</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{conversation.epoch_count}</p>
              <p className="text-sm text-muted-foreground">Epochs</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{conversation.files_count}</p>
              <p className="text-sm text-muted-foreground">Files</p>
            </div>
          </div>
        </div>
      </div>

      {/* Epochs Section */}
      {conversation.epochs && conversation.epochs.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Epochs</h2>
          <div className="space-y-3">
            {conversation.epochs.map((epoch) => (
              <div
                key={epoch.id}
                className="border border-border rounded-md p-4 bg-background"
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-sm font-medium">Epoch {epoch.sequence}</span>
                  <span className="text-xs text-muted-foreground">
                    {epoch.message_count} messages
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {epoch.intent && (
                    <div>
                      <span className="text-muted-foreground">Intent: </span>
                      {epoch.intent}
                    </div>
                  )}
                  {epoch.outcome && (
                    <div>
                      <span className="text-muted-foreground">Outcome: </span>
                      {epoch.outcome}
                    </div>
                  )}
                  {epoch.sentiment && (
                    <div>
                      <span className="text-muted-foreground">Sentiment: </span>
                      {epoch.sentiment}
                      {epoch.sentiment_score !== null && (
                        <span className="ml-1 text-xs">({epoch.sentiment_score.toFixed(2)})</span>
                      )}
                    </div>
                  )}
                  {epoch.duration_seconds !== null && (
                    <div>
                      <span className="text-muted-foreground">Duration: </span>
                      {Math.round(epoch.duration_seconds / 60)} min
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Files Touched Section */}
      {conversation.files_touched && conversation.files_touched.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <details className="group" open>
            <summary className="cursor-pointer list-none flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">
                Files Touched
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  ({conversation.files_touched.length} modifications across {groupedFiles.length} unique files)
                </span>
              </h2>
              <span className="text-muted-foreground group-open:rotate-180 transition-transform">
                ▼
              </span>
            </summary>

            <div className="space-y-2">
              {groupedFiles.map((file) => {
                const hasChanges = file.total_lines_added > 0 || file.total_lines_deleted > 0 || file.total_lines_modified > 0;

                return (
                  <details key={file.file_path} className="group/file border border-border rounded-md bg-background">
                    <summary className="cursor-pointer list-none flex items-center justify-between p-3 hover:bg-accent/50">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span className="text-muted-foreground group-open/file:rotate-90 transition-transform">
                          ▶
                        </span>
                        <p className="font-mono text-sm truncate">{file.file_path}</p>
                        <span className="text-xs text-muted-foreground shrink-0">
                          ({file.total_operations} operation{file.total_operations !== 1 ? 's' : ''})
                        </span>
                      </div>
                      {hasChanges && (
                        <div className="text-right text-sm ml-4 shrink-0">
                          <div className="flex gap-3">
                            {file.total_lines_added > 0 && (
                              <span className="text-green-600 dark:text-green-400">
                                +{file.total_lines_added}
                              </span>
                            )}
                            {file.total_lines_deleted > 0 && (
                              <span className="text-red-600 dark:text-red-400">
                                -{file.total_lines_deleted}
                              </span>
                            )}
                            {file.total_lines_modified > 0 && (
                              <span className="text-blue-600 dark:text-blue-400">
                                ~{file.total_lines_modified}
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </summary>

                    <div className="px-6 py-3 space-y-2 border-t border-border">
                      {Object.values(file.operations).map((operation) => {
                        const icon = operation.change_type === 'read' ? '📖' :
                                   operation.change_type === 'edit' || operation.change_type === 'modified' ? '✏️' :
                                   operation.change_type === 'create' || operation.change_type === 'created' ? '➕' :
                                   operation.change_type === 'delete' || operation.change_type === 'deleted' ? '🗑️' : '📄';

                        const hasOperationChanges = operation.total_lines_added > 0 || operation.total_lines_deleted > 0 || operation.total_lines_modified > 0;

                        return (
                          <div key={operation.change_type} className="text-sm">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span>{icon}</span>
                                <span className="capitalize">{operation.change_type}</span>
                                <span className="text-xs text-muted-foreground">
                                  ({operation.count}×)
                                </span>
                              </div>
                              {hasOperationChanges && (
                                <div className="flex gap-3">
                                  {operation.total_lines_added > 0 && (
                                    <span className="text-green-600 dark:text-green-400">
                                      +{operation.total_lines_added}
                                    </span>
                                  )}
                                  {operation.total_lines_deleted > 0 && (
                                    <span className="text-red-600 dark:text-red-400">
                                      -{operation.total_lines_deleted}
                                    </span>
                                  )}
                                  {operation.total_lines_modified > 0 && (
                                    <span className="text-blue-600 dark:text-blue-400">
                                      ~{operation.total_lines_modified}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="ml-6 mt-1 text-xs text-muted-foreground">
                              {(() => {
                                // Group by formatted timestamp
                                const timestampCounts = new Map<string, number>();
                                operation.modifications.forEach((mod) => {
                                  const formatted = format(new Date(mod.timestamp), 'MMM d, yyyy h:mm a');
                                  timestampCounts.set(formatted, (timestampCounts.get(formatted) || 0) + 1);
                                });

                                return Array.from(timestampCounts.entries()).map(([timestamp, count]) => (
                                  <div key={timestamp}>
                                    {timestamp} {count > 1 && `(${count}×)`}
                                  </div>
                                ));
                              })()}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </details>
                );
              })}
            </div>
          </details>
        </div>
      )}

      {/* Tags Section */}
      {conversation.conversation_tags && conversation.conversation_tags.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Tags</h2>
          <div className="flex flex-wrap gap-2">
            {conversation.conversation_tags.map((tag) => (
              <div
                key={tag.id}
                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-sm"
              >
                <span className="font-medium">{tag.tag_type}:</span>
                <span>{tag.tag_value}</span>
                {tag.confidence !== null && (
                  <span className="text-xs opacity-75">
                    ({Math.round(tag.confidence * 100)}%)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Message Timeline */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">
          Message Timeline ({conversation.messages.length})
        </h2>

        <div className="space-y-4">
          {conversation.messages.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No messages in this conversation
            </p>
          ) : (
            conversation.messages.map((message) => (
              <div
                key={message.id}
                className="border border-border rounded-lg p-4 bg-background"
              >
                {/* Message Header */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-medium text-muted-foreground">
                      #{message.sequence}
                    </span>
                    <span
                      className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                        message.role === 'user'
                          ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                          : message.role === 'assistant'
                            ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                            : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                      }`}
                    >
                      {message.role}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {format(new Date(message.timestamp), 'PPp')}
                  </span>
                </div>

                {/* Message Content */}
                <div className="prose prose-sm dark:prose-invert max-w-none mb-3">
                  <pre className="whitespace-pre-wrap text-sm bg-muted p-3 rounded-md overflow-x-auto">
                    {message.content}
                  </pre>
                </div>

                {/* Tool Calls */}
                {message.tool_calls && message.tool_calls.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-primary hover:underline">
                      Tool Calls ({message.tool_calls.length})
                    </summary>
                    <div className="mt-2 space-y-2">
                      {message.tool_calls.map((call, i) => (
                        <div key={i} className="bg-muted p-3 rounded-md">
                          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(call, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* Tool Results */}
                {message.tool_results && message.tool_results.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-primary hover:underline">
                      Tool Results ({message.tool_results.length})
                    </summary>
                    <div className="mt-2 space-y-2">
                      {message.tool_results.map((result, i) => (
                        <div key={i} className="bg-muted p-3 rounded-md">
                          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(result, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}

                {/* Code Changes */}
                {message.code_changes && message.code_changes.length > 0 && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-primary hover:underline">
                      Code Changes ({message.code_changes.length})
                    </summary>
                    <div className="mt-2 space-y-2">
                      {message.code_changes.map((change, i) => (
                        <div key={i} className="bg-muted p-3 rounded-md">
                          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(change, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
