import pytest
from report_check.engine.rule_engine import RuleEngine


class TestRuleEngine:
    """Test RuleEngine class."""

    @pytest.fixture
    def engine(self):
        return RuleEngine()

    def test_filters_disabled_rules(self, engine):
        """Test that disabled rules are filtered out."""
        user_rules = [
            {
                "id": "rule1",
                "type": "text",
                "name": "Rule 1",
                "keywords": ["test"],
                "enabled": True,
            },
            {
                "id": "rule2",
                "type": "text",
                "name": "Rule 2",
                "keywords": ["test"],
                "enabled": False,
            },
        ]
        rules = engine.get_rules(user_rules)
        assert len(rules) == 1
        assert rules[0]["id"] == "rule1"

    def test_default_enabled_when_not_specified(self, engine):
        """Test that rules are enabled by default."""
        user_rules = [
            {
                "id": "rule1",
                "type": "text",
                "name": "Rule 1",
                "keywords": ["test"],
            },
        ]
        rules = engine.get_rules(user_rules)
        assert len(rules) == 1
        assert rules[0]["id"] == "rule1"

    def test_merge_with_base_template_override(self, engine):
        """Test merging user rules with base template rules."""
        base_rules = [
            {
                "id": "rule1",
                "type": "text",
                "name": "Base Rule 1",
                "keywords": ["base"],
            },
            {
                "id": "rule2",
                "type": "text",
                "name": "Base Rule 2",
                "keywords": ["base"],
            },
        ]
        user_rules = [
            {
                "id": "rule1",
                "type": "text",
                "name": "User Rule 1",
                "keywords": ["user"],
            },
            {
                "id": "rule3",
                "type": "text",
                "name": "User Rule 3",
                "keywords": ["user"],
            },
        ]
        rules = engine.get_rules(user_rules, base_rules)
        # Should have rule1 (overridden), rule2 (from base), rule3 (from user)
        assert len(rules) == 3
        rule1 = next(r for r in rules if r["id"] == "rule1")
        assert rule1["name"] == "User Rule 1"  # User version overrides base
        assert any(r["id"] == "rule2" for r in rules)
        assert any(r["id"] == "rule3" for r in rules)

    def test_disable_base_rule_via_override(self, engine):
        """Test disabling a base rule via user override."""
        base_rules = [
            {
                "id": "rule1",
                "type": "text",
                "name": "Base Rule 1",
                "keywords": ["base"],
            },
            {
                "id": "rule2",
                "type": "text",
                "name": "Base Rule 2",
                "keywords": ["base"],
            },
        ]
        user_rules = [
            {
                "id": "rule1",
                "enabled": False,
            },
        ]
        rules = engine.get_rules(user_rules, base_rules)
        # Should only have rule2 (rule1 is disabled)
        assert len(rules) == 1
        assert rules[0]["id"] == "rule2"
