"""Main canonicalization orchestrator."""

import logging
from datetime import datetime
from typing import Optional

from catsyphon.canonicalization.builders import JSONBuilder, PlayFormatBuilder
from catsyphon.canonicalization.models import (
    CanonicalConfig,
    CanonicalConversation,
    CanonicalType,
)
from catsyphon.canonicalization.samplers import EpochSampler, SemanticSampler
from catsyphon.canonicalization.tokens import BudgetAllocator, TokenCounter
from catsyphon.canonicalization.version import CANONICAL_VERSION
from catsyphon.models.db import Conversation

logger = logging.getLogger(__name__)


class Canonicalizer:
    """Convert conversations into canonical narrative form.

    Orchestrates the entire canonicalization process:
    1. Configure token budget and sampling strategy
    2. Sample messages intelligently (semantic or epoch-based)
    3. Build narrative in desired format (play, JSON, etc.)
    4. Extract structured metadata
    5. Handle hierarchical contexts (children)
    """

    def __init__(
        self,
        canonical_type: CanonicalType = CanonicalType.TAGGING,
        config: Optional[CanonicalConfig] = None,
        sampling_strategy: str = "semantic",  # "semantic" or "epoch"
        model: str = "gpt-4o-mini",  # For token counting
    ):
        """Initialize canonicalizer.

        Args:
            canonical_type: Type of canonical form (determines defaults)
            config: Custom configuration (overrides type defaults)
            sampling_strategy: "semantic" or "epoch"
            model: Model name for token counting
        """
        self.canonical_type = canonical_type
        self.config = config or CanonicalConfig.for_type(canonical_type)
        self.sampling_strategy = sampling_strategy
        self.model = model

        # Initialize components
        self.token_counter = TokenCounter(model=model)
        self.budget_allocator = BudgetAllocator(self.config.token_budget)

        # Initialize sampler
        if sampling_strategy == "semantic":
            self.sampler = SemanticSampler(self.config, self.token_counter)
        elif sampling_strategy == "epoch":
            self.sampler = EpochSampler(self.config, self.token_counter)
        else:
            raise ValueError(f"Unknown sampling strategy: {sampling_strategy}")

        # Initialize builders
        self.play_builder = PlayFormatBuilder(self.config)
        self.json_builder = JSONBuilder(self.config)

        logger.info(
            f"Canonicalizer initialized: type={canonical_type}, "
            f"budget={self.config.token_budget}, strategy={sampling_strategy}"
        )

    def canonicalize(
        self,
        conversation: Conversation,
        children: Optional[list[Conversation]] = None,
    ) -> CanonicalConversation:
        """Canonicalize a conversation into narrative form.

        Args:
            conversation: Main conversation from database
            children: Child conversations (agents, MCP, etc.)

        Returns:
            CanonicalConversation with narrative and metadata
        """
        logger.info(f"Canonicalizing conversation {conversation.id}")

        # Allocate token budget
        self._allocate_budget(len(children) if children else 0)

        # Sample messages for main conversation
        main_budget = self.budget_allocator.remaining("main_messages")
        sampled_messages = self.sampler.sample(
            messages=list(conversation.messages),
            epochs=list(conversation.epochs),
            token_budget=main_budget,
        )

        # Canonicalize children (if included)
        canonical_children: list[CanonicalConversation] = []
        if children and self.config.include_children:
            child_budget = self.budget_allocator.remaining("children")
            budget_per_child = child_budget // len(children) if children else 0

            for child in children:
                # Recursively canonicalize child with smaller budget
                child_canonicalizer = Canonicalizer(
                    canonical_type=self.canonical_type,
                    config=CanonicalConfig(
                        token_budget=budget_per_child,
                        include_thinking=self.config.include_thinking,
                        include_tool_details=self.config.include_tool_details,
                        include_code_changes=self.config.include_code_changes,
                        include_children=False,  # Don't include nested children
                    ),
                    sampling_strategy=self.sampling_strategy,
                    model=self.model,
                )
                canonical_children.append(
                    child_canonicalizer.canonicalize(child, children=None)
                )

        # Build narrative
        narrative = self.play_builder.build(
            conversation=conversation,
            sampled_messages=sampled_messages,
            files_touched=list(conversation.files_touched),
            children=canonical_children,
        )

        # Count tokens in final narrative
        token_count = self.token_counter.count(narrative)

        # Extract structured metadata
        tools_used = self._extract_tools_used(sampled_messages)
        files_touched = [f.file_path for f in conversation.files_touched]
        has_errors = self._detect_errors(sampled_messages)
        code_changes_summary = self._summarize_code_changes(sampled_messages)

        # Count tool calls
        tool_calls_count = sum(
            len(sm.message.tool_calls) for sm in sampled_messages if sm.message.tool_calls
        )

        # Calculate duration
        duration_seconds = None
        if conversation.start_time and conversation.end_time:
            duration_seconds = int(
                (conversation.end_time - conversation.start_time).total_seconds()
            )

        # Build CanonicalConversation
        canonical = CanonicalConversation(
            session_id=conversation.extra_data.get("session_id", str(conversation.id)),
            conversation_id=str(conversation.id),
            agent_type=conversation.agent_type,
            agent_version=conversation.agent_version,
            conversation_type=conversation.conversation_type,
            start_time=conversation.start_time,
            end_time=conversation.end_time,
            duration_seconds=duration_seconds,
            message_count=conversation.message_count,
            epoch_count=conversation.epoch_count,
            files_count=len(conversation.files_touched),
            tool_calls_count=tool_calls_count,
            narrative=narrative,
            token_count=token_count,
            parent_id=(
                str(conversation.parent_conversation_id)
                if conversation.parent_conversation_id
                else None
            ),
            children=canonical_children,
            tools_used=tools_used,
            files_touched=files_touched,
            has_errors=has_errors,
            code_changes_summary=code_changes_summary,
            config=self.config,
            canonical_version=CANONICAL_VERSION,
            generated_at=datetime.now(),
        )

        logger.info(
            f"Canonicalized conversation {conversation.id}: "
            f"{token_count} tokens, {len(sampled_messages)} messages sampled"
        )

        return canonical

    def to_play_format(self, canonical: CanonicalConversation) -> str:
        """Get play format narrative from canonical conversation.

        Args:
            canonical: Canonical conversation

        Returns:
            Play format narrative string
        """
        return canonical.narrative

    def to_json(self, canonical: CanonicalConversation) -> dict:
        """Get JSON representation from canonical conversation.

        Args:
            canonical: Canonical conversation

        Returns:
            Dictionary suitable for JSON serialization
        """
        return canonical.to_dict()

    def _allocate_budget(self, num_children: int) -> None:
        """Allocate token budget across components.

        Args:
            num_children: Number of child conversations
        """
        # Metadata: 10%
        self.budget_allocator.allocate("metadata", 0.10)

        # Children: Up to 30% or child_token_budget
        if num_children > 0 and self.config.include_children:
            child_percentage = min(
                0.30, self.config.child_token_budget / self.config.token_budget
            )
            self.budget_allocator.allocate("children", child_percentage)
        else:
            self.budget_allocator.allocate("children", 0.0)

        # Main messages: Remainder
        remaining_percentage = 1.0 - 0.10 - (
            self.budget_allocator.allocations.get("children", 0)
            / self.config.token_budget
            if self.config.token_budget > 0
            else 0
        )
        self.budget_allocator.allocate("main_messages", remaining_percentage)

        logger.debug(f"Budget allocation: {self.budget_allocator.summary()}")

    def _extract_tools_used(self, sampled_messages: list) -> list[str]:
        """Extract unique tool names from sampled messages.

        Args:
            sampled_messages: Sampled messages

        Returns:
            List of unique tool names
        """
        tools = set()
        for sm in sampled_messages:
            if sm.message.tool_calls:
                for tc in sm.message.tool_calls:
                    tool_name = tc.get("tool_name")
                    if tool_name:
                        tools.add(tool_name)
        return sorted(tools)

    def _detect_errors(self, sampled_messages: list) -> bool:
        """Detect if any sampled messages contain errors.

        Args:
            sampled_messages: Sampled messages

        Returns:
            True if errors detected
        """
        for sm in sampled_messages:
            content_lower = (sm.message.content or "").lower()
            error_patterns = ["error", "exception", "failed", "failure", "traceback"]
            if any(pattern in content_lower for pattern in error_patterns):
                return True
        return False

    def _summarize_code_changes(self, sampled_messages: list) -> dict:
        """Summarize code changes from sampled messages.

        Args:
            sampled_messages: Sampled messages

        Returns:
            Dictionary with added/deleted/modified counts
        """
        summary = {"added": 0, "deleted": 0, "modified": 0}

        for sm in sampled_messages:
            if sm.message.code_changes:
                for cc in sm.message.code_changes:
                    summary["added"] += cc.get("lines_added", 0)
                    summary["deleted"] += cc.get("lines_deleted", 0)

                    # Count modifications (files with both adds and deletes)
                    if cc.get("lines_added", 0) > 0 and cc.get("lines_deleted", 0) > 0:
                        summary["modified"] += 1

        return summary
