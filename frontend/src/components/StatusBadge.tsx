/**
 * StatusBadge - Unified status badge component for conversation/session status
 */

interface StatusBadgeProps {
  status: string;
  success?: boolean | null;
  variant?: 'observatory' | 'default';
}

export function StatusBadge({ status, success, variant = 'default' }: StatusBadgeProps) {
  if (variant === 'observatory') {
    // Observatory theme: cyan/emerald/rose colors with neon aesthetic
    const colorClass =
      status === 'completed'
        ? 'bg-emerald-400/10 border border-emerald-400/30 text-emerald-400'
        : status === 'failed'
          ? 'bg-rose-400/10 border border-rose-400/30 text-rose-400'
          : 'bg-cyan-400/10 border border-cyan-400/30 text-cyan-400';

    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wide ${colorClass}`}>
        {status.replace('_', ' ')}
      </span>
    );
  }

  // Default theme: uses success indicator for color
  let colorClass = 'bg-muted/50 text-muted-foreground';

  if (success === true) {
    colorClass = 'bg-green-500/10 text-green-600 border-green-500/20';
  } else if (success === false) {
    colorClass = 'bg-destructive/10 text-destructive border-destructive/20';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colorClass}`}>
      {status}
    </span>
  );
}
