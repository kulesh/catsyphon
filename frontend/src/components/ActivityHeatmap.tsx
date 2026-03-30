interface HeatmapCell {
  hour: number;
  count: number;
}

interface ActivityHeatmapProps {
  data: HeatmapCell[];
}

export default function ActivityHeatmap({ data }: ActivityHeatmapProps) {
  if (data.length === 0) return null;

  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const cellSize = 24;
  const gap = 2;
  const labelWidth = 30;

  // Build hour → count map
  const hourMap = new Map(data.map((d) => [d.hour, d.count]));

  return (
    <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-slate-700/50 rounded-xl p-6">
      <h4 className="text-sm font-mono font-semibold tracking-wider uppercase text-muted-foreground mb-4">
        Activity by Hour
      </h4>
      <div className="flex items-end gap-1">
        {Array.from({ length: 24 }, (_, hour) => {
          const count = hourMap.get(hour) || 0;
          const intensity = count / maxCount;
          const opacity = count === 0 ? 0.05 : 0.15 + intensity * 0.85;
          return (
            <div key={hour} className="flex flex-col items-center gap-1">
              <div
                className="rounded-sm transition-colors"
                style={{
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(34, 211, 238, ${opacity})`,
                }}
                title={`${hour}:00 — ${count} sessions`}
              />
              {hour % 3 === 0 && (
                <span className="text-[9px] font-mono text-muted-foreground">
                  {hour.toString().padStart(2, '0')}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
