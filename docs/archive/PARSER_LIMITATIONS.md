# Parser Limitations

This document describes known limitations and edge cases for conversation log parsers.

## Claude Code Parser

### Legacy Format (Pre-v2.0)

**Issue:** Parser cannot properly handle hierarchical agent conversations from older Claude Code versions.

**Affected Files:** Approximately 58 conversation files in existing datasets

#### Legacy Format Characteristics

Older Claude Code versions (pre-v2.0) used a different file structure:

- **File naming:** `{session_id}.jsonl` (all messages in one file)
- **Agent identification:** Per-message `isSidechain: true` flag
- **No separation:** Agent and main messages mixed in same file
- **Missing field:** No `agentId` field in messages

**Example legacy message:**
```json
{
  "parentUuid": null,
  "isSidechain": true,
  "sessionId": "904bb889-576c-4193-9fb9-2780c4db9028",
  "version": "2.0.17",
  "type": "user",
  "message": {"role": "user", "content": "..."}
}
```

#### Modern Format (v2.0+)

Current Claude Code versions use separate files for better organization:

- **Main conversations:** `{session_id}.jsonl`
- **Agent conversations:** `agent-{agent_id}.jsonl`
- **Agent identification:** `agentId` field in every message
- **Parent linking:** Agent's `sessionId` contains parent's session ID

**Example modern message:**
```json
{
  "parentUuid": null,
  "isSidechain": true,
  "agentId": "d3846599",
  "sessionId": "10c62eac-5b38-4fbc-9ae4-d4182ec840b0",
  "version": "2.0.17",
  "type": "user",
  "message": {"role": "user", "content": "..."}
}
```

#### Current Parser Behavior

**For legacy files:**
1. Parser detects `isSidechain: true` in messages
2. Classifies conversation as "agent" type
3. Cannot extract `parent_session_id` (no `agentId` field)
4. Cannot link to parent conversation
5. Results in orphaned agent conversations

**Statistics from test dataset:**
- Total agents: 203
- Successfully linked (modern format): 106 (52.2%)
- Orphaned (legacy format): 58 (28.6%)
- Orphaned (incomplete parent files): 39 (19.2%)

#### Workarounds

**None available.** Legacy format files will be parsed as agent conversations but cannot be linked to parent conversations.

#### Impact

- **Functional:** Parser works correctly for modern format (v2.0+)
- **Legacy support:** Limited - files are ingested but hierarchy is lost
- **Data integrity:** No data loss, just missing parent-child relationships
- **Migration:** No automatic migration path from legacy to modern format

#### Detection

To identify legacy format files in your dataset:

```sql
-- Find agent conversations without parent_session_id
SELECT
    metadata->>'session_id' as session_id,
    conversation_type,
    agent_metadata
FROM conversations
WHERE conversation_type = 'agent'
  AND agent_metadata->>'parent_session_id' IS NULL;
```

Files with `agent_metadata->>'parent_session_id' IS NULL` are likely legacy format.

#### Recommendations

1. **For new deployments:** Use Claude Code v2.0+ to ensure proper hierarchy
2. **For existing datasets:** Accept that legacy files cannot be fully hierarchical
3. **For migration:** Consider re-running conversations with modern Claude Code if hierarchy is critical
4. **For analysis:** Filter out legacy orphaned agents when analyzing parent-child relationships

### Incomplete Conversation Files

**Issue:** Some conversation files contain only metadata without actual messages.

**Characteristics:**
- File exists with valid name pattern: `{session_id}.jsonl`
- Contains only `summary` and `file-history-snapshot` messages
- Missing `sessionId` and `version` fields
- No user/assistant conversation messages

**Example incomplete file:**
```json
{"type":"summary","summary":"Project setup","leafUuid":"..."}
{"type":"file-history-snapshot","messageId":"...","snapshot":{...}}
```

**Parser behavior:**
- `can_parse()` correctly rejects these files (no sessionId found)
- Files are not ingested
- Agent conversations referencing these parents remain orphaned

**Statistics:**
- Incomplete files: 23
- Orphaned agents due to incomplete parents: 39
- Unique missing parent session IDs: 20

**Recommendation:** This is correct behavior. These files don't represent actual conversations and should not be ingested.

## Summary

| Issue | Affected Files | Impact | Status |
|-------|---------------|--------|--------|
| Legacy format without agentId | ~58 files | Cannot link to parents | **Documented limitation** |
| Incomplete conversation files | 23 files | 39 orphaned children | **Working as intended** |
| Modern format | 106+ files | Full hierarchy support | **Fully supported** |

## Version History

- **2025-11-18:** Initial documentation of Claude Code parser limitations
