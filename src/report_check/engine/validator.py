from dataclasses import dataclass, field
from typing import Any, Dict, List
from report_check.core.exceptions import RuleValidationError


@dataclass
class ValidationResult:
    """Result of rule validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)


class RuleValidator:
    """Validates rule definitions against their types."""

    # Valid operators for API rules
    VALID_OPERATORS = {"eq", "neq", "contains", "gt", "gte"}

    # Required fields for each rule type
    REQUIRED_FIELDS = {
        "text": {"keywords"},
        "semantic": {"requirement"},
        "image": {"requirement"},
        "api": {"extract", "api", "validation"},
        "external_data": {"extract", "external_api", "analysis"},
    }

    def validate(self, rule: Any) -> ValidationResult:
        """
        Validate a rule definition.

        Args:
            rule: The rule dictionary to validate

        Returns:
            ValidationResult with is_valid flag and list of errors

        Raises:
            RuleValidationError: If rule is None or invalid type
        """
        if rule is None or not isinstance(rule, dict):
            raise RuleValidationError("Rule must be a dictionary")

        errors = []

        # Check for required base fields
        if "type" not in rule:
            errors.append("Rule must have a 'type' field")
            return ValidationResult(is_valid=False, errors=errors)

        rule_type = rule.get("type")

        # Check if rule type is valid
        if rule_type not in self.REQUIRED_FIELDS:
            errors.append(f"Unknown rule type: {rule_type}")
            return ValidationResult(is_valid=False, errors=errors)

        # Check for required fields based on type
        required = self.REQUIRED_FIELDS[rule_type]
        for field in required:
            if field not in rule:
                errors.append(f"Rule type '{rule_type}' requires field '{field}'")

        # Type-specific validation
        if rule_type == "text":
            if "keywords" in rule and not isinstance(rule["keywords"], list):
                errors.append("'keywords' must be a list")
            elif "keywords" in rule and len(rule["keywords"]) == 0:
                errors.append("'keywords' must not be empty")

        elif rule_type == "api":
            if "validation" in rule:
                validation = rule["validation"]
                if isinstance(validation, dict):
                    if "operator" in validation:
                        operator = validation["operator"]
                        if operator not in self.VALID_OPERATORS:
                            errors.append(
                                f"Invalid operator '{operator}'. "
                                f"Valid operators: {', '.join(self.VALID_OPERATORS)}"
                            )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
