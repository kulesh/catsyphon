# Type System Reconciliation: aiobscura ↔ CatSyphon

This document compares the data models, type systems, and ubiquitous language between aiobscura (the collector) and CatSyphon (the enterprise backend), and proposes a reconciled model.

## 1. Ubiquitous Language Comparison

### Core Entity Naming

| Concept | aiobscura | CatSyphon | Recommendation |
|---------|-----------|-----------|----------------|
| Primary work unit | `Session` | `Conversation` | **Session** (aiobscura is more recent thinking) |
| Conversation flow | `Thread` | `Epoch` | **Thread** (semantic meaning clearer) |
| Message producer | `Author` with `AuthorRole` | `role` (string) | **Author** with **AuthorRole** enum |
| AI product | `Assistant` (enum) | `agent_type` (string) | **Assistant** enum |
| LLM model | `BackingModel` | N/A (in metadata) | **BackingModel** (explicit tracking) |
| Source file | `SourceFile` | `RawLog` | Keep both (different purposes) |
| Ingestion state | `Checkpoint` | `last_processed_offset` etc. | **Checkpoint** (cleaner abstraction) |

### Author Roles

| aiobscura | CatSyphon | Notes |
|-----------|-----------|-------|
| `Human` | `user` | **Human** preferred (avoids "user" ambiguity) |
| `Caller` | N/A | Add to CatSyphon (CLI/parent invoking) |
| `Assistant` | `assistant` | ✅ Aligned |
| `Agent` | N/A (in metadata) | Add explicit role |
| `Tool` | N/A (in tool_results) | Add explicit role |
| `System` | `system` | ✅ Aligned |

**Recommendation**: Adopt aiobscura's 6-role `AuthorRole` enum exactly.

### Message Types

| aiobscura | CatSyphon | Notes |
|-----------|-----------|-------|
| `Prompt` | N/A (role=user) | Add explicit type |
| `Response` | N/A (role=assistant) | Add explicit type |
| `ToolCall` | `tool_calls` (JSONB) | Make first-class type |
| `ToolResult` | `tool_results` (JSONB) | Make first-class type |
| `Plan` | `PlanInfo` (parsed model) | Make first-class type |
| `Summary` | `summaries` (in metadata) | Make first-class type |
| `Context` | N/A | Add for context injection |
| `Error` | N/A (in metadata) | Make first-class type |

**Recommendation**: Adopt aiobscura's 8-type `MessageType` enum.

### Thread vs Epoch

| Aspect | aiobscura `Thread` | CatSyphon `Epoch` |
|--------|-------------------|------------------|
| Meaning | Conversation flow (main/agent) | Segment/turn grouping |
| Hierarchy | `parent_thread_id` | N/A |
| Spawning | `spawned_by_message_id` | N/A |
| Types | Main, Agent, Background | N/A (flat) |

**Recommendation**:
- Adopt `Thread` for conversation flows (main, agent, background)
- Keep `Epoch` for analysis grouping (sentiment, intent, outcome per segment)
- These are complementary, not conflicting

### Session Status

| aiobscura | CatSyphon | Notes |
|-----------|-----------|-------|
| `Active` | `open` | Align to **Active** |
| `Inactive` | N/A | Add to CatSyphon |
| `Stale` | N/A | Add to CatSyphon |
| N/A | `completed` | Keep (outcome state) |
| N/A | `abandoned` | Keep (outcome state) |

**Recommendation**: Split into two enums:
- `ActivityStatus`: Active, Inactive, Stale (liveness)
- `OutcomeStatus`: Open, Completed, Abandoned (completion)

---

## 2. Structural Divergences

### Entity Hierarchy

**aiobscura**:
```
Project
  └── Session
        ├── Thread (Main, Agent, Background)
        │     └── Message
        └── Plan
```

**CatSyphon**:
```
Workspace
  └── Conversation
        ├── Epoch
        │     └── Message
        │           └── FileTouched
        ├── Children (agent conversations)
        └── RawLog
```

**Recommendation**:
```
Workspace
  └── Project
        └── Session (renamed from Conversation)
              ├── Thread (new - replaces hierarchy)
              │     └── Message
              ├── Epoch (kept - for analysis segments)
              │     └── FileTouched
              ├── Plan (promoted from metadata)
              └── RawLog
```

### Timestamp Semantics

