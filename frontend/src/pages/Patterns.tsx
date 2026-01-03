/**
 * Workflow pattern library page.
 */

import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getWorkflowPatterns } from '@/lib/api';
import { Activity, AlertTriangle } from 'lucide-react';

export default function Patterns() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['patterns', 'workflow'],
    queryFn: () => getWorkflowPatterns(),
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
      </div>
    </div>
  );
}
