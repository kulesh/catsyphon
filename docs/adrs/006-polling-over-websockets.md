# ADR-006: Polling Over WebSockets

**Status:** Accepted
**Date:** 2025-11-01

## Context

The frontend needs to reflect changes as conversations are ingested: new entries appearing on the dashboard, ingestion job status updates, conversation list growth. The question is how to propagate server-side state changes to the browser.

## Decision

TanStack React Query with polling at 15-second intervals. Each query hook sets `refetchInterval: 15000`, causing periodic GET requests to the existing REST API. No additional server infrastructure required.

```typescript
useQuery({
  queryKey: ["conversations"],
  queryFn: () => api.getConversations(filters),
  refetchInterval: 15_000,
});
```

The frontend uses freshness indicators (timestamps, "new" badges) so users can see when data last updated and which items are recent.

## Alternatives Considered

**WebSockets.** True push semantics with lower latency. But WebSocket connections require server-side connection management, heartbeats, reconnection logic, and stateful tracking of connected clients. Adds operational complexity (sticky sessions behind load balancers, connection limits). The FastAPI backend would need a broadcast mechanism to notify connected clients when ingestion completes.

**Server-Sent Events (SSE).** Simpler than WebSockets (unidirectional, HTTP-based). Still requires server-side connection management and doesn't work well through certain reverse proxies. Partial benefit for partial complexity.

**Long polling.** Server holds the request open until data changes. Requires careful timeout management and thread/connection pool sizing. More complex than simple interval polling with no meaningful UX improvement for this use case.

## Consequences

- No additional server infrastructure. The REST API serves both initial loads and polling refreshes identically.
- Works transparently through proxies, CDNs, and load balancers. No sticky sessions required.
- 15-second maximum latency between server-side change and frontend display. Acceptable for an analytics tool where sub-second updates provide no meaningful user benefit.
- Slight bandwidth overhead from repeated full responses. Mitigated by TanStack Query's structural sharing (only re-renders if data actually changed) and HTTP caching headers.
- If real-time requirements change (e.g., live streaming of in-progress conversations), this decision should be revisited. WebSockets or SSE would be appropriate then.
