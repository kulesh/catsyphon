"""Weekly digest generator using existing analytics."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from catsyphon.db.repositories.conversation import ConversationRepository


class WeeklyDigestGenerator:
    """Generate weekly digests from stored conversations."""

    def __init__(self, session):
        self.session = session
        self.conversation_repo = ConversationRepository(session)

    def generate(
        self,
        workspace_id,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        # Don't load relations - digest only needs conversation metadata and tags
        conversations = self.conversation_repo.get_by_filters(
            workspace_id=workspace_id,
            start_date=period_start,
            end_date=period_end,
            load_relations=False,
        )

        total_sessions = len(conversations)
        success_sessions = sum(1 for conv in conversations if conv.success is True)
        failed_sessions = sum(1 for conv in conversations if conv.success is False)
        success_rate = (
            round(success_sessions / total_sessions, 2) if total_sessions else None
        )

        project_counts = Counter(
            conv.project.name for conv in conversations if conv.project
        )
        top_projects = [name for name, _ in project_counts.most_common(3)]

        feature_counts: Counter[str] = Counter()
        problem_counts: Counter[str] = Counter()

        for conv in conversations:
            tags = conv.tags or {}
            for feature in tags.get("features", []) or []:
                feature_counts[feature] += 1
            for problem in tags.get("problems", []) or []:
                problem_counts[problem] += 1

        wins = []
        if success_rate is not None:
            wins.append(f"Success rate {int(success_rate * 100)}%")
        wins.extend([f"Feature: {name}" for name, _ in feature_counts.most_common(3)])

        blockers = [name for name, _ in problem_counts.most_common(5)]

        highlights = []
        if top_projects:
            highlights.append(
                "Top projects: " + ", ".join(top_projects)
            )
        if total_sessions:
            highlights.append(f"Total sessions: {total_sessions}")

        summary = (
            f"{total_sessions} sessions from {period_start.date()} to {period_end.date()}."
            if total_sessions
            else f"No sessions between {period_start.date()} and {period_end.date()}."
        )

        metrics = {
            "total_sessions": total_sessions,
            "success_sessions": success_sessions,
            "failed_sessions": failed_sessions,
            "success_rate": success_rate,
            "top_projects": top_projects,
        }

        return {
            "summary": summary,
            "wins": wins,
            "blockers": blockers,
            "highlights": highlights,
            "metrics": metrics,
        }
