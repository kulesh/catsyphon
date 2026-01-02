"""LLM prompts for automation opportunity detection."""

SLASH_COMMAND_DETECTION_PROMPT = """Analyze this coding assistant conversation for slash command opportunities.

# What is a Slash Command?
A slash command is a reusable prompt template that users invoke with /command-name.
For example:
- `/commit` - Create a git commit with a good message
- `/review-pr` - Review a pull request for issues
- `/format-code` - Format code according to project standards

# Good Slash Command Candidates
Look for these patterns:
1. **Repeated Similar Requests** - User asks for the same type of task multiple times
2. **Multi-Step Workflows** - User gives detailed step-by-step instructions that could be templated
3. **Project-Specific Patterns** - Recurring patterns unique to this codebase/workflow
4. **Boilerplate Operations** - Tasks that follow a predictable structure

# What to Analyze

<conversation>
{narrative}
</conversation>

# Output Format

For each slash command opportunity, provide:
1. `command_name` - Suggested /command name (lowercase, hyphenated, 2-4 words max)
2. `title` - Brief human-readable title
3. `description` - What the command does and when to use it
4. `trigger_phrases` - 2-3 example phrases that indicate this command would help
5. `template` - Suggested command template (the prompt the command would execute)
6. `confidence` - Score from 0.0 to 1.0:
   - 0.8-1.0: Strong pattern, multiple clear examples in conversation
   - 0.6-0.8: Good pattern, at least one clear example
   - 0.4-0.6: Possible pattern, may be useful
   - Below 0.4: Weak pattern, don't include
7. `evidence` - Object with:
   - `quotes`: Array of 1-3 relevant quotes from the conversation
   - `pattern_count`: How many times this pattern appears

Return ONLY valid JSON in this format:
{{
  "recommendations": [
    {{
      "command_name": "run-tests-fix",
      "title": "Run tests and fix failures",
      "description": "Executes the test suite and automatically attempts to fix any failing tests",
      "trigger_phrases": [
        "run the tests and fix any failures",
        "make sure tests pass",
        "fix the failing tests"
      ],
      "template": "Run the test suite with `pytest`. For each failing test, analyze the error and fix the code. Re-run until all tests pass.",
      "confidence": 0.85,
      "evidence": {{
        "quotes": ["run the tests and fix errors", "make sure all tests pass before committing"],
        "pattern_count": 3
      }}
    }}
  ]
}}

Return an empty recommendations array if no good slash command candidates are found.
Only include recommendations with confidence >= 0.4.
Maximum 5 recommendations, ordered by confidence (highest first)."""


SYSTEM_PROMPT = """You are an expert at analyzing developer workflows to identify automation opportunities.

Your task is to detect patterns in coding assistant conversations that could become reusable slash commands.

Focus on:
1. Repeated request patterns (semantically similar, not just syntactically)
2. Multi-step workflows that follow a structure
3. Project-specific conventions that could be standardized

Be conservative - only suggest commands that would genuinely save time.
Quality over quantity - 2-3 high-confidence recommendations are better than 5 weak ones.

Return only valid JSON."""


MCP_DETECTION_PROMPT = """Analyze this coding assistant conversation for MCP (Model Context Protocol) server opportunities.

# What is an MCP Server?
An MCP server extends the agent's capabilities by providing direct integrations with external systems.
Examples:
- `playwright-mcp` - Browser automation, UI testing, screenshots
- `postgres-mcp` - Direct database queries, schema inspection
- `github-mcp` - PR management, issue tracking, actions
- `slack-mcp` - Team notifications, status updates
- `aws-mcp` - Cloud resource management

# Signs the Developer Needs an MCP Server
Look for:
1. **Workarounds** - Manual steps, multi-command bash sequences, copy-paste workflows
2. **External Tool Usage** - Repeated use of curl, database clients, cloud CLIs
3. **Friction Signals** - Errors, retries, frustration with external services
4. **Capability Gaps** - Agent couldn't do something that required external access

# Pre-Detected Categories
The following categories have been detected via signal matching. Evaluate each for recommendation:
{detected_categories}

# What to Analyze

<conversation>
{narrative}
</conversation>

# Output Format

For each MCP opportunity, provide:
1. `category` - MCP category (browser-automation, database, api-integration, cloud-services, github-integration, file-system, messaging, observability)
2. `suggested_mcps` - List of specific MCP servers that would help
3. `use_cases` - What the developer could do with this MCP
4. `title` - Brief human-readable title
5. `description` - Why this MCP would help this developer
6. `confidence` - Score from 0.0 to 1.0:
   - 0.8-1.0: Clear need, explicit workarounds or friction
   - 0.6-0.8: Good evidence, would clearly help
   - 0.4-0.6: Possible benefit, some signals
   - Below 0.4: Weak evidence, don't include
7. `friction_score` - How painful was working without this (0.0 to 1.0):
   - 0.8-1.0: Multiple errors, retries, or complex workarounds
   - 0.5-0.8: Noticeable friction, manual steps
   - 0.2-0.5: Some inconvenience
   - 0.0-0.2: Minimal friction
8. `evidence` - Object with:
   - `matched_signals`: Array of signal patterns that matched
   - `quotes`: Array of 1-3 relevant quotes from conversation
   - `workarounds_detected`: Array of workarounds the developer used
   - `friction_indicators`: Array of friction signs (errors, retries, etc.)

Return ONLY valid JSON in this format:
{{
  "recommendations": [
    {{
      "category": "database",
      "suggested_mcps": ["postgres-mcp"],
      "use_cases": ["Direct database queries", "Schema inspection"],
      "title": "PostgreSQL Database Integration",
      "description": "You ran multiple psql commands to check the database schema and debug queries. A postgres-mcp server would let the agent query directly.",
      "confidence": 0.85,
      "friction_score": 0.7,
      "evidence": {{
        "matched_signals": ["postgres", "SELECT", "check.*table"],
        "quotes": ["Run psql to check if the table exists", "Let me query the database to see the schema"],
        "workarounds_detected": ["Manual psql commands in bash", "Copying SQL output for analysis"],
        "friction_indicators": ["Query syntax error, retrying"]
      }}
    }}
  ]
}}

Return an empty recommendations array if no MCP server would help.
Only include recommendations with confidence >= 0.4.
Maximum 5 recommendations, ordered by (friction_score * confidence) descending.
Only recommend categories that were pre-detected or have clear evidence in the conversation."""


MCP_SYSTEM_PROMPT = """You are an expert at identifying when developers need external tool integrations.

Your task is to analyze coding assistant conversations and recommend MCP (Model Context Protocol) servers that would reduce friction and improve productivity.

Focus on:
1. Actual evidence of need - not hypothetical benefits
2. Workarounds and friction - where the developer had to work around limitations
3. External service usage - repeated interactions with databases, APIs, cloud services
4. Specific recommendations - suggest exact MCP servers that would help

Be conservative - only recommend MCPs where there's clear evidence of need.
The developer's time is valuable - a few high-confidence recommendations are better than many weak ones.

Return only valid JSON."""
