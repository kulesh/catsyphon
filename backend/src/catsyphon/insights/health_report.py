"""Health Report Generator.

Generates evidence-based health reports for developer AI collaboration.
Provides:
- Overall health score with plain English summary
- Diagnosis of strengths and gaps
- Real session examples as evidence
- AI-generated recommendations backed by data
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository
from catsyphon.models.db import Conversation

logger = logging.getLogger(__name__)


HEALTH_REPORT_PROMPT = """You are analyzing a developer's AI coding session history to provide actionable insights.

## Developer Stats
- Total sessions: {total_sessions}
- Success rate: {success_rate}%
- Average throughput: {avg_loc_hour} LOC/hour (target: 200)
- Average time to first change: {avg_first_change}m (target: <10m)

## Session Duration Analysis
- Short sessions (<30m): {short_count} sessions, {short_success_rate}% success
- Medium sessions (30-60m): {medium_count} sessions, {medium_success_rate}% success
- Long sessions (>60m): {long_count} sessions, {long_success_rate}% success

## Sample Successful Session
Title: {success_title}
Duration: {success_duration}m
First messages: {success_preview}

## Sample Failed Session
Title: {failure_title}
Duration: {failure_duration}m
First messages: {failure_preview}

Based on this data, generate a JSON response with:
1. An explanation of why the successful session worked (1-2 sentences)
2. An explanation of why the failed session didn't work (1-2 sentences)
3. 2-3 specific recommendations backed by the data

Return ONLY valid JSON in this exact format:
{{
  "success_explanation": "...",
  "failure_explanation": "...",
  "recommendations": [
    {{"advice": "...", "evidence": "..."}},
    {{"advice": "...", "evidence": "..."}}
  ]
}}
"""


EVIDENCE_ANALYSIS_PROMPT = """You are analyzing coding sessions to find representative examples.

## Successful Session Candidates
{success_candidates}

## Failed Session Candidates
{failure_candidates}

## Overall Metrics
- Success rate: {success_rate}%
- Average duration: {avg_duration} min
- Pattern: {pattern_summary}

## Task
Pick the BEST example for each category and explain the KEY OUTCOME.

For the success example, explain:
1. What was accomplished (concrete deliverable)
2. Why this session worked (1-2 factors)

For the failure example, explain:
1. What went wrong (specific blocker)
2. What could have helped

