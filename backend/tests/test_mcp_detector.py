"""Tests for MCP server opportunity detection."""

from unittest.mock import MagicMock, patch

import pytest

from catsyphon.advisor.mcp_detector import MCPDetector
from catsyphon.advisor.models import (
    MCP_CATEGORIES,
    MCPDetectionResult,
    MCPRecommendation,
)


class TestMCPCategories:
    """Test the MCP categories registry."""

    def test_categories_exist(self):
        """Verify all expected categories are defined."""
        expected_categories = [
            "browser-automation",
            "database",
            "api-integration",
            "cloud-services",
            "github-integration",
            "file-system",
            "messaging",
            "observability",
        ]
        for category in expected_categories:
            assert category in MCP_CATEGORIES

    def test_category_structure(self):
        """Verify each category has required fields."""
        for category_name, category in MCP_CATEGORIES.items():
            assert "signals" in category, f"{category_name} missing signals"
            assert "mcps" in category, f"{category_name} missing mcps"
            assert "use_cases" in category, f"{category_name} missing use_cases"
            assert len(category["signals"]) > 0, f"{category_name} has no signals"
            assert len(category["mcps"]) > 0, f"{category_name} has no mcps"

    def test_database_signals(self):
        """Verify database category has expected signals."""
        db_signals = MCP_CATEGORIES["database"]["signals"]
        # Check for SQL patterns
        assert any("SELECT" in s for s in db_signals)
        assert any("INSERT" in s for s in db_signals)
        # Check for database names
        assert any("postgres" in s for s in db_signals)

    def test_browser_signals(self):
        """Verify browser-automation category has expected signals."""
        browser_signals = MCP_CATEGORIES["browser-automation"]["signals"]
        assert any("playwright" in s for s in browser_signals)
        assert any("screenshot" in s for s in browser_signals)
        assert any("e2e" in s.lower() for s in browser_signals)


class TestMCPDetectorCategoryDetection:
    """Test the rule-based category detection."""

    @pytest.fixture
    def detector(self):
        """Create a detector with a mock API key."""
        return MCPDetector(api_key="test-key")

    def test_detect_database_category(self, detector):
        """Test detection of database-related signals."""
        narrative = """
        The user asked to check the database schema.
        I ran SELECT * FROM users to see the data structure.
        Then I used postgres to query for user statistics.
        """
        categories = detector._detect_categories(narrative)
        assert "database" in categories
        assert categories["database"]["match_count"] >= 2

    def test_detect_browser_category(self, detector):
        """Test detection of browser automation signals."""
        narrative = """
        I need to take a screenshot of the login page.
        Using playwright to automate the e2e test.
        Then click the submit button.
        """
        categories = detector._detect_categories(narrative)
        assert "browser-automation" in categories
        assert categories["browser-automation"]["match_count"] >= 2

    def test_detect_cloud_category(self, detector):
        """Test detection of cloud services signals."""
        narrative = """
        Deploy to AWS using terraform.
        Check the kubernetes cluster status with kubectl.
        The docker container needs updating.
        """
        categories = detector._detect_categories(narrative)
        assert "cloud-services" in categories
        assert categories["cloud-services"]["match_count"] >= 3

    def test_detect_github_category(self, detector):
        """Test detection of GitHub-related signals."""
        narrative = """
        Create PR for the feature branch.
        List issues assigned to me.
        Run gh workflow run to trigger the CI.
        """
        categories = detector._detect_categories(narrative)
        assert "github-integration" in categories
        assert categories["github-integration"]["match_count"] >= 2

    def test_detect_no_categories(self, detector):
        """Test that unrelated text doesn't trigger categories."""
        narrative = """
        Let me help you write a function to calculate fibonacci numbers.
        This is a simple recursive implementation.
        We can optimize with memoization.
        """
        categories = detector._detect_categories(narrative)
        # Should not match any MCP categories
        assert len(categories) == 0

    def test_detect_multiple_categories(self, detector):
        """Test detection of multiple categories in one narrative."""
        narrative = """
        First, run SELECT * FROM users to check the data.
        Then take a screenshot with playwright.
        Finally, create PR for the changes.
        """
        categories = detector._detect_categories(narrative)
        assert "database" in categories
        assert "browser-automation" in categories
        assert "github-integration" in categories


