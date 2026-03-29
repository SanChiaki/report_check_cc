"""
Unit tests for SignatureChecker grid reference method.

These tests focus on the core grid generation and coordinate conversion logic.
"""
import pytest
from PIL import Image
from unittest.mock import MagicMock

from report_check.checkers.signature import SignatureChecker
from report_check.parser.models import ReportData


def create_test_report_data(file_name="test.pdf"):
    """Helper to create test ReportData."""
    return ReportData(
        file_name=file_name,
        source_type="pdf",
        content_blocks=[],
        images=[],
        metadata={}
    )


class TestGridOverlay:
    """Test grid overlay generation."""

    def test_add_grid_overlay_basic(self):
        """Test basic grid overlay with default 20x20."""
        img = Image.new('RGB', (1000, 1000), color='white')
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        result = checker._add_grid_overlay(img, grid_size=20)

        assert result.size == (1000, 1000)
        assert isinstance(result, Image.Image)

    def test_add_grid_overlay_custom_size(self):
        """Test grid overlay with custom grid size."""
        img = Image.new('RGB', (800, 600), color='white')
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        result = checker._add_grid_overlay(img, grid_size=10)

        assert result.size == (800, 600)
        # Verify grid lines are drawn (image should be modified)
        assert result != img


class TestBoundaryToBbox:
    """Test boundary cell to bbox conversion."""

    def test_boundary_to_bbox_no_padding(self):
        """Test bbox conversion without padding."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        bbox = checker._boundary_to_bbox(
            top_left="C3",
            bottom_right="E5",
            img_width=1000,
            img_height=1000,
            grid_size=10,
            padding_cells=0
        )

        # Grid 10x10: each cell is 100px
        # C3 = col 2 (200px), row 2 (200px)
        # E5 = col 4 (400px), row 4 (400px)
        # bbox should be [200, 200, 500, 500] (right/bottom +1 cell)
        assert bbox == {"x1": 200, "y1": 200, "x2": 500, "y2": 500}

    def test_boundary_to_bbox_with_padding(self):
        """Test bbox conversion with padding."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        bbox = checker._boundary_to_bbox(
            top_left="C3",
            bottom_right="E5",
            img_width=1000,
            img_height=1000,
            grid_size=10,
            padding_cells=1
        )

        # With padding=1, expand by 1 cell on each side
        # Original: [200, 200, 500, 500]
        # After padding: [100, 100, 600, 600]
        assert bbox == {"x1": 100, "y1": 100, "x2": 600, "y2": 600}

    def test_boundary_to_bbox_edge_clipping(self):
        """Test bbox clipping at image edges."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        # Top-left corner with padding should clip to [0, 0]
        bbox = checker._boundary_to_bbox(
            top_left="A1",
            bottom_right="B2",
            img_width=1000,
            img_height=1000,
            grid_size=10,
            padding_cells=2
        )

        # Original: [0, 0, 200, 200]
        # After padding: [-200, -200, 400, 400] → clipped to [0, 0, 400, 400]
        assert bbox["x1"] == 0
        assert bbox["y1"] == 0

    def test_boundary_to_bbox_20x20_grid(self):
        """Test bbox conversion with 20x20 grid (production default)."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        bbox = checker._boundary_to_bbox(
            top_left="D15",
            bottom_right="D15",
            img_width=2000,
            img_height=2000,
            grid_size=20,
            padding_cells=1
        )

        # Grid 20x20: each cell is 100px
        # D15 = col 3 (300px), row 14 (1400px)
        # Single cell: [300, 1400, 400, 1500]
        # With padding=1: [200, 1300, 500, 1600]
        assert bbox == {"x1": 200, "y1": 1300, "x2": 500, "y2": 1600}

    def test_boundary_to_bbox_single_cell(self):
        """Test bbox for a single cell signature."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        bbox = checker._boundary_to_bbox(
            top_left="A1",
            bottom_right="A1",
            img_width=1000,
            img_height=1000,
            grid_size=10,
            padding_cells=0
        )

        # Single cell A1: [0, 0, 100, 100]
        assert bbox == {"x1": 0, "y1": 0, "x2": 100, "y2": 100}

    def test_boundary_to_bbox_large_region(self):
        """Test bbox for a large multi-cell region."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        bbox = checker._boundary_to_bbox(
            top_left="A1",
            bottom_right="J10",
            img_width=2000,
            img_height=2000,
            grid_size=20,
            padding_cells=0
        )

        # A1 to J10: [0, 0, 1000, 1000]
        assert bbox == {"x1": 0, "y1": 0, "x2": 1000, "y2": 1000}


class TestCellParsing:
    """Test cell ID parsing logic."""

    def test_parse_various_cells(self):
        """Test parsing different cell formats."""
        checker = SignatureChecker(
            report_data=create_test_report_data(),
            model_manager=MagicMock()
        )

        test_cases = [
            ("A1", 0, 0),
            ("B2", 1, 1),
            ("T20", 19, 19),  # Valid for 20x20 grid
        ]

        for cell_id, expected_col, expected_row in test_cases:
            # Parse by creating a bbox
            bbox = checker._boundary_to_bbox(
                top_left=cell_id,
                bottom_right=cell_id,
                img_width=2000,
                img_height=2000,
                grid_size=20,
                padding_cells=0
            )

            assert bbox["x1"] == expected_col * 100
            assert bbox["y1"] == expected_row * 100
