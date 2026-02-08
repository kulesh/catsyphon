/**
 * Project Detail page - Deep-dive analytics for a single project.
 *
 * Features five tabs:
 * - Stats: Overview metrics, health report, and pairing highlights
 * - Analytics: Pairing effectiveness, role dynamics, and handoff metrics
 * - Insights: AI-generated collaboration quality scores and patterns
 * - Sessions: Paginated list of all conversations
 * - Files: Aggregated file modification statistics
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getProjects } from '@/lib/api';
import {
  BarChart3,
  FileText,
  Activity,
  Brain,
  Lightbulb,
  Folder,
} from 'lucide-react';
import { TabNavigation, type TabDefinition } from '@/components';
import StatsTab from './StatsTab';
import AnalyticsTab from './AnalyticsTab';
import InsightsTab from './InsightsTab';
import SessionsTab from './SessionsTab';
import FilesTab from './FilesTab';

type Tab = 'stats' | 'analytics' | 'insights' | 'sessions' | 'files';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('stats');

  const { data: projects } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const project = projects?.find((p) => p.id === id);

  if (!id) {
    return (
      <div className="container mx-auto px-6 py-8">
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-6">
          <p className="text-destructive font-medium">Project ID is required</p>
        </div>
      </div>
    );
  }

  const tabs: TabDefinition<Tab>[] = [
    { id: 'stats', label: 'Stats & Insights', icon: BarChart3 },
    { id: 'analytics', label: 'Pairing Analytics', icon: Brain },
    { id: 'insights', label: 'AI Insights', icon: Lightbulb },
    { id: 'sessions', label: 'Sessions', icon: Activity },
    { id: 'files', label: 'Files', icon: FileText },
  ];

  return (
    <div className="container mx-auto px-6 py-8">
      {/* Observatory Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center glow-amber">
              <Folder className="w-6 h-6 text-slate-950" />
            </div>
            <div>
              <h1 className="text-3xl font-display tracking-wide text-foreground">
                {project?.name?.toUpperCase() || 'LOADING...'}
              </h1>
              {project?.description && (
                <p className="text-sm font-mono text-muted-foreground mt-1">
                  {project.description}
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => navigate('/projects')}
            className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 transition-all"
          >
            ← Projects
          </button>
        </div>
      </div>

      {/* Observatory Tab Navigation */}
      <TabNavigation tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Tab Content */}
      <div className="animate-in fade-in duration-300">
        {activeTab === 'stats' && <StatsTab projectId={id} />}
        {activeTab === 'analytics' && <AnalyticsTab projectId={id} />}
        {activeTab === 'insights' && <InsightsTab projectId={id} />}
        {activeTab === 'sessions' && <SessionsTab projectId={id} />}
        {activeTab === 'files' && <FilesTab projectId={id} />}
      </div>
    </div>
  );
}
