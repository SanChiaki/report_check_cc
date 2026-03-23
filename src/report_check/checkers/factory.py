"""Checker factory for creating checker instances."""

import logging
from typing import TYPE_CHECKING, Type

from .base import BaseChecker
from .text import TextChecker
from .semantic import SemanticChecker
from .image import ImageChecker
from .api_check import ApiChecker
from .external import ExternalDataChecker

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class CheckerFactory:
    """Factory for creating checker instances."""

    CHECKER_MAP = {
        "text": TextChecker,
        "semantic": SemanticChecker,
        "image": ImageChecker,
        "api": ApiChecker,
        "external_data": ExternalDataChecker,
    }

    @classmethod
    def create(
        cls,
        checker_type: str,
        report_data,
        model_manager,
        artifacts: "CheckArtifact | None" = None,
    ) -> BaseChecker:
        """Create a checker instance.

        Args:
            checker_type: Type of checker to create
            report_data: ReportData instance
            model_manager: ModelManager instance
            artifacts: Optional CheckArtifact instance for recording execution details

        Returns:
            BaseChecker instance

        Raises:
            ValueError: If checker_type is unknown
        """
        if checker_type not in cls.CHECKER_MAP:
            raise ValueError(
                f"Unknown checker type: {checker_type}. "
                f"Available types: {list(cls.CHECKER_MAP.keys())}"
            )

        checker_class = cls.CHECKER_MAP[checker_type]
        return checker_class(report_data, model_manager, artifacts=artifacts)

    @classmethod
    def register(cls, checker_type: str, checker_class: Type[BaseChecker]) -> None:
        """Register a new checker type.

        Args:
            checker_type: Name of the checker type
            checker_class: Checker class to register
        """
        cls.CHECKER_MAP[checker_type] = checker_class
        logger.info(f"Registered checker type: {checker_type}")
