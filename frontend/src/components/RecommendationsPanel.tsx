/**
 * RecommendationsPanel - Displays automation recommendations for a conversation
 * Supports both slash command and MCP server recommendations
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Loader2,
  Sparkles,
  Check,
  X,
  Terminal,
  Quote,
  ChevronDown,
  ChevronRight,
  Plug,
  AlertTriangle,
} from 'lucide-react';
import {
  getConversationRecommendations,
  detectRecommendations,
  detectMCPRecommendations,
  updateRecommendation,
} from '@/lib/api';
import type { RecommendationResponse } from '@/types/api';

interface RecommendationsPanelProps {
  conversationId: string;
}

type TabType = 'slash_command' | 'mcp_server';

export function RecommendationsPanel({ conversationId }: RecommendationsPanelProps) {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('slash_command');

  // Fetch existing recommendations
  const {
    data: recommendationsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['recommendations', conversationId],
    queryFn: () => getConversationRecommendations(conversationId),
    staleTime: 60000, // Cache for 1 minute
  });

  // Slash command detection mutation
  const detectSlashMutation = useMutation({
    mutationFn: (forceRegenerate: boolean) =>
      detectRecommendations(conversationId, forceRegenerate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', conversationId] });
    },
  });

  // MCP detection mutation
  const detectMCPMutation = useMutation({
    mutationFn: (forceRegenerate: boolean) =>
      detectMCPRecommendations(conversationId, forceRegenerate),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', conversationId] });
    },
  });

  // Update recommendation mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      updateRecommendation(id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', conversationId] });
    },
  });

  const allRecommendations = recommendationsData?.items || [];
  const slashRecommendations = allRecommendations.filter(
    (r) => r.recommendation_type === 'slash_command'
  );
  const mcpRecommendations = allRecommendations.filter(
    (r) => r.recommendation_type === 'mcp_server'
  );

  const currentRecommendations =
    activeTab === 'slash_command' ? slashRecommendations : mcpRecommendations;
  const hasCurrentRecommendations = currentRecommendations.length > 0;

  const detectMutation =
    activeTab === 'slash_command' ? detectSlashMutation : detectMCPMutation;
  const isDetecting = detectMutation.isPending;

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.8) {
      return {
        label: 'High',
        className: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30',
      };
    } else if (confidence >= 0.6) {
      return {
        label: 'Medium',
        className: 'bg-amber-500/10 text-amber-500 border-amber-500/30',
      };
    } else {
      return {
        label: 'Low',
        className: 'bg-slate-500/10 text-slate-500 border-slate-500/30',
      };
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'accepted':
        return {
          label: 'Accepted',
          className: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30',
        };
      case 'dismissed':
        return {
          label: 'Dismissed',
          className: 'bg-slate-500/10 text-slate-500 border-slate-500/30',
        };
      case 'implemented':
        return {
          label: 'Implemented',
          className: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
        };
      default:
        return {
          label: 'Pending',
          className: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/30',
        };
    }
  };

  const getFrictionBadge = (frictionScore: number) => {
    if (frictionScore >= 0.7) {
      return {
        label: 'High Friction',
        className: 'bg-red-500/10 text-red-500 border-red-500/30',
      };
    } else if (frictionScore >= 0.4) {
      return {
        label: 'Medium Friction',
        className: 'bg-amber-500/10 text-amber-500 border-amber-500/30',
      };
    } else {
      return {
        label: 'Low Friction',
        className: 'bg-slate-500/10 text-slate-500 border-slate-500/30',
      };
    }
  };

  return (
    <div className="space-y-6">
      {/* Tab navigation */}
      <div className="flex items-center gap-1 border-b border-border">
        <button
          onClick={() => setActiveTab('slash_command')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'slash_command'
              ? 'border-cyan-500 text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Terminal className="h-4 w-4" />
          Slash Commands
          {slashRecommendations.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-cyan-500/10 text-cyan-500">
              {slashRecommendations.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('mcp_server')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'mcp_server'
              ? 'border-purple-500 text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Plug className="h-4 w-4" />
          MCP Servers
          {mcpRecommendations.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-purple-500/10 text-purple-500">
              {mcpRecommendations.length}
            </span>
          )}
        </button>
      </div>

      {/* Header with detect button */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            {activeTab === 'slash_command' ? (
              <>
                <Terminal className="h-5 w-5 text-cyan-500" />
                Slash Command Recommendations
              </>
            ) : (
              <>
                <Plug className="h-5 w-5 text-purple-500" />
                MCP Server Recommendations
              </>
            )}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {activeTab === 'slash_command'
              ? 'AI-detected patterns that could become reusable commands'
              : 'External tool integrations that would reduce friction'}
          </p>
        </div>
        <button
          onClick={() => detectMutation.mutate(hasCurrentRecommendations)}
          disabled={isDetecting}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-primary-foreground hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium ${
            activeTab === 'slash_command' ? 'bg-cyan-600' : 'bg-purple-600'
          }`}
        >
          {isDetecting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              {hasCurrentRecommendations
                ? 'Re-analyze'
                : activeTab === 'slash_command'
                  ? 'Detect Commands'
                  : 'Detect MCPs'}
            </>
          )}
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
          <p className="text-destructive text-sm">
            Failed to load recommendations: {error.message}
          </p>
        </div>
      )}

      {/* Detection error */}
      {detectMutation.isError && (
        <div className="bg-destructive/10 border border-destructive rounded-lg p-4">
          <p className="text-destructive text-sm">
            Detection failed: {detectMutation.error?.message || 'Unknown error'}
          </p>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="text-center py-12">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">Loading recommendations...</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !hasCurrentRecommendations && (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          {activeTab === 'slash_command' ? (
            <>
              <Terminal className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No Slash Commands Detected</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Click "Detect Commands" to analyze this conversation for slash command
                opportunities.
              </p>
              <p className="text-xs text-muted-foreground">
                The AI will look for repeated patterns that could be automated.
              </p>
            </>
          ) : (
            <>
              <Plug className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No MCP Servers Detected</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Click "Detect MCPs" to analyze this conversation for external tool
                integration needs.
              </p>
              <p className="text-xs text-muted-foreground">
                The AI will look for friction signals and workarounds that MCP servers
                could solve.
              </p>
            </>
          )}
        </div>
      )}

      {/* Recommendations list */}
      {!isLoading && hasCurrentRecommendations && (
        <div className="space-y-4">
          {currentRecommendations.map((rec) => (
            <RecommendationCard
              key={rec.id}
              recommendation={rec}
              isExpanded={expandedId === rec.id}
              onToggleExpand={() =>
                setExpandedId(expandedId === rec.id ? null : rec.id)
              }
              onAccept={() => updateMutation.mutate({ id: rec.id, status: 'accepted' })}
              onDismiss={() =>
                updateMutation.mutate({ id: rec.id, status: 'dismissed' })
              }
              isUpdating={updateMutation.isPending}
              getConfidenceBadge={getConfidenceBadge}
              getStatusBadge={getStatusBadge}
              getFrictionBadge={getFrictionBadge}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface RecommendationCardProps {
  recommendation: RecommendationResponse;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onAccept: () => void;
  onDismiss: () => void;
  isUpdating: boolean;
  getConfidenceBadge: (confidence: number) => { label: string; className: string };
  getStatusBadge: (status: string) => { label: string; className: string };
  getFrictionBadge: (frictionScore: number) => { label: string; className: string };
}

function RecommendationCard({
  recommendation,
  isExpanded,
  onToggleExpand,
  onAccept,
  onDismiss,
  isUpdating,
  getConfidenceBadge,
  getStatusBadge,
  getFrictionBadge,
}: RecommendationCardProps) {
  const confidenceBadge = getConfidenceBadge(recommendation.confidence);
  const statusBadge = getStatusBadge(recommendation.status);
  const isPending = recommendation.status === 'pending';
  const impl = recommendation.suggested_implementation;
  const isMCP = recommendation.recommendation_type === 'mcp_server';

  return (
    <div className="bg-card border border-border rounded-lg overflow-hidden">
      {/* Header - always visible */}
      <div
        className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={onToggleExpand}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="mt-1">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                {/* Slash command name */}
                {!isMCP && impl?.command_name && (
                  <code className="px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-500 font-mono text-sm">
                    /{impl.command_name}
                  </code>
                )}
                {/* MCP category */}
                {isMCP && impl?.category && (
                  <code className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-500 font-mono text-sm">
                    {impl.category}
                  </code>
                )}
                {/* Confidence badge */}
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border ${confidenceBadge.className}`}
                >
                  {confidenceBadge.label} ({Math.round(recommendation.confidence * 100)}
                  %)
                </span>
                {/* Friction badge for MCP */}
                {isMCP && impl?.friction_score !== undefined && (
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border ${getFrictionBadge(impl.friction_score).className}`}
                  >
                    {Math.round(impl.friction_score * 100)}% Friction
                  </span>
                )}
                {/* Status badge */}
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide border ${statusBadge.className}`}
                >
                  {statusBadge.label}
                </span>
              </div>
              <h3 className="font-medium text-sm">{recommendation.title}</h3>
              <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                {recommendation.description}
              </p>
            </div>
          </div>

          {/* Action buttons - only show for pending */}
          {isPending && (
            <div
              className="flex items-center gap-2 shrink-0"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={onAccept}
                disabled={isUpdating}
                className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                title="Accept recommendation"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={onDismiss}
                disabled={isUpdating}
                className="p-2 rounded-lg bg-slate-500/10 text-slate-500 hover:bg-slate-500/20 transition-colors disabled:opacity-50"
                title="Dismiss recommendation"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-0 border-t border-border">
          <div className="pt-4 space-y-4">
            {/* Slash command: Trigger phrases */}
            {!isMCP &&
              impl?.trigger_phrases &&
              impl.trigger_phrases.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Trigger Phrases
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {impl.trigger_phrases.map((phrase, idx) => (
                      <span key={idx} className="px-2 py-1 rounded bg-muted text-sm">
                        "{phrase}"
                      </span>
                    ))}
                  </div>
                </div>
              )}

            {/* Slash command: Template */}
            {!isMCP && impl?.template && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Suggested Template
                </h4>
                <pre className="p-3 rounded-lg bg-muted text-sm font-mono whitespace-pre-wrap overflow-x-auto">
                  {impl.template}
                </pre>
              </div>
            )}

            {/* MCP: Suggested servers */}
            {isMCP && impl?.suggested_mcps && impl.suggested_mcps.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Suggested MCP Servers
                </h4>
                <div className="flex flex-wrap gap-2">
                  {impl.suggested_mcps.map((mcp, idx) => (
                    <code
                      key={idx}
                      className="px-2 py-1 rounded bg-purple-500/10 text-purple-500 font-mono text-sm"
                    >
                      {mcp}
                    </code>
                  ))}
                </div>
              </div>
            )}

            {/* MCP: Use cases */}
            {isMCP && impl?.use_cases && impl.use_cases.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Use Cases
                </h4>
                <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                  {impl.use_cases.map((useCase, idx) => (
                    <li key={idx}>{useCase}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Evidence: Quotes */}
            {recommendation.evidence.quotes &&
              recommendation.evidence.quotes.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                    <Quote className="h-3 w-3" />
                    Evidence{' '}
                    {recommendation.evidence.pattern_count > 0 &&
                      `(${recommendation.evidence.pattern_count} occurrences)`}
                  </h4>
                  <div className="space-y-2">
                    {recommendation.evidence.quotes.map((quote, idx) => (
                      <blockquote
                        key={idx}
                        className={`pl-3 border-l-2 text-sm text-muted-foreground italic ${
                          isMCP ? 'border-purple-500/50' : 'border-cyan-500/50'
                        }`}
                      >
                        "{quote}"
                      </blockquote>
                    ))}
                  </div>
                </div>
              )}

            {/* MCP: Workarounds detected */}
            {isMCP &&
              recommendation.evidence.workarounds_detected &&
              recommendation.evidence.workarounds_detected.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Workarounds Detected
                  </h4>
                  <ul className="list-disc list-inside text-sm text-amber-500/80 space-y-1">
                    {recommendation.evidence.workarounds_detected.map(
                      (workaround, idx) => (
                        <li key={idx}>{workaround}</li>
                      )
                    )}
                  </ul>
                </div>
              )}

            {/* MCP: Friction indicators */}
            {isMCP &&
              recommendation.evidence.friction_indicators &&
              recommendation.evidence.friction_indicators.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Friction Indicators
                  </h4>
                  <ul className="list-disc list-inside text-sm text-red-400/80 space-y-1">
                    {recommendation.evidence.friction_indicators.map(
                      (indicator, idx) => (
                        <li key={idx}>{indicator}</li>
                      )
                    )}
                  </ul>
                </div>
              )}

            {/* MCP: Matched signals */}
            {isMCP &&
              recommendation.evidence.matched_signals &&
              recommendation.evidence.matched_signals.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Matched Signals
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {recommendation.evidence.matched_signals.map((signal, idx) => (
                      <code
                        key={idx}
                        className="px-2 py-1 rounded bg-muted text-xs font-mono"
                      >
                        {signal}
                      </code>
                    ))}
                  </div>
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  );
}

export default RecommendationsPanel;
