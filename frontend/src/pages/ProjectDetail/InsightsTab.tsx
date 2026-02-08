/**
 * AI Insights tab for ProjectDetail.
 *
 * Displays LLM-generated insights including collaboration quality scores,
 * workflow patterns, learning opportunities, anti-patterns, and trends.
 */

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { getProjectInsights } from '@/lib/api';
import {
  Users,
  FileText,
  Clock,
  Activity,
  Brain,
  Lightbulb,
  AlertTriangle,
  BookOpen,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import type { PatternFrequency, TrendPoint } from '@/types/api';

// ===== Helper Components =====

function ScoreCard({
  title,
  score,
  icon,
  color,
  description,
}: {
  title: string;
  score: number;
  icon: React.ReactNode;
  color: 'cyan' | 'emerald' | 'purple';
  description: string;
}) {
  const colorClasses = {
    cyan: 'text-cyan-400 border-cyan-400/30 bg-cyan-400/5',
    emerald: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/5',
    purple: 'text-purple-400 border-purple-400/30 bg-purple-400/5',
  };

  const barColorClasses = {
    cyan: 'from-cyan-500 to-cyan-400',
    emerald: 'from-emerald-500 to-emerald-400',
    purple: 'from-purple-500 to-purple-400',
  };

  return (
    <div className={`observatory-card p-5 border ${colorClasses[color].split(' ')[1]} ${colorClasses[color].split(' ')[2]}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={colorClasses[color].split(' ')[0]}>{icon}</span>
        <h4 className="font-semibold text-sm">{title}</h4>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className={`text-3xl font-mono font-bold ${colorClasses[color].split(' ')[0]}`}>
          {score.toFixed(1)}
        </span>
        <span className="text-sm text-muted-foreground">/ 10</span>
      </div>
      <div className="h-1.5 bg-slate-900/50 rounded-full overflow-hidden border border-border/30 mb-2">
        <div
          className={`h-full bg-gradient-to-r ${barColorClasses[color]} transition-all`}
          style={{ width: `${(score / 10) * 100}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  );
}

function PatternCard({
  title,
  icon,
  patterns,
  color,
}: {
  title: string;
  icon: React.ReactNode;
  patterns: PatternFrequency[];
  color: 'cyan' | 'emerald' | 'amber' | 'red';
}) {
  const barColorClasses = {
    cyan: 'bg-cyan-400/80',
    emerald: 'bg-emerald-400/80',
    amber: 'bg-amber-400/80',
    red: 'bg-red-400/80',
  };

  return (
    <div className="observatory-card p-5">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h4 className="font-semibold">{title}</h4>
      </div>
      <div className="space-y-3">
        {patterns.slice(0, 5).map((pattern, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-foreground/90 truncate pr-2">{pattern.pattern}</span>
              <span className="text-muted-foreground font-mono text-xs whitespace-nowrap">
                {pattern.count} ({pattern.percentage}%)
              </span>
            </div>
            <div className="h-1 bg-slate-900/50 rounded-full overflow-hidden">
              <div
                className={`h-full ${barColorClasses[color]} transition-all`}
                style={{ width: `${Math.min(pattern.percentage, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendMiniChart({
  title,
  data,
  color,
}: {
  title: string;
  data: TrendPoint[];
  color: 'cyan' | 'emerald' | 'purple';
}) {
  const colorClasses = {
    cyan: 'text-cyan-400',
    emerald: 'text-emerald-400',
    purple: 'text-purple-400',
  };

  const dotColorClasses = {
    cyan: 'bg-cyan-400',
    emerald: 'bg-emerald-400',
    purple: 'bg-purple-400',
  };

  const firstScore = data[0]?.avg_score ?? 0;
  const lastScore = data[data.length - 1]?.avg_score ?? 0;
  const diff = lastScore - firstScore;
  const trendDirection = diff > 0.5 ? 'up' : diff < -0.5 ? 'down' : 'stable';

  const minScore = Math.min(...data.map((d) => d.avg_score));
  const maxScore = Math.max(...data.map((d) => d.avg_score));
  const range = maxScore - minScore || 1;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{title}</span>
        <span className={`text-sm font-mono ${colorClasses[color]}`}>
          {trendDirection === 'up' && '↑'}
          {trendDirection === 'down' && '↓'}
          {trendDirection === 'stable' && '→'}
          {lastScore.toFixed(1)}
        </span>
      </div>
      <div className="flex items-end gap-1 h-12">
        {data.map((point, idx) => {
          const height = ((point.avg_score - minScore) / range) * 100;
          return (
            <div
              key={idx}
              className={`flex-1 rounded-t ${dotColorClasses[color]} opacity-70 hover:opacity-100 transition-opacity`}
              style={{ height: `${Math.max(height, 10)}%` }}
              title={`${point.date}: ${point.avg_score.toFixed(1)} (${point.count} sessions)`}
            />
          );
        })}
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-muted-foreground">{data[0]?.date?.slice(5)}</span>
        <span className="text-xs text-muted-foreground">{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}

// ===== Main InsightsTab Component =====

export default function InsightsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const {
    data: insights,
    isLoading,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['projects', projectId, 'insights', dateRange],
    queryFn: () => getProjectInsights(projectId, dateRange, true, false),
    staleTime: 60000,
  });

  const handleRegenerate = async () => {
    setIsRegenerating(true);
    setRegenerateError(null);
    try {
      const freshInsights = await getProjectInsights(projectId, dateRange, true, true);
      queryClient.setQueryData(['projects', projectId, 'insights', dateRange], freshInsights);
    } catch (err) {
      console.error('Failed to regenerate insights:', err);
      setRegenerateError(err instanceof Error ? err.message : 'Failed to regenerate insights');
    } finally {
      setIsRegenerating(false);
    }
  };

  const canRegenerate = insights && insights.conversations_analyzed > 0;

  const dateRangeLabels = {
    '7d': 'Last 7 days',
    '30d': 'Last 30 days',
    '90d': 'Last 90 days',
    'all': 'All time',
  };

  const isStale = insights?.oldest_insight_at && insights?.latest_conversation_at
    ? new Date(insights.oldest_insight_at) < new Date(insights.latest_conversation_at)
    : false;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="observatory-card p-6">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-cyan-400 animate-spin" />
            <div>
              <p className="text-sm font-medium">Analyzing conversations...</p>
              <p className="text-xs text-muted-foreground mt-1">
                First-time analysis may take 1-2 minutes for large projects
              </p>
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="observatory-card p-6 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/3 mb-4"></div>
              <div className="h-32 bg-muted rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">Failed to load insights</p>
      </div>
    );
  }

  if (!insights) {
    return null;
  }

  const hasPatterns =
    insights.top_workflow_patterns.length > 0 ||
    insights.top_learning_opportunities.length > 0 ||
    insights.top_anti_patterns.length > 0;

  return (
    <div className="space-y-8">
      {/* Time Range Control */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Time Range:
          </span>
          <div className="flex gap-2">
            {(['7d', '30d', '90d', 'all'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setDateRange(range)}
                disabled={isFetching || isRegenerating}
                className={`
                  px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider rounded-md transition-all duration-200
                  ${
                    dateRange === range
                      ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/30'
                      : 'border border-border/50 text-muted-foreground hover:text-foreground hover:bg-accent/30 hover:border-border'
                  }
                  disabled:opacity-50 disabled:cursor-not-allowed
                `}
              >
                {dateRangeLabels[range]}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleRegenerate}
          disabled={isFetching || isRegenerating || !canRegenerate}
          title={!canRegenerate ? 'No conversations in selected date range' : undefined}
          className={`
            flex items-center gap-2 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider rounded-md
            border border-amber-400/30 text-amber-400 hover:bg-amber-400/10 transition-all
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
        >
          <RefreshCw className={`w-4 h-4 ${isRegenerating ? 'animate-spin' : ''}`} />
          {isRegenerating ? 'Regenerating...' : 'Regenerate'}
        </button>
      </div>

      {isRegenerating && (
        <div className="observatory-card p-4 border-amber-400/30 bg-amber-400/5">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 text-amber-400 animate-spin" />
            <div>
              <p className="text-sm font-medium text-amber-400">Regenerating insights...</p>
              <p className="text-xs text-muted-foreground mt-1">
                This may take several minutes for projects with many conversations.
                Each conversation requires an LLM analysis call.
              </p>
            </div>
          </div>
        </div>
      )}

      {regenerateError && (
        <div className="observatory-card p-4 border-red-400/30 bg-red-400/5">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <div>
              <p className="text-sm font-medium text-red-400">Regeneration failed</p>
              <p className="text-xs text-muted-foreground mt-1">{regenerateError}</p>
            </div>
          </div>
        </div>
      )}

      {/* Freshness Indicator */}
      {insights.oldest_insight_at && (
        <div className={`observatory-card p-4 ${isStale ? 'border-amber-400/30' : 'border-emerald-400/30'}`}>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              {isStale ? (
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              ) : (
                <Clock className="w-4 h-4 text-emerald-400" />
              )}
              <div>
                <span className="text-xs font-mono text-muted-foreground">
                  {isStale ? 'INSIGHTS MAY BE STALE' : 'INSIGHTS UP TO DATE'}
                </span>
                <p className="text-sm">
                  Oldest insight:{' '}
                  <span className={isStale ? 'text-amber-400' : 'text-foreground'}>
                    {formatDistanceToNow(new Date(insights.oldest_insight_at), { addSuffix: true })}
                  </span>
                  {insights.latest_conversation_at && (
                    <>
                      {' · Latest session: '}
                      <span className="text-foreground">
                        {formatDistanceToNow(new Date(insights.latest_conversation_at), { addSuffix: true })}
                      </span>
                    </>
                  )}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
              <span>
                <span className="text-cyan-400">{insights.insights_cached}</span> cached
              </span>
              {insights.insights_generated > 0 && (
                <span>
                  <span className="text-emerald-400">{insights.insights_generated}</span> generated
                </span>
              )}
              {insights.insights_failed > 0 && (
                <span>
                  <span className="text-red-400">{insights.insights_failed}</span> failed
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Coverage Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Sessions Analyzed
          </span>
          <p className="text-2xl font-mono font-bold text-cyan-400 mt-1">
            {insights.conversations_analyzed}
          </p>
        </div>
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            With Insights
          </span>
          <p className="text-2xl font-mono font-bold text-emerald-400 mt-1">
            {insights.conversations_with_insights}
          </p>
        </div>
        <div className="observatory-card p-4">
          <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
            Coverage
          </span>
          <p className="text-2xl font-mono font-bold text-purple-400 mt-1">
            {insights.conversations_analyzed > 0
              ? `${Math.round((insights.conversations_with_insights / insights.conversations_analyzed) * 100)}%`
              : 'N/A'}
          </p>
        </div>
      </div>

      {/* LLM Summary */}
      {insights.summary && (
        <div className="observatory-card p-6 border-l-4 border-l-cyan-400">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-cyan-400" />
            <h3 className="text-lg font-semibold">AI Summary</h3>
          </div>
          <div className="prose prose-sm prose-invert max-w-none">
            <p className="text-foreground/90 leading-relaxed whitespace-pre-wrap">
              {insights.summary}
            </p>
          </div>
        </div>
      )}

      {/* Score Averages */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ScoreCard
          title="Collaboration Quality"
          score={insights.avg_collaboration_quality}
          icon={<Users className="w-5 h-5" />}
          color="cyan"
          description="How well developers and AI work together"
        />
        <ScoreCard
          title="Agent Effectiveness"
          score={insights.avg_agent_effectiveness}
          icon={<Brain className="w-5 h-5" />}
          color="emerald"
          description="How well AI agents complete tasks"
        />
        <ScoreCard
          title="Scope Clarity"
          score={insights.avg_scope_clarity}
          icon={<FileText className="w-5 h-5" />}
          color="purple"
          description="How clear task requirements are"
        />
      </div>

      {/* Trends */}
      {(insights.collaboration_trend.length > 1 ||
        insights.effectiveness_trend.length > 1 ||
        insights.scope_clarity_trend.length > 1) && (
        <div className="observatory-card p-6">
          <h3 className="text-lg font-semibold mb-4">Weekly Trends</h3>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {insights.collaboration_trend.length > 1 && (
              <TrendMiniChart
                title="Collaboration"
                data={insights.collaboration_trend}
                color="cyan"
              />
            )}
            {insights.effectiveness_trend.length > 1 && (
              <TrendMiniChart
                title="Effectiveness"
                data={insights.effectiveness_trend}
                color="emerald"
              />
            )}
            {insights.scope_clarity_trend.length > 1 && (
              <TrendMiniChart
                title="Scope Clarity"
                data={insights.scope_clarity_trend}
                color="purple"
              />
            )}
          </div>
        </div>
      )}

      {/* Pattern Cards */}
      {hasPatterns && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {insights.top_workflow_patterns.length > 0 && (
            <PatternCard
              title="Top Workflow Patterns"
              icon={<Activity className="w-5 h-5 text-cyan-400" />}
              patterns={insights.top_workflow_patterns}
              color="cyan"
            />
          )}

          {insights.top_learning_opportunities.length > 0 && (
            <PatternCard
              title="Learning Opportunities"
              icon={<BookOpen className="w-5 h-5 text-emerald-400" />}
              patterns={insights.top_learning_opportunities}
              color="emerald"
            />
          )}

          {insights.top_anti_patterns.length > 0 && (
            <PatternCard
              title="Anti-Patterns"
              icon={<AlertTriangle className="w-5 h-5 text-amber-400" />}
              patterns={insights.top_anti_patterns}
              color="amber"
            />
          )}

          {insights.common_technical_debt.length > 0 && (
            <PatternCard
              title="Technical Debt Indicators"
              icon={<AlertTriangle className="w-5 h-5 text-red-400" />}
              patterns={insights.common_technical_debt}
              color="red"
            />
          )}
        </div>
      )}

      {/* Empty State */}
      {!hasPatterns && !insights.summary && (
        <div className="observatory-card p-12 text-center">
          <Lightbulb className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No Insights Yet</h3>
          {insights.conversations_analyzed === 0 ? (
            <div className="text-sm text-muted-foreground">
              <p className="mb-2">
                No conversations found in the selected time range ({dateRangeLabels[dateRange]}).
              </p>
              <p>
                Try selecting a longer time range like{' '}
                <button
                  onClick={() => setDateRange('all')}
                  className="text-cyan-400 hover:underline font-medium"
                >
                  All time
                </button>
                .
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Insights will appear here after analyzing conversation sessions.
              <br />
              Click <span className="text-amber-400 font-medium">Regenerate</span> to generate insights for all conversations.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
