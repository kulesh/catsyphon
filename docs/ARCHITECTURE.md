# CatSyphon Architecture

This document provides a comprehensive technical overview of CatSyphon's architecture, data flow, and key design decisions.

## Table of Contents

- [System Overview](#system-overview)
- [High-Level Architecture](#high-level-architecture)
- [Data Flow](#data-flow)
- [Parser Plugin System](#parser-plugin-system)
- [Database Schema](#database-schema)
- [Incremental Parsing](#incremental-parsing)
- [Canonicalization System](#canonicalization-system)
- [Insights System](#insights-system)
- [Frontend Architecture](#frontend-architecture)
- [API Design](#api-design)
- [Key Design Decisions](#key-design-decisions)

## System Overview

CatSyphon is a full-stack application for analyzing AI coding assistant conversation logs. It provides:

- **Log ingestion** from multiple AI coding assistants (Claude Code, Cursor, Copilot, etc.)
- **AI-powered enrichment** using OpenAI GPT-4o-mini for sentiment, intent, and outcome analysis
- **Canonicalization** with intelligent message sampling and LLM-optimized narrative generation
- **60+ insights** across session success, developer experience, tool usage, and code productivity
- **Real-time monitoring** with live directory watching and automatic file deduplication
- **Advanced analytics** through a modern web interface with dashboards and visualizations
- **REST API** for programmatic access to conversation data

**Test Coverage**: 1,345+ tests (1,062 backend with 84% coverage, 283 frontend)

## High-Level Architecture

```mermaid
graph TB
    subgraph "Data Sources"
        CC[Claude Code Logs]
        CX[OpenAI Codex Logs]
        CR[Cursor Logs]
        CP[Copilot Logs]
        OT[Other Agent Logs]
    end

    subgraph "Ingestion Layer"
        WD[Watch Daemon<br/>Live Monitoring]
        CLI[CLI Tool<br/>Batch Ingestion]
        UPLOAD[Upload API<br/>Web Upload]
    end

    subgraph "Processing Pipeline"
        REG[Parser Registry<br/>Format Detection]
        PAR[Parsers<br/>Plugin System]
        INC[Incremental Parser<br/>10-106x Faster]
        DUP[Deduplication<br/>Hash-based]
        TAG[AI Tagging<br/>OpenAI GPT-4o-mini]
    end

    subgraph "Canonicalization"
        CANON[Canonicalizer<br/>Token Budget]
        SAMPLER[SemanticSampler<br/>Priority Selection]
        BUILDER[PlayFormatBuilder<br/>Narrative]
    end

    subgraph "Storage Layer"
        PG[(PostgreSQL<br/>Conversations, Messages,<br/>Canonical, Metadata)]
        CACHE[File Cache<br/>Tagging Results]
    end

    subgraph "API Layer"
        REST[FastAPI REST API<br/>Async SQLAlchemy]
    end

    subgraph "Frontend"
        UI[React Web UI<br/>Dashboard, Analytics,<br/>Real-time Polling]
    end

    CC --> WD
    CC --> CLI
    CC --> UPLOAD
    CX --> WD
    CX --> CLI
    CX --> UPLOAD
    CR --> WD
    CR --> CLI
    OT --> WD

    WD --> REG
    CLI --> REG
    UPLOAD --> REG

    REG --> PAR
    PAR --> INC
    INC --> DUP
    DUP --> TAG
    TAG --> PG
    TAG --> CACHE

    PG --> CANON
    CANON --> SAMPLER
    SAMPLER --> BUILDER
    BUILDER --> PG

    PG --> REST
    REST --> UI

    style INC fill:#90EE90
    style DUP fill:#87CEEB
    style TAG fill:#FFB6C1
    style CANON fill:#FFD700
    style UI fill:#DDA0DD
```

### Key Components

| Layer | Component | Purpose |
|-------|-----------|---------|
| **Ingestion** | Watch Daemon | Monitors directories for new logs |
| | CLI Tool | Batch processing of log files |
| | Upload API | Web-based file uploads |
| **Processing** | Parser Registry | Auto-detects log format |
| | Plugin Parsers | Extensible parser implementations |
| | Incremental Parser | Optimized for appends (10-106x faster) |
| | Deduplication | Hash-based duplicate prevention |
| | AI Tagging | Sentiment, intent, outcome enrichment |
| **Canonicalization** | Canonicalizer | Token budget management |
| | SemanticSampler | Priority-based message selection |
| | PlayFormatBuilder | LLM-optimized narrative generation |
| **Storage** | PostgreSQL | Normalized schema with JSONB |
| | File Cache | 30-day TTL for tagging results |
| **API** | FastAPI | Async REST API |
| | SQLAlchemy 2.0 | Async ORM with repository pattern |
| **Frontend** | React 19 | Real-time polling, interactive charts |

## Data Flow

### Complete Ingestion Flow

```mermaid
sequenceDiagram
    participant User
    participant Ingestion as Ingestion Entry Point<br/>(CLI/API/Watch)
    participant Registry as Parser Registry
    participant Parser as Parser Plugin
    participant Incremental as Incremental Parser
    participant Dedup as Deduplication
    participant Tagging as AI Tagging Engine
    participant DB as PostgreSQL
    participant Cache as File Cache

    User->>Ingestion: Submit log file
    Ingestion->>Registry: Parse file
    Registry->>Parser: can_parse(file)?
    Parser-->>Registry: Yes

    Registry->>DB: Check if file exists

    alt File exists (RawLog found)
        Registry->>Incremental: Check for changes
        Incremental->>Incremental: Compare size & hash

        alt File UNCHANGED
            Incremental-->>Registry: Skip processing
            Registry-->>User: File unchanged
        else File APPENDED
            Incremental->>Parser: parse_incremental(offset, line)
            Parser-->>Incremental: New messages only
            Incremental->>DB: Append new messages
            Incremental-->>Registry: Success (10-106x faster)
        else File TRUNCATED/REWRITTEN
            Incremental->>Parser: parse(file) [full reparse]
            Parser-->>Registry: Full conversation
        end
    else New file
        Registry->>Dedup: Check duplicate (SHA-256 hash)

        alt Duplicate found
            Dedup-->>Registry: Skip (duplicate)
            Registry-->>User: Duplicate skipped
        else Not duplicate
            Registry->>Parser: parse(file)
            Parser-->>Registry: ParsedConversation
            Registry->>Tagging: Enrich (if enabled)

            alt Tagging enabled
                Tagging->>Cache: Check cache
                alt Cache hit
                    Cache-->>Tagging: Cached tags
                else Cache miss
                    Tagging->>Tagging: Call OpenAI API
                    Tagging->>Cache: Store result (30 days)
                end
            end

            Tagging->>DB: Store conversation
            DB-->>Registry: Success
            Registry-->>User: Ingestion complete
        end
    end
```

### Watch Daemon Flow

```mermaid
graph LR
    subgraph "Watch Daemon Lifecycle"
        START[Start Daemon] --> INIT[Initialize Watchdog]
        INIT --> SCAN[Scan existing files]
        SCAN --> WATCH[Monitor directory]

        WATCH --> |New file| DETECT[File detected]
        WATCH --> |Modified file| DETECT
        WATCH --> |Deleted file| LOG[Log event]

        DETECT --> WAIT[Wait for stability<br/>2s no changes]
        WAIT --> PROCESS[Process file]
        PROCESS --> |Success| WATCH
        PROCESS --> |Error| LOG
        LOG --> WATCH
    end

    PROCESS --> INGEST[Ingestion Pipeline<br/>Incremental parsing,<br/>deduplication, tagging]
```

## Parser Plugin System

### Parser Discovery and Registration

```mermaid
graph TB
    subgraph "Plugin Discovery"
        EP[Entry Points<br/>pip install packages]
        LOCAL[Local Directory<br/>~/.catsyphon/plugins/<br/>.catsyphon/parsers/]
    end

    subgraph "Parser Registry"
        REG[Parser Registry<br/>Singleton]
        BUILTIN[Built-in Parsers<br/>Claude Code]
    end

    subgraph "Parser Implementation"
        BASE[BaseParser Protocol<br/>can_parse, parse, metadata]
        CC_PARSER[Claude Code Parser]
        CUSTOM[Custom Parsers<br/>Your implementations]
    end

    EP --> REG
    LOCAL --> REG
    BUILTIN --> REG

    REG --> |Auto-detection| BASE
    BASE --> CC_PARSER
    BASE --> CUSTOM

    style BASE fill:#FFD700
    style REG fill:#87CEEB
```

### Parser Interface

Every parser must implement the `ConversationParser` protocol:

```python
class ConversationParser(Protocol):
    @property
    def metadata(self) -> ParserMetadata:
        """Parser name, version, capabilities"""
        ...

    def can_parse(self, file_path: Path) -> bool:
        """Fast format detection (check first few lines)"""
        ...

    def parse(self, file_path: Path) -> ParsedConversation:
        """Parse entire file into structured format"""
        ...
```

For incremental parsing support, implement `IncrementalParser`:

```python
class IncrementalParser(Protocol):
    def parse_incremental(
        self,
        file_path: Path,
        last_offset: int,
        last_line: int
    ) -> ParsedConversation:
        """Parse only new content from offset"""
        ...
```

### Parser Priority

Parsers are tried in registration order:

1. **Built-in parsers** (Claude Code)
2. **Entry point parsers** (pip installed)
3. **Local directory parsers** (development)

The **first parser** where `can_parse()` returns `True` is selected.

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    ORGANIZATION ||--o{ WORKSPACE : "contains"
    WORKSPACE ||--o{ PROJECT : "has"
    WORKSPACE ||--o{ DEVELOPER : "has"
    WORKSPACE ||--o{ CONVERSATION : "owns"
    WORKSPACE ||--o{ WATCH_CONFIG : "configures"

    PROJECT ||--o{ CONVERSATION : "groups"
    DEVELOPER ||--o{ CONVERSATION : "creates"

    CONVERSATION ||--o{ EPOCH : "spans"
    CONVERSATION ||--o{ MESSAGE : "contains"
    CONVERSATION ||--o{ FILE_TOUCHED : "modifies"
    CONVERSATION ||--o{ RAW_LOG : "sourced from"

    CONVERSATION {
        uuid id PK
        uuid workspace_id FK
        uuid project_id FK
        uuid developer_id FK
        string agent_type
        datetime start_time
        datetime end_time
        string status
        boolean success
        jsonb tags
        float sentiment_score
    }

    MESSAGE {
        uuid id PK
        uuid conversation_id FK
        uuid epoch_id FK
        string role
        text content
        int sequence_number
        datetime timestamp
    }

    EPOCH {
        uuid id PK
        uuid conversation_id FK
        datetime start_time
        datetime end_time
        float sentiment_score
        jsonb metadata
    }

    FILE_TOUCHED {
        uuid id PK
        uuid conversation_id FK
        string file_path
        int lines_added
        int lines_deleted
        datetime timestamp
    }

    RAW_LOG {
        uuid id PK
        uuid conversation_id FK
        string file_path
        string content_hash
        int file_size_bytes
        int last_processed_offset
        int last_processed_line
        string partial_hash
    }

    CONVERSATION_CANONICAL {
        uuid id PK
        uuid conversation_id FK
        int version
        string canonical_type
        text narrative
        int token_count
        jsonb metadata
        jsonb config
    }

    INGESTION_JOB {
        uuid id PK
        uuid raw_log_id FK
        string status
        jsonb metrics
        string error_message
        timestamp created_at
    }
```

### Key Tables

#### Core Entities
- **organizations**: Multi-workspace companies
- **workspaces**: Data isolation boundary (multi-tenancy)
- **projects**: Code projects/repositories
- **developers**: Users creating conversations

#### Conversation Data
- **conversations**: Main conversation/session entity
- **epochs**: Time segments within conversations (for sentiment tracking)
- **messages**: Individual messages (user/assistant turns)
- **files_touched**: File modifications tracked in conversation
- **raw_logs**: Source file metadata and incremental parsing state

#### Configuration
- **watch_configurations**: Directory monitoring settings
- **collector_configs**: Remote collector agent settings (future)

#### Canonicalization & Processing
- **conversation_canonical**: Cached LLM-optimized representations
- **ingestion_jobs**: Processing status and metrics tracking

### Indexes

Optimized for common query patterns:

```sql
-- Conversation queries
CREATE INDEX idx_conv_workspace ON conversations(workspace_id);
CREATE INDEX idx_conv_project ON conversations(project_id);
CREATE INDEX idx_conv_developer ON conversations(developer_id);
CREATE INDEX idx_conv_start_time ON conversations(start_time);
CREATE INDEX idx_conv_agent_type ON conversations(agent_type);

-- Message queries
CREATE INDEX idx_msg_conversation ON messages(conversation_id);
CREATE INDEX idx_msg_epoch ON messages(epoch_id);
CREATE INDEX idx_msg_sequence ON messages(conversation_id, sequence_number);

-- File tracking
CREATE INDEX idx_file_conversation ON files_touched(conversation_id);
CREATE INDEX idx_file_path ON files_touched(file_path);

-- Deduplication
CREATE INDEX idx_rawlog_hash ON raw_logs(content_hash);
CREATE UNIQUE INDEX idx_rawlog_path ON raw_logs(file_path);
```

## Incremental Parsing

### Performance Improvement

Incremental parsing provides dramatic performance improvements for files being actively appended:

| Scenario | Speedup | Memory Reduction |
|----------|---------|------------------|
| Small append (1→100 messages) | **9.9x faster** | 45x less |
| Medium log (10→1000 messages) | **36.6x faster** | 45x less |
| Large log (1→5000 messages) | **106x faster** | 465x less |
| Multiple sequential appends | **14x faster** | N/A |

### Change Detection Algorithm

```mermaid
graph TD
    START[Parse Request] --> CHECK{RawLog exists?}

    CHECK -->|No| FULL[Full Parse<br/>Store state]
    CHECK -->|Yes| COMPARE[Compare file state]

    COMPARE --> SIZE{Size changed?}

    SIZE -->|No| HASH{Hash changed?}
    HASH -->|No| UNCHANGED[Status: UNCHANGED<br/>Skip processing]
    HASH -->|Yes| REWRITE[Status: REWRITE<br/>Full reparse]

    SIZE -->|Smaller| TRUNCATE[Status: TRUNCATE<br/>Full reparse]
    SIZE -->|Larger| APPEND_CHECK[Check partial hash]

    APPEND_CHECK --> PARTIAL{Partial hash<br/>matches?}
    PARTIAL -->|No| REWRITE
    PARTIAL -->|Yes| APPEND[Status: APPEND<br/>Incremental parse]

    APPEND --> READ[Read from last_offset]
    READ --> PARSE[Parse new content only]
    PARSE --> UPDATE[Update state<br/>new offset, line, hash]

    FULL --> STORE[Store state<br/>offset, line, hash]
    REWRITE --> STORE
    TRUNCATE --> STORE

    UPDATE --> SUCCESS[Return result]
    STORE --> SUCCESS
    UNCHANGED --> SUCCESS

    style APPEND fill:#90EE90
    style UNCHANGED fill:#87CEEB
    style SUCCESS fill:#FFD700
```

### State Tracking

The `raw_logs` table stores parsing state:

```python
class RawLog(Base):
    file_path: str                    # Absolute path to source file
    content_hash: str                 # SHA-256 hash of entire file
    file_size_bytes: int             # File size in bytes
    last_processed_offset: int       # Byte offset of last parsed position
    last_processed_line: int         # Line number of last parsed message
    partial_hash: str                # Hash of first 64KB (for append detection)
```

### Incremental Parsing Flow

```mermaid
sequenceDiagram
    participant IP as Ingestion Pipeline
    participant IC as Incremental<br/>Change Detector
    participant P as Parser
    participant DB as Database

    IP->>DB: Get RawLog by file_path
    DB-->>IP: Previous state (offset, line, hash)

    IP->>IC: Detect change type
    IC->>IC: Compare size & hashes
    IC-->>IP: ChangeType (APPEND/REWRITE/TRUNCATE/UNCHANGED)

    alt APPEND
        IP->>P: parse_incremental(offset, line)
        P->>P: Seek to offset
        P->>P: Parse new messages only
        P-->>IP: New messages
        IP->>DB: Append messages to conversation
        IP->>DB: Update RawLog state
    else REWRITE or TRUNCATE
        IP->>P: parse(file_path) [full parse]
        P-->>IP: Full conversation
        IP->>DB: Replace conversation
        IP->>DB: Update RawLog state
    else UNCHANGED
        IP-->>IP: Skip processing
    end
```

## Canonicalization System

The canonicalization system converts raw conversation logs into optimized, hierarchical narrative representations for efficient LLM analysis.

### Key Benefits

| Benefit | Improvement |
|---------|-------------|
| Tagging Latency | 50%+ reduction |
| Token Efficiency | 90%+ fit within 10K budget |
| API Cost Reduction | 80-90% fewer OpenAI calls |
| Context Quality | Hierarchical agent context |

### Canonicalization Flow

```mermaid
graph TB
    subgraph "Input"
        CONV[Conversation + Messages]
        CHILDREN[Child Conversations]
    end

    subgraph "Canonicalization Module"
        CACHE{Cache Check}
        CONFIG[CanonicalConfig<br/>Token Budget]
        SAMPLER[SemanticSampler<br/>Priority Selection]
        BUILDER[PlayFormatBuilder<br/>Narrative Generation]
    end

    subgraph "Output"
        DB[(conversation_canonical)]
        CONSUMERS[Tagging / Insights / API]
    end

    CONV --> CACHE
    CACHE -->|Miss| CONFIG
    CACHE -->|Hit| DB
    CONFIG --> SAMPLER
    CHILDREN --> SAMPLER
    SAMPLER --> BUILDER
    BUILDER --> DB
    DB --> CONSUMERS

    style CACHE fill:#f9f,stroke:#333,stroke-width:2px
    style DB fill:#bbf,stroke:#333,stroke-width:2px
```

### Canonical Types

| Type | Token Budget | Use Case |
|------|-------------|----------|
| **TAGGING** | 8K | Quick metadata extraction |
| **INSIGHTS** | 12K | Analytics and patterns |
| **EXPORT** | 20K | Full representation |

### Sampling Strategies

| Strategy | Budget | Best For |
|----------|--------|----------|
| **semantic** | Enforced | Most use cases (priority-based) |
| **epoch** | Enforced | Workflow analysis (full first/last epochs) |
| **chronological** | Unlimited | Large context models, exports |

### Message Priority

```python
Priority Levels:
- 1000: First/last messages (always included)
- 900:  Error messages
- 800:  Tool calls
- 700:  Thinking content
- 600:  Epoch boundaries
- 500:  Code changes
```

### Play Format Narrative

The builder generates a theatrical "play" format optimized for LLM comprehension:

```
=== CONVERSATION: claude-code-2024-11-21-14-30-00 ===
Agent: claude-code v1.2.5
Type: main
Duration: 17 minutes 32 seconds
Status: COMPLETED (SUCCESS)
Messages: 42 | Epochs: 3 | Files: 5

--- EPOCH 1 ---

[14:30:15] USER: Help me implement JWT authentication
  [PRIORITY: first]

[14:30:30] ASSISTANT: I'll help you add JWT authentication...
  [TOOLS: Glob, Read]
    ✓ Read: /app/models/user.py

┌─ AGENT DELEGATION: child-session-id ─┐
│ Type: agent
│ Tools: Read, Edit
│   [14:37:05] AGENT: Analyzing...
└────────────────────────────────────────┘

=== SUMMARY ===
Outcome: SUCCESS
Intent: feature_add
Sampling: 18/42 messages (43%)
```

For full details, see [Canonicalization Architecture](./docs/canonicalization-architecture.md).

---

## Insights System

CatSyphon extracts 60+ insights from conversation logs to measure agent-human collaboration effectiveness.

### Insight Categories

```mermaid
pie title Insights Distribution
    "Session Success" : 18
    "Developer Experience" : 18
    "Tool Usage" : 9
    "Temporal Metrics" : 9
    "Code Productivity" : 15
    "Error Analysis" : 6
```

| Category | Insights | Key Metrics |
|----------|----------|-------------|
| **Session Success** | 18 | Success rate by project, developer, intent |
| **Developer Experience** | 18 | Sentiment trends, frustration detection |
| **Tool Usage** | 9 | Agent behavior, tool effectiveness |
| **Temporal Metrics** | 9 | Duration analysis, time patterns |
| **Code Productivity** | 15 | Lines changed, files touched |
| **Error Analysis** | 6 | Problem patterns, resolution rates |

### Example Insights

**Success Rate by Context:**
- Overall success rate: `SUM(success=True) / COUNT(*)`
- Success by project: Identify difficult codebases
- Success by developer: Find learning opportunities
- Success by intent: Compare task type effectiveness

**Intent vs. Outcome Analysis:**
- Success rate by intent type
- Average duration by intent
- Intent-outcome matrix heatmap
- Sentiment by intent type

**Tool Usage Patterns:**
- Most used tools per project
- Tool call success/failure rates
- Tool call sequences
- Agent delegation frequency

For the complete catalog, see [Insights Comprehensive Analysis](./docs/insights-comprehensive-analysis.md).

---

## Frontend Architecture

### Component Structure

```mermaid
graph TB
    subgraph "Pages (Routes)"
        DASH[Dashboard<br/>System overview]
        PROJ_LIST[Project List<br/>All projects]
        PROJ_DETAIL[Project Detail<br/>Epic 7: Analytics dashboard]
        CONV_LIST[Conversation List<br/>Search & filter]
        CONV_DETAIL[Conversation Detail<br/>Messages, files, tags]
        SETUP[Setup<br/>Onboarding wizard]
        INGEST[Ingestion<br/>Upload & watch management]
    end

    subgraph "Shared Components"
        CHART[Chart Components<br/>Recharts wrappers]
        TABLE[Table Components<br/>Sortable, filterable]
        LAYOUT[Layout<br/>Navigation, header]
        UI[shadcn/ui<br/>Base components]
    end

    subgraph "Data Layer"
        QUERY[TanStack Query<br/>Caching, polling]
        API[API Client<br/>Type-safe fetch]
    end

    subgraph "Backend API"
        REST[FastAPI REST<br/>http://localhost:8000]
    end

    DASH --> CHART
    PROJ_DETAIL --> CHART
    PROJ_DETAIL --> TABLE
    CONV_LIST --> TABLE

    DASH --> QUERY
    PROJ_LIST --> QUERY
    PROJ_DETAIL --> QUERY
    CONV_LIST --> QUERY
    CONV_DETAIL --> QUERY

    QUERY --> API
    API --> REST

    CHART --> UI
    TABLE --> UI
    LAYOUT --> UI

    style PROJ_DETAIL fill:#90EE90
    style QUERY fill:#87CEEB
```

### Real-Time Data Strategy

```mermaid
sequenceDiagram
    participant User
    participant UI as React Component
    participant Query as TanStack Query
    participant API as Backend API
    participant DB as PostgreSQL

    User->>UI: Load page
    UI->>Query: useQuery('project-stats')
    Query->>API: GET /projects/{id}/stats
    API->>DB: SELECT conversations...
    DB-->>API: Data
    API-->>Query: JSON response
    Query-->>UI: Cached data
    UI-->>User: Render


    Note over Query: 15 seconds pass...

    Query->>API: GET /projects/{id}/stats
    API->>DB: SELECT conversations...
    DB-->>API: Updated data
    API-->>Query: JSON response

    alt Data changed
        Query->>UI: Trigger re-render
        UI->>UI: Highlight new items
        UI-->>User: Show freshness indicator
    else No changes
        Query->>Query: Update cache timestamp
    end

    Note over Query,UI: Automatic refetch<br/>every 15 seconds
```

### Key Frontend Features

1. **Auto-refresh polling**: 15-second intervals with TanStack Query
2. **Freshness indicators**: Shows when data was last updated
3. **New item highlighting**: Visual indication of new conversations
4. **Optimistic updates**: Immediate UI feedback for mutations
5. **Smart caching**: Deduplication and background refetching

## API Design

### REST Endpoint Organization

```
/
├── /health                          # Health check
├── /ready                           # Readiness probe
├── /docs                            # Swagger UI
│
├── /setup                           # Onboarding wizard
│   ├── GET  /status                 # Check setup status
│   └── POST /initialize             # Create workspace
│
├── /conversations                   # Conversation queries
│   ├── GET  /                       # List with filters
│   ├── GET  /{id}                   # Get by ID
│   ├── GET  /{id}/messages          # Get messages
│   ├── GET  /{id}/files             # Get file changes
│   ├── GET  /{id}/canonical         # Get canonical representation
│   ├── GET  /{id}/canonical/narrative  # Get narrative only
│   └── POST /{id}/canonical/regenerate # Force regenerate
│
├── /projects                        # Project analytics
│   ├── GET  /                       # List projects
│   ├── GET  /{id}/stats             # Project statistics (Epic 7)
│   ├── GET  /{id}/sessions          # Session list (Epic 7)
│   └── GET  /{id}/files             # File aggregations
│
├── /stats                           # System-wide statistics
│   ├── GET  /overview               # Dashboard metrics
│   ├── GET  /by-project             # Project breakdown
│   └── GET  /by-developer           # Developer patterns
│
├── /metadata                        # Lookup tables
│   ├── GET  /projects               # All projects
│   ├── GET  /developers             # All developers
│   └── GET  /workspaces             # All workspaces
│
├── /upload                          # File upload
│   └── POST /                       # Multipart upload
│
├── /ingestion                       # Ingestion management
│   ├── POST /process                # Process log file
│   ├── GET  /jobs                   # List ingestion jobs
│   ├── GET  /jobs/{id}              # Get job details
│   └── GET  /stats                  # Pipeline performance stats
│
└── /watch                           # Directory watching
    ├── GET    /configs              # List watch configs
    ├── POST   /configs              # Create watch config
    ├── GET    /configs/{id}         # Get watch config
    ├── PUT    /configs/{id}         # Update watch config
    ├── DELETE /configs/{id}         # Delete watch config
    ├── POST   /configs/{id}/start   # Start daemon
    ├── POST   /configs/{id}/stop    # Stop daemon
    └── GET    /configs/{id}/status  # Daemon status
```

### Query Parameters (Epic 7 Features)

**GET /projects/{id}/stats**
- `date_range`: Filter by date (7d, 30d, 90d, all)

**GET /projects/{id}/sessions**
- `page`, `page_size`: Pagination
- `developer`: Filter by developer username
- `outcome`: Filter by success/failed status
- `date_from`, `date_to`: Date range filters
- `sort_by`: Column to sort (start_time, duration, status, developer)
- `order`: Sort order (asc, desc)

### Response Models (Pydantic)

All endpoints return typed Pydantic models:

```python
class ProjectStats(BaseModel):
    project_id: UUID
    session_count: int
    total_messages: int
    total_files_changed: int
    success_rate: Optional[float]
    avg_session_duration_seconds: Optional[float]
    first_session_at: Optional[datetime]
    last_session_at: Optional[datetime]
    top_features: list[str]
    top_problems: list[str]
    tool_usage: dict[str, int]
    developer_count: int
    developers: list[str]
    sentiment_timeline: list[SentimentTimelinePoint]
```

## Key Design Decisions

### 1. Plugin-Based Parser System

**Decision**: Use a registry pattern with auto-detection

**Rationale**:
- Extensibility: Easy to add new agent support
- Separation of concerns: Each parser is independent
- Auto-detection: No manual format specification needed
- Entry points: Standard Python packaging for distribution

**Trade-offs**:
- Slightly slower than hardcoded parsers
- Requires parsers to implement `can_parse()` efficiently

### 2. Incremental Parsing

**Decision**: Store parsing state and only process new content

**Rationale**:
- Massive performance improvements (10-106x faster)
- Essential for live file watching (watch daemon)
- Reduces memory usage by 45-465x
- Graceful degradation to full parse if needed

**Trade-offs**:
- Additional state tracking in database
- Complexity in change detection logic
- Not all parsers may support incremental mode

### 3. Hash-Based Deduplication

**Decision**: Use SHA-256 content hash for duplicate detection

**Rationale**:
- Prevents reprocessing identical files
- Content-based (not path-based)
- Cryptographically secure (collision-resistant)
- Fast computation (modern CPUs optimize SHA-256)

**Trade-offs**:
- Requires hashing entire file
- Storage overhead for hashes
- Can't detect semantic duplicates (only exact matches)

### 4. AI Tagging with File Cache

**Decision**: Use OpenAI GPT-4o-mini with 30-day file cache

**Rationale**:
- Cost reduction: 80-90% savings on repeated ingestions
- Fast: Cache lookups are instant
- Simple: File-based, no database overhead
- TTL: Automatic cleanup of stale entries

**Trade-offs**:
- Cache can become stale if model improves
- File system dependency (not distributed)
- Manual cache invalidation required for updates

### 5. Canonicalization System

**Decision**: Convert conversations to token-budgeted, theatrical narrative format

**Rationale**:
- 50%+ reduction in tagging latency
- 80-90% fewer OpenAI API calls through caching
- Priority-based sampling preserves key context
- LLM-optimized format improves classification accuracy
- Hierarchical context for parent/child conversations

**Trade-offs**:
- Additional storage for canonical representations
- Cache invalidation complexity
- Token counting overhead

### 6. Real-Time Polling (15s Intervals)

**Decision**: Client-side polling with TanStack Query

**Rationale**:
- Simple implementation (no WebSockets)
- Built-in caching and deduplication
- Works with standard HTTP infrastructure
- Battery-friendly intervals

**Trade-offs**:
- Not true real-time (15s delay)
- Extra network requests
- Less efficient than WebSockets for high-frequency updates

### 7. Repository Pattern for Data Access

**Decision**: Separate repository classes for each entity

**Rationale**:
- Type safety: Strong typing with SQLAlchemy 2.0
- Testability: Easy to mock repositories
- Separation: Business logic separate from ORM
- Reusability: Common queries encapsulated

**Trade-offs**:
- More boilerplate code
- Indirection layer
- Can be over-engineering for simple CRUD

### 8. Monorepo Structure

**Decision**: Single repository for backend and frontend

**Rationale**:
- Shared documentation and issue tracking
- Atomic commits across frontend/backend
- Single CI/CD pipeline
- Easier for small teams

**Trade-offs**:
- Larger repository size
- Mixed language tooling
- Potential for cross-contamination

## Performance Considerations

### Database Optimization

1. **Indexes**: Strategic indexes on foreign keys and query columns
2. **JSONB**: Flexible metadata storage with GIN indexes for search
3. **Connection pooling**: SQLAlchemy async connection pool
4. **Query optimization**: Eager loading with `joinedload()` where needed

### API Performance

1. **Async/await**: Non-blocking I/O throughout
2. **Pagination**: Default page sizes to prevent large result sets
3. **Selective fields**: Only fetch required columns
4. **Caching**: TanStack Query client-side caching

### Frontend Performance

1. **Code splitting**: Route-based lazy loading
2. **React Query**: Automatic caching and deduplication
3. **Virtualization**: Large lists use react-virtual (future)
4. **Memoization**: useMemo/useCallback for expensive computations

## Security Considerations

### Authentication & Authorization

**Current**: Not implemented (single-user mode)

**Planned**:
- Multi-workspace isolation (database ready)
- JWT-based authentication
- Role-based access control (RBAC)
- API key authentication for CLI

### Data Protection

1. **SQL injection**: Prevented by SQLAlchemy ORM
2. **XSS**: React auto-escaping, CSP headers
3. **CORS**: Configurable origin whitelist
4. **File uploads**: Validated file types and size limits

### Secrets Management

1. **OpenAI API keys**: Environment variables only
2. **Database credentials**: Never committed to code
3. **.env.example**: Template without secrets
4. **File cache**: Local filesystem only (no sensitive data)

## Deployment Architecture (Future)

```mermaid
graph TB
    subgraph "Cloud Provider"
        LB[Load Balancer]

        subgraph "Application Tier"
            API1[FastAPI Instance 1]
            API2[FastAPI Instance 2]
            API3[FastAPI Instance N]
        end

        subgraph "Worker Tier"
            W1[Watch Daemon Worker 1]
            W2[Watch Daemon Worker 2]
            W3[Watch Daemon Worker N]
        end

        subgraph "Data Tier"
            PG[(PostgreSQL<br/>Managed DB)]
            REDIS[(Redis Cache)]
            S3[S3 Bucket<br/>File Storage]
        end

        subgraph "Monitoring"
            PROM[Prometheus]
            GRAF[Grafana]
            LOG[Centralized Logging]
        end
    end

    LB --> API1
    LB --> API2
    LB --> API3

    API1 --> PG
    API2 --> PG
    API3 --> PG

    API1 --> REDIS
    API2 --> REDIS
    API3 --> REDIS

    W1 --> PG
    W2 --> PG
    W3 --> PG

    W1 --> S3
    W2 --> S3
    W3 --> S3

    API1 --> PROM
    API2 --> PROM
    W1 --> PROM

    PROM --> GRAF
    API1 --> LOG
    W1 --> LOG
```

## Conclusion

CatSyphon's architecture prioritizes:

| Priority | Implementation |
|----------|---------------|
| **Extensibility** | Plugin system for new agent support |
| **Performance** | Incremental parsing (10-106x speedups), canonicalization caching |
| **Insights** | 60+ metrics across 6 categories |
| **Simplicity** | Standard patterns (REST API, React, PostgreSQL) |
| **Maintainability** | Clear separation of concerns, 84% test coverage |
| **Future-proofing** | Multi-tenancy ready, scalable design |

For more details, see:
- [Implementation Plan](./docs/implementation-plan.md)
- [Parser Plugin SDK](./docs/plugin-sdk.md)
- [Incremental Parsing Guide](./docs/incremental-parsing.md)
- [Canonicalization Architecture](./docs/canonicalization-architecture.md)
- [Insights Comprehensive Analysis](./docs/insights-comprehensive-analysis.md)
