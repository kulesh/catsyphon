/**
 * SessionPagination - Unified pagination controls for session lists
 */

import { ChevronLeft, ChevronRight } from 'lucide-react';

interface SessionPaginationProps {
  /** Current page number (1-indexed) */
  currentPage: number;
  /** Total number of pages (undefined for simple mode) */
  totalPages?: number;
  /** Total number of items (undefined for simple mode) */
  totalItems?: number;
  /** Number of items per page */
  pageSize: number;
  /** Number of items on current page (for detecting last page in simple mode) */
  currentPageItemCount?: number;
  /** Callback when page changes */
  onPageChange: (page: number) => void;
  /** Pagination style */
  variant?: 'full' | 'simple';
}

export function SessionPagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  currentPageItemCount,
  onPageChange,
  variant = 'full',
}: SessionPaginationProps) {
  const isFirstPage = currentPage === 1;
  const isLastPage =
    variant === 'full'
      ? currentPage === totalPages
      : currentPageItemCount !== undefined && currentPageItemCount < pageSize;

  if (variant === 'simple') {
    // Simple mode: Just prev/next buttons and page number
    return (
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Page {currentPage}</p>
        <div className="flex gap-2">
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={isFirstPage}
            className="px-4 py-2 bg-card border border-border rounded-lg text-sm hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Previous page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={isLastPage}
            className="px-4 py-2 bg-card border border-border rounded-lg text-sm hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Next page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // Full mode: Observatory-themed with total count
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems || 0);

  return (
    <div className="flex items-center justify-between mt-6">
      <div className="font-mono text-xs text-muted-foreground">
        <span className="text-foreground/90">{startItem.toLocaleString()}</span>
        {' - '}
        <span className="text-foreground/90">{endItem.toLocaleString()}</span>
        {' of '}
        <span className="text-cyan-400">{(totalItems || 0).toLocaleString()}</span>
        {' entries'}
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={isFirstPage}
          className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-muted-foreground disabled:hover:border-border/50 disabled:hover:bg-transparent transition-all"
        >
          Prev
        </button>

        <div className="px-4 py-2 bg-slate-900/50 border border-border/50 rounded-md">
          <span className="font-mono text-xs text-foreground/90">
            Page <span className="text-cyan-400 font-semibold">{currentPage}</span>
            {' / '}
            <span className="text-muted-foreground">{totalPages || '?'}</span>
          </span>
        </div>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={isLastPage}
          className="px-4 py-2 font-mono text-xs font-semibold uppercase tracking-wider text-muted-foreground hover:text-cyan-400 border border-border/50 rounded-md hover:border-cyan-400/50 hover:bg-cyan-400/5 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:text-muted-foreground disabled:hover:border-border/50 disabled:hover:bg-transparent transition-all"
        >
          Next
        </button>
      </div>
    </div>
  );
}
