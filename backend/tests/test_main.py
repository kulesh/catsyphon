"""
Tests for main module.
"""

from unittest.mock import patch

from catsyphon.main import hello, main


class TestHello:
    """Tests for hello function."""

    def test_hello_default_name(self):
        """Test hello with default name."""
        result = hello()

        assert result == "Hello, World!"

    def test_hello_with_custom_name(self):
        """Test hello with custom name."""
        result = hello("Alice")

        assert result == "Hello, Alice!"

    def test_hello_with_empty_name(self):
        """Test hello with empty string."""
        result = hello("")

        assert result == "Hello, !"

    def test_hello_returns_string(self):
        """Test that hello returns a string."""
        result = hello()

        assert isinstance(result, str)


class TestMain:
    """Tests for main function."""

    @patch("builtins.print")
    def test_main_prints_hello(self, mock_print):
        """Test that main prints hello message."""
        main()

        mock_print.assert_called_once_with("Hello, World!")

    @patch("catsyphon.main.hello")
    def test_main_calls_hello(self, mock_hello):
        """Test that main calls hello function."""
        mock_hello.return_value = "Hello, World!"

        main()

        mock_hello.assert_called_once()
