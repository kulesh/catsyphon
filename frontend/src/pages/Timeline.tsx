import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getActivityTimeline } from '@/lib/api';
import type { ActivityTimeline as ActivityTimelineType } from '@/types/api';
import ActivityHeatmap from '@/components/ActivityHeatmap';

export default function Timeline() {
  const [days, setDays] = useState(7);
  const [search, setSearch] = useState('');

  const { data: timeline, isLoading } = useQuery<ActivityTimelineType>({
    queryKey: ['activity-timeline', days],
    queryFn: () => getActivityTimeline(days, 500),
    staleTime: 60000,
  });

  const filteredEntries = timeline?.entries.filter((e) =>
    search ? e.display.toLowerCase().includes(search.toLowerCase()) ||
             (e.project || '').toLowerCase().includes(search.toLowerCase())
    : true
  ) || [];

  const dayButtons = [
    { label: '7D', value: 7 },
    { label: '14D', value: 14 },
    { label: '30D', value: 30 },
    { label: '60D', value: 60 },
    { label: '90D', value: 90 },
  ];

  function getRelativeTime(ts: number): string {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-cyan-400" />
          <h1 className="text-2xl font-mono font-bold">Activity Timeline</h1>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-1">
          {dayButtons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => setDays(btn.value)}
              className={`px-3 py-1 text-xs font-mono rounded-md transition-colors ${
                days === btn.value
                  ? 'bg-cyan-400/20 text-cyan-400 border border-cyan-400/30'
                  : 'text-muted-foreground hover:text-foreground border border-transparent'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search prompts or projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm font-mono bg-slate-900/50 border border-slate-700/50 rounded-lg focus:outline-none focus:border-cyan-400/50"
          />
        </div>
      </div>

      {/* Heatmap */}
      {timeline?.heatmap && timeline.heatmap.length > 0 && (
        <ActivityHeatmap data={timeline.heatmap} />
      )}

      {/* Timeline entries */}
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(10)].map((_, i) => (
            <div key={i} className="h-12 bg-slate-800/50 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="space-y-1">
          {filteredEntries.map((entry, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 px-4 py-2.5 rounded-lg text-sm font-mono transition-colors hover:bg-slate-800/30 ${
                entry.project_switch ? 'border-t border-cyan-400/20 mt-2 pt-4' : ''
              }`}
            >
              <span className="text-muted-foreground whitespace-nowrap w-16 shrink-0 text-xs">
                {getRelativeTime(entry.timestamp)}
              </span>
              {entry.source && (
                <span className={`px-1.5 py-0.5 rounded text-[10px] shrink-0 ${
                  entry.source === 'claude'
                    ? 'bg-purple-400/10 text-purple-400'
                    : 'bg-emerald-400/10 text-emerald-400'
                }`}>
                  {entry.source}
                </span>
              )}
              {entry.project && (
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400 text-xs whitespace-nowrap shrink-0">
                  {entry.project.split('/').pop()}
                </span>
              )}
              <span className="text-foreground/80 truncate">
                {entry.conversation_id ? (
                  <Link
                    to={`/conversations/${entry.conversation_id}`}
                    className="hover:text-cyan-400 transition-colors"
                  >
                    {entry.display}
                  </Link>
                ) : (
                  entry.display
                )}
              </span>
            </div>
          ))}
          {filteredEntries.length === 0 && (
            <div className="text-center py-12 text-muted-foreground font-mono">
              No activity found
            </div>
          )}
        </div>
      )}
    </div>
  );
}
