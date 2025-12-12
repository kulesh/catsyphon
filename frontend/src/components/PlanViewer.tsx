/**
 * PlanViewer - Full plan viewing component with markdown rendering and diff support
 */

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { createTwoFilesPatch } from 'diff';
import * as Diff2Html from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';
import {
  ChevronRight,
  ClipboardList,
  FileEdit,
  FilePlus,
  Clock,
  CheckCircle2,
  Circle,
  XCircle,
} from 'lucide-react';
import type { PlanResponse, PlanOperation } from '../types/api';

interface PlanViewerProps {
  plans: PlanResponse[];
  onMessageClick?: (messageIndex: number) => void;
}

type ViewMode = 'final' | 'initial' | 'diff';

/**
 * Extract filename from full path
 */
function getBasename(filePath: string): string {
  const parts = filePath.split('/');
  return parts[parts.length - 1] || filePath;
}

/**
 * Get status badge styling
 */
function getStatusStyle(status: string): { bg: string; text: string; border: string } {
  switch (status) {
    case 'approved':
      return {
        bg: 'bg-emerald-400/10',
        text: 'text-emerald-400',
        border: 'border-emerald-400/30',
      };
    case 'active':
      return {
        bg: 'bg-blue-400/10',
        text: 'text-blue-400',
        border: 'border-blue-400/30',
      };
    case 'abandoned':
      return {
        bg: 'bg-slate-400/10',
        text: 'text-slate-400',
        border: 'border-slate-400/30',
      };
    default:
      return {
        bg: 'bg-cyan-400/10',
        text: 'text-cyan-400',
        border: 'border-cyan-400/30',
      };
  }
}

/**
 * Get operation icon
 */
function getOperationIcon(operationType: string) {
  switch (operationType) {
    case 'create':
      return <FilePlus className="w-4 h-4 text-emerald-400" />;
    case 'edit':
      return <FileEdit className="w-4 h-4 text-amber-400" />;
    default:
      return <Circle className="w-4 h-4 text-slate-400" />;
  }
}

/**
 * Status badge component
 */
