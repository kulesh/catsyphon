/**
 * Project List page - Browse all projects with session counts.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getProjects } from '@/lib/api';
import { Folder, Activity, Clock, ChevronRight } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export default function ProjectList() {
  const navigate = useNavigate();

  // Fetch projects
  const { data: projects, isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  if (error) {
    return (
      <div className="container mx-auto px-6 py-8">
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
          <p className="text-destructive font-medium">Failed to load projects</p>
          <p className="text-sm text-muted-foreground mt-2">
            {error instanceof Error ? error.message : 'Unknown error'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-6 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Projects</h1>
        <p className="text-muted-foreground">
          Browse analytics for all your projects
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-card border border-border rounded-lg p-6 animate-pulse"
            >
              <div className="h-6 bg-muted rounded w-1/3 mb-3"></div>
              <div className="h-4 bg-muted rounded w-2/3"></div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && projects && projects.length === 0 && (
        <div className="bg-card border border-border rounded-lg p-12 text-center">
          <Folder className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No projects yet</h3>
          <p className="text-sm text-muted-foreground">
            Upload conversation logs to get started
          </p>
        </div>
      )}

      {/* Project Cards */}
      {!isLoading && projects && projects.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {projects.map((project, index) => (
            <button
              key={project.id}
              onClick={() => navigate(`/projects/${project.id}`)}
              className="group relative bg-card border border-border/60 rounded-lg p-6 text-left hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5 transition-all duration-300"
              style={{
                animation: `fadeInUp 0.4s ease-out ${index * 0.08}s both`
              }}
            >
              {/* Subtle gradient overlay on hover */}
              <div className="absolute inset-0 bg-gradient-to-br from-primary/0 to-primary/0 group-hover:from-primary/3 group-hover:to-transparent rounded-lg transition-all duration-500 pointer-events-none" />

              <div className="relative flex items-start justify-between gap-6">
                <div className="flex-1 min-w-0">
                  {/* Project Header */}
                  <div className="flex items-center gap-3 mb-3">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center group-hover:bg-primary/15 transition-colors">
                      <Folder className="w-5 h-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold tracking-tight group-hover:text-primary transition-colors truncate">
                        {project.name}
                      </h3>
                      {project.directory_path && (
                        <p className="text-xs font-mono text-muted-foreground/70 truncate mt-0.5">
                          {project.directory_path}
                        </p>
                      )}
                    </div>
                  </div>

                  {project.description && (
                    <p className="text-sm text-muted-foreground leading-relaxed mb-4 line-clamp-2">
                      {project.description}
                    </p>
                  )}

                  {/* Metrics Row */}
                  <div className="flex items-center gap-6">
                    {/* Session Count */}
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-md bg-blue-500/10 flex items-center justify-center">
                        <Activity className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Sessions</p>
                        <p className="text-lg font-bold font-mono tabular-nums">
                          {project.session_count}
                        </p>
                      </div>
                    </div>

                    {/* Last Activity */}
                    {project.last_session_at && (
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-md bg-emerald-500/10 flex items-center justify-center">
                          <Clock className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                        </div>
                        <div>
                          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Last Active</p>
                          <p className="text-sm font-medium tabular-nums">
                            {formatDistanceToNow(new Date(project.last_session_at), { addSuffix: true })}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Arrow Indicator */}
                <div className="shrink-0 self-center">
                  <ChevronRight className="w-5 h-5 text-muted-foreground/40 group-hover:text-primary group-hover:translate-x-1 transition-all duration-300" />
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      <style>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
