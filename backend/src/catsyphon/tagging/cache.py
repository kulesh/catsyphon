"""File-based cache for conversation tags."""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from catsyphon.models.parsed import ConversationTags, ParsedConversation

logger = logging.getLogger(__name__)


class TagCache:
    """File-based cache for conversation tags.

    Caches tags using SHA-256 hash of conversation content as key.
    Automatically expires entries older than TTL.
    """

    def __init__(self, cache_dir: Path, ttl_days: int = 30):
        """Initialize the tag cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_days: Time-to-live in days (default: 30)
        """
        self.cache_dir = cache_dir
        self.ttl_days = ttl_days
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, parsed: ParsedConversation) -> Optional[ConversationTags]:
        """Get cached tags for a conversation.

        Args:
            parsed: The parsed conversation

        Returns:
            Cached ConversationTags if found and not expired, None otherwise
        """
        cache_key = self._compute_cache_key(parsed)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            logger.debug(f"Cache miss: {cache_key}")
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check expiration
            cached_at = datetime.fromisoformat(data["cached_at"])
            age = datetime.now(timezone.utc) - cached_at
            if age > timedelta(days=self.ttl_days):
                logger.debug(f"Cache expired: {cache_key} (age: {age.days} days)")
                cache_file.unlink()  # Delete expired entry
                return None

            # Reconstruct ConversationTags from cached data
            tags_dict = data["tags"]
            tags = ConversationTags(
                sentiment=tags_dict.get("sentiment"),
                sentiment_score=tags_dict.get("sentiment_score"),
                intent=tags_dict.get("intent"),
                outcome=tags_dict.get("outcome"),
                iterations=tags_dict.get("iterations", 1),
                entities=tags_dict.get("entities", {}),
                features=tags_dict.get("features", []),
                problems=tags_dict.get("problems", []),
                patterns=tags_dict.get("patterns", []),
                tools_used=tags_dict.get("tools_used", []),
                has_errors=tags_dict.get("has_errors", False),
            )

            logger.debug(f"Cache hit: {cache_key}")
            return tags

        except Exception as e:
            logger.warning(f"Failed to read cache for {cache_key}: {e}")
            return None

    def set(self, parsed: ParsedConversation, tags: ConversationTags) -> None:
        """Store tags in cache.

        Args:
            parsed: The parsed conversation
            tags: The tags to cache
        """
        cache_key = self._compute_cache_key(parsed)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "tags": tags.to_dict(),
                "metadata": {
                    "agent_type": parsed.agent_type,
                    "message_count": len(parsed.messages),
                },
            }

            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Cached tags: {cache_key}")

        except Exception as e:
            logger.warning(f"Failed to write cache for {cache_key}: {e}")

    def _compute_cache_key(self, parsed: ParsedConversation) -> str:
        """Compute SHA-256 hash of conversation content for cache key.

        Args:
            parsed: The parsed conversation

        Returns:
            Hex string of SHA-256 hash
        """
        # Build a stable string representation of the conversation
        content_parts = [
            f"agent:{parsed.agent_type}",
            f"messages:{len(parsed.messages)}",
        ]

        # Include message content (truncated to avoid massive hashes)
        for msg in parsed.messages:
            role = msg.role or "unknown"
            content = (msg.content or "")[:500]  # First 500 chars per message
            content_parts.append(f"{role}:{content}")

        content_string = "\n".join(content_parts)

        # Compute SHA-256 hash
        hash_obj = hashlib.sha256(content_string.encode("utf-8"))
        return hash_obj.hexdigest()

    def clear_expired(self) -> int:
        """Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    cached_at = datetime.fromisoformat(data["cached_at"])
                    age = datetime.now(timezone.utc) - cached_at

                    if age > timedelta(days=self.ttl_days):
                        cache_file.unlink()
                        removed += 1
                        logger.debug(f"Removed expired cache: {cache_file.name}")

                except Exception as e:
                    logger.warning(f"Failed to check cache file {cache_file}: {e}")

            if removed > 0:
                logger.info(f"Cleared {removed} expired cache entries")

        except Exception as e:
            logger.error(f"Failed to clear expired cache: {e}")

        return removed

    def stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats (total, expired, valid)
        """
        total = 0
        expired = 0
        valid = 0

        try:
            for cache_file in self.cache_dir.glob("*.json"):
                total += 1
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    cached_at = datetime.fromisoformat(data["cached_at"])
                    age = datetime.now(timezone.utc) - cached_at

                    if age > timedelta(days=self.ttl_days):
                        expired += 1
                    else:
                        valid += 1

                except Exception:
                    expired += 1  # Treat corrupted files as expired

        except Exception as e:
            logger.error(f"Failed to compute cache stats: {e}")

        return {"total": total, "valid": valid, "expired": expired}
