from typing import List, Dict, Any, Optional


class RuleEngine:
    """Engine for managing rules: merge, filter, and retrieve."""

    def get_rules(
        self,
        user_rules: Optional[List[Dict[str, Any]]] = None,
        base_rules: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Merge base rules with user rules and filter by enabled status.

        Merge logic:
        1. Start with base_rules as the foundation
        2. Apply user_rules as overrides (matched by id)
        3. Filter out disabled rules

        Args:
            user_rules: List of user-defined rules (can override base rules)
            base_rules: List of base template rules

        Returns:
            List of enabled rules after merge and filtering
        """
        if user_rules is None:
            user_rules = []
        if base_rules is None:
            base_rules = []

        # Create a map of user rules by id for quick lookup
        user_rules_map = {rule.get("id"): rule for rule in user_rules if "id" in rule}

        # Start with base rules
        merged_rules = []
        base_ids_seen = set()

        # Process base rules, applying overrides from user rules
        for base_rule in base_rules:
            base_id = base_rule.get("id")
            if base_id in user_rules_map:
                # Merge user rule with base rule (user rule overrides)
                merged_rule = {**base_rule, **user_rules_map[base_id]}
                merged_rules.append(merged_rule)
                base_ids_seen.add(base_id)
            else:
                # Use base rule as-is
                merged_rules.append(base_rule)
                if base_id:
                    base_ids_seen.add(base_id)

        # Add user rules that don't override a base rule
        for user_rule in user_rules:
            user_id = user_rule.get("id")
            if user_id and user_id not in base_ids_seen:
                merged_rules.append(user_rule)
            elif not user_id:
                # User rule without id (shouldn't happen, but add it anyway)
                merged_rules.append(user_rule)

        # Filter out disabled rules (default is enabled)
        enabled_rules = [
            rule for rule in merged_rules
            if rule.get("enabled", True) is True
        ]

        return enabled_rules
