# Epic 6: Project-Centric Analytics Dashboard - Product Narrative

**Epic ID:** catsyphon-up7
**Status:** In Progress (3/25 tasks complete)
**Priority:** P1
**Estimated Duration:** 2-3 weeks

---

## Table of Contents

1. [Current State: Conversation-Centric](#current-state-conversation-centric)
2. [The Transformation: Project-Centric](#the-transformation-project-centric)
3. [Product Walkthrough](#product-walkthrough)
4. [Backend API Contracts](#backend-api-contracts)
5. [Value Proposition](#value-proposition)
6. [Task Mapping](#task-mapping)
7. [Success Metrics](#success-metrics)

---

## Current State: Conversation-Centric

### What CatSyphon Looks Like Today

CatSyphon is currently a **conversation log viewer**. Users land on a chronological list of individual Claude Code sessions:

- **Entry Point:** ConversationList page - shows all conversations sorted by date
- **Detail View:** Click a conversation → see messages, tags, basic stats
- **Analytics:** Per-conversation metrics (sentiment, intent, outcome, features, problems)
- **Navigation:** Flat list with no grouping or project context

### The Problem

A manager asks: **"Is AI helping my team ship the payment service faster?"**

Today's CatSyphon answers: **"Here are 47 individual conversation logs from the last 2 weeks. Good luck."**

The manager would need to:
1. Open 23+ individual conversation logs manually
2. Read through messages to understand context
3. Try to remember patterns across sessions
4. Make subjective judgment calls about effectiveness
5. **Result: Takes hours, so it never actually happens**

### Why This Fails

- Real work happens across **MULTIPLE sessions** within a project
- Individual conversations lack business context
- Analytics at single-session granularity are meaningless
- No way to aggregate insights or identify patterns
- Managers can't quantify AI agent ROI

---

## The Transformation: Project-Centric

### Prerequisites Completed ✅

1. **catsyphon-up7.1** - Added `project_directory_path` and metadata fields to Project model
2. **catsyphon-up7.2** - Parser extracts `working_directory` from Claude Code logs
3. **catsyphon-up7.3** - Auto-create/match projects during ingestion based on directory path

### What Changes (Tasks up7.5-20)

Epic 6 transforms CatSyphon from a **log viewer** into an **analytics platform** by:

1. **Backend APIs (up7.5-8):** Aggregated project-level data endpoints
2. **Frontend Foundation (up7.9-11):** Routing, types, API client for projects
3. **Projects List (up7.12):** New landing page showing all projects
4. **Project Dashboard (up7.13-20):** Multi-tab analytics interface

**Core Insight:** Instead of showing conversations, show **projects with their sessions**.

---

## Product Walkthrough

### Entry Point: Projects List (up7.12)

**Task:** catsyphon-up7.12 - Implement ProjectList page with sortable table and filters

**Navigation:** New "Projects" link in main nav (up7.9)

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Projects                                    [Sort: Recent ▾] [Filter] │
├─────────────────────────────────────────────────────────────────┤
│ Project                    Sessions  Success  Last Active       │
├─────────────────────────────────────────────────────────────────┤
│ 📁 payment-service            23      87%     2 hours ago       │
│    /Users/kulesh/dev/payment-service                            │
│                                                                  │
│ 📁 catsyphon                  156     78%     5 mins ago        │
│    /Users/kulesh/dev/catsyphon                                  │
│                                                                  │
│ 📁 mobile-app                 45      62%     1 day ago         │
│    /Users/sarah/projects/mobile-app                             │
└─────────────────────────────────────────────────────────────────┘
```

**Manager thinks:** *"Payment service has 23 AI sessions with 87% success rate. That's recent work. Let me see what's happening."*

**Features:**
- Sortable by: name, session count, success rate, last active
- Filters: date range, developer, success rate threshold
- Click project → navigate to Project Dashboard

**Data Source:** `GET /projects` (enhanced - up7.7)

---

### Project Dashboard: Header & Navigation (up7.13)

**Task:** catsyphon-up7.13 - Build ProjectDetail page with header, tabs, and breadcrumb navigation

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Projects                                               │
│                                                                  │
│ 📁 payment-service                              [Last 30 days ▾] │
│ /Users/kulesh/dev/payment-service                                │
│                                                                  │
│ [Overview] [Sessions] [Files] [Timeline]                         │
├─────────────────────────────────────────────────────────────────┤
│ (Tab content appears below)                                      │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Breadcrumb navigation back to Projects
- Project name and directory path
- Date range selector (Last 7 days, 30 days, 90 days, All time)
- Tab navigation: Overview, Sessions, Files, Timeline (future)

---

### Tab 1: Overview - Metrics Cards (up7.14)

**Task:** catsyphon-up7.14 - Implement Overview tab with metrics cards

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Overview Tab                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ ╔════════╗  ╔════════╗  ╔════════╗  ╔════════╗                 │
│ ║   23   ║  ║  87%   ║  ║   12   ║  ║   8    ║                 │
│ ║Sessions║  ║Success ║  ║Features║  ║Problems║                 │
│ ╚════════╝  ╚════════╝  ╚════════╝  ╚════════╝                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Metrics:**
1. **Total Sessions:** Count of conversations in this project
2. **Success Rate:** % of sessions with outcome="success"
3. **Features Delivered:** Unique features extracted from tags.features across all sessions
4. **Problems Encountered:** Unique problems from tags.problems

**Data Source:** `GET /projects/{id}/stats` (up7.5)

---

### Tab 1: Overview - Sentiment Timeline Chart (up7.15)

**Task:** catsyphon-up7.15 - Create sentiment over time line chart for project timeline

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Sentiment Over Time                                              │
│                                                                  │
│  1.0 ┤                              ╭─╮                          │
│  0.5 ┤        ╭─╮     ╭──╮    ╭────╯ ╰─╮                        │
│  0.0 ┼────────┴─┴─────┴──┴────┴────────┴──────                  │
│ -0.5 ┤                                                           │
│ -1.0 ┤    ╭╮                                                     │
│      └────────────────────────────────────────────────────────   │
│        Nov 1      Nov 8     Nov 15    Nov 22                    │
└─────────────────────────────────────────────────────────────────┘
```

**Chart Type:** Line chart (using Recharts or similar)

**Data:**
- X-axis: Date
- Y-axis: Average sentiment score (-1.0 to 1.0)
- Aggregates `sentiment_score` from epochs across all sessions, grouped by date
- Shows trend: improving (upward) vs degrading (downward) team morale

**Manager insight:** *"Sentiment started negative (Nov 1-5) but has been trending positive. Team is getting more productive with AI over time."*

**Data Source:** `GET /projects/{id}/stats` → `sentiment_timeline` array

---

### Tab 1: Overview - Tool Usage Chart (up7.16)

**Task:** catsyphon-up7.16 - Create tool usage bar chart aggregating tags.tools_used across sessions

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Tool Usage                                                       │
│                                                                  │
│ git      ████████████████████ 18                                │
│ bash     ████████████████ 15                                    │
│ npm      ████████████ 11                                        │
│ pytest   ████████ 7                                             │
│ docker   ████ 4                                                 │
│ curl     ██ 2                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Chart Type:** Horizontal bar chart

**Data:**
- Aggregates `tags.tools_used` arrays across all sessions
- Counts occurrences of each tool
- Sorted by frequency (descending)
- Shows top 10 tools

**Manager insight:** *"Team is using AI for the full workflow: git commits, bash commands, testing, deployment. High tool diversity = deep integration."*

**Data Source:** `GET /projects/{id}/stats` → `tool_usage` object

---

### Tab 1: Overview - Features & Problems Lists (up7.17)

**Task:** catsyphon-up7.17 - Display top features delivered and problems encountered lists

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Top Features Delivered                                           │
│                                                                  │
│ ✓ Stripe payment gateway integration (5 sessions)               │
│ ✓ Refund processing workflow (4 sessions)                       │
│ ✓ Webhook validation and signature verification (3 sessions)    │
│ ✓ Error handling and retry logic (3 sessions)                   │
│ ✓ Rate limiting for API endpoints (2 sessions)                  │
│                                                                  │
│ [Show all 12 features →]                                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Common Problems Encountered                                      │
│                                                                  │
│ ⚠ Stripe API authentication errors (3 sessions)                 │
│ ⚠ Docker container networking issues (2 sessions)               │
│ ⚠ Type errors in payment models (2 sessions)                    │
│ ⚠ Redis connection timeouts (1 session)                         │
│                                                                  │
│ [Show all 8 problems →]                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Features List:**
- Aggregates `tags.features` arrays from all sessions
- Groups by feature name, counts occurrences
- Sorted by frequency (most common first)
- Shows top 5, expandable to all

**Problems List:**
- Aggregates `tags.problems` arrays from all sessions
- Groups by problem name, counts occurrences
- Sorted by frequency (identifies systemic blockers)
- Shows top 4, expandable to all

**Manager insight:** *"Stripe auth errors happened 3 times - that's a pattern. I should create a shared credentials doc for the team to prevent future failures."*

**Data Source:** `GET /projects/{id}/stats` → `features_delivered` and `problems_encountered` arrays

---

### Tab 2: Sessions - Sortable Table (up7.18)

**Task:** catsyphon-up7.18 - Implement Sessions tab with sortable, filterable session table

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Sessions Tab                          [Filter: All ▾] [Search]  │
├─────────────────────────────────────────────────────────────────┤
│ Session                     Developer  Outcome    Duration      │
├─────────────────────────────────────────────────────────────────┤
│ Add Stripe webhooks         kulesh     ✓ Success  1h 23m       │
│ Nov 22, 2:14 PM                                                 │
│ Features: webhook validation, signature verification            │
│                                                                  │
│ Fix payment refunds         sarah      ✓ Success  45m          │
│ Nov 22, 10:30 AM                                                │
│ Features: refund processing, error handling                     │
│                                                                  │
│ Debug Stripe auth           kulesh     ✗ Failed   2h 15m       │
│ Nov 21, 3:45 PM                                                 │
│ Problems: Stripe API authentication errors                      │
│                                                                  │
│ Implement rate limiting     sarah      ✓ Success  1h 05m       │
│ Nov 21, 9:00 AM                                                 │
│ Features: rate limiting, API throttling                         │
│                                                                  │
│ [Load more sessions...]                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Sortable columns: date, developer, outcome, duration
- Filters: developer, outcome (success/failed/partial), date range
- Search: by session title or features/problems
- Click session → navigate to ConversationDetail (with breadcrumb back to project)
- Pagination: 20 sessions per page
- Shows: title, timestamp, developer, outcome icon, duration, preview of features/problems

**Manager insight:** *"Kulesh spent 2h 15m debugging Stripe auth and failed. Let me click into that session to see what happened, then reach out to help."*

**Data Source:** `GET /projects/{id}/sessions` (up7.6)

---

### Tab 3: Files - Aggregated Changes (up7.20)

**Task:** catsyphon-up7.20 - Implement Files tab showing all files touched in project

**User sees:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Files Tab                                 [Sort: Most Changed ▾] │
├─────────────────────────────────────────────────────────────────┤
│ File                                    Sessions  Lines Changed │
├─────────────────────────────────────────────────────────────────┤
│ src/payments/stripe.py                     12       +245 -89   │
│ Most recent: Add Stripe webhooks (2 hours ago)                  │
│                                                                  │
│ src/payments/models.py                      8        +123 -45   │
│ Most recent: Fix payment refunds (5 hours ago)                  │
│                                                                  │
│ tests/test_stripe.py                        6        +89 -12    │
│ Most recent: Add webhook tests (2 hours ago)                    │
│                                                                  │
│ docker-compose.yml                          3        +15 -3     │
│ Most recent: Update payment service config (1 day ago)          │
│                                                                  │
│ requirements.txt                            2        +5 -1      │
│ Most recent: Add stripe dependency (3 days ago)                 │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Aggregates `files_touched` from all sessions in project
- Groups by file path, sums lines added/removed
- Shows session count per file (how many times modified)
- Displays most recent session that touched the file
- Sortable: by session count, total changes, most recent
- Click file → filter Sessions tab to show only sessions touching that file (future enhancement)

**Manager insight:** *"The team is heavily modifying stripe.py across 12 sessions. That's our core payment logic - good to see active development and testing coverage."*

**Data Source:** `GET /projects/{id}/files` (up7.8)

---

### Breadcrumb Navigation (up7.19)

**Task:** catsyphon-up7.19 - Add project breadcrumb and 'Back to Project' link in ConversationDetail

**User flow:**
1. Projects List → click payment-service
2. Project Dashboard → Sessions tab → click "Debug Stripe auth"
3. **ConversationDetail page now shows:**

```
┌─────────────────────────────────────────────────────────────────┐
│ Projects > payment-service > Debug Stripe auth                  │
│                                                                  │
│ [Dashboard] [Timeline]                                          │
│ (existing ConversationDetail page content)                      │
└─────────────────────────────────────────────────────────────────┘
```

**Features:**
- Breadcrumb: Projects > {project.name} > {conversation.title}
- Click "payment-service" → navigate back to Project Dashboard
- Click "Projects" → navigate to Projects List
- Provides context: "This session is part of the payment-service project"

---

## Backend API Contracts

### GET /projects (Enhanced) - up7.7

**Task:** catsyphon-up7.7 - Enhance GET /projects endpoint with session counts and recent activity

**Endpoint:** `GET /projects?limit=50&offset=0&sort=last_active`

**Response:**
```json
{
  "projects": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "payment-service",
      "slug": "payment-service",
      "description": "Payment processing service with Stripe integration",
      "directory_path": "/Users/kulesh/dev/payment-service",
      "session_count": 23,
      "success_rate": 0.87,
      "last_activity": "2025-11-22T16:45:00Z",
      "created_at": "2025-10-15T10:00:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "catsyphon",
      "slug": "catsyphon",
      "description": "AI conversation analytics platform",
      "directory_path": "/Users/kulesh/dev/catsyphon",
      "session_count": 156,
      "success_rate": 0.78,
      "last_activity": "2025-11-22T17:50:00Z",
      "created_at": "2025-09-01T08:00:00Z"
    }
  ],
  "total": 8,
  "limit": 50,
  "offset": 0
}
```

**Query Parameters:**
- `limit` (default: 50): Max results per page
- `offset` (default: 0): Pagination offset
- `sort` (default: "last_active"): Sort by last_active, name, session_count, success_rate
- `order` (default: "desc"): asc or desc

**New Fields:**
- `session_count`: Total conversations in project
- `success_rate`: % of sessions with outcome="success"
- `last_activity`: Timestamp of most recent session end_time

---

### GET /projects/{id}/stats - up7.5

**Task:** catsyphon-up7.5 - Implement GET /projects/{id}/stats endpoint with aggregated metrics

**Endpoint:** `GET /projects/{project_id}/stats?date_range=30d`

**Response:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "date_range": {
    "start": "2025-10-23T00:00:00Z",
    "end": "2025-11-22T23:59:59Z"
  },
  "overview": {
    "total_sessions": 23,
    "success_rate": 0.87,
    "total_duration_minutes": 1247,
    "avg_session_duration_minutes": 54
  },
  "features_delivered": [
    {
      "name": "Stripe payment gateway integration",
      "count": 5,
      "first_seen": "2025-11-01T10:00:00Z",
      "last_seen": "2025-11-20T15:30:00Z"
    },
    {
      "name": "Refund processing workflow",
      "count": 4,
      "first_seen": "2025-11-05T09:00:00Z",
      "last_seen": "2025-11-22T10:30:00Z"
    },
    {
      "name": "Webhook validation and signature verification",
      "count": 3,
      "first_seen": "2025-11-15T14:00:00Z",
      "last_seen": "2025-11-22T14:14:00Z"
    }
  ],
  "problems_encountered": [
    {
      "name": "Stripe API authentication errors",
      "count": 3,
      "sessions": ["abc-123", "def-456", "ghi-789"],
      "first_seen": "2025-11-10T11:00:00Z",
      "last_seen": "2025-11-21T15:45:00Z"
    },
    {
      "name": "Docker container networking issues",
      "count": 2,
      "sessions": ["jkl-012", "mno-345"],
      "first_seen": "2025-11-08T16:00:00Z",
      "last_seen": "2025-11-18T13:20:00Z"
    }
  ],
  "tool_usage": {
    "git": 18,
    "bash": 15,
    "npm": 11,
    "pytest": 7,
    "docker": 4,
    "curl": 2
  },
  "sentiment_timeline": [
    {
      "date": "2025-11-01",
      "avg_sentiment": -0.5,
      "session_count": 3
    },
    {
      "date": "2025-11-08",
      "avg_sentiment": 0.3,
      "session_count": 5
    },
    {
      "date": "2025-11-15",
      "avg_sentiment": 0.6,
      "session_count": 7
    },
    {
      "date": "2025-11-22",
      "avg_sentiment": 0.8,
      "session_count": 8
    }
  ],
  "outcome_distribution": {
    "success": 20,
    "partial": 2,
    "failed": 1
  }
}
```

**Query Parameters:**
- `date_range` (default: "30d"): "7d", "30d", "90d", "all"

**Aggregation Logic:**
- `features_delivered`: Flatten all `tags.features` arrays, group by name, count occurrences
- `problems_encountered`: Flatten all `tags.problems` arrays, group by name, count occurrences, track session IDs
- `tool_usage`: Flatten all `tags.tools_used` arrays, count occurrences per tool
- `sentiment_timeline`: Group sessions by date, average `sentiment_score` from epochs per day

---

### GET /projects/{id}/sessions - up7.6

**Task:** catsyphon-up7.6 - Implement GET /projects/{id}/sessions endpoint listing conversations

**Endpoint:** `GET /projects/{project_id}/sessions?limit=20&offset=0&sort=start_time&order=desc`

**Response:**
```json
{
  "sessions": [
    {
      "id": "abc-123",
      "title": "Add Stripe webhooks",
      "start_time": "2025-11-22T14:14:00Z",
      "end_time": "2025-11-22T15:37:00Z",
      "duration_minutes": 83,
      "developer": {
        "id": "dev-001",
        "username": "kulesh",
        "name": "Kulesh Shanmugasundaram"
      },
      "outcome": "success",
      "sentiment_score": 0.7,
      "features": [
        "webhook validation",
        "signature verification"
      ],
      "problems": [],
      "tools_used": ["git", "bash", "pytest"],
      "message_count": 45,
      "files_touched_count": 4
    },
    {
      "id": "def-456",
      "title": "Fix payment refunds",
      "start_time": "2025-11-22T10:30:00Z",
      "end_time": "2025-11-22T11:15:00Z",
      "duration_minutes": 45,
      "developer": {
        "id": "dev-002",
        "username": "sarah",
        "name": "Sarah Chen"
      },
      "outcome": "success",
      "sentiment_score": 0.5,
      "features": [
        "refund processing",
        "error handling"
      ],
      "problems": [],
      "tools_used": ["git", "bash"],
      "message_count": 32,
      "files_touched_count": 3
    },
    {
      "id": "ghi-789",
      "title": "Debug Stripe auth",
      "start_time": "2025-11-21T15:45:00Z",
      "end_time": "2025-11-21T18:00:00Z",
      "duration_minutes": 135,
      "developer": {
        "id": "dev-001",
        "username": "kulesh",
        "name": "Kulesh Shanmugasundaram"
      },
      "outcome": "failed",
      "sentiment_score": -0.6,
      "features": [],
      "problems": [
        "Stripe API authentication errors",
        "API key configuration issues"
      ],
      "tools_used": ["bash", "curl", "git"],
      "message_count": 67,
      "files_touched_count": 2
    }
  ],
  "total": 23,
  "limit": 20,
  "offset": 0
}
```

**Query Parameters:**
- `limit` (default: 20): Results per page
- `offset` (default: 0): Pagination offset
- `sort` (default: "start_time"): start_time, duration, outcome
- `order` (default: "desc"): asc or desc
- `developer` (optional): Filter by developer username
- `outcome` (optional): Filter by outcome (success, partial, failed)

---

### GET /projects/{id}/files - up7.8

**Task:** catsyphon-up7.8 - Create GET /projects/{id}/files endpoint aggregating files_touched

**Endpoint:** `GET /projects/{project_id}/files?limit=50&sort=sessions`

**Response:**
```json
{
  "files": [
    {
      "path": "src/payments/stripe.py",
      "session_count": 12,
      "total_lines_added": 245,
      "total_lines_removed": 89,
      "net_change": 156,
      "first_modified": "2025-11-01T10:00:00Z",
      "last_modified": "2025-11-22T16:45:00Z",
      "last_modified_session": {
        "id": "abc-123",
        "title": "Add Stripe webhooks"
      }
    },
    {
      "path": "src/payments/models.py",
      "session_count": 8,
      "total_lines_added": 123,
      "total_lines_removed": 45,
      "net_change": 78,
      "first_modified": "2025-11-03T09:00:00Z",
      "last_modified": "2025-11-22T10:30:00Z",
      "last_modified_session": {
        "id": "def-456",
        "title": "Fix payment refunds"
      }
    },
    {
      "path": "tests/test_stripe.py",
      "session_count": 6,
      "total_lines_added": 89,
      "total_lines_removed": 12,
      "net_change": 77,
      "first_modified": "2025-11-05T11:00:00Z",
      "last_modified": "2025-11-22T14:14:00Z",
      "last_modified_session": {
        "id": "abc-123",
        "title": "Add Stripe webhooks"
      }
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

**Query Parameters:**
- `limit` (default: 50): Results per page
- `offset` (default: 0): Pagination offset
- `sort` (default: "sessions"): sessions, total_changes, last_modified
- `order` (default: "desc"): asc or desc

**Aggregation Logic:**
- Join conversations with files_touched table
- Group by file path
- Count distinct session IDs touching each file
- Sum lines_added and lines_removed across all sessions
- Get most recent session timestamp

---

## Value Proposition

### For Engineering Managers

✅ **Quantify AI agent ROI at project level**
- "87% success rate across 23 sessions" → concrete effectiveness metric
- Compare project success rates to identify best practices

✅ **Identify team friction points**
- "Stripe auth errors in 3 sessions" → systemic blocker requiring intervention
- Spot patterns managers can fix (credentials, docs, training)

✅ **Track feature delivery velocity**
- "12 features delivered this month" → business value quantification
- Understand what AI agents are helping teams build

✅ **Spot training opportunities**
- Tool usage patterns show workflow integration depth
- Low tool diversity might indicate underutilization

✅ **Make data-driven decisions about AI adoption**
- Sentiment trends show team morale improving/degrading over time
- Success rate trends validate AI investment

### For Development Teams

✅ **Understand project-level patterns**
- See what's working across multiple sessions
- Learn from successful approaches

✅ **Learn from past sessions**
- "How did we solve webhook validation before?" → check features list
- Identify knowledge gaps when same problems recur

✅ **Context for current work**
- New team member: "What's been happening on this project?"
- Onboarding: Review project history at a glance

✅ **Celebrate wins**
- Visualize progress: 12 features delivered, sentiment trending positive
- Share success stories with stakeholders

### For CatSyphon (Product)

🎯 **Shifts from log viewer → analytics platform**
- Moves upmarket to manager/team lead personas
- Creates defensible moat through data aggregation insights

🎯 **Answers "Is AI helping?" not "What did AI do?"**
- Strategic question vs operational question
- Higher value, harder to replace with simple log viewer

🎯 **Targets managers, not just developers**
- Expands addressable market
- Increases willingness to pay (manager budgets > dev tool budgets)

🎯 **Enables decision-making, not just observation**
- Actionable insights (fix Stripe auth setup)
- Drives behavior change, not passive consumption

---

## Task Mapping

### Backend Tasks (up7.5-8)

| Task ID | Description | Deliverable |
|---------|-------------|-------------|
| up7.5 | GET /projects/{id}/stats | Aggregated metrics API endpoint |
| up7.6 | GET /projects/{id}/sessions | Session list API endpoint |
| up7.7 | Enhance GET /projects | Add session_count, success_rate, last_activity |
| up7.8 | GET /projects/{id}/files | Files aggregation API endpoint |

**Dependencies:** None (prerequisites up7.1-3 complete)

**Estimated:** 2-3 days

---

### Frontend Foundation (up7.9-11)

| Task ID | Description | Deliverable |
|---------|-------------|-------------|
| up7.9 | Add Projects navigation | New "Projects" link in main nav |
| up7.10 | Define TypeScript types | Types for project API responses |
| up7.11 | Create API client methods | Frontend API client functions |

**Dependencies:** up7.5-8 (need API contracts)

**Estimated:** 1 day

---

### Frontend Pages (up7.12-13)

| Task ID | Description | Deliverable |
|---------|-------------|-------------|
| up7.12 | ProjectList page | Sortable table of projects |
| up7.13 | ProjectDetail header | Page layout with tabs |

**Dependencies:** up7.9-11

**Estimated:** 1-2 days

---

### Dashboard Tabs (up7.14-20)

| Task ID | Description | Deliverable |
|---------|-------------|-------------|
| up7.14 | Overview: Metrics cards | 4 KPI cards (sessions, success, features, problems) |
| up7.15 | Overview: Sentiment chart | Line chart showing sentiment over time |
| up7.16 | Overview: Tool usage chart | Bar chart of tool frequencies |
| up7.17 | Overview: Features & problems | Two lists with top items |
| up7.18 | Sessions tab | Sortable, filterable session table |
| up7.19 | Breadcrumb navigation | Project context in ConversationDetail |
| up7.20 | Files tab | Aggregated file changes table |

**Dependencies:** up7.12-13

**Estimated:** 4-5 days

---

## Success Metrics

### Quantitative

- ✅ **Managers can assess project health in <30 seconds**
  - Metric: Time from landing on ProjectDetail to identifying actionable insight
  - Target: <30s average

- ✅ **Clear answer to "Are we delivering faster with AI?"**
  - Metric: Success rate visible within 2 clicks (Projects → Project Dashboard)
  - Target: 100% of managers can find this metric

- ✅ **Identification of improvement opportunities**
  - Metric: % of projects with >1 recurring problem (count ≥2)
  - Target: Surface 80%+ of systemic blockers

### Qualitative

- ✅ **Visibility into team AI adoption patterns**
  - Tool usage diversity shows workflow integration
  - Sentiment trends show team morale

- ✅ **Manager satisfaction**
  - "I can finally see if AI is helping my team" feedback
  - Reduced time spent manually reviewing conversation logs

---

## Open Questions

1. **How to handle projects without directory info (uploaded files)?**
   - **Proposal:** Fall back to project_name from ingestion, manual grouping later

2. **Should we auto-create projects from directory structure?**
   - **Status:** YES (completed in up7.3)

3. **How to handle project renames/moves?**
   - **Proposal:** Manual project merge tool (future epic)

4. **Should project dashboard be the new default landing page?**
   - **Proposal:** YES - redirect / to /projects (after up7.12 complete)
   - **Rationale:** Aligns with manager persona as primary user

---

## Summary

**Epic 6 transforms CatSyphon from:**

> "Here's a chronological list of AI conversations"

**Into:**

> "Here's how AI is helping your team deliver the payment service, with 87% success rate, 12 features shipped, and 3 blockers you should address."

**The product becomes a manager's dashboard for AI-assisted development effectiveness.**
