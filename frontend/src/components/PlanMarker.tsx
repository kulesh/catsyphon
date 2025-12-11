/**
 * PlanMarker - Inline markers for plan mode events in message timeline
 */

import { ClipboardList, CheckCircle2, XCircle, FileEdit } from 'lucide-react';

export type PlanMarkerType = 'entry' | 'approved' | 'abandoned' | 'edit';

interface PlanMarkerProps {
  type: PlanMarkerType;
  onClick?: () => void;
}

const markerConfig: Record<
  PlanMarkerType,
  {
    icon: React.ReactNode;
    label: string;
    bg: string;
    text: string;
    border: string;
  }
> = {
  entry: {
    icon: <ClipboardList className="w-3 h-3" />,
    label: 'Plan Mode Started',
    bg: 'bg-cyan-400/10',
    text: 'text-cyan-400',
    border: 'border-cyan-400/30',
  },
  approved: {
    icon: <CheckCircle2 className="w-3 h-3" />,
    label: 'Plan Approved',
    bg: 'bg-emerald-400/10',
    text: 'text-emerald-400',
    border: 'border-emerald-400/30',
  },
  abandoned: {
    icon: <XCircle className="w-3 h-3" />,
    label: 'Plan Abandoned',
    bg: 'bg-slate-400/10',
    text: 'text-slate-400',
    border: 'border-slate-400/30',
  },
  edit: {
    icon: <FileEdit className="w-3 h-3" />,
    label: 'Plan Updated',
    bg: 'bg-amber-400/10',
    text: 'text-amber-400',
    border: 'border-amber-400/30',
  },
};

export function PlanMarker({ type, onClick }: PlanMarkerProps) {
  const config = markerConfig[type];

  const Component = onClick ? 'button' : 'span';

  return (
    <Component
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full font-mono text-[10px] uppercase tracking-wide border ${config.bg} ${config.text} ${config.border} ${onClick ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
    >
      {config.icon}
      {config.label}
    </Component>
  );
}

export default PlanMarker;
