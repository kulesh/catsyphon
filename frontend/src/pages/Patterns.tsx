/**
 * Workflow pattern library page.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getWorkflowPatterns, getAgentPatterns } from '@/lib/api';
import type { AgentPatterns } from '@/types/api';
import { Activity, AlertTriangle, Bot } from 'lucide-react';

export default function Patterns() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['patterns', 'workflow'],
    queryFn: () => getWorkflowPatterns(),
    staleTime: 60000,
  });

  const { data: agentData } = useQuery<AgentPatterns>({
    queryKey: ['patterns', 'agents'],
    queryFn: () => getAgentPatterns(),
    staleTime: 60000,
  });

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center py-12">
          <p className="text-muted-foreground">Loading workflow patterns...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <div className="observatory-card border-destructive/50 p-6">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-destructive" />
            <h3 className="font-heading text-lg text-destructive">Pattern Error</h3>
          </div>
          <p className="font-mono text-sm text-destructive/80">
            {error.message}
          </p>
        </div>
      </div>
    );
  }

  const items = data?.items || [];

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto p-6">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-6 h-6 text-cyan-400" />
            <h1 className="text-3xl font-heading text-foreground">Workflow Patterns</h1>
          </div>
          <p className="text-muted-foreground font-mono text-sm">
            Passive pattern signals derived from conversation insights.
          </p>
        </div>

        {items.length === 0 ? (
          <div className="observatory-card p-6">
            <p className="text-sm text-muted-foreground">
              No workflow patterns available yet. Generate insights on conversations
              to populate this library.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {items.map((item) => (
              <div key={item.pattern} className="observatory-card p-6">
                <div className="flex items-center justify-between gap-4 flex-wrap mb-3">
                  <h2 className="text-lg font-semibold text-foreground">
                    {item.pattern}
                  </h2>
                  <div className="text-xs font-mono text-muted-foreground">
                    {item.count} sessions
                    {item.success_rate !== null && item.success_rate !== undefined && (
                      <> • {Math.round(item.success_rate * 100)}% success</>
                    )}
                  </div>
                </div>

                {item.examples.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-medium text-muted-foreground">
                      Examples
                    </h3>
                    {item.examples.map((example) => (
                      <div
                        key={example.conversation_id}
                        className="flex items-start justify-between gap-4 rounded-md bg-muted/40 p-3"
                      >
                        <div>
                          <Link
                            to={`/conversations/${example.conversation_id}`}
                            className="text-sm font-medium text-primary hover:underline"
                          >
                            {example.summary || example.conversation_id}
                          </Link>
                          {example.outcome && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Outcome: {example.outcome}
                            </p>
                          )}
                        </div>
                        <Link
                          to={`/conversations/${example.conversation_id}`}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          View
                        </Link>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Agent Delegation Patterns */}
        {agentData && agentData.agent_types.length > 0 && (
          <div className="mt-12">
            <div className="flex items-center gap-3 mb-6">
              <Bot className="w-6 h-6 text-purple-400" />
              <h2 className="text-2xl font-heading text-foreground">Agent Delegation Patterns</h2>
              <span className="text-xs font-mono text-muted-foreground">
                {agentData.total_agent_conversations} conversations • {agentData.total_metadata_files} metadata files
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
              {agentData.agent_types.map((agent) => (
                <div key={agent.type} className="observatory-card p-5 group hover:border-purple-400/30 transition-all">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-mono font-semibold text-foreground">
                      {agent.type}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      {agent.conversation_count} sessions
                    </span>
                  </div>
                  {agent.success_rate != null && (
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs font-mono">
                        <span className="text-muted-foreground">success rate</span>
                        <span className={agent.success_rate >= 70 ? 'text-emerald-400' : agent.success_rate >= 40 ? 'text-amber-400' : 'text-rose-400'}>
                          {agent.success_rate}%
                        </span>
                      </div>
                      <div className="relative h-1.5 bg-slate-900/50 rounded-full overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 rounded-full ${
                            agent.success_rate >= 70 ? 'bg-emerald-400' : agent.success_rate >= 40 ? 'bg-amber-400' : 'bg-rose-400'
                          }`}
                          style={{ width: `${Math.min(agent.success_rate, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {agentData.common_descriptions.length > 0 && (
              <div className="observatory-card p-5">
                <h3 className="text-xs font-mono font-semibold tracking-wider uppercase text-muted-foreground mb-3">
                  Common Delegation Descriptions
                </h3>
                <div className="space-y-2">
                  {agentData.common_descriptions.slice(0, 10).map((desc, i) => (
                    <div key={i} className="flex items-center justify-between text-xs font-mono">
                      <span className="text-foreground/80 truncate mr-4">{desc.description}</span>
                      <span className="text-muted-foreground shrink-0">{desc.count}×</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
