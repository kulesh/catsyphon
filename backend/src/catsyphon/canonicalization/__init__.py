"""
Conversation canonicalization module.

Provides unified "play-format" narrative representation of conversations
for LLM analysis, replacing multiple ad-hoc sampling approaches with a
centralized, cacheable, hierarchical canonicalization strategy.

Key features:
- Configurable token budgets per analysis type (tagging, insights, export)
- Semantic sampling (prioritizes errors, tool calls, thinking content)
- Hierarchical narrative (includes agent delegations and nested contexts)
- Window-based regeneration (efficient updates for active conversations)
- Multiple output formats (play, JSON, markdown)
"""

from catsyphon.canonicalization.canonicalizer import Canonicalizer
from catsyphon.canonicalization.models import (
    CanonicalConfig,
    CanonicalConversation,
    CanonicalType,
)
from catsyphon.canonicalization.version import CANONICAL_VERSION

__all__ = [
    "Canonicalizer",
    "CanonicalConfig",
    "CanonicalConversation",
    "CanonicalType",
    "CANONICAL_VERSION",
]
