/**
 * Project List page - Browse all projects with session counts and recent activity.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getProjects } from '@/lib/api';
import type { RecentSession } from '@/types/api';
import { Folder, ChevronRight, CircleDot } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

// --- Intent styling ---

const intentConfig: Record<string, { dot: string; badge: string; label: string }> = {
  feature_add: { dot: 'text-emerald-500', badge: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400', label: 'feature' },
  bug_fix:     { dot: 'text-amber-500',   badge: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',       label: 'bugfix' },
  refactor:    { dot: 'text-blue-500',     badge: 'bg-blue-500/10 text-blue-700 dark:text-blue-400',           label: 'refactor' },
  learning:    { dot: 'text-violet-500',   badge: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',     label: 'learning' },
  debugging:   { dot: 'text-orange-500',   badge: 'bg-orange-500/10 text-orange-700 dark:text-orange-400',     label: 'debug' },
};

const defaultIntent = { dot: 'text-muted-foreground/40', badge: 'bg-muted text-muted-foreground', label: 'session' };

function outcomeIndicator(outcome: string | null): string {
  if (outcome === 'success') return 'text-emerald-500';
  if (outcome === 'partial') return 'text-amber-500';
  if (outcome === 'failed') return 'text-red-500';
  return 'text-muted-foreground/30';
}

function SessionChip({ session }: { session: RecentSession }) {
  const intent = (session.intent && intentConfig[session.intent]) || defaultIntent;
  const displayText = session.feature || intent.label;

  return (
    <div className="flex items-center gap-1.5 min-w-0 max-w-xs">
      <CircleDot className={`w-3 h-3 shrink-0 ${outcomeIndicator(session.outcome)}`} />
      <span className={`px-1.5 py-px rounded text-[10px] font-medium shrink-0 ${intent.badge}`}>
        {intent.label}
      </span>
      {session.feature && (
        <span className="text-xs text-foreground/70 truncate" title={session.feature}>
          {displayText}
        </span>
      )}
      <span className="text-[11px] text-muted-foreground/50 whitespace-nowrap ml-auto tabular-nums">
        {formatDistanceToNow(new Date(session.last_active), { addSuffix: true })}
      </span>
    </div>
  );
}

export default function ProjectList() {
  const navigate = useNavigate();

  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-6">
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <p className="text-destructive text-sm font-medium">Failed to load projects</p>
          <p className="text-xs text-muted-foreground mt-1">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-6">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold">Projects</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {projects ? `${projects.length} projects` : 'Loading...'}
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-4 animate-pulse">
              <div className="h-4 bg-muted rounded w-1/4 mb-2"></div>
              <div className="h-3 bg-muted rounded w-1/2"></div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && projects && projects.length === 0 && (
        <div className="bg-card border border-border rounded-lg p-10 text-center">
          <Folder className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <h3 className="text-base font-medium mb-1">No projects yet</h3>
          <p className="text-sm text-muted-foreground">
            Upload conversation logs to get started
          </p>
        </div>
      )}

      {/* Project Cards */}
      {!isLoading && projects && projects.length > 0 && (
        <div className="space-y-2">
          {projects.map((project, index) => {
            const hasActivity = project.recent_sessions.length > 0;
            return (
              <button
                key={project.id}
                onClick={() => navigate(`/projects/${project.id}`)}
                className="group relative w-full bg-card border border-border/60 rounded-lg px-4 py-3 text-left hover:border-primary/40 hover:shadow-md hover:shadow-primary/5 transition-all duration-200"
                style={{ animation: `fadeIn 0.3s ease-out ${index * 0.05}s both` }}
              >
                <div className="flex items-center gap-3">
                  {/* Icon */}
                  <div className="shrink-0 w-8 h-8 rounded-md bg-primary/8 flex items-center justify-center group-hover:bg-primary/12 transition-colors">
                    <Folder className="w-4 h-4 text-primary" />
                  </div>

                  {/* Name + path */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <h3 className="text-sm font-semibold group-hover:text-primary transition-colors truncate">
                        {project.name}
                      </h3>
                      {project.directory_path && (
                        <span className="text-[11px] font-mono text-muted-foreground/50 truncate hidden sm:inline">
                          {project.directory_path}
                        </span>
                      )}
                    </div>
                    {project.description && (
                      <p className="text-xs text-muted-foreground/70 truncate mt-0.5">
                        {project.description}
                      </p>
                    )}
                  </div>

                  {/* Inline metrics */}
                  <div className="hidden sm:flex items-center gap-4 shrink-0 text-xs">
                    <div className="text-right">
                      <span className="font-mono font-bold text-sm tabular-nums">{project.session_count}</span>
                      <span className="text-muted-foreground/60 ml-1">sessions</span>
                    </div>
                    {project.last_session_at && (
                      <span className="text-muted-foreground/50 tabular-nums whitespace-nowrap">
                        {formatDistanceToNow(new Date(project.last_session_at), { addSuffix: true })}
                      </span>
                    )}
                  </div>

                  {/* Arrow */}
                  <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground/30 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </div>

                {/* Recent activity strip */}
                {hasActivity && (
                  <div className="mt-2 pt-2 border-t border-border/40 flex flex-wrap gap-x-6 gap-y-1">
                    {project.recent_sessions.map((rs) => (
                      <SessionChip key={rs.id} session={rs} />
                    ))}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
