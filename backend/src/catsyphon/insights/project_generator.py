"""Project-level insights generator.

Aggregates conversation insights across a project to provide:
- Pattern aggregation (workflow patterns, learning opportunities, anti-patterns)
- Temporal trends (collaboration quality, agent effectiveness over time)
- LLM-generated narrative summary
"""

import json
import logging
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from catsyphon.db.repositories import ConversationRepository, InsightsRepository
from catsyphon.insights import InsightsGenerator

logger = logging.getLogger(__name__)


PROJECT_SUMMARY_PROMPT = """Analyze this project's AI collaboration patterns and generate a 2-3 paragraph summary.

Project: {project_name}
Date Range: {date_range}
Sessions Analyzed: {session_count}

## Top Workflow Patterns
{workflow_patterns}

## Common Learning Opportunities
{learning_opportunities}

## Anti-Patterns (Negative Productivity Indicators)
{anti_patterns}

## Collaboration Trends
- Collaboration Quality: {collab_trend} (avg: {avg_collab:.1f}/10)
- Agent Effectiveness: {effectiveness_trend} (avg: {avg_effectiveness:.1f}/10)
- Scope Clarity: {clarity_trend} (avg: {avg_clarity:.1f}/10)

## Key Statistics
- Total sessions: {session_count}
- Total messages: {total_messages}
- Success rate: {success_rate}

Generate a narrative summary that:
1. Highlights what's working well in this team's AI collaboration
2. Identifies specific areas for improvement with actionable suggestions
3. Notes any concerning trends or patterns that need attention

Return only the narrative summary (2-3 paragraphs), no JSON or headers."""


