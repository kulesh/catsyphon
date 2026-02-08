/**
 * Pairing Analytics tab for ProjectDetail.
 *
 * Displays developer-agent pairing effectiveness, role dynamics,
 * handoff metrics, impact, sentiment, influence flows, and error heatmaps.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProjectAnalytics } from '@/lib/api';
import {
  MessageSquare,
  Clock,
  TrendingUp,
  Network,
  ArrowLeftRight,
  Brain,
} from 'lucide-react';
import type { ProjectAnalytics } from '@/types/api';

export default function AnalyticsTab({ projectId }: { projectId: string }) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const {
    data: analytics,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['projects', projectId, 'analytics', dateRange],
    queryFn: () => getProjectAnalytics(projectId, dateRange),
    refetchInterval: 20000,
    staleTime: 0,
  });

  const rangeButtons: Array<{ label: string; value: '7d' | '30d' | '90d' | 'all' }> =
    [
      { label: '7D', value: '7d' },
      { label: '30D', value: '30d' },
      { label: '90D', value: '90d' },
      { label: 'All', value: 'all' },
    ];

  const loadingSkeleton = (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="bg-card border border-border rounded-lg p-6 animate-pulse h-44"
        >
          <div className="h-4 bg-muted rounded w-1/3 mb-4"></div>
          <div className="h-3 bg-muted rounded w-2/3 mb-2"></div>
          <div className="h-3 bg-muted rounded w-1/2"></div>
        </div>
      ))}
    </div>
  );

  if (isLoading) return loadingSkeleton;
  if (error || !analytics) {
    return (
      <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
        <p className="text-destructive font-medium">
          Failed to load analytics
        </p>
      </div>
    );
  }

  const {
    pairing_top,
    pairing_bottom,
    role_dynamics,
    handoffs,
    impact,
    sentiment_by_agent,
    thinking_time,
  } = analytics;
  const { influence_flows, error_heatmap } = analytics;

  const renderPairList = (pairs: ProjectAnalytics['pairing_top'], tone: 'good' | 'bad') => (
    <div className="space-y-2">
      {pairs.length === 0 ? (
        <p className="text-muted-foreground text-sm">No data.</p>
      ) : (
        pairs.map((pair, idx) => (
          <div
            key={`${pair.developer}-${pair.agent_type}-${idx}`}
            className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
          >
            <div>
              <p className="font-semibold text-foreground">
                {pair.developer || 'Unassigned'} · {pair.agent_type}
              </p>
              <p className="text-xs text-muted-foreground">
                {pair.sessions} sessions · success{' '}
                {pair.success_rate !== null && pair.success_rate !== undefined
                  ? `${Math.round(pair.success_rate * 100)}%`
                  : '–'}
              </p>
            </div>
            <div className="text-right">
              <div
                className={`text-lg font-bold ${
                  tone === 'good' ? 'text-emerald-400' : 'text-amber-300'
                }`}
              >
                {pair.score.toFixed(2)}
              </div>
              <p className="text-xs text-muted-foreground">
                {pair.lines_per_hour
                  ? `${pair.lines_per_hour.toFixed(0)} LOC/hr`
                  : 'LOC/hr n/a'}
              </p>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-foreground">Pairing Analytics</h2>
        <div className="flex items-center gap-2">
          {rangeButtons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => setDateRange(btn.value)}
              className={`px-3 py-1 rounded-md text-xs font-semibold border transition-colors ${
                dateRange === btn.value
                  ? 'border-cyan-400 text-cyan-300 bg-cyan-400/10'
                  : 'border-border text-muted-foreground hover:text-foreground hover:bg-accent/30'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <ArrowLeftRight className="w-4 h-4 text-cyan-300" />
            <h3 className="text-lg font-semibold">Top Pairings</h3>
          </div>
          {renderPairList(pairing_top, 'good')}
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <ArrowLeftRight className="w-4 h-4 text-amber-300" />
            <h3 className="text-lg font-semibold">Pairs Needing Attention</h3>
          </div>
          {renderPairList(pairing_bottom, 'bad')}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-purple-300" />
              <h3 className="text-lg font-semibold">Role Dynamics</h3>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Agent-led</span>
              <span className="font-semibold">{role_dynamics.agent_led}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Dev-led</span>
              <span className="font-semibold">{role_dynamics.dev_led}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Co-pilot</span>
              <span className="font-semibold">{role_dynamics.co_pilot}</span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <Network className="w-4 h-4 text-emerald-300" />
            <h3 className="text-lg font-semibold">Handoffs</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Count</span>
              <span className="font-semibold">{handoffs.handoff_count}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg response</span>
              <span className="font-semibold">
                {handoffs.avg_response_minutes !== null &&
                handoffs.avg_response_minutes !== undefined
                  ? `${handoffs.avg_response_minutes.toFixed(1)}m`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Success rate</span>
              <span className="font-semibold">
                {handoffs.success_rate !== null && handoffs.success_rate !== undefined
                  ? `${Math.round(handoffs.success_rate * 100)}%`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Clarifications</span>
              <span className="font-semibold">
                {handoffs.clarifications_avg !== null &&
                handoffs.clarifications_avg !== undefined
                  ? handoffs.clarifications_avg.toFixed(1)
                  : '–'}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-cyan-300" />
            <h3 className="text-lg font-semibold">Impact</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Avg LOC/hour</span>
              <span className="font-semibold">
                {impact.avg_lines_per_hour !== null && impact.avg_lines_per_hour !== undefined
                  ? impact.avg_lines_per_hour.toFixed(0)
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Median time to first change</span>
              <span className="font-semibold">
                {impact.median_first_change_minutes !== null &&
                impact.median_first_change_minutes !== undefined
                  ? `${impact.median_first_change_minutes.toFixed(1)}m`
                  : '–'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total lines changed</span>
              <span className="font-semibold">{impact.total_lines_changed}</span>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-blue-300" />
            <h3 className="text-lg font-semibold">Thinking Time</h3>
          </div>
          {thinking_time ? (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Median</span>
                <span className="font-semibold">
                  {thinking_time.median_latency_seconds !== null &&
                  thinking_time.median_latency_seconds !== undefined
                    ? `${thinking_time.median_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">P95</span>
                <span className="font-semibold">
                  {thinking_time.p95_latency_seconds !== null &&
                  thinking_time.p95_latency_seconds !== undefined
                    ? `${thinking_time.p95_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Max</span>
                <span className="font-semibold">
                  {thinking_time.max_latency_seconds !== null &&
                  thinking_time.max_latency_seconds !== undefined
                    ? `${thinking_time.max_latency_seconds.toFixed(1)}s`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">% with thinking</span>
                <span className="font-semibold">
                  {thinking_time.pct_with_thinking !== null &&
                  thinking_time.pct_with_thinking !== undefined
                    ? `${Math.round(thinking_time.pct_with_thinking * 100)}%`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">% with tool calls</span>
                <span className="font-semibold">
                  {thinking_time.pct_with_tool_calls !== null &&
                  thinking_time.pct_with_tool_calls !== undefined
                    ? `${Math.round(thinking_time.pct_with_tool_calls * 100)}%`
                    : '–'}
                </span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Pairs</span>
                <span>{thinking_time.pair_count}</span>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No thinking-time data.</p>
          )}
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-5">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquare className="w-4 h-4 text-blue-300" />
          <h3 className="text-lg font-semibold">Sentiment by Agent</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sentiment_by_agent.length === 0 ? (
            <p className="text-muted-foreground text-sm col-span-full">
              No sentiment data.
            </p>
          ) : (
            sentiment_by_agent.map((s) => (
              <div
                key={s.agent_type}
                className="border border-border/50 rounded-md p-3 bg-slate-900/30"
              >
                <p className="font-semibold">{s.agent_type}</p>
                <p className="text-xs text-muted-foreground mb-1">
                  {s.sessions} sessions
                </p>
                <p className="text-lg font-bold">
                  {s.avg_sentiment !== null && s.avg_sentiment !== undefined
                    ? s.avg_sentiment.toFixed(2)
                    : '–'}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {(influence_flows.length > 0 || error_heatmap.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {influence_flows.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <ArrowLeftRight className="w-4 h-4 text-cyan-300" />
                <h3 className="text-lg font-semibold">Influence Flows</h3>
              </div>
              <div className="space-y-2">
                {influence_flows.map((flow) => (
                  <div
                    key={`${flow.source}-${flow.target}`}
                    className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
                  >
                    <div>
                      <p className="font-semibold text-foreground">
                        {flow.source} → {flow.target}
                      </p>
                    </div>
                    <p className="text-sm font-bold text-cyan-300">{flow.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error_heatmap.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-5">
              <div className="flex items-center gap-2 mb-3">
                <Network className="w-4 h-4 text-amber-300" />
                <h3 className="text-lg font-semibold">Error Heatmap</h3>
              </div>
              <div className="space-y-2">
                {error_heatmap.map((bucket) => (
                  <div
                    key={`${bucket.agent_type}-${bucket.category}`}
                    className="flex items-center justify-between border border-border/50 rounded-md px-3 py-2 bg-slate-900/30"
                  >
                    <div>
                      <p className="font-semibold text-foreground">{bucket.agent_type}</p>
                      <p className="text-xs text-muted-foreground">{bucket.category}</p>
                    </div>
                    <p className="text-sm font-bold text-amber-300">{bucket.count}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