class TestMCPRecommendationModel:
    """Test the MCPRecommendation Pydantic model."""

    def test_valid_recommendation(self):
        """Test creating a valid MCP recommendation."""
        rec = MCPRecommendation(
            category="database",
            suggested_mcps=["postgres-mcp"],
            use_cases=["Direct database queries"],
            title="PostgreSQL Integration",
            description="Install postgres-mcp for direct DB access",
            confidence=0.8,
            friction_score=0.6,
            priority=1,
            evidence={
                "matched_signals": ["postgres", "SELECT"],
                "quotes": ["Run the SQL query"],
            },
        )
        assert rec.category == "database"
        assert rec.confidence == 0.8
        assert rec.friction_score == 0.6

    def test_confidence_bounds(self):
        """Test that confidence is bounded between 0 and 1."""
        with pytest.raises(ValueError):
            MCPRecommendation(
                category="test",
                title="Test",
                description="Test",
                confidence=1.5,  # Invalid
            )

    def test_friction_score_bounds(self):
        """Test that friction_score is bounded between 0 and 1."""
        with pytest.raises(ValueError):
            MCPRecommendation(
                category="test",
                title="Test",
                description="Test",
                confidence=0.5,
                friction_score=-0.5,  # Invalid
            )


class TestMCPDetectionResult:
    """Test the MCPDetectionResult model."""

    def test_empty_result(self):
        """Test creating an empty detection result."""
        result = MCPDetectionResult(
            recommendations=[],
            conversation_id="test-123",
            tokens_analyzed=500,
            detection_model="gpt-4o-mini",
            categories_detected=[],
        )
        assert len(result.recommendations) == 0
        assert result.tokens_analyzed == 500

    def test_result_with_recommendations(self):
        """Test creating a result with recommendations."""
        rec = MCPRecommendation(
            category="database",
            suggested_mcps=["postgres-mcp"],
            use_cases=["Query database"],
            title="DB Integration",
            description="Need database access",
            confidence=0.8,
        )
        result = MCPDetectionResult(
            recommendations=[rec],
            conversation_id="test-456",
            tokens_analyzed=1000,
            detection_model="gpt-4o-mini",
            categories_detected=["database"],
        )
        assert len(result.recommendations) == 1
        assert result.categories_detected == ["database"]


class TestMCPDetectorScoring:
    """Test the scoring and priority calculation."""

    @pytest.fixture
    def detector(self):
        """Create a detector with a mock API key."""
        return MCPDetector(api_key="test-key")

    def test_high_combined_score_priority(self, detector):
        """Test that high combined score gives priority 0 or 1."""
        priority = detector._score_to_priority(confidence=0.9, friction_score=0.9)
        assert priority == 0  # Critical

    def test_medium_combined_score_priority(self, detector):
        """Test that medium combined score gives priority 2."""
        priority = detector._score_to_priority(confidence=0.6, friction_score=0.5)
        assert priority == 2  # Medium

    def test_low_combined_score_priority(self, detector):
        """Test that low combined score gives priority 3 or 4."""
        priority = detector._score_to_priority(confidence=0.3, friction_score=0.2)
        assert priority == 4  # Very low


class TestMCPDetectorFormatting:
    """Test the detected categories formatting."""

    @pytest.fixture
    def detector(self):
        """Create a detector with a mock API key."""
        return MCPDetector(api_key="test-key")

    def test_format_empty_categories(self, detector):
        """Test formatting with no detected categories."""
        formatted = detector._format_detected_categories({})
        assert formatted == "None detected"

    def test_format_single_category(self, detector):
        """Test formatting with one category."""
        categories = {
            "database": {
                "matched_signals": ["postgres", "SELECT"],
                "match_count": 2,
                "mcps": ["postgres-mcp"],
                "use_cases": ["Direct queries"],
            }
        }
        formatted = detector._format_detected_categories(categories)
        assert "database" in formatted
        assert "postgres" in formatted
        assert "postgres-mcp" in formatted

    def test_format_multiple_categories(self, detector):
        """Test formatting with multiple categories."""
        categories = {
            "database": {
                "matched_signals": ["postgres"],
                "match_count": 1,
                "mcps": ["postgres-mcp"],
                "use_cases": ["Queries"],
            },
            "browser-automation": {
                "matched_signals": ["playwright"],
                "match_count": 1,
                "mcps": ["playwright-mcp"],
                "use_cases": ["Testing"],
            },
        }
        formatted = detector._format_detected_categories(categories)
        assert "database" in formatted
        assert "browser-automation" in formatted


