"""Specs for audit_ml_view.py — Rich rendering for the audit-ml command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


class DescribeShowSummary:
    def it_should_display_summary_statistics(self):
        from gilt.cli.command.audit_ml_view import show_summary

        con, buf = _make_console()
        builder = MagicMock()
        builder.get_statistics.return_value = {
            "total_examples": 20,
            "positive_examples": 10,
            "negative_examples": 10,
            "class_balance": 0.5,
            "sufficient_for_training": True,
        }
        result = show_summary(con, builder)
        output = buf.getvalue()
        assert "20" in output
        assert result == 0

    def it_should_return_zero(self):
        from gilt.cli.command.audit_ml_view import show_summary

        con, buf = _make_console()
        builder = MagicMock()
        builder.get_statistics.return_value = {
            "total_examples": 0,
            "positive_examples": 0,
            "negative_examples": 0,
            "class_balance": 0.0,
            "sufficient_for_training": False,
        }
        result = show_summary(con, builder)
        assert result == 0


class DescribeShowPredictions:
    def it_should_show_no_candidates_message_when_empty(self):
        from gilt.cli.command.audit_ml_view import show_predictions

        con, buf = _make_console()
        result = show_predictions(con, MagicMock(), [], None, 10)
        output = buf.getvalue()
        assert "No candidates" in output
        assert result == 0

    def it_should_show_unavailable_message_when_detector_is_none(self):
        from gilt.cli.command.audit_ml_view import show_predictions

        con, buf = _make_console()
        result = show_predictions(con, None, [], None, 10)
        output = buf.getvalue()
        assert "not available" in output
        assert result == 0


class DescribePrintValidModes:
    def it_should_list_all_modes(self):
        from gilt.cli.command.audit_ml_view import print_valid_modes

        con, buf = _make_console()
        print_valid_modes(con)
        output = buf.getvalue()
        assert "summary" in output
        assert "predictions" in output
