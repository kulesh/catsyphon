/**
 * SessionTable - Unified session/conversation table component
 */

import { format } from 'date-fns';
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import type { ConversationListItem, ProjectSession } from '@/types/api';

type Session = ConversationListItem | ProjectSession;

export interface ColumnConfig {
  id: string;
  label: string;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  render: (session: Session) => React.ReactNode;
}

interface SessionTableProps {
  sessions: Session[];
  columns: ColumnConfig[];
  onRowClick: (id: string) => void;
  /** New item IDs to highlight (Observatory theme only) */
  highlightNewIds?: Set<string>;
  /** Table variant */
  variant?: 'observatory' | 'default';
  /** Sorting configuration */
  sorting?: {
    sortBy: string;
    order: 'asc' | 'desc';
    onSort: (columnId: string) => void;
  };
  /** Empty state message */
  emptyMessage?: string;
  emptyHint?: string;
}

export function SessionTable({
  sessions,
  columns,
  onRowClick,
  highlightNewIds,
  variant = 'default',
  sorting,
  emptyMessage = 'No sessions found',
  emptyHint,
}: SessionTableProps) {
  const isObservatory = variant === 'observatory';

  // Empty state
  if (sessions.length === 0) {
    return (
      <div className={isObservatory ? 'observatory-card overflow-hidden' : 'bg-card border border-border rounded-lg overflow-hidden'}>
        <table className="w-full">
          <thead>
            <tr className={isObservatory ? 'bg-slate-900/50 border-b border-border/50' : 'bg-muted/50'}>
              {columns.map((col) => (
                <th
                  key={col.id}
                  className={`px-${isObservatory ? '4' : '6'} py-3 text-${col.align || 'left'} text-xs font-${isObservatory ? 'mono' : 'medium'} ${isObservatory ? 'font-semibold' : ''} text-muted-foreground uppercase tracking-wider`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={columns.length} className={`px-${isObservatory ? '4' : '6'} py-12 text-center`}>
                <p className={`font-${isObservatory ? 'mono' : 'medium'} text-sm text-muted-foreground`}>
                  {isObservatory ? emptyMessage.toUpperCase() : emptyMessage}
                </p>
                {emptyHint && (
                  <p className={`font-${isObservatory ? 'mono' : 'normal'} text-xs text-muted-foreground${isObservatory ? '/60' : ''} mt-1`}>
                    {emptyHint}
                  </p>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  // Table with data
  return (
    <div className={isObservatory ? 'observatory-card overflow-hidden' : 'bg-card border border-border rounded-lg overflow-hidden'}>
      <table className={isObservatory ? 'w-full' : 'min-w-full divide-y divide-border'}>
        <thead>
          <tr className={isObservatory ? 'bg-slate-900/50 border-b border-border/50' : 'bg-muted/50'}>
            {columns.map((col) => {
              const isSortable = col.sortable && sorting;
              const isSorted = sorting?.sortBy === col.id;

              if (isSortable) {
                return (
                  <th
                    key={col.id}
                    onClick={() => sorting.onSort(col.id)}
                    className={`px-${isObservatory ? '4' : '6'} py-3 text-${col.align || 'left'} text-xs font-${isObservatory ? 'mono' : 'medium'} ${isObservatory ? 'font-semibold' : ''} text-muted-foreground uppercase tracking-wider cursor-pointer hover:bg-${isObservatory ? 'slate-800/50' : 'muted'} transition-colors`}
                  >
                    <div className="flex items-center gap-2">
                      {col.label}
                      {isSorted ? (
                        sorting.order === 'asc' ? (
                          <ArrowUp className="w-4 h-4" />
                        ) : (
                          <ArrowDown className="w-4 h-4" />
                        )
                      ) : (
                        <ArrowUpDown className="w-4 h-4 opacity-30" />
                      )}
                    </div>
                  </th>
                );
              }

              return (
                <th
                  key={col.id}
                  className={`px-${isObservatory ? '4' : '6'} py-3 text-${col.align || 'left'} text-xs font-${isObservatory ? 'mono' : 'medium'} ${isObservatory ? 'font-semibold' : ''} text-muted-foreground uppercase tracking-wider`}
                >
                  {col.label}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className={isObservatory ? 'divide-y divide-border/30' : 'bg-card divide-y divide-border'}>
          {sessions.map((session) => {
            const isHighlighted = highlightNewIds?.has(session.id);
            const conv = session as ConversationListItem;
            const depthLevel = conv.depth_level ?? 0;
            const isChild = depthLevel > 0;

            return (
              <tr
                key={session.id}
                onClick={() => onRowClick(session.id)}
                className={`group cursor-pointer transition-all ${
                  isObservatory
                    ? `duration-300 hover:bg-cyan-400/5 ${
                        isHighlighted
                          ? 'bg-emerald-400/10 animate-pulse border-l-2 border-l-emerald-400'
                          : isChild
                            ? 'bg-slate-800/30'
                            : ''
                      }`
                    : isChild
                      ? 'bg-muted/30 hover:bg-muted/50'
                      : 'hover:bg-accent'
                }`}
              >
                {columns.map((col) => (
                  <td
                    key={col.id}
                    className={`px-${isObservatory ? '4' : '6'} py-${isObservatory ? '3.5' : '4'} ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''} ${col.id.includes('time') || col.id === 'messages' ? 'whitespace-nowrap' : ''}`}
                    style={col.id === 'agent_type' && isChild ? { paddingLeft: `calc(${isObservatory ? '1rem' : '1.5rem'} + 1em)` } : undefined}
                  >
                    {col.render(session)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ===== Helper Render Functions =====
// Exported in a separate object to avoid react-refresh issues

/**
 * Render functions for common column types.
 * These can be used in column config or as reference for custom renders.
 */

// eslint-disable-next-line react-refresh/only-export-components
export const renderHelpers = {
  /** Format start time */
  startTime: (session: Session, variant: 'observatory' | 'default' = 'default') => (
    <span className={`font-mono text-${variant === 'observatory' ? 'xs' : 'sm'} text-foreground${variant === 'observatory' ? '/90' : ''}`}>
      {format(
        new Date(session.start_time),
        variant === 'observatory' ? 'MMM dd, yyyy HH:mm' : 'PPp'
      )}
    </span>
  ),

  /** Format last activity / end time */
  lastActivity: (session: Session) => {
    const conv = session as ConversationListItem;
    return (
      <span className="font-mono text-xs text-muted-foreground">
        {conv.end_time ? format(new Date(conv.end_time), 'MMM dd, yyyy HH:mm') : '---'}
      </span>
    );
  },

  /** Format duration */
  duration: (session: Session) => {
    const projSession = session as ProjectSession;
    return (
      <span className="font-mono text-sm">
        {projSession.duration_seconds ? `${Math.round(projSession.duration_seconds / 60)}m` : '-'}
      </span>
    );
  },

  /** Format project name */
  project: (session: Session) => {
    const conv = session as ConversationListItem;
    return <span className="font-mono text-xs text-foreground/80">{conv.project?.name || '---'}</span>;
  },

  /** Format developer (Observatory style) */
  developerObservatory: (session: Session) => {
    const developer = (session as ConversationListItem).developer?.username || (session as ProjectSession).developer;
    return <span className="font-mono text-xs text-cyan-400/90">{developer || '---'}</span>;
  },

  /** Format developer (Default style) */
  developer: (session: Session) => {
    const developer = (session as ConversationListItem).developer?.username || (session as ProjectSession).developer;
    return <span className="text-sm">{developer || '-'}</span>;
  },

  /** Format agent type with badges */
  agentType: (session: Session) => {
    const conv = session as ConversationListItem;
    const projSession = session as ProjectSession;

    // Check if this is a sub-agent:
    // - ConversationListItem: conversation_type === 'agent'
    // - ProjectSession: depth_level > 0
    const isSubAgent = conv.conversation_type === 'agent' || (projSession.depth_level !== undefined && projSession.depth_level > 0);

    return (
      <div className="flex items-center gap-2">
        {isSubAgent && (
          <span
            className="inline-flex items-center px-1.5 py-0.5 rounded bg-purple-400/10 border border-purple-400/30 text-[10px] font-mono text-purple-400 uppercase tracking-wide"
            title="Agent conversation"
          >
            Sub
          </span>
        )}
        <span className="font-mono text-xs text-foreground/80">{session.agent_type}</span>
        {(conv.children_count ?? 0) > 0 && (
          <span
            className="font-mono text-[10px] text-amber-400"
            title={`${conv.children_count} spawned agent${conv.children_count !== 1 ? 's' : ''}`}
          >
            +{conv.children_count}
          </span>
        )}
      </div>
    );
  },

  /** Format status badge */
  status: (session: Session, variant: 'observatory' | 'default' = 'default') => (
    <StatusBadge status={session.status} success={session.success} variant={variant} />
  ),

  /** Format message count */
  messageCount: (session: Session, variant: 'observatory' | 'default' = 'default') => (
    <span
      className={`font-mono text-${variant === 'observatory' ? 'xs' : 'sm'} ${variant === 'observatory' ? 'text-foreground/90' : ''}`}
      title="Total number of messages in this conversation"
    >
      {session.message_count.toLocaleString()}
    </span>
  ),

  /** Format files count */
  filesCount: (session: Session) => {
    const projSession = session as ProjectSession;
    return <span className="font-mono text-sm">{projSession.files_count}</span>;
  },

  /** Format success indicator (checkmark/X) */
  successIndicator: (session: Session) => {
    if (session.success === null) {
      return (
        <span
          className="font-mono text-xs text-muted-foreground"
          title="Success status unknown or not yet determined"
        >
          ---
        </span>
      );
    }
    if (session.success) {
      return (
        <span
          className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-400/20 text-emerald-400 text-sm cursor-help"
          title="Session achieved its goal"
        >
          ✓
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-rose-400/20 text-rose-400 text-sm cursor-help"
        title="Session failed to achieve its goal"
      >
        ✗
      </span>
    );
  },
};
