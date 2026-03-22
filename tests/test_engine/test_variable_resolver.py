import pytest
import os
from report_check.engine.variable_resolver import VariableResolver
from report_check.core.exceptions import VariableMissingError


class TestVariableResolver:
    """Test VariableResolver class."""

    @pytest.fixture
    def resolver(self):
        return VariableResolver()

    def test_resolve_context_var(self, resolver):
        """Test resolving a variable from context_vars."""
        context_vars = {"name": "John", "age": "30"}
        result = resolver.resolve("${name}", context_vars)
        assert result == "John"

    def test_resolve_env_var(self, resolver, monkeypatch):
        """Test resolving a variable from environment."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        context_vars = {}
        result = resolver.resolve("${TEST_VAR}", context_vars)
        assert result == "test_value"

    def test_resolve_builtin_var(self, resolver):
        """Test resolving a builtin variable."""
        context_vars = {}
        # Test with __timestamp__ builtin
        result = resolver.resolve("${__timestamp__}", context_vars)
        assert result is not None
        assert len(str(result)) > 0

    def test_missing_var_raises_error(self, resolver):
        """Test that missing variable raises VariableMissingError."""
        context_vars = {}
        with pytest.raises(VariableMissingError):
            resolver.resolve("${missing_var}", context_vars)

    def test_no_vars_passthrough(self, resolver):
        """Test that strings without vars pass through unchanged."""
        context_vars = {}
        result = resolver.resolve("no variables here", context_vars)
        assert result == "no variables here"

    def test_recursive_dict_resolution(self, resolver):
        """Test recursive resolution in dictionary values."""
        context_vars = {"name": "Alice", "greeting": "Hello ${name}"}
        result = resolver.resolve_dict({"msg": "Hello ${name}", "nested": {"value": "${greeting}"}}, context_vars)
        assert result["msg"] == "Hello Alice"
        # greeting resolves to "Hello ${name}", which then resolves to "Hello Alice"
        assert result["nested"]["value"] == "Hello Alice"

    def test_resolve_dict_with_lists(self, resolver):
        """Test resolution in dictionaries with lists."""
        context_vars = {"item": "apple"}
        result = resolver.resolve_dict(
            {"items": ["${item}", "banana"]},
            context_vars
        )
        assert result["items"][0] == "apple"
        assert result["items"][1] == "banana"

    def test_resolve_multiple_vars_in_string(self, resolver):
        """Test resolving multiple variables in one string."""
        context_vars = {"first": "Hello", "second": "World"}
        result = resolver.resolve("${first} ${second}", context_vars)
        assert result == "Hello World"
