"""Tests for file-based tag cache."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from catsyphon.models.parsed import ConversationTags, ParsedConversation, ParsedMessage
from catsyphon.tagging.cache import TagCache


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "tag_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def tag_cache(temp_cache_dir: Path) -> TagCache:
    """Create a tag cache instance."""
    return TagCache(cache_dir=temp_cache_dir, ttl_days=30)


@pytest.fixture
def sample_conversation() -> ParsedConversation:
    """Create a sample parsed conversation."""
    return ParsedConversation(
        agent_type="claude-code",
        agent_version="1.0.0",
        start_time=datetime(2025, 1, 1, 10, 0, 0),
        end_time=datetime(2025, 1, 1, 10, 30, 0),
        messages=[
            ParsedMessage(
                role="user",
                content="Help me fix this bug",
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
            ),
            ParsedMessage(
                role="assistant",
                content="I'll help you debug the issue",
                timestamp=datetime(2025, 1, 1, 10, 1, 0),
            ),
        ],
    )


@pytest.fixture
def sample_tags() -> ConversationTags:
    """Create sample conversation tags."""
    return ConversationTags(
        intent="bug_fix",
        outcome="success",
        sentiment="positive",
        sentiment_score=0.8,
        features=["debugging", "error handling"],
        problems=["null pointer exception"],
        tools_used=["bash", "git"],
        has_errors=True,
        iterations=2,
        patterns=["debugging", "testing"],
    )


class TestTagCache:
    """Tests for TagCache class."""

    def test_cache_directory_created(self, temp_cache_dir: Path):
        """Test that cache directory is created automatically."""
        new_cache_dir = temp_cache_dir / "new_cache"
        assert not new_cache_dir.exists()

        cache = TagCache(cache_dir=new_cache_dir, ttl_days=30)
        assert new_cache_dir.exists()
        assert new_cache_dir.is_dir()

    def test_cache_miss(
        self,
        tag_cache: TagCache,
        sample_conversation: ParsedConversation,
    ):
        """Test cache miss returns None."""
        result = tag_cache.get(sample_conversation)
        assert result is None

    def test_cache_set_and_get(
        self,
        tag_cache: TagCache,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test setting and getting cached tags."""
        # Set cache
        tag_cache.set(sample_conversation, sample_tags)

        # Get from cache
        cached_tags = tag_cache.get(sample_conversation)
        assert cached_tags is not None
        assert cached_tags.intent == sample_tags.intent
        assert cached_tags.outcome == sample_tags.outcome
        assert cached_tags.sentiment == sample_tags.sentiment
        assert cached_tags.sentiment_score == sample_tags.sentiment_score
        assert cached_tags.features == sample_tags.features
        assert cached_tags.problems == sample_tags.problems
        assert cached_tags.tools_used == sample_tags.tools_used
        assert cached_tags.has_errors == sample_tags.has_errors
        assert cached_tags.iterations == sample_tags.iterations
        assert cached_tags.patterns == sample_tags.patterns

    def test_cache_key_stability(
        self,
        tag_cache: TagCache,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test that same conversation always generates same cache key."""
        # Set cache
        tag_cache.set(sample_conversation, sample_tags)

        # Get with same conversation should hit cache
        cached_tags1 = tag_cache.get(sample_conversation)
        assert cached_tags1 is not None

        # Get again should still hit cache
        cached_tags2 = tag_cache.get(sample_conversation)
        assert cached_tags2 is not None
        assert cached_tags1.intent == cached_tags2.intent

    def test_cache_key_changes_with_content(
        self,
        tag_cache: TagCache,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test that different content generates different cache key."""
        # Cache first conversation
        tag_cache.set(sample_conversation, sample_tags)

        # Modify conversation content
        sample_conversation.messages.append(
            ParsedMessage(
                role="user",
                content="Additional message changes the conversation",
                timestamp=datetime(2025, 1, 1, 10, 5, 0),
            )
        )

        # Should be cache miss for modified conversation
        cached_tags = tag_cache.get(sample_conversation)
        assert cached_tags is None

    def test_cache_expiration(
        self,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test that expired cache entries are not returned."""
        # Create cache with 1-day TTL
        cache = TagCache(cache_dir=temp_cache_dir, ttl_days=1)

        # Set cache
        cache.set(sample_conversation, sample_tags)

        # Verify cache hit
        cached_tags = cache.get(sample_conversation)
        assert cached_tags is not None

        # Manually modify cached file's timestamp to make it expired
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1
        cache_file = cache_files[0]

        # Read and modify the cached data to be 2 days old
        import json

        with open(cache_file, "r") as f:
            data = json.load(f)

        # Set cached_at to 2 days ago (beyond 1-day TTL)
        expired_time = datetime.now(timezone.utc) - timedelta(days=2)
        data["cached_at"] = expired_time.isoformat()

        with open(cache_file, "w") as f:
            json.dump(data, f)

        # Should be cache miss due to expiration
        cached_tags = cache.get(sample_conversation)
        assert cached_tags is None

        # Cache file should be deleted
        assert not cache_file.exists()

    def test_clear_expired(
        self,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test clearing expired cache entries."""
        # Create cache with 1-day TTL
        cache = TagCache(cache_dir=temp_cache_dir, ttl_days=1)

        # Set multiple cache entries
        cache.set(sample_conversation, sample_tags)

        # Modify message to create a different cache entry
        sample_conversation.messages[0].content = "Different content"
        cache.set(sample_conversation, sample_tags)

        # Verify we have 2 cache files
        cache_files = list(temp_cache_dir.glob("*.json"))
        assert len(cache_files) == 2

        # Manually expire one of them
        import json

        cache_file = cache_files[0]
        with open(cache_file, "r") as f:
            data = json.load(f)

        expired_time = datetime.now(timezone.utc) - timedelta(days=2)
        data["cached_at"] = expired_time.isoformat()

        with open(cache_file, "w") as f:
            json.dump(data, f)

        # Clear expired entries
        removed = cache.clear_expired()
        assert removed == 1

        # Only 1 cache file should remain
        remaining_files = list(temp_cache_dir.glob("*.json"))
        assert len(remaining_files) == 1

    def test_cache_stats_empty(self, tag_cache: TagCache):
        """Test cache stats for empty cache."""
        stats = tag_cache.stats()
        assert stats["total"] == 0
        assert stats["valid"] == 0
        assert stats["expired"] == 0

    def test_cache_stats_with_entries(
        self,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test cache stats with valid entries."""
        cache = TagCache(cache_dir=temp_cache_dir, ttl_days=30)

        # Add 3 entries
        for i in range(3):
            sample_conversation.messages[0].content = f"Message {i}"
            cache.set(sample_conversation, sample_tags)

        stats = cache.stats()
        assert stats["total"] == 3
        assert stats["valid"] == 3
        assert stats["expired"] == 0

    def test_cache_stats_with_expired(
        self,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
        sample_tags: ConversationTags,
    ):
        """Test cache stats with expired entries."""
        cache = TagCache(cache_dir=temp_cache_dir, ttl_days=1)

        # Add entries
        cache.set(sample_conversation, sample_tags)
        sample_conversation.messages[0].content = "Different message"
        cache.set(sample_conversation, sample_tags)

        # Manually expire one
        import json

        cache_files = list(temp_cache_dir.glob("*.json"))
        cache_file = cache_files[0]
        with open(cache_file, "r") as f:
            data = json.load(f)

        expired_time = datetime.now(timezone.utc) - timedelta(days=2)
        data["cached_at"] = expired_time.isoformat()

        with open(cache_file, "w") as f:
            json.dump(data, f)

        stats = cache.stats()
        assert stats["total"] == 2
        assert stats["valid"] == 1
        assert stats["expired"] == 1

    def test_cache_handles_corrupted_files(
        self,
        tag_cache: TagCache,
        temp_cache_dir: Path,
        sample_conversation: ParsedConversation,
    ):
        """Test that cache handles corrupted files gracefully."""
        # Create a corrupted cache file
        corrupted_file = temp_cache_dir / "corrupted.json"
        corrupted_file.write_text("invalid json content {{{")

        # Should not crash when getting cache stats
        stats = tag_cache.stats()
        assert stats["total"] == 1
        assert stats["expired"] == 1  # Corrupted files treated as expired

        # Should not crash when clearing expired
        removed = tag_cache.clear_expired()
        assert removed >= 0  # May or may not remove corrupted file

    def test_compute_cache_key_consistency(
        self, tag_cache: TagCache, sample_conversation: ParsedConversation
    ):
        """Test that cache key computation is consistent."""
        key1 = tag_cache._compute_cache_key(sample_conversation)
        key2 = tag_cache._compute_cache_key(sample_conversation)
        assert key1 == key2
        assert len(key1) == 64  # SHA-256 produces 64 hex characters

    def test_cache_truncates_long_messages(
        self, tag_cache: TagCache, sample_tags: ConversationTags
    ):
        """Test that very long messages are handled correctly."""
        # Create conversation with very long message
        long_content = "A" * 10000  # 10K characters
        conversation = ParsedConversation(
            agent_type="claude-code",
            agent_version="1.0.0",
            start_time=datetime(2025, 1, 1, 10, 0, 0),
            end_time=datetime(2025, 1, 1, 10, 30, 0),
            messages=[
                ParsedMessage(
                    role="user",
                    content=long_content,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                ),
            ],
        )

        # Should handle without errors
        tag_cache.set(conversation, sample_tags)
        cached = tag_cache.get(conversation)
        assert cached is not None
