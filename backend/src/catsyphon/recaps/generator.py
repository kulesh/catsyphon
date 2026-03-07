"""Recap generator for conversation summaries."""

from __future__ import annotations

import json
import time
from typing import Any

from catsyphon.canonicalization import CanonicalType
from catsyphon.db.repositories.canonical import CanonicalRepository
from catsyphon.llm import create_llm_client_for
from catsyphon.models.db import Conversation
from catsyphon.tagging.llm_logger import llm_logger

RECAP_PROMPT = """You are generating a concise developer recap for a coding session.

Return ONLY valid JSON in this exact shape:
{{
  "summary": "1-3 sentences, plain language",
  "key_files": ["path/one", "path/two"],
  "blockers": ["Short blocker", "Short blocker"],
  "next_steps": ["Short next step", "Short next step"],
  "metadata": {{
    "intent": "best-effort guess",
    "outcome": "success|partial|failed|abandoned|unknown",
    "confidence": 0.0
  }}
}}

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
        provider: str = "openai",
        temperature: float = 0.2,
    ):
        _ = timeout_s  # Provider SDKs currently use default timeout handling.
        self.client = create_llm_client_for(provider=provider, api_key=api_key)
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

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
            temperature=self.temperature,
        )

        start_time = time.time()
        response = self.client.generate_json(
            model=self.model,
            system_prompt="You produce concise developer recaps. Return only JSON.",
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        duration_ms = (time.time() - start_time) * 1000

        llm_logger.log_response(
            request_id=request_id,
            response=response,
            duration_ms=duration_ms,
        )

        content = response.content
        if not content:
            raise ValueError("Empty recap response from provider")

        recap = json.loads(content)
        llm_metrics = {
            "llm_recap_ms": duration_ms,
            "llm_provider": response.provider,
            "llm_model": response.model,
            "llm_prompt_tokens": response.usage.prompt_tokens,
            "llm_completion_tokens": response.usage.completion_tokens,
            "llm_total_tokens": response.usage.total_tokens,
            "llm_cost_usd": response.usage.cost_usd,
            "canonical_version": canonical.canonical_version,
        }

        return recap, llm_metrics
