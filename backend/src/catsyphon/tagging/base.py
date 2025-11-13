"""Base protocol for conversation taggers."""

from typing import Protocol

from catsyphon.models.parsed import ConversationTags, ParsedConversation


class BaseTagger(Protocol):
    """Protocol for conversation taggers.

    Taggers analyze parsed conversations and return metadata tags
    that provide insights into the conversation's purpose, outcome,
    and characteristics.
    """

    def tag_conversation(self, parsed: ParsedConversation) -> ConversationTags:
        """Tag a parsed conversation.

        Args:
            parsed: The parsed conversation to analyze

        Returns:
            ConversationTags with extracted metadata

        Raises:
            Exception: If tagging fails (implementations should handle gracefully)
        """
        ...