class ProjectInsightsGenerator:
    """Generator for project-level insights aggregation.

    Aggregates conversation insights across a project to provide:
    - Pattern frequency analysis
    - Temporal trend computation
    - LLM-powered narrative summary
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
    ):
        """Initialize the project insights generator.

        Args:
            api_key: OpenAI API key
            model: OpenAI model to use for summary generation
            max_tokens: Maximum tokens for summary response
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        project_id: UUID,
        project_name: str,
        session: Session,
        date_range: str = "30d",
        include_summary: bool = True,
        workspace_id: Optional[UUID] = None,
        force_regenerate: bool = False,
    ) -> dict[str, Any]:
        """Generate comprehensive project-level insights.

        Args:
            project_id: Project ID
            project_name: Project name for summary
            session: Database session
            date_range: Date range filter ('7d', '30d', '90d', 'all')
            include_summary: Whether to generate LLM summary
            workspace_id: Workspace ID for repository queries
            force_regenerate: If True, regenerate all insights (ignore cache)

        Returns:
            Dictionary with aggregated insights
        """
        start_time = time.time()

        # Calculate date filter
        date_filter = self._parse_date_range(date_range)

        # Get conversations and their insights
        conversation_repo = ConversationRepository(session)
        insights_repo = InsightsRepository(session)

        conversations = conversation_repo.get_by_project(
            project_id, workspace_id, limit=100
        )

        # Filter by date if applicable
        if date_filter:
            conversations = [
                c for c in conversations
                if c.start_time and c.start_time >= date_filter
            ]

        if not conversations:
            return self._empty_response(project_id, date_range)

        # If force_regenerate, invalidate all cached insights for these conversations
        if force_regenerate:
            logger.info(f"Force regenerating insights for {len(conversations)} conversations")
            for conv in conversations:
                insights_repo.invalidate(conversation_id=conv.id)

        # Track cache stats
        insights_cached = 0
        insights_generated = 0
        insights_failed = 0
        oldest_insight_at: Optional[datetime] = None
        newest_insight_at: Optional[datetime] = None

        # Get latest conversation activity for freshness comparison
        latest_conversation_at: Optional[datetime] = None
        for conv in conversations:
            conv_time = conv.end_time or conv.start_time
            if conv_time and (latest_conversation_at is None or conv_time > latest_conversation_at):
                latest_conversation_at = conv_time

        # Lazy-initialized insights generator for on-demand generation
        conv_insights_generator: Optional[InsightsGenerator] = None

        # Collect insights (from cache or generate on-demand)
        all_insights = []

        for idx, conv in enumerate(conversations):
            cached = insights_repo.get_cached(conv.id)
            if cached:
                insights_cached += 1
                insight_time = cached.generated_at
                if oldest_insight_at is None or insight_time < oldest_insight_at:
                    oldest_insight_at = insight_time
                if newest_insight_at is None or insight_time > newest_insight_at:
                    newest_insight_at = insight_time

                all_insights.append({
                    "insights": cached.to_response_dict(),
                    "conversation": conv,
                })
            else:
                # Generate insights on-demand
                if conv_insights_generator is None:
                    conv_insights_generator = InsightsGenerator(
                        api_key=self.client.api_key,
                        model=self.model,
                    )

                logger.info(
                    f"Generating insights for conversation {conv.id} "
                    f"({idx + 1}/{len(conversations)})"
                )

                try:
                    generated = conv_insights_generator.generate_insights(conv, session)
                    # Save to cache
                    saved = insights_repo.save(
                        conversation_id=conv.id,
                        insights=generated,
                        canonical_version=generated.get("canonical_version", 1),
                        project_last_activity=latest_conversation_at,
                    )
                    insights_generated += 1

                    insight_time = saved.generated_at
                    if oldest_insight_at is None or insight_time < oldest_insight_at:
                        oldest_insight_at = insight_time
                    if newest_insight_at is None or insight_time > newest_insight_at:
                        newest_insight_at = insight_time

                    all_insights.append({
                        "insights": generated,
                        "conversation": conv,
                    })
                except Exception as e:
                    logger.warning(f"Failed to generate insights for {conv.id}: {e}")
                    insights_failed += 1
                    all_insights.append({
                        "insights": None,
                        "conversation": conv,
                    })

        # Separate conversations with insights from those without
        with_insights = [i for i in all_insights if i["insights"]]
        total_conversations = len(conversations)
        conversations_with_insights = len(with_insights)

        # Aggregate patterns
        patterns = self._aggregate_patterns(with_insights)

        # Compute temporal trends
        trends = self._compute_trends(with_insights)

        # Compute averages
        averages = self._compute_averages(with_insights)

        # Compute quantitative stats
        stats = self._compute_stats(all_insights)

        # Generate LLM summary (optional)
        summary = None
        if include_summary and with_insights:
            summary = self._generate_summary(
                project_name=project_name,
                date_range=date_range,
                patterns=patterns,
                trends=trends,
                averages=averages,
                stats=stats,
            )

        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Generated project insights for {project_id} "
            f"({conversations_with_insights}/{total_conversations} with insights, "
            f"cached={insights_cached}, generated={insights_generated}, failed={insights_failed}, "
            f"{duration_ms:.0f}ms)"
        )

        return {
            "project_id": str(project_id),
            "date_range": date_range,
            "conversations_analyzed": total_conversations,
            "conversations_with_insights": conversations_with_insights,

            # Pattern Aggregation
            "top_workflow_patterns": patterns["workflow"],
            "top_learning_opportunities": patterns["learning"],
            "top_anti_patterns": patterns["anti_patterns"],
            "common_technical_debt": patterns["tech_debt"],

            # Temporal Trends
            "collaboration_trend": trends["collaboration"],
            "effectiveness_trend": trends["effectiveness"],
            "scope_clarity_trend": trends["clarity"],

            # Averages
            "avg_collaboration_quality": averages["collaboration"],
            "avg_agent_effectiveness": averages["effectiveness"],
            "avg_scope_clarity": averages["clarity"],

            # Stats
            "total_messages": stats["total_messages"],
            "total_tool_calls": stats["total_tool_calls"],
            "success_rate": stats["success_rate"],

            # Summary
            "summary": summary,

            # Metadata
            "generated_at": time.time(),

            # Cache metadata (for freshness indicators)
            "insights_cached": insights_cached,
            "insights_generated": insights_generated,
            "insights_failed": insights_failed,
            "oldest_insight_at": oldest_insight_at.isoformat() if oldest_insight_at else None,
            "newest_insight_at": newest_insight_at.isoformat() if newest_insight_at else None,
            "latest_conversation_at": latest_conversation_at.isoformat() if latest_conversation_at else None,
        }

    def _parse_date_range(self, date_range: str) -> Optional[datetime]:
        """Convert date range string to datetime filter."""
        if date_range == "all":
            return None

        days = {"7d": 7, "30d": 30, "90d": 90}.get(date_range, 30)
        return datetime.now().astimezone() - timedelta(days=days)

    def _aggregate_patterns(
        self, insights_list: list[dict]
    ) -> dict[str, list[dict]]:
        """Aggregate patterns from multiple conversations."""
        workflow_counter: Counter = Counter()
        learning_counter: Counter = Counter()
        anti_pattern_counter: Counter = Counter()
        tech_debt_counter: Counter = Counter()

        # Negative productivity indicators = anti-patterns
        negative_indicators = {
            "frequent-context-switches",
            "repeated-failures",
            "scope-creep",
            "unclear-requirements",
            "blocked-progress",
            "high-iteration-count",
        }

        for item in insights_list:
            insights = item["insights"]
            if not insights:
                continue

            # Workflow patterns
            for pattern in insights.get("workflow_patterns", []):
                workflow_counter[pattern] += 1

            # Learning opportunities
            for opp in insights.get("learning_opportunities", []):
                learning_counter[opp] += 1

            # Technical debt
            for debt in insights.get("technical_debt_indicators", []):
                tech_debt_counter[debt] += 1

            # Extract anti-patterns from productivity indicators
            for indicator in insights.get("productivity_indicators", []):
                if indicator in negative_indicators or "fail" in indicator.lower():
                    anti_pattern_counter[indicator] += 1

        total = len(insights_list) or 1

        def to_frequency_list(counter: Counter, limit: int = 10) -> list[dict]:
            return [
                {
                    "pattern": pattern,
                    "count": count,
                    "percentage": round(count / total * 100, 1),
                }
                for pattern, count in counter.most_common(limit)
            ]

        return {
            "workflow": to_frequency_list(workflow_counter),
            "learning": to_frequency_list(learning_counter),
            "anti_patterns": to_frequency_list(anti_pattern_counter),
            "tech_debt": to_frequency_list(tech_debt_counter),
        }

    def _compute_trends(
        self, insights_list: list[dict]
    ) -> dict[str, list[dict]]:
        """Compute temporal trends grouped by week."""
        # Group by week
        weekly_data: dict[str, dict] = defaultdict(lambda: {
            "collaboration": [],
            "effectiveness": [],
            "clarity": [],
            "count": 0,
        })

        for item in insights_list:
            insights = item["insights"]
            conv = item["conversation"]

            if not insights or not conv.start_time:
                continue

            # Get week start (Monday)
            week_start = conv.start_time - timedelta(days=conv.start_time.weekday())
            week_key = week_start.strftime("%Y-%m-%d")

            weekly_data[week_key]["collaboration"].append(
                insights.get("collaboration_quality", 5)
            )
            weekly_data[week_key]["effectiveness"].append(
                insights.get("agent_effectiveness", 5)
            )
            weekly_data[week_key]["clarity"].append(
                insights.get("scope_clarity", 5)
            )
            weekly_data[week_key]["count"] += 1

        # Convert to trend points
        def to_trend_points(metric: str) -> list[dict]:
            points = []
            for week, data in sorted(weekly_data.items()):
                values = data[metric]
                if values:
                    points.append({
                        "date": week,
                        "avg_score": round(sum(values) / len(values), 2),
                        "count": data["count"],
                    })
            return points

        return {
            "collaboration": to_trend_points("collaboration"),
            "effectiveness": to_trend_points("effectiveness"),
            "clarity": to_trend_points("clarity"),
        }

    def _compute_averages(
        self, insights_list: list[dict]
    ) -> dict[str, float]:
        """Compute average scores across all insights."""
        collab = []
        effect = []
        clarity = []

        for item in insights_list:
            insights = item["insights"]
            if not insights:
                continue

            collab.append(insights.get("collaboration_quality", 5))
            effect.append(insights.get("agent_effectiveness", 5))
            clarity.append(insights.get("scope_clarity", 5))

        def safe_avg(values: list) -> float:
            return round(sum(values) / len(values), 2) if values else 5.0

        return {
            "collaboration": safe_avg(collab),
            "effectiveness": safe_avg(effect),
            "clarity": safe_avg(clarity),
        }

    def _compute_stats(
        self, insights_list: list[dict]
    ) -> dict[str, Any]:
        """Compute quantitative statistics."""
        total_messages = 0
        total_tool_calls = 0
        success_count = 0
        total_count = 0

        for item in insights_list:
            conv = item["conversation"]
            insights = item["insights"]

            total_count += 1

            # From conversation
            if conv.success:
                success_count += 1

            # From insights quantitative metrics
            if insights:
                metrics = insights.get("quantitative_metrics", {})
                total_messages += metrics.get("message_count", 0)
                total_tool_calls += metrics.get("tool_calls_count", 0)

        success_rate = None
        if total_count > 0:
            success_rate = round(success_count / total_count * 100, 1)

        return {
            "total_messages": total_messages,
            "total_tool_calls": total_tool_calls,
            "success_rate": success_rate,
        }

    def _generate_summary(
        self,
        project_name: str,
        date_range: str,
        patterns: dict,
        trends: dict,
        averages: dict,
        stats: dict,
    ) -> Optional[str]:
        """Generate LLM-powered narrative summary."""
        try:
            # Format patterns for prompt
            workflow_str = "\n".join(
                f"- {p['pattern']} ({p['count']} sessions, {p['percentage']}%)"
                for p in patterns["workflow"][:5]
            ) or "- No patterns detected"

            learning_str = "\n".join(
                f"- {p['pattern']} ({p['count']} sessions)"
                for p in patterns["learning"][:5]
            ) or "- No opportunities detected"

            anti_str = "\n".join(
                f"- {p['pattern']} ({p['count']} sessions)"
                for p in patterns["anti_patterns"][:5]
            ) or "- No anti-patterns detected"

            # Determine trend directions
            def trend_direction(trend_data: list) -> str:
                if len(trend_data) < 2:
                    return "stable"
                first = trend_data[0]["avg_score"]
                last = trend_data[-1]["avg_score"]
                diff = last - first
                if diff > 0.5:
                    return "improving"
                elif diff < -0.5:
                    return "declining"
                return "stable"

            prompt = PROJECT_SUMMARY_PROMPT.format(
                project_name=project_name,
                date_range=date_range,
                session_count=stats.get("total_messages", 0) // 50 or 1,  # Rough estimate
                workflow_patterns=workflow_str,
                learning_opportunities=learning_str,
                anti_patterns=anti_str,
                collab_trend=trend_direction(trends["collaboration"]),
                avg_collab=averages["collaboration"],
                effectiveness_trend=trend_direction(trends["effectiveness"]),
                avg_effectiveness=averages["effectiveness"],
                clarity_trend=trend_direction(trends["clarity"]),
                avg_clarity=averages["clarity"],
                total_messages=stats["total_messages"],
                success_rate=f"{stats['success_rate']}%" if stats["success_rate"] else "N/A",
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing developer-AI collaboration patterns. Provide actionable, specific insights.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Failed to generate project summary: {e}")
            return None

    def _empty_response(
        self, project_id: UUID, date_range: str
    ) -> dict[str, Any]:
        """Return empty response when no conversations found."""
        return {
            "project_id": str(project_id),
            "date_range": date_range,
            "conversations_analyzed": 0,
            "conversations_with_insights": 0,
            "top_workflow_patterns": [],
            "top_learning_opportunities": [],
            "top_anti_patterns": [],
            "common_technical_debt": [],
            "collaboration_trend": [],
            "effectiveness_trend": [],
            "scope_clarity_trend": [],
            "avg_collaboration_quality": 5.0,
            "avg_agent_effectiveness": 5.0,
            "avg_scope_clarity": 5.0,
            "total_messages": 0,
            "total_tool_calls": 0,
            "success_rate": None,
            "summary": None,
            "generated_at": time.time(),
            # Cache metadata
            "insights_cached": 0,
            "insights_generated": 0,
            "insights_failed": 0,
            "oldest_insight_at": None,
            "newest_insight_at": None,
            "latest_conversation_at": None,
        }
