/**
 * Project List page - Browse all projects with session counts.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getProjects } from '@/lib/api';
import { Folder, TrendingUp } from 'lucide-react';

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
        <div className="grid grid-cols-1 gap-4">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => navigate(`/projects/${project.id}`)}
              className="bg-card border border-border rounded-lg p-6 text-left hover:border-primary/50 hover:shadow-md transition-all group"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Folder className="w-5 h-5 text-primary" />
                    <h3 className="text-xl font-bold group-hover:text-primary transition-colors">
                      {project.name}
                    </h3>
                  </div>

                  {project.description && (
                    <p className="text-muted-foreground text-sm mb-3">
                      {project.description}
                    </p>
                  )}

                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4" />
                      <span className="font-mono">View Analytics</span>
                    </div>
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