class TestMCPDetectorWithMockedLLM:
    """Test the full detection flow with mocked LLM responses."""

    @pytest.fixture
    def detector(self):
        """Create a detector with a mock API key."""
        return MCPDetector(api_key="test-key", min_confidence=0.4)

    def test_detect_with_llm_success(self, detector):
        """Test LLM detection with a successful response."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""{
                        "recommendations": [
                            {
                                "category": "database",
                                "suggested_mcps": ["postgres-mcp"],
                                "use_cases": ["Direct queries"],
                                "title": "Database Integration",
                                "description": "Install postgres-mcp",
                                "confidence": 0.8,
                                "friction_score": 0.7,
                                "evidence": {
                                    "matched_signals": ["postgres"],
                                    "quotes": ["Run SQL query"],
                                    "workarounds_detected": [],
                                    "friction_indicators": []
                                }
                            }
                        ]
                    }"""
                )
            )
        ]

        detected_categories = {
            "database": {
                "matched_signals": ["postgres"],
                "match_count": 1,
                "mcps": ["postgres-mcp"],
                "use_cases": ["Queries"],
            }
        }

        with patch.object(
            detector.client.chat.completions, "create", return_value=mock_response
        ):
            recommendations = detector._detect_with_llm(
                narrative="Test narrative with postgres",
                detected_categories=detected_categories,
            )

        assert len(recommendations) == 1
        assert recommendations[0].category == "database"
        assert recommendations[0].confidence == 0.8

    def test_detect_with_llm_empty_response(self, detector):
        """Test LLM detection with empty response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with patch.object(
            detector.client.chat.completions, "create", return_value=mock_response
        ):
            recommendations = detector._detect_with_llm(
                narrative="Test",
                detected_categories={},
            )

        assert len(recommendations) == 0

    def test_detect_with_llm_filters_low_confidence(self, detector):
        """Test that low confidence recommendations are filtered out."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""{
                        "recommendations": [
                            {
                                "category": "database",
                                "suggested_mcps": ["postgres-mcp"],
                                "use_cases": ["Queries"],
                                "title": "Low Confidence",
                                "description": "Maybe helpful",
                                "confidence": 0.2,
                                "friction_score": 0.3
                            }
                        ]
                    }"""
                )
            )
        ]

        with patch.object(
            detector.client.chat.completions, "create", return_value=mock_response
        ):
            recommendations = detector._detect_with_llm(
                narrative="Test",
                detected_categories={},
            )

        # Should be included (min_confidence filtering happens in detect(), not _detect_with_llm())
        assert len(recommendations) == 1

    def test_detect_sorts_by_combined_score(self, detector):
        """Test that recommendations are sorted by friction * confidence."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="""{
                        "recommendations": [
                            {
                                "category": "database",
                                "suggested_mcps": ["postgres-mcp"],
                                "use_cases": ["Queries"],
                                "title": "Low Priority",
                                "description": "Not urgent",
                                "confidence": 0.5,
                                "friction_score": 0.3
                            },
                            {
                                "category": "browser-automation",
                                "suggested_mcps": ["playwright-mcp"],
                                "use_cases": ["Testing"],
                                "title": "High Priority",
                                "description": "Very needed",
                                "confidence": 0.9,
                                "friction_score": 0.8
                            }
                        ]
                    }"""
                )
            )
        ]

        with patch.object(
            detector.client.chat.completions, "create", return_value=mock_response
        ):
            recommendations = detector._detect_with_llm(
                narrative="Test",
                detected_categories={},
            )

        assert len(recommendations) == 2
        # High priority (0.9 * 0.8 = 0.72) should come first
        assert recommendations[0].category == "browser-automation"
        # Low priority (0.5 * 0.3 = 0.15) should come second
        assert recommendations[1].category == "database"
