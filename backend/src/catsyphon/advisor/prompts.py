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