| aiobscura | CatSyphon | Recommendation |
|-----------|-----------|----------------|
| `emitted_at` | `timestamp` | **emitted_at** (when produced) |
| `observed_at` | `created_at` | **observed_at** (when parsed) |

CatSyphon should adopt dual timestamps for accurate timeline reconstruction.

### Conversation Type Mapping

| aiobscura ThreadType | CatSyphon ConversationType | Recommendation |
|---------------------|---------------------------|----------------|
| `Main` | `MAIN` | ✅ Aligned |
| `Agent` | `AGENT` | ✅ Aligned |
| `Background` | N/A | Add to CatSyphon |
| N/A | `METADATA` | Keep (aiobscura doesn't have) |
| N/A | `MCP` | Keep (aiobscura doesn't have) |
| N/A | `SKILL` | Keep (aiobscura doesn't have) |
| N/A | `COMMAND` | Keep (aiobscura doesn't have) |
| N/A | `OTHER` | Keep (catch-all) |

**Recommendation**:
- Use `ThreadType` for thread-level classification (Main, Agent, Background)
- Use expanded `ConversationType` for session-level classification

### Assistant Enum

| aiobscura | CatSyphon | Notes |
|-----------|-----------|-------|
| `ClaudeCode` | `claude-code` (string) | Enum better |
| `Codex` | `codex` (string) | Enum better |
| `Aider` | `aider` (string) | Enum better |
| `Cursor` | `cursor` (string) | Enum better |

**Recommendation**: Use enum with values matching aiobscura.

---

## 3. Missing Entities

### In CatSyphon (from aiobscura)

| Entity | Purpose | Priority |
|--------|---------|----------|
| `BackingModel` | LLM version tracking | High |
| `Thread` | Conversation flow hierarchy | High |
| `SourceFile` | File-level ingestion state | Medium |
| `SessionMetrics` | Computed aggregates | Low (has ConversationInsights) |
| `PluginMetric` | Custom analytics | Low |
| `Assessment` | LLM-based evaluation | Low (has insights) |

### In aiobscura (from CatSyphon)

| Entity | Purpose | Priority |
|--------|---------|----------|
| `Organization` | Multi-workspace grouping | High (enterprise) |
| `Workspace` | Data isolation | High (enterprise) |
| `CollectorConfig` | Remote collector auth | High (enterprise) |
| `Epoch` | Analysis segmentation | Medium |
| `ConversationInsights` | Rich cached insights | Medium |
| `ConversationCanonical` | Pre-computed narratives | Low |
| `WatchConfiguration` | Directory monitoring | Low (local-first) |
| `IngestionJob` | Audit trail | Low (enterprise) |

---

## 4. Field-Level Divergences

### Message Fields

| Field | aiobscura | CatSyphon | Recommendation |
|-------|-----------|-----------|----------------|
| Sequence | `seq` (i32) | `sequence` (int) | `seq` (shorter) |
| Content type | `content_type` enum | N/A | Add `content_type` |
| Tool name | `tool_name` | In `tool_calls` JSONB | Promote to field |
| Tool input | `tool_input` (JSON) | In `tool_calls` JSONB | Promote to field |
| Tool result | `tool_result` | In `tool_results` JSONB | Promote to field |
| Duration | `duration_ms` | N/A | Add for tool timing |
| Source tracking | `source_file_path`, `source_offset`, `source_line` | N/A (in RawLog) | Add for traceability |
| Raw data | `raw_data` (JSON) | N/A (in RawLog) | Add per-message |

### Session/Conversation Fields

| Field | aiobscura | CatSyphon | Recommendation |
|-------|-----------|-----------|----------------|
| Name | N/A | `slug` | Keep `slug` |
| Git branch | N/A | `git_branch` (in metadata) | Promote to field |
| Working dir | N/A | `working_directory` (parsed) | Promote to field |
| Summaries | N/A | `summaries` (in metadata) | Keep in metadata |
| Compaction | N/A | `compaction_events` | Keep in metadata |

---

## 5. Protobuf Schema Alignment

The current protobuf (`proto/catsyphon/telemetry/v1/sessions.proto`) is already well-aligned with aiobscura. Key alignments:

✅ `AuthorRole` enum matches aiobscura exactly
✅ `MessageType` enum matches aiobscura exactly
✅ `ThreadType` enum matches aiobscura exactly
✅ `Assistant` enum matches aiobscura exactly
✅ `Session` → `Thread` → `Message` hierarchy matches
✅ Dual timestamps (`emitted_at_ns`, `observed_at_ns`)
✅ `raw_data` preservation
✅ `BackingModel` entity

**No changes needed to protobuf** - it was designed from aiobscura's types.

---

## 6. Reconciliation Recommendations

### Priority 1: Terminology Alignment (No Schema Change)

Update CatSyphon code and documentation to use consistent terminology:

| Current | New | Notes |
|---------|-----|-------|
| "Conversation" | "Session" (in docs, APIs) | Database table can stay |
| "user" role | "human" | Wire format change |
| `agent_type` string | `assistant` enum | Wire format change |

### Priority 2: Add Missing Enums (Schema Migration)

```sql
-- Add author_role enum
ALTER TABLE messages
ADD COLUMN author_role VARCHAR(20);  -- human, caller, assistant, agent, tool, system

-- Add message_type enum
ALTER TABLE messages
ADD COLUMN message_type VARCHAR(20);  -- prompt, response, tool_call, tool_result, plan, summary, context, error

-- Backfill from role
UPDATE messages SET
  author_role = CASE role WHEN 'user' THEN 'human' WHEN 'system' THEN 'system' ELSE 'assistant' END,
  message_type = CASE role WHEN 'user' THEN 'prompt' ELSE 'response' END;
```

### Priority 3: Add Thread Model (Schema Migration)

```sql
CREATE TABLE threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    parent_thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
    thread_type VARCHAR(20) NOT NULL DEFAULT 'main',
    spawned_by_message_id UUID REFERENCES messages(id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add thread reference to messages
ALTER TABLE messages ADD COLUMN thread_id UUID REFERENCES threads(id);
```

### Priority 4: Add BackingModel (Schema Migration)

```sql
CREATE TABLE backing_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}',
    UNIQUE (provider, model_id)
);

ALTER TABLE conversations
ADD COLUMN backing_model_id UUID REFERENCES backing_models(id);
```

### Priority 5: Add Dual Timestamps (Schema Migration)

```sql
ALTER TABLE messages
ADD COLUMN emitted_at TIMESTAMPTZ,
ADD COLUMN observed_at TIMESTAMPTZ;

-- Backfill
UPDATE messages SET
  emitted_at = timestamp,
  observed_at = created_at;
```

---

## 7. Summary: Type System Alignment

### Adopt from aiobscura (more recent thinking)

| Type | Reason |
|------|--------|
| `AuthorRole` enum (6 values) | Avoids "user" ambiguity, explicit Tool/Agent roles |
| `MessageType` enum (8 values) | Makes tool calls, plans first-class citizens |
| `ThreadType` enum (3 values) | Clean hierarchy for agent spawning |
| `Assistant` enum | Type-safe vs string |
| `BackingModel` entity | LLM tracking for cost/capability analysis |
| Dual timestamps | Accurate timeline reconstruction |
| `raw_data` per message | Lossless capture for reprocessing |
| `Checkpoint` abstraction | Cleaner incremental parsing |

### Keep from CatSyphon (enterprise features)

| Type | Reason |
|------|--------|
| `Organization` / `Workspace` | Multi-tenancy |
| `CollectorConfig` | Remote collector management |
| `Epoch` | Analysis segmentation with sentiment/intent |
| `ConversationType` (expanded) | MCP, Skill, Command distinctions |
| `ConversationInsights` | Rich LLM-generated insights |
| `IngestionJob` | Audit trail |
| `slug` field | Human-readable session names |

### Merged Model

The reconciled type system combines aiobscura's clean domain model with CatSyphon's enterprise features:

```
Organization (enterprise)
  └── Workspace (enterprise)
        └── Project
              └── Session (renamed from Conversation)
                    ├── backing_model_id → BackingModel
                    ├── Thread (new)
                    │     └── Message
                    │           ├── author_role (AuthorRole enum)
                    │           ├── message_type (MessageType enum)
                    │           ├── emitted_at, observed_at
                    │           └── raw_data (per-message)
                    ├── Epoch (kept for analysis)
                    ├── Plan (promoted)
                    └── RawLog (kept for file-level state)
```

---

## 8. Next Steps

1. **Update protobuf** - Already aligned, no changes needed
2. **Create migrations** - Add new columns/tables incrementally
3. **Update parsers** - Populate new fields from existing data
4. **Update API schemas** - Expose new types in responses
5. **Update documentation** - Use consistent terminology
6. **Backfill existing data** - Map old values to new enums