function PlanStatusBadge({ status }: { status: string }) {
  const style = getStatusStyle(status);
  const icon =
    status === 'approved' ? (
      <CheckCircle2 className="w-3 h-3" />
    ) : status === 'abandoned' ? (
      <XCircle className="w-3 h-3" />
    ) : (
      <Circle className="w-3 h-3" />
    );

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wide ${style.bg} ${style.text} border ${style.border}`}
    >
      {icon}
      {status}
    </span>
  );
}

/**
 * Plan header with metadata
 */
function PlanHeader({ plan }: { plan: PlanResponse }) {
  return (
    <div className="flex items-center justify-between flex-wrap gap-2 p-4 bg-slate-800/50 rounded-lg border border-cyan-900/30">
      <div className="flex items-center gap-3">
        <ClipboardList className="w-5 h-5 text-cyan-400" />
        <div>
          <div className="font-mono text-sm text-white">{getBasename(plan.plan_file_path)}</div>
          <div className="text-xs text-slate-400">{plan.plan_file_path}</div>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <PlanStatusBadge status={plan.status} />
        <div className="text-xs text-slate-400">
          <span className="text-cyan-400">{plan.iteration_count}</span> iteration
          {plan.iteration_count !== 1 ? 's' : ''}
        </div>
        <div className="text-xs text-slate-400">
          <span className="text-cyan-400">{plan.operations.length}</span> operation
          {plan.operations.length !== 1 ? 's' : ''}
        </div>
      </div>
    </div>
  );
}

/**
 * View mode toggle buttons
 */
function ViewModeToggle({
  value,
  onChange,
  hasInitial,
}: {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
  hasInitial: boolean;
}) {
  const modes: { id: ViewMode; label: string; disabled?: boolean }[] = [
    { id: 'final', label: 'Final' },
    { id: 'initial', label: 'Initial', disabled: !hasInitial },
    { id: 'diff', label: 'Diff', disabled: !hasInitial },
  ];

  return (
    <div className="flex items-center gap-1 p-1 bg-slate-800/50 rounded-lg border border-cyan-900/30">
      {modes.map((mode) => (
        <button
          key={mode.id}
          onClick={() => !mode.disabled && onChange(mode.id)}
          disabled={mode.disabled}
          className={`px-3 py-1 text-xs font-mono uppercase tracking-wide rounded transition-colors ${
            value === mode.id
              ? 'bg-cyan-400/20 text-cyan-400'
              : mode.disabled
                ? 'text-slate-600 cursor-not-allowed'
                : 'text-slate-400 hover:text-cyan-400 hover:bg-cyan-400/10'
          }`}
        >
          {mode.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Markdown content renderer with Observatory theme styling
 */
function MarkdownContent({ content }: { content: string | undefined }) {
  if (!content) {
    return (
      <div className="text-center py-8 text-slate-500 font-mono text-sm">No content available</div>
    );
  }

  return (
    <div className="plan-markdown prose prose-invert prose-sm max-w-none p-4 bg-slate-900/50 rounded-lg border border-cyan-900/30 overflow-auto max-h-[600px]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Style headers with cyan accent
          h1: ({ children }) => (
            <h1 className="text-xl font-bold text-cyan-400 border-b border-cyan-900/50 pb-2 mb-4">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-lg font-semibold text-cyan-300 mt-6 mb-3">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-base font-medium text-cyan-200 mt-4 mb-2">{children}</h3>
          ),
          // Style code blocks
          code: ({ className, children }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 bg-slate-800 text-amber-300 rounded text-xs font-mono">
                  {children}
                </code>
              );
            }
            return (
              <code className="block p-3 bg-slate-800 rounded-lg text-xs font-mono overflow-x-auto">
                {children}
              </code>
            );
          },
          // Style lists
          ul: ({ children }) => <ul className="list-disc list-inside space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-slate-300">{children}</li>,
          // Style links
          a: ({ href, children }) => (
            <a
              href={href}
              className="text-cyan-400 hover:text-cyan-300 underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          // Style tables
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border border-cyan-900/30">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 bg-slate-800 text-left text-xs font-mono text-cyan-400 border border-cyan-900/30">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3 py-2 text-xs text-slate-300 border border-cyan-900/30">
              {children}
            </td>
          ),
          // Style blockquotes
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-cyan-400/50 pl-4 italic text-slate-400">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Side-by-side diff viewer
 */
function SideBySideDiff({
  initial,
  final,
}: {
  initial: string | undefined;
  final: string | undefined;
}) {
  const initialContent = initial || '';
  const finalContent = final || '';

  // Generate unified diff
  const unifiedDiff = createTwoFilesPatch(
    'initial',
    'final',
    initialContent,
    finalContent,
    'Initial Plan',
    'Final Plan'
  );

  // Convert to HTML using diff2html
  const diffHtml = Diff2Html.html(unifiedDiff, {
    outputFormat: 'side-by-side',
    drawFileList: false,
    matching: 'lines',
    diffStyle: 'word',
  });

  return (
    <div className="plan-diff rounded-lg border border-cyan-900/30 overflow-auto max-h-[600px]">
      <style>{`
        .plan-diff .d2h-wrapper {
          background: transparent;
        }
        .plan-diff .d2h-file-wrapper {
          border: none;
          margin: 0;
        }
        .plan-diff .d2h-file-header {
          display: none;
        }
        .plan-diff .d2h-diff-table {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          font-size: 12px;
        }
        .plan-diff .d2h-code-side-linenumber {
          background: rgb(30 41 59 / 0.5);
          color: rgb(100 116 139);
          border-right: 1px solid rgb(34 211 238 / 0.1);
        }
        .plan-diff .d2h-code-side-line {
          background: rgb(15 23 42 / 0.5);
          color: rgb(226 232 240);
        }
        .plan-diff .d2h-ins {
          background: rgb(34 197 94 / 0.1);
          border-color: rgb(34 197 94 / 0.3);
        }
        .plan-diff .d2h-del {
          background: rgb(239 68 68 / 0.1);
          border-color: rgb(239 68 68 / 0.3);
        }
        .plan-diff .d2h-ins .d2h-code-side-line {
          background: rgb(34 197 94 / 0.1);
        }
        .plan-diff .d2h-del .d2h-code-side-line {
          background: rgb(239 68 68 / 0.1);
        }
        .plan-diff ins {
          background: rgb(34 197 94 / 0.3);
          text-decoration: none;
        }
        .plan-diff del {
          background: rgb(239 68 68 / 0.3);
          text-decoration: none;
        }
        .plan-diff .d2h-file-side-diff {
          width: 50%;
        }
        .plan-diff .d2h-code-side-emptyplaceholder {
          background: rgb(30 41 59 / 0.3);
        }
      `}</style>
      <div dangerouslySetInnerHTML={{ __html: diffHtml }} />
    </div>
  );
}

/**
 * Operation timeline showing plan evolution
 */
function OperationTimeline({
  operations,
  onMessageClick,
}: {
  operations: PlanOperation[];
  onMessageClick?: (messageIndex: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);

  if (operations.length === 0) {
    return null;
  }

  return (
    <div className="border border-cyan-900/30 rounded-lg bg-slate-900/50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 p-3 text-left hover:bg-cyan-400/5 transition-colors"
      >
        <ChevronRight
          className={`w-4 h-4 text-cyan-400 transition-transform ${expanded ? 'rotate-90' : ''}`}
        />
        <span className="font-mono text-xs uppercase tracking-wider text-cyan-400">
          Operation Timeline
        </span>
        <span className="text-xs text-slate-500">({operations.length} operations)</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4">
          <div className="relative pl-6 space-y-3">
            {/* Vertical line */}
            <div className="absolute left-2 top-2 bottom-2 w-px bg-cyan-900/50" />

            {operations.map((op, idx) => (
              <div key={idx} className="relative flex items-start gap-3">
                {/* Timeline dot */}
                <div className="absolute left-[-16px] mt-1">{getOperationIcon(op.operation_type)}</div>

                <div className="flex-1 bg-slate-800/50 rounded p-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-xs uppercase text-white">
                      {op.operation_type}
                    </span>
                    {op.timestamp && (
                      <span className="flex items-center gap-1 text-xs text-slate-500">
                        <Clock className="w-3 h-3" />
                        {new Date(op.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 font-mono truncate">
                    {getBasename(op.file_path)}
                  </div>
                  {onMessageClick && (
                    <button
                      onClick={() => onMessageClick(op.message_index)}
                      className="mt-2 text-xs text-cyan-400 hover:text-cyan-300"
                    >
                      Jump to message #{op.message_index}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Plan selector for multiple plans
 */
function PlanSelector({
  plans,
  selectedIndex,
  onSelect,
}: {
  plans: PlanResponse[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div className="flex items-center gap-2 p-1 bg-slate-800/50 rounded-lg border border-cyan-900/30">
      {plans.map((plan, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(idx)}
          className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
            selectedIndex === idx
              ? 'bg-cyan-400/20 text-cyan-400'
              : 'text-slate-400 hover:text-cyan-400 hover:bg-cyan-400/10'
          }`}
        >
          {getBasename(plan.plan_file_path)}
        </button>
      ))}
    </div>
  );
}

