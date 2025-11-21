"""Tests for token counting and budget allocation."""

import pytest

from catsyphon.canonicalization.tokens import BudgetAllocator, TokenCounter


class TestTokenCounter:
    """Test TokenCounter class."""

    def test_count_empty_string(self):
        """Test counting empty string returns 0."""
        counter = TokenCounter()
        assert counter.count("") == 0

    def test_count_simple_text(self):
        """Test counting simple text."""
        counter = TokenCounter()
        result = counter.count("Hello, world!")

        # Should be around 3-4 tokens
        assert 2 <= result <= 5

    def test_count_longer_text(self):
        """Test counting longer text."""
        counter = TokenCounter()
        text = "This is a longer piece of text that should result in more tokens."
        result = counter.count(text)

        # Should be around 15-20 tokens
        assert 10 <= result <= 25

    def test_truncate_to_budget_no_truncation(self):
        """Test truncation when text fits in budget."""
        counter = TokenCounter()
        text = "Short text"
        truncated, token_count = counter.truncate_to_budget(text, token_budget=100)

        assert truncated == text
        assert token_count <= 100

    def test_truncate_to_budget_with_truncation(self):
        """Test truncation when text exceeds budget."""
        counter = TokenCounter()
        text = " ".join(["word"] * 1000)  # Very long text
        truncated, token_count = counter.truncate_to_budget(text, token_budget=50)

        assert len(truncated) < len(text)
        assert token_count <= 50


class TestBudgetAllocator:
    """Test BudgetAllocator class."""

    def test_allocate_percentage(self):
        """Test allocating budget by percentage."""
        allocator = BudgetAllocator(total_budget=1000)
        allocated = allocator.allocate("component_a", 0.3)

        assert allocated == 300
        assert allocator.allocations["component_a"] == 300

    def test_allocate_invalid_percentage(self):
        """Test allocating invalid percentage raises error."""
        allocator = BudgetAllocator(total_budget=1000)

        with pytest.raises(ValueError):
            allocator.allocate("component_a", 1.5)  # > 1.0

        with pytest.raises(ValueError):
            allocator.allocate("component_b", -0.1)  # < 0.0

    def test_spend_and_remaining(self):
        """Test spending budget and checking remaining."""
        allocator = BudgetAllocator(total_budget=1000)
        allocator.allocate("component_a", 0.5)  # 500 tokens

        allocator.spend("component_a", 200)
        assert allocator.remaining("component_a") == 300

        allocator.spend("component_a", 300)
        assert allocator.remaining("component_a") == 0

    def test_total_remaining(self):
        """Test total remaining budget."""
        allocator = BudgetAllocator(total_budget=1000)
        allocator.allocate("component_a", 0.3)  # 300
        allocator.allocate("component_b", 0.5)  # 500

        allocator.spend("component_a", 100)
        allocator.spend("component_b", 200)

        # Total allocated: 800, total spent: 300, remaining: 500
        assert allocator.total_remaining() == 500

    def test_summary(self):
        """Test budget summary."""
        allocator = BudgetAllocator(total_budget=1000)
        allocator.allocate("component_a", 0.5)
        allocator.spend("component_a", 200)

        summary = allocator.summary()

        assert "component_a" in summary
        assert summary["component_a"]["allocated"] == 500
        assert summary["component_a"]["spent"] == 200
        assert summary["component_a"]["remaining"] == 300
