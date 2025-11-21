# File Filtering and Skipped Files

## Overview

CatSyphon automatically filters out metadata-only files during ingestion to focus on actual conversational logs containing user-assistant interactions. This filtering prevents parse errors and reduces noise in your ingestion history.

## What Files Are Skipped?

### Metadata-Only Files

These are `.jsonl` files that contain **only** metadata entries without any actual conversation messages. They typically include:

- **Summary entries**: `type: "summary"` - Brief file summaries
- **File history snapshots**: `type: "file-history-snapshot"` - State tracking for files

### Example of a Metadata-Only File

```jsonl
{"type":"summary","summary":"Project setup completed","leafUuid":"..."}
{"type":"file-history-snapshot","messageId":"msg-1","snapshot":{...}}
```

These files **do not** contain the required conversation markers (`sessionId` and `version` fields) that identify actual Claude Code conversation logs.

## What Files Are Processed?

### Conversational Logs

Files containing actual user-assistant conversations with Claude Code. These files have:

- **Session markers**: Both `sessionId` and `version` fields
- **User messages**: `type: "user"` with user prompts
- **Assistant messages**: `type: "assistant"` with Claude's responses
- **Tool calls**: Function calls, file operations, etc.

### Example of a Conversational Log

```jsonl
{"sessionId":"test-session-001","version":"2.0.17","type":"user","uuid":"msg-001","timestamp":"2025-01-01T00:00:00.000Z","message":{"role":"user","content":"Hello"}}
{"sessionId":"test-session-001","version":"2.0.17","type":"assistant","uuid":"msg-002","timestamp":"2025-01-01T00:00:01.000Z","message":{"role":"assistant","content":"Hi there!"}}
```

## How Filtering Works

### Pre-Filter Detection

Before attempting to parse a file, CatSyphon performs a quick scan of the **first 5 lines** to detect conversation markers:

1. **Scan first 5 lines** for `sessionId` + `version` fields
2. **If found**: File is a conversational log → proceed to parsing
3. **If not found**: File is metadata-only → skip with explanation

This lightweight check avoids expensive parse attempts on files that will inevitably fail.

### Detection Algorithm

```python
# Pseudo-code
for line in first_5_lines(file):
    data = parse_json(line)
    if "sessionId" in data and "version" in data:
        return CONVERSATIONAL_LOG  # Process this file

return METADATA_ONLY  # Skip this file
```

## Viewing Skipped Files

### In the Web UI

Navigate to **Ingestion → Jobs** to view all ingestion activity, including skipped files:

- **Status column**: Shows "skipped" for filtered files
- **Error message**: Explains why the file was skipped
- **File path**: Shows the original file location
- **Timestamp**: When the skip occurred

**Example:**
```
Status: skipped
Message: Metadata-only file (no conversation messages found).
         These files typically contain only 'summary' or 'file-history-snapshot'
         entries and are not meant to be parsed as conversations.
File: ~/.claude/projects/my-project/metadata-only.jsonl
```

### In CLI Output

When using `catsyphon ingest`, skipped files are reported:

```bash
$ catsyphon ingest ~/.claude/projects/

Skipped 5 metadata-only file(s)
  - file-001.jsonl (no conversation messages)
  - file-002.jsonl (no conversation messages)
  - file-003.jsonl (no conversation messages)
  - file-004.jsonl (no conversation messages)
  - file-005.jsonl (no conversation messages)

Found 15 conversational log(s) to process

Parsing: conversation-001.jsonl... ✓ 42 messages, 8 tool calls
...
```

## Why This Matters

### Benefits of Filtering

1. **Cleaner ingestion history**: No false "failures" for files that aren't meant to be parsed
2. **Faster processing**: Skip files early without expensive parse attempts
3. **Better UX**: Clear distinction between actual failures and expected skips
4. **Reduced noise**: Ingestion logs focus on real issues

### Before Filtering (Old Behavior)

```
Found 20 file(s) to process
Parsing: conversation-001.jsonl... ✓
Parsing: metadata-only.jsonl... ✗ ParseFormatError: Missing required field: sessionId
Parsing: conversation-002.jsonl... ✓
...
Failed: 5 files
```

**Problem**: Users see "failures" for files that aren't meant to be conversations.

### After Filtering (New Behavior)

```
Skipped 5 metadata-only file(s)
Found 15 conversational log(s) to process
Parsing: conversation-001.jsonl... ✓
Parsing: conversation-002.jsonl... ✓
...
Successful: 15 files
```

**Benefit**: Only real conversational logs are attempted, skipped files are clearly labeled.

## Common Scenarios

### Scenario 1: Fresh Database Ingestion

When ingesting `~/.claude/projects/` for the first time:

- **Expected**: Some files will be skipped (metadata-only)
- **Typical rate**: 5-10% of files are metadata-only
- **What to do**: Nothing! This is normal and expected.

### Scenario 2: Watch Daemon Monitoring

When watching a directory for new files:

- **Behavior**: Metadata-only files are detected and skipped automatically
- **Tracking**: Skipped files appear in ingestion jobs with "skipped" status
- **Stats**: Watch daemon tracks skipped count separately from processed count

### Scenario 3: API Upload

When uploading files via the web UI or API:

- **Response**: Upload response includes status for each file
- **Skipped files**: Returned with `status: "skipped"` and explanation in `error` field
- **Success count**: Skipped files are counted as "successful" (not failed) since they were handled correctly

## Customization

### Adjusting Detection Depth

The default detection scans the **first 5 lines** of each file. This is configurable in the code:

```python
# In your code
from catsyphon.parsers.utils import is_conversational_log

# Default: check first 5 lines
is_conversational = is_conversational_log(file_path)

# Custom: check first 10 lines
is_conversational = is_conversational_log(file_path, max_lines=10)
```

**Trade-off**: Higher `max_lines` = more thorough detection but slower pre-filter.

## Troubleshooting

### "Too many files are being skipped"

**Possible causes:**
1. Files are incomplete (conversation was started but never had messages)
2. Files are corrupted or malformed
3. Files are from an unsupported agent format

**How to investigate:**
1. Check a skipped file manually to verify it's metadata-only
2. Look for `sessionId` and `version` fields in the file
3. If they're present, the file should have been processed - this indicates a bug

### "A conversational log was skipped by mistake"

**Possible cause:** File has `sessionId` + `version` after the first 5 lines.

**Solution:**
1. This is rare - most files have markers in the first line
2. If needed, increase `max_lines` in the detection function
3. Report this as a potential bug with the file structure

### "I want to see ALL parse attempts, even metadata files"

**Why:** You're debugging the parser or investigating file structure.

**Workaround:**
- The pre-filter is intentional and cannot be disabled via configuration
- For debugging, temporarily modify the code to bypass `is_conversational_log()` check
- This is an advanced use case - not recommended for production use

## Related Documentation

- [CLAUDE_CODE_LOG_FORMAT.md](./CLAUDE_CODE_LOG_FORMAT.md) - Claude Code log file structure
- [PARSER_LIMITATIONS.md](./PARSER_LIMITATIONS.md) - Parser limitations and known issues
- [implementation-plan.md](./implementation-plan.md) - Technical architecture details