/**
 * Main PlanViewer component
 */
export function PlanViewer({ plans, onMessageClick }: PlanViewerProps) {
  const [selectedPlanIdx, setSelectedPlanIdx] = useState(0);
  const [viewMode, setViewMode] = useState<ViewMode>('final');

  if (!plans || plans.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500 font-mono text-sm">
        No plans found in this conversation
      </div>
    );
  }

  const plan = plans[selectedPlanIdx];
  const hasInitial = !!plan.initial_content && plan.initial_content !== plan.final_content;

  return (
    <div className="space-y-4">
      {/* Plan selector (if multiple) */}
      {plans.length > 1 && (
        <PlanSelector plans={plans} selectedIndex={selectedPlanIdx} onSelect={setSelectedPlanIdx} />
      )}

      {/* Plan header */}
      <PlanHeader plan={plan} />

      {/* View mode toggle */}
      <div className="flex items-center justify-between">
        <ViewModeToggle value={viewMode} onChange={setViewMode} hasInitial={hasInitial} />
        {plan.entry_message_index !== undefined && onMessageClick && (
          <button
            onClick={() => onMessageClick(plan.entry_message_index!)}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-mono"
          >
            Jump to plan start (message #{plan.entry_message_index})
          </button>
        )}
      </div>

      {/* Content display */}
      {viewMode === 'diff' ? (
        <SideBySideDiff initial={plan.initial_content} final={plan.final_content} />
      ) : (
        <MarkdownContent
          content={viewMode === 'final' ? plan.final_content : plan.initial_content}
        />
      )}

      {/* Operation timeline */}
      <OperationTimeline operations={plan.operations} onMessageClick={onMessageClick} />
    </div>
  );
}

export default PlanViewer;
