/**
 * Conversation Detail page - Full conversation with messages.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Loader2, Sparkles, Info, MessageSquare, FileText } from 'lucide-react';
import { getConversation, getCanonicalNarrative, tagConversation } from '@/lib/api';
import { groupFilesByPath } from '@/lib/utils';
import { format, formatDistanceToNow } from 'date-fns';
import { useRefreshCountdown } from '@/hooks/useRefreshCountdown';

type Tab = 'overview' | 'messages' | 'canonical';

export default function ConversationDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const { data: conversation, isLoading, error, dataUpdatedAt, isFetching } = useQuery({
    queryKey: ['conversation', id],
    queryFn: () => getConversation(id!),
    enabled: !!id,
    refetchInterval: 15000, // Auto-refresh every 15 seconds
    staleTime: 0, // Always fetch fresh data - override global 5min staleTime
    placeholderData: (previousData) => previousData, // Show cached data while refetching
  });

  const secondsUntilRefresh = useRefreshCountdown(15000, dataUpdatedAt);

  // Canonical narrative query (only fetch when tab is active)
  const { data: canonicalNarrative, isLoading: isLoadingCanonical, error: canonicalError } = useQuery({
    queryKey: ['canonical-narrative', id, 'chronological'],
    queryFn: () => getCanonicalNarrative(id!, 'tagging', 'chronological'),
    enabled: !!id && activeTab === 'canonical',
    staleTime: 60000 * 5, // Cache for 5 minutes
  });

  // Tab configuration
  const tabs = [
    { id: 'overview' as Tab, label: 'Overview', icon: Info },
    { id: 'messages' as Tab, label: 'Messages', icon: MessageSquare },
    { id: 'canonical' as Tab, label: 'Canonical', icon: FileText },
  ];

  // Group files by path for collapsible display
  const groupedFiles = useMemo(() => {
    if (!conversation?.files_touched) return [];
    return groupFilesByPath(conversation.files_touched);
  }, [conversation?.files_touched]);

  // Tagging mutation setup
  const queryClient = useQueryClient();
  const [tagError, setTagError] = useState<string | null>(null);

  const tagMutation = useMutation({
    mutationFn: ({ conversationId, force }: { conversationId: string; force: boolean }) =>
      tagConversation(conversationId, force),
    onSuccess: (data) => {
      // Update cached conversation data
      queryClient.setQueryData(['conversation', id], data);
      setTagError(null);
    },
    onError: (error: Error) => {
      setTagError(error.message || 'Failed to tag conversation');
    },
  });

  const hasTags = conversation?.conversation_tags && conversation.conversation_tags.length > 0;

  const handleTagClick = () => {
    if (!id) return;
    setTagError(null);
    tagMutation.mutate({ conversationId: id, force: Boolean(hasTags) });
  };

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

      {/* Tagging Error Display */}
      {tagError && (
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4 mb-6">
          <p className="text-destructive text-sm">
            <strong>Tagging Error:</strong> {tagError}
          </p>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="mb-6">
        <nav className="flex gap-2 bg-slate-900/30 p-1 rounded-lg border border-border/50" aria-label="Tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex-1 inline-flex items-center justify-center gap-2 py-3 px-4 rounded-md font-mono text-xs font-semibold uppercase tracking-wider
                  transition-all duration-200
                  ${
                    isActive
                      ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                      : 'text-muted-foreground hover:text-foreground hover:bg-accent/30'
                  }
                `}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="animate-in fade-in duration-300">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
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
      <div className="bg-card border border-border rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">Tags</h2>
          <button
            onClick={handleTagClick}
            disabled={tagMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            {tagMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {hasTags ? 'Retagging...' : 'Tagging...'}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                {hasTags ? 'Retag' : 'Tag Conversation'}
              </>
            )}
          </button>
        </div>

        {hasTags ? (
          <>
            <div className="flex flex-wrap gap-2 mb-4">
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

            {/* AI Reasoning */}
            {conversation.tags?.reasoning && (
              <div className="mt-4 pt-4 border-t border-border">
                <div className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <h3 className="text-sm font-medium text-muted-foreground mb-1">
                      AI Analysis
                    </h3>
                    <p className="text-sm text-foreground/80">
                      {conversation.tags.reasoning}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <p className="text-muted-foreground text-sm">
            No tags yet. Click "Tag Conversation" to analyze this conversation with AI.
          </p>
        )}
      </div>
          </>
        )}

        {/* Messages Tab */}
        {activeTab === 'messages' && (
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

                {/* Thinking Content */}
                {message.thinking_content && (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-sm font-medium text-amber-600 dark:text-amber-400 hover:underline flex items-center gap-2">
                      <span>💭</span>
                      <span>Extended Thinking</span>
                    </summary>
                    <div className="mt-2 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3 rounded-md">
                      <pre className="text-xs overflow-x-auto whitespace-pre-wrap text-amber-900 dark:text-amber-100">
                        {message.thinking_content}
                      </pre>
                    </div>
                  </details>
                )}

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
        )}

        {/* Canonical Tab */}
        {activeTab === 'canonical' && (
          <div className="bg-card border border-border rounded-lg p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">Canonical Narrative</h2>
              {canonicalNarrative && (
                <span className="text-sm text-muted-foreground font-mono">
                  {canonicalNarrative.token_count.toLocaleString()} tokens
                </span>
              )}
            </div>

            {isLoadingCanonical ? (
              <div className="text-center py-12">
                <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                <p className="mt-4 text-muted-foreground">Generating canonical narrative...</p>
                <p className="mt-2 text-sm text-muted-foreground">This may take a moment for large conversations</p>
              </div>
            ) : canonicalError ? (
              <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
                <p className="text-destructive">Failed to load canonical narrative</p>
                <p className="text-sm text-destructive/80 mt-1">{canonicalError.message}</p>
              </div>
            ) : canonicalNarrative ? (
              <div>
                <p className="text-sm text-muted-foreground mb-4">
                  Complete chronological log of the entire conversation including all messages, tool calls, and thinking content.
                </p>
                <pre className="whitespace-pre-wrap text-sm bg-muted p-4 rounded-md overflow-x-auto max-h-[800px] overflow-y-auto border border-border">
                  {canonicalNarrative.narrative}
                </pre>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
