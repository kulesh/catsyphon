import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { DollarSign, TrendingUp, FileText, Percent } from 'lucide-react';
import { getProjectCosts } from '@/lib/api';
import type { ProjectCosts } from '@/types/api';
import CostChart from '@/components/CostChart';

interface CostTabProps {
  projectId: string;
}

export default function CostTab({ projectId }: CostTabProps) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');

  const { data: costs, isLoading } = useQuery<ProjectCosts>({
    queryKey: ['project-costs', projectId, dateRange],
    queryFn: () => getProjectCosts(projectId, dateRange),
    staleTime: 300000,
  });

  const rangeButtons = [
    { label: '7D', value: '7d' as const },
    { label: '30D', value: '30d' as const },
    { label: '90D', value: '90d' as const },
    { label: 'All', value: 'all' as const },
  ];

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="observatory-card p-6 h-28" />
          ))}
        </div>
      </div>
    );
  }

  if (!costs) return null;

  const metrics = [
    {
      label: 'Total Cost',
      value: `$${costs.total_cost_usd.toFixed(2)}`,
      icon: DollarSign,
      color: 'amber',
    },
    {
      label: '$ / Conversation',
      value: costs.cost_per_conversation != null ? `$${costs.cost_per_conversation.toFixed(4)}` : '—',
      icon: TrendingUp,
      color: 'cyan',
    },
    {
      label: '$ / File Changed',
      value: costs.cost_per_file_changed != null ? `$${costs.cost_per_file_changed.toFixed(4)}` : '—',
      icon: FileText,
      color: 'emerald',
    },
    {
      label: 'Cache Hit Ratio',
      value: `${(costs.cache_ratio * 100).toFixed(0)}%`,
      icon: Percent,
      color: 'purple',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Date range selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-mono text-muted-foreground">Period:</span>
        {rangeButtons.map((btn) => (
          <button
            key={btn.value}
            onClick={() => setDateRange(btn.value)}
            className={`px-3 py-1 text-xs font-mono rounded-md transition-colors ${
              dateRange === btn.value
                ? 'bg-cyan-400/20 text-cyan-400 border border-cyan-400/30'
                : 'text-muted-foreground hover:text-foreground border border-transparent'
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Hero metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {metrics.map((m) => (
          <div
            key={m.label}
            className={`observatory-card p-6 group hover:border-${m.color}-400/30 transition-all`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-muted-foreground tracking-wider uppercase">
                {m.label}
              </span>
              <m.icon className={`w-4 h-4 text-${m.color}-400/60 group-hover:text-${m.color}-400`} />
            </div>
            <div className={`text-2xl font-mono font-bold text-${m.color}-400`}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* Daily cost chart */}
      {costs.daily_costs.length > 0 && <CostChart data={costs.daily_costs} />}

      {/* Model breakdown */}
      {Object.keys(costs.cost_by_model).length > 0 && (
        <div className="observatory-card p-6">
          <h4 className="text-sm font-mono font-semibold tracking-wider uppercase text-muted-foreground mb-4">
            Cost by Model
          </h4>
          <div className="space-y-3">
            {Object.entries(costs.cost_by_model).map(([model, cost]) => {
              const pct = costs.total_cost_usd > 0 ? (cost / costs.total_cost_usd) * 100 : 0;
              return (
                <div key={model} className="space-y-1">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-foreground/80">{model}</span>
                    <span className="text-amber-400">${cost.toFixed(4)}</span>
                  </div>
                  <div className="relative h-1.5 bg-slate-900/50 rounded-full overflow-hidden">
                    <div
                      className="absolute inset-y-0 left-0 bg-gradient-to-r from-amber-500 to-amber-400 rounded-full"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4 text-xs font-mono text-muted-foreground">
        <div>Conversations: <span className="text-foreground/80">{costs.conversation_count}</span></div>
        <div>Files Changed: <span className="text-foreground/80">{costs.total_files_changed}</span></div>
      </div>
    </div>
  );
}
