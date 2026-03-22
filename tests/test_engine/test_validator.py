import pytest
from report_check.engine.validator import RuleValidator, ValidationResult
from report_check.core.exceptions import RuleValidationError


class TestRuleValidator:
    """Test RuleValidator class."""

    @pytest.fixture
    def validator(self):
        return RuleValidator()

    def test_valid_text_rule(self, validator):
        """Test validation of a valid text rule."""
        rule = {
            "id": "test_rule",
            "type": "text",
            "name": "Test Rule",
            "keywords": ["keyword1", "keyword2"],
        }
        result = validator.validate(rule)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_semantic_rule(self, validator):
        """Test validation of a valid semantic rule."""
        rule = {
            "id": "test_rule",
            "type": "semantic",
            "name": "Test Rule",
            "requirement": "Check for specific content",
        }
        result = validator.validate(rule)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_image_rule(self, validator):
        """Test validation of a valid image rule."""
        rule = {
            "id": "test_rule",
            "type": "image",
            "name": "Test Rule",
            "requirement": "Check image quality",
        }
        result = validator.validate(rule)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_api_rule(self, validator):
        """Test validation of a valid api rule."""
        rule = {
            "id": "test_rule",
            "type": "api",
            "name": "Test Rule",
            "extract": "field_name",
            "api": "https://api.example.com/validate",
            "validation": {
                "field": "status",
                "operator": "eq",
                "value": "success",
            },
        }
        result = validator.validate(rule)
        assert result.is_valid is True
        assert result.errors == []

    def test_valid_external_data_rule(self, validator):
        """Test validation of a valid external_data rule."""
        rule = {
            "id": "test_rule",
            "type": "external_data",
            "name": "Test Rule",
            "extract": "field_name",
            "external_api": "https://external.example.com/data",
            "analysis": "Check the returned data",
        }
        result = validator.validate(rule)
        assert result.is_valid is True
        assert result.errors == []

    def test_missing_rules_key(self, validator):
        """Test validation fails when rules key is missing."""
        # If validator is called with None or dict without 'rules' key
        with pytest.raises(RuleValidationError):
            validator.validate(None)

    def test_missing_required_fields(self, validator):
        """Test validation fails when required fields are missing."""
        rule = {
            "id": "test_rule",
            "type": "text",
            # missing 'keywords' which is required for text type
        }
        result = validator.validate(rule)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_unknown_rule_type(self, validator):
        """Test validation fails for unknown rule type."""
        rule = {
            "id": "test_rule",
            "type": "unknown_type",
            "name": "Test Rule",
        }
        result = validator.validate(rule)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_text_rule_missing_keywords(self, validator):
        """Test text rule validation fails without keywords."""
        rule = {
            "id": "test_rule",
            "type": "text",
            "name": "Test Rule",
        }
        result = validator.validate(rule)
        assert result.is_valid is False
        assert any("keywords" in str(error).lower() for error in result.errors)

    def test_api_rule_invalid_operator(self, validator):
        """Test api rule validation fails with invalid operator."""
        rule = {
            "id": "test_rule",
            "type": "api",
            "name": "Test Rule",
            "extract": "field_name",
            "api": "https://api.example.com/validate",
            "validation": {
                "field": "status",
                "operator": "invalid_op",
                "value": "success",
            },
        }
        result = validator.validate(rule)
        assert result.is_valid is False
        assert any("operator" in str(error).lower() for error in result.errors)