Return ONLY valid JSON in this format:
{{
  "success_pick": "session_id_here",
  "success_outcome": "Implemented [feature] - [what was built]. Worked because [reason].",
  "failure_pick": "session_id_here",
  "failure_outcome": "Attempted [goal] but [what went wrong]. [What could have helped]."
}}
"""


def get_health_label(score: float) -> tuple[str, str]:
    """Get health label and summary for a score.

    Returns:
        Tuple of (label, summary)
    """
    if score >= 0.8:
        return ("Excellent", "Your AI sessions consistently achieve their goals")
    elif score >= 0.6:
        return ("Good", "Most AI sessions are productive and successful")
    elif score >= 0.4:
        return (
            "Developing",
            "Sessions are productive but often don't complete their goal",
        )
    else:
        return (
            "Needs Attention",
            "Sessions frequently end without achieving the intended outcome",
        )


class HealthReportGenerator:
    """Generator for evidence-based health reports."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
    ):
        """Initialize the health report generator.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use
            max_tokens: Maximum tokens for response
        """
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        project_id: UUID,
        session: Session,
        workspace_id: UUID,
        date_range: str = "30d",
        developer_filter: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate a health report for a project.

        Args:
            project_id: Project ID
            session: Database session
            workspace_id: Workspace ID
            date_range: Date range filter ('7d', '30d', '90d', 'all')
            developer_filter: Optional developer name to filter by

        Returns:
            HealthReportResponse dict
        """
        start_time = time.time()

        # Calculate date filter
        date_filter = self._parse_date_range(date_range)

        # Get conversations
        conv_repo = ConversationRepository(session)
        conversations = conv_repo.get_by_project(project_id, workspace_id, limit=500)

        # Filter by date
        if date_filter:
            conversations = [
                c for c in conversations if c.start_time and c.start_time >= date_filter
            ]

        # Filter by developer (compare username)
        if developer_filter:
            conversations = [
                c
                for c in conversations
                if c.developer and c.developer.username == developer_filter
            ]

        if not conversations:
            return self._empty_response()

        # Compute metrics
        metrics = self._compute_metrics(conversations)

        # Get score and label
        score = metrics["overall_score"]
        label, base_summary = get_health_label(score)

        # Build diagnosis
        diagnosis = self._build_diagnosis(metrics)

        # Get evidence examples
        evidence = self._get_evidence(conversations, metrics, session)

        # Generate AI recommendations if we have API key and evidence
        recommendations = []
        if (
            self.client
            and evidence.get("success_example")
            and evidence.get("failure_example")
        ):
            recommendations = self._generate_recommendations(
                metrics, evidence, conversations
            )

        # Build session links
        session_links = {
            "all_successful": f"/sessions?project={project_id}&outcome=success",
            "all_failed": f"/sessions?project={project_id}&outcome=failed",
        }

        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"Generated health report for {project_id} in {duration_ms:.0f}ms")

        return {
            "score": round(score, 2),
            "label": label,
            "summary": base_summary,
            "diagnosis": diagnosis,
            "evidence": evidence,
            "recommendations": recommendations,
            "session_links": session_links,
            "sessions_analyzed": len(conversations),
            "generated_at": time.time(),
            "cached": False,
        }

    def _parse_date_range(self, date_range: str) -> Optional[datetime]:
        """Convert date range string to datetime filter."""
        if date_range == "all":
            return None
        days = {"7d": 7, "30d": 30, "90d": 90}.get(date_range, 30)
        return datetime.now().astimezone() - timedelta(days=days)

    def _compute_metrics(self, conversations: list[Conversation]) -> dict[str, Any]:
        """Compute aggregate metrics from conversations."""
        total = len(conversations)
        success_count = 0
        failed_count = 0
        loc_hours = []
        first_changes = []

        # Duration buckets
        short_sessions = []  # <30m
        medium_sessions = []  # 30-60m
        long_sessions = []  # >60m

        for conv in conversations:
            # Success rate
            if conv.success is True:
                success_count += 1
            elif conv.success is False:
                failed_count += 1

            # Compute duration from start_time and end_time
            duration_seconds = None
            if conv.start_time and conv.end_time:
                duration_seconds = (conv.end_time - conv.start_time).total_seconds()

            # LOC/hour - get lines from files_touched if loaded
            if duration_seconds and duration_seconds > 0:
                hours = duration_seconds / 3600

                # Try to get lines from files_touched relationship
                total_lines = 0
                first_file_change_at = None
                try:
                    if conv.files_touched:
                        for ft in conv.files_touched:
                            total_lines += (ft.lines_added or 0) + (
                                ft.lines_deleted or 0
                            )
                            if ft.timestamp and (
                                first_file_change_at is None
                                or ft.timestamp < first_file_change_at
                            ):
                                first_file_change_at = ft.timestamp

                        if total_lines > 0:
                            loc_hour = total_lines / hours if hours > 0 else 0
                            loc_hours.append(loc_hour)

                        # First change latency
                        if first_file_change_at and conv.start_time:
                            delta = (
                                first_file_change_at - conv.start_time
                            ).total_seconds() / 60
                            if delta >= 0:
                                first_changes.append(delta)
                except Exception:
                    # files_touched might not be loaded - skip
                    pass

                # Duration bucket
                minutes = duration_seconds / 60
                if minutes < 30:
                    short_sessions.append(conv)
                elif minutes < 60:
                    medium_sessions.append(conv)
                else:
                    long_sessions.append(conv)

        # Compute rates
        total_with_outcome = success_count + failed_count
        success_rate = (
            (success_count / total_with_outcome * 100)
            if total_with_outcome > 0
            else None
        )

        avg_loc_hour = sum(loc_hours) / len(loc_hours) if loc_hours else None
        avg_first_change = (
            sum(first_changes) / len(first_changes) if first_changes else None
        )

        # Compute success rates by duration
        def bucket_success_rate(sessions: list[Conversation]) -> Optional[float]:
            success = sum(1 for s in sessions if s.success is True)
            failed = sum(1 for s in sessions if s.success is False)
            total = success + failed
            return (success / total * 100) if total > 0 else None

        # Compute overall score (same formula as pairing effectiveness)
        throughput_component = min((avg_loc_hour or 0) / 200.0, 1.0)
        latency_component = max(0.0, 1 - (avg_first_change or 30) / 60.0)
        success_component = (success_rate or 50) / 100

        overall_score = (
            success_component * 0.6
            + throughput_component * 0.3
            + latency_component * 0.1
        )

        return {
            "total_sessions": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_rate,
            "avg_loc_hour": avg_loc_hour,
            "avg_first_change": avg_first_change,
            "overall_score": overall_score,
            "short_sessions": len(short_sessions),
            "short_success_rate": bucket_success_rate(short_sessions),
            "medium_sessions": len(medium_sessions),
            "medium_success_rate": bucket_success_rate(medium_sessions),
            "long_sessions": len(long_sessions),
            "long_success_rate": bucket_success_rate(long_sessions),
        }

    def _build_diagnosis(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Build diagnosis from metrics."""
        strengths = []
        gaps = []
        primary_issue = None
        primary_issue_detail = None

        # Check each metric against targets
        success_rate = metrics.get("success_rate")
        avg_loc = metrics.get("avg_loc_hour")
        avg_latency = metrics.get("avg_first_change")

        # Success rate (target: >70%)
        if success_rate is not None:
            if success_rate >= 70:
                strengths.append(f"High success rate ({success_rate:.0f}%)")
            else:
                gaps.append(f"Low success rate ({success_rate:.0f}% vs 70% target)")
                if primary_issue is None:
                    primary_issue = "success_rate"
                    primary_issue_detail = (
                        f"Your {success_rate:.0f}% success rate is the main factor. "
                        "Most sessions aren't completing their intended task."
                    )

        # Throughput (target: 200 LOC/hr)
        if avg_loc is not None:
            if avg_loc >= 200:
                strengths.append(f"Good throughput ({avg_loc:.0f} LOC/hr)")
            elif avg_loc >= 100:
                strengths.append(f"Moderate throughput ({avg_loc:.0f} LOC/hr)")
            else:
                gaps.append(f"Low throughput ({avg_loc:.0f} LOC/hr vs 200 target)")
                if primary_issue is None:
                    primary_issue = "throughput"
                    primary_issue_detail = (
                        f"Your throughput ({avg_loc:.0f} LOC/hr) is below target. "
                        "Sessions may be spending time on non-coding activities."
                    )

        # Latency (target: <10m)
        if avg_latency is not None:
            if avg_latency <= 10:
                strengths.append(f"Fast startup ({avg_latency:.1f}m to first change)")
            else:
                gaps.append(f"Slow startup ({avg_latency:.1f}m vs <10m target)")
                if primary_issue is None:
                    primary_issue = "latency"
                    primary_issue_detail = (
                        f"Time to first change ({avg_latency:.1f}m) is slow. "
                        "Consider starting sessions with clearer context."
                    )

        return {
            "strengths": strengths,
            "gaps": gaps,
            "primary_issue": primary_issue,
            "primary_issue_detail": primary_issue_detail,
        }

    def _get_conversation_title(self, conv: Conversation) -> str:
        """Get title for a conversation from tags or metadata."""
        # Try to get title from tags
        if isinstance(conv.tags, dict):
            if "title" in conv.tags:
                return conv.tags["title"]
        # Try from extra_data (metadata)
        if isinstance(conv.extra_data, dict):
            if "title" in conv.extra_data:
                return conv.extra_data["title"]
        # Fallback to agent type and date (using local timezone)
        if conv.start_time:
            dt = conv.start_time
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_dt = dt.astimezone()
            date_str = local_dt.strftime("%b %d")
        else:
            date_str = "Unknown"
        return f"{conv.agent_type} session on {date_str}"

    def _get_duration_minutes(self, conv: Conversation) -> int:
        """Compute duration in minutes from start/end times."""
        if conv.start_time and conv.end_time:
            return int((conv.end_time - conv.start_time).total_seconds() / 60)
        return 0

    def _format_date_local(self, dt: Optional[datetime]) -> str:
        """Format datetime to local date string (YYYY-MM-DD).

        Handles UTC timestamps by converting to local timezone.
        """
        if not dt:
            return "Unknown"

        # If datetime is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Convert to local timezone
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d")

    def _get_first_user_message(
        self, conv: Conversation, db_session: Session
    ) -> Optional[str]:
        """Get the first user message from a conversation as context preview."""
        from catsyphon.models.db import Message

        try:
            # Query for the first user message with actual content
            first_msg = (
                db_session.query(Message)
                .filter(Message.conversation_id == conv.id)
                .filter(Message.role == "user")
                .filter(Message.content.isnot(None))
                .filter(Message.content != "")
                .order_by(Message.sequence.asc())
                .first()
            )

            if first_msg and first_msg.content:
                content = first_msg.content.strip()
                if len(content) > 150:
                    content = content[:147] + "..."
                return content
        except Exception as e:
            logger.debug(f"Could not fetch first message: {e}")
        return None

    def _conversation_has_content(
        self, conv: Conversation, db_session: Session
    ) -> bool:
        """Check if a conversation has user messages with actual content."""
        from catsyphon.models.db import Message

        try:
            has_content = (
                db_session.query(Message)
                .filter(Message.conversation_id == conv.id)
                .filter(Message.role == "user")
                .filter(Message.content.isnot(None))
                .filter(Message.content != "")
                .limit(1)
                .first()
            ) is not None
            return has_content
        except Exception:
            return False

    def _gather_candidate_sessions(
        self,
        conversations: list[Conversation],
        db_session: Session,
        success_filter: Optional[bool],
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Gather candidate sessions with rich metadata for LLM analysis.

        Args:
            conversations: List of conversations to filter
            db_session: Database session
            success_filter: Filter by success status (True/False/None for any)
            limit: Maximum candidates to return

        Returns:
            List of candidate dicts with rich metadata
        """
        from catsyphon.models.db import Message

        # Filter for sessions with meaningful content (lowered threshold for broader match)
        # First, try sessions with message_count > 5
        candidates = [
            c for c in conversations if c.message_count and c.message_count > 5
        ]

        # If no candidates found, fall back to any session with messages
        if not candidates:
            candidates = [
                c for c in conversations if c.message_count and c.message_count > 0
            ]
            logger.debug(
                f"Fell back to any sessions with messages: {len(candidates)} found"
            )

        # If still no candidates, use all conversations
        if not candidates:
            candidates = list(conversations)
            logger.debug(f"Fell back to all conversations: {len(candidates)} found")

        # Apply success filter with fallback to undetermined sessions
        if success_filter is True:
            filtered = [c for c in candidates if c.success is True]
            if not filtered:
                # Fallback: sessions with undetermined success
                filtered = [c for c in candidates if c.success is None]
            candidates = filtered
        elif success_filter is False:
            filtered = [c for c in candidates if c.success is False]
            if not filtered:
                # Fallback: sessions with undetermined success
                filtered = [c for c in candidates if c.success is None]
            candidates = filtered

        # Sort by recency (most recent first)
        candidates.sort(key=lambda c: (c.start_time or datetime.min), reverse=True)

        result = []
        for conv in candidates[
            : limit * 3
        ]:  # Check more candidates to find ones with content
            if len(result) >= limit:
                break

            # Get first user message (optional - we'll include even without it)
            first_msg = self._get_first_user_message(conv, db_session)

            # Get files changed
            files_changed = []
            lines_added = 0
            lines_deleted = 0
            try:
                if conv.files_touched:
                    for ft in conv.files_touched:
                        if ft.file_path:
                            files_changed.append(ft.file_path)
                        lines_added += ft.lines_added or 0
                        lines_deleted += ft.lines_deleted or 0
            except Exception:
                pass

            # Get tags info
            tags = conv.tags if isinstance(conv.tags, dict) else {}

            # Get tool calls summary from messages
            tool_calls_summary: dict[str, int] = defaultdict(int)
            try:
                messages = (
                    db_session.query(Message)
                    .filter(Message.conversation_id == conv.id)
                    .all()
                )
                for msg in messages:
                    if msg.tool_calls:
                        for tc in msg.tool_calls:
                            tool_name = (
                                tc.get("name", "unknown")
                                if isinstance(tc, dict)
                                else "unknown"
                            )
                            tool_calls_summary[tool_name] += 1
            except Exception:
                pass

            result.append(
                {
                    "session_id": str(conv.id),
                    "start_time": (
                        conv.start_time.isoformat() if conv.start_time else None
                    ),
                    "duration_minutes": self._get_duration_minutes(conv),
                    "message_count": conv.message_count or 0,
                    "files_changed": files_changed[:10],  # Limit to first 10
                    "lines_added": lines_added,
                    "lines_deleted": lines_deleted,
                    "tags": {
                        "intent": tags.get("intent"),
                        "outcome": tags.get("outcome"),
                        "features": tags.get("features", []),
                        "problems": tags.get("problems", []),
                        "sentiment": tags.get("sentiment"),
                    },
                    "first_user_message": first_msg[:200] if first_msg else None,
                    "tool_calls_summary": dict(tool_calls_summary),
                }
            )

        return result

    def _generate_evidence_with_llm(
        self,
        success_candidates: list[dict[str, Any]],
        failure_candidates: list[dict[str, Any]],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """Use LLM to pick best examples and explain outcomes.

        Args:
            success_candidates: Candidate successful sessions
            failure_candidates: Candidate failed sessions
            metrics: Overall metrics for context

        Returns:
            Dict with success_pick, success_outcome, failure_pick, failure_outcome
        """
        if not self.client:
            raise ValueError("LLM client not available")

        # Build pattern summary
        short_rate = metrics.get("short_success_rate")
        long_rate = metrics.get("long_success_rate")
        pattern_summary = "No clear pattern"
        if short_rate is not None and long_rate is not None:
            if short_rate > long_rate + 10:
                pattern_summary = f"Short sessions (<30m) succeed {short_rate:.0f}% vs {long_rate:.0f}% for long sessions"
            elif long_rate > short_rate + 10:
                pattern_summary = f"Long sessions succeed better ({long_rate:.0f}% vs {short_rate:.0f}%)"

        prompt = EVIDENCE_ANALYSIS_PROMPT.format(
            success_candidates=json.dumps(success_candidates, indent=2),
            failure_candidates=json.dumps(failure_candidates, indent=2),
            success_rate=int(metrics.get("success_rate") or 0),
            avg_duration=int(metrics.get("avg_duration_minutes") or 30),
            pattern_summary=pattern_summary,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing developer-AI collaboration sessions. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.3,
        )

        content = response.choices[0].message.content
        if content:
            return json.loads(content)
        return {}

    def _fallback_evidence(
        self,
        candidates: list[dict[str, Any]],
        is_success: bool,
    ) -> Optional[str]:
        """Generate fallback outcome from tags when LLM unavailable.

        Args:
            candidates: List of candidate sessions
            is_success: Whether these are success or failure candidates

        Returns:
            Fallback outcome string or None
        """
        if not candidates:
            return None

        candidate = candidates[0]
        tags = candidate.get("tags", {})
        features = tags.get("features", [])
        problems = tags.get("problems", [])

        if is_success:
            if features:
                return f"Added: {', '.join(features[:3])}"
            return "Session completed successfully"
        else:
            if problems:
                return f"Blocked by: {', '.join(problems[:3])}"
            return "Session did not achieve its goal"

    def _get_evidence(
        self,
        conversations: list[Conversation],
        metrics: dict[str, Any],
        db_session: Session,
    ) -> dict[str, Any]:
        """Get real session examples as evidence with LLM-generated outcomes.

        This method:
        1. Gathers candidate sessions with rich metadata
        2. Calls LLM to pick best examples and explain key outcomes
        3. Falls back to tag-based evidence if LLM unavailable
        """
        evidence: dict[str, Any] = {
            "success_example": None,
            "failure_example": None,
            "patterns": [],
        }

        # Gather candidate sessions with rich metadata
        success_candidates = self._gather_candidate_sessions(
            conversations, db_session, success_filter=True, limit=3
        )
        failure_candidates = self._gather_candidate_sessions(
            conversations, db_session, success_filter=False, limit=3
        )

        logger.debug(
            f"Evidence candidates: {len(success_candidates)} success, "
            f"{len(failure_candidates)} failure from {len(conversations)} conversations"
        )

        # Build a mapping of session_id to conversation for lookups
        conv_map = {str(c.id): c for c in conversations}

        # Try LLM-powered evidence analysis
        llm_result = None
        if self.client and (success_candidates or failure_candidates):
            try:
                llm_result = self._generate_evidence_with_llm(
                    success_candidates, failure_candidates, metrics
                )
            except Exception as e:
                logger.warning(f"LLM evidence analysis failed: {e}")

        # Build success example
        if success_candidates:
            if llm_result and llm_result.get("success_pick"):
                picked_id = llm_result["success_pick"]
                outcome = llm_result.get("success_outcome", "")
                logger.debug(f"LLM picked success session: {picked_id}")
            else:
                picked_id = success_candidates[0]["session_id"]
                outcome = (
                    self._fallback_evidence(success_candidates, is_success=True) or ""
                )
                logger.debug(f"Using fallback success session: {picked_id}")

            # Find the conversation for this session
            conv = conv_map.get(picked_id)
            if conv:
                evidence["success_example"] = {
                    "session_id": picked_id,
                    "title": self._get_conversation_title(conv),
                    "date": self._format_date_local(conv.start_time),
                    "duration_minutes": self._get_duration_minutes(conv),
                    "explanation": "",  # Will be filled by recommendations LLM
                    "outcome": outcome,
                }
                logger.debug(
                    f"Built success example: {evidence['success_example']['title']}"
                )
            else:
                logger.warning(
                    f"Could not find conversation for success session {picked_id}"
                )
        else:
            logger.debug("No success candidates found for evidence")

        # Build failure example
        if failure_candidates:
            if llm_result and llm_result.get("failure_pick"):
                picked_id = llm_result["failure_pick"]
                outcome = llm_result.get("failure_outcome", "")
                logger.debug(f"LLM picked failure session: {picked_id}")
            else:
                picked_id = failure_candidates[0]["session_id"]
                outcome = (
                    self._fallback_evidence(failure_candidates, is_success=False) or ""
                )
                logger.debug(f"Using fallback failure session: {picked_id}")

            conv = conv_map.get(picked_id)
            if conv:
                evidence["failure_example"] = {
                    "session_id": picked_id,
                    "title": self._get_conversation_title(conv),
                    "date": self._format_date_local(conv.start_time),
                    "duration_minutes": self._get_duration_minutes(conv),
                    "explanation": "",
                    "outcome": outcome,
                }
                logger.debug(
                    f"Built failure example: {evidence['failure_example']['title']}"
                )
            else:
                logger.warning(
                    f"Could not find conversation for failure session {picked_id}"
                )
        else:
            logger.debug("No failure candidates found for evidence")

        # Add patterns based on duration analysis
        short_rate = metrics.get("short_success_rate")
        long_rate = metrics.get("long_success_rate")

        if short_rate is not None and long_rate is not None:
            if short_rate > long_rate + 20:  # Significant difference
                evidence["patterns"].append(
                    {
                        "description": f"Short sessions (<30m) succeed {short_rate:.0f}% vs {long_rate:.0f}% for long sessions",
                        "data": {
                            "short_sessions_success": short_rate / 100,
                            "long_sessions_success": long_rate / 100,
                        },
                    }
                )

        return evidence

    def _generate_recommendations(
        self,
        metrics: dict[str, Any],
        evidence: dict[str, Any],
        conversations: list[Conversation],
    ) -> list[dict[str, str]]:
        """Generate AI-powered recommendations."""
        if not self.client:
            return self._static_recommendations(metrics)

        try:
            # Get message previews for context
            success_conv = None
            failure_conv = None

            for conv in conversations:
                if (
                    evidence.get("success_example")
                    and str(conv.id) == evidence["success_example"]["session_id"]
                ):
                    success_conv = conv
                if (
                    evidence.get("failure_example")
                    and str(conv.id) == evidence["failure_example"]["session_id"]
                ):
                    failure_conv = conv

            success_preview = "N/A"
            failure_preview = "N/A"

            if success_conv and success_conv.messages:
                first_messages = success_conv.messages[:3]
                success_preview = " | ".join(
                    m.content[:100] for m in first_messages if m.content
                )[:300]

            if failure_conv and failure_conv.messages:
                first_messages = failure_conv.messages[:3]
                failure_preview = " | ".join(
                    m.content[:100] for m in first_messages if m.content
                )[:300]

            prompt = HEALTH_REPORT_PROMPT.format(
                total_sessions=metrics["total_sessions"],
                success_rate=metrics.get("success_rate", 0) or 0,
                avg_loc_hour=int(metrics.get("avg_loc_hour") or 0),
                avg_first_change=int(metrics.get("avg_first_change") or 0),
                short_count=metrics.get("short_sessions", 0),
                short_success_rate=int(metrics.get("short_success_rate") or 0),
                medium_count=metrics.get("medium_sessions", 0),
                medium_success_rate=int(metrics.get("medium_success_rate") or 0),
                long_count=metrics.get("long_sessions", 0),
                long_success_rate=int(metrics.get("long_success_rate") or 0),
                success_title=evidence.get("success_example", {}).get("title", "N/A"),
                success_duration=evidence.get("success_example", {}).get(
                    "duration_minutes", 0
                ),
                success_preview=success_preview,
                failure_title=evidence.get("failure_example", {}).get("title", "N/A"),
                failure_duration=evidence.get("failure_example", {}).get(
                    "duration_minutes", 0
                ),
                failure_preview=failure_preview,
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing developer-AI collaboration. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            if content:
                # Parse JSON response
                result = json.loads(content)

                # Update evidence explanations
                if evidence.get("success_example"):
                    evidence["success_example"]["explanation"] = result.get(
                        "success_explanation", ""
                    )
                if evidence.get("failure_example"):
                    evidence["failure_example"]["explanation"] = result.get(
                        "failure_explanation", ""
                    )

                # Return recommendations
                return result.get("recommendations", [])

        except Exception as e:
            logger.warning(f"Failed to generate AI recommendations: {e}")

        # Fall back to static recommendations
        return self._static_recommendations(metrics)

    def _static_recommendations(self, metrics: dict[str, Any]) -> list[dict[str, str]]:
        """Generate static recommendations based on metrics."""
        recommendations = []

        # Duration-based recommendation
        short_rate = metrics.get("short_success_rate")
        long_rate = metrics.get("long_success_rate")
        if short_rate is not None and long_rate is not None and short_rate > long_rate:
            recommendations.append(
                {
                    "advice": "Break large tasks into smaller sessions",
                    "evidence": f"Your short sessions (<30m) have {short_rate:.0f}% success vs {long_rate:.0f}% for long sessions",
                }
            )

        # Success rate recommendation
        success_rate = metrics.get("success_rate")
        if success_rate is not None and success_rate < 50:
            recommendations.append(
                {
                    "advice": "Review your unsuccessful sessions to identify patterns",
                    "evidence": f"Only {success_rate:.0f}% of sessions achieved their goal",
                }
            )

        # Throughput recommendation
        avg_loc = metrics.get("avg_loc_hour")
        if avg_loc is not None and avg_loc < 100:
            recommendations.append(
                {
                    "advice": "Focus on code-producing activities during sessions",
                    "evidence": f"Your throughput ({avg_loc:.0f} LOC/hr) is below the 200 target",
                }
            )

        return recommendations

    def _empty_response(self) -> dict[str, Any]:
        """Return empty response when no data available."""
        return {
            "score": 0.5,
            "label": "No Data",
            "summary": "Not enough session data to generate a health report",
            "diagnosis": {
                "strengths": [],
                "gaps": [],
                "primary_issue": None,
                "primary_issue_detail": None,
            },
            "evidence": {
                "success_example": None,
                "failure_example": None,
                "patterns": [],
            },
            "recommendations": [],
            "session_links": {},
            "sessions_analyzed": 0,
            "generated_at": time.time(),
            "cached": False,
        }
