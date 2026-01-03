"""Recap generator for conversation summaries."""

from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI

from catsyphon.canonicalization import CanonicalType
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.models.db import Conversation
from catsyphon.tagging.llm_logger import llm_logger

RECAP_PROMPT = """You are generating a concise developer recap for a coding session.

Return ONLY valid JSON in this exact shape:
{
  "summary": "1-3 sentences, plain language",
  "key_files": ["path/one", "path/two"],
  "blockers": ["Short blocker", "Short blocker"],
  "next_steps": ["Short next step", "Short next step"],
  "metadata": {
    "intent": "best-effort guess",
    "outcome": "success|partial|failed|abandoned|unknown",
    "confidence": 0.0
  }
}

Guidelines:
- key_files must be file paths that appear in the narrative.
- If no blockers or next steps, return an empty list.
- Be concise and action-oriented.

Conversation Narrative:
{narrative}
"""


class RecapGenerator:
    """Generate recaps using canonical narratives."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 600,
        timeout_s: float = 60.0,
    ):
        self.client = OpenAI(api_key=api_key, timeout=timeout_s)
        self.model = model
        self.max_tokens = max_tokens

    def generate(
        self,
        conversation: Conversation,
        session,
        children: list[Conversation] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        canonical_repo = CanonicalRepository(session)
        canonical = canonical_repo.get_or_generate(
            conversation=conversation,
            canonical_type=CanonicalType.INSIGHTS,
            children=children,
        )

        prompt = RECAP_PROMPT.format(narrative=canonical.narrative)

        log_conversation = type(
            "_LogConversation",
            (),
            {
                "session_id": conversation.extra_data.get(
                    "session_id", str(conversation.id)
                ),
                "messages": conversation.messages or [],
            },
        )()

        request_id = llm_logger.log_request(
            conversation=log_conversation,
            model=self.model,
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )

        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You produce concise developer recaps. Return only JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        duration_ms = (time.time() - start_time) * 1000

        llm_logger.log_response(
            request_id=request_id,
            response=response,
            duration_ms=duration_ms,
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty recap response from OpenAI")

        recap = json.loads(content)
        llm_metrics = {
            "llm_recap_ms": duration_ms,
            "llm_model": response.model,
            "llm_prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "llm_completion_tokens": (
                response.usage.completion_tokens if response.usage else 0
            ),
            "llm_total_tokens": response.usage.total_tokens if response.usage else 0,
            "canonical_version": canonical.canonical_version,
        }

        return recap, llm_metrics
