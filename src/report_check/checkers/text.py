import logging
import time
from typing import Optional

from .base import BaseChecker, CheckResult

logger = logging.getLogger(__name__)


class TextChecker(BaseChecker):
    """Checker for text-based rules."""

    def check(self, rule_config) -> CheckResult:
        """Execute a text check rule.

        Args:
            rule_config: Configuration dict containing:
                - rule_id: str
                - rule_name: str
                - rule_type: str
                - keywords: list[str]
                - match_mode: str ("any", "all", or "exact")
                - case_sensitive: bool
                - min_occurrences: int

        Returns:
            CheckResult instance
        """
        start_time = time.time()

        rule_id = rule_config.get("rule_id")
        rule_name = rule_config.get("rule_name")
        rule_type = rule_config.get("rule_type")
        keywords = rule_config.get("keywords", [])
        match_mode = rule_config.get("match_mode", "any")
        case_sensitive = rule_config.get("case_sensitive", False)
        min_occurrences = rule_config.get("min_occurrences", 1)

        # Search for text
        search_results = {}
        for keyword in keywords:
            locations = self.report_data.search_text(
                keyword, case_sensitive=case_sensitive
            )
            search_results[keyword] = locations or []

        # Determine status based on match_mode
        status, message, location, suggestion, example = self._evaluate_results(
            keywords, search_results, match_mode, min_occurrences
        )

        execution_time = time.time() - start_time

        return CheckResult(
            rule_id=rule_id,
            rule_name=rule_name,
            rule_type=rule_type,
            status=status,
            location=location,
            message=message,
            suggestion=suggestion,
            example=example,
            confidence=1.0,
            execution_time=execution_time,
        )

    def _evaluate_results(
        self, keywords, search_results, match_mode, min_occurrences
    ) -> tuple:
        """Evaluate search results based on match mode.

        Returns:
            Tuple of (status, message, location, suggestion, example)
        """
        if match_mode == "any":
            return self._evaluate_any_mode(keywords, search_results, min_occurrences)
        elif match_mode == "all":
            return self._evaluate_all_mode(keywords, search_results, min_occurrences)
        elif match_mode == "exact":
            return self._evaluate_exact_mode(keywords, search_results)
        else:
            return "error", f"Unknown match_mode: {match_mode}", {}, "", ""

    def _evaluate_any_mode(self, keywords, search_results, min_occurrences) -> tuple:
        """Evaluate for 'any' match mode."""
        found_keywords = [k for k, v in search_results.items() if len(v) > 0]
        total_occurrences = sum(len(v) for v in search_results.values())

        if len(found_keywords) > 0 and total_occurrences >= min_occurrences:
            # Build location info from first result
            location = {}
            for keyword in found_keywords:
                if search_results[keyword]:
                    location = search_results[keyword][0]
                    break

            message = f"Found {total_occurrences} occurrence(s) of keywords: {', '.join(found_keywords)}"
            suggestion = "Content matches the expected keywords."
            example = found_keywords[0]
            return "passed", message, location, suggestion, example
        else:
            message = f"Required keywords not found. Expected at least {min_occurrences} occurrence(s)."
            suggestion = f"Add content containing any of these keywords: {', '.join(keywords)}"
            example = keywords[0] if keywords else ""
            return "error", message, {}, suggestion, example

    def _evaluate_all_mode(self, keywords, search_results, min_occurrences) -> tuple:
        """Evaluate for 'all' match mode."""
        found_keywords = [k for k, v in search_results.items() if len(v) > 0]
        missing_keywords = [k for k in keywords if k not in found_keywords]

        if not missing_keywords and all(
            len(v) >= min_occurrences for v in search_results.values()
        ):
            # All keywords found with minimum occurrences
            location = {}
            for keyword in found_keywords:
                if search_results[keyword]:
                    location = search_results[keyword][0]
                    break

            message = f"All required keywords found with at least {min_occurrences} occurrence(s) each"
            suggestion = "Content matches all required keywords."
            example = found_keywords[0] if found_keywords else ""
            return "passed", message, location, suggestion, example
        else:
            if missing_keywords:
                message = f"Missing required keywords: {', '.join(missing_keywords)}"
                suggestion = f"Add content containing these keywords: {', '.join(missing_keywords)}"
                example = missing_keywords[0]
            else:
                below_min = [
                    k for k, v in search_results.items() if len(v) < min_occurrences
                ]
                message = f"Keywords '{', '.join(below_min)}' appear less than {min_occurrences} times"
                suggestion = f"Add more occurrences of: {', '.join(below_min)}"
                example = below_min[0] if below_min else ""
            return "error", message, {}, suggestion, example

    def _evaluate_exact_mode(self, keywords, search_results) -> tuple:
        """Evaluate for 'exact' match mode."""
        found_keywords = [k for k, v in search_results.items() if len(v) > 0]

        if len(found_keywords) == len(keywords) and all(
            len(v) > 0 for v in search_results.values()
        ):
            # Exact match: all keywords present
            location = {}
            for keyword in found_keywords:
                if search_results[keyword]:
                    location = search_results[keyword][0]
                    break

            message = "All required keywords found exactly"
            suggestion = "Content matches exactly."
            example = found_keywords[0] if found_keywords else ""
            return "passed", message, location, suggestion, example
        else:
            missing = [k for k in keywords if k not in found_keywords]
            message = f"Not all keywords found. Missing: {', '.join(missing)}"
            suggestion = f"Add content containing exactly these keywords: {', '.join(keywords)}"
            example = keywords[0] if keywords else ""
            return "error", message, {}, suggestion, example
