"""Specs for prompt_stats_view.py — Rich rendering for the prompt-stats command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


def _make_metrics():
    from gilt.transfer.prompt_learning import AccuracyMetrics

    return AccuracyMetrics(
        total_feedback=20,
        true_positives=8,
        false_positives=2,
        true_negatives=8,
        false_negatives=2,
        accuracy=0.8,
    )


class DescribeDisplayAccuracyMetrics:
    def it_should_render_total_feedback(self):
        from gilt.cli.command.prompt_stats_view import display_accuracy_metrics

        con, buf = _make_console()
        metrics = _make_metrics()
        display_accuracy_metrics(con, metrics)
        output = buf.getvalue()
        assert "20" in output

    def it_should_render_accuracy_as_percentage(self):
        from gilt.cli.command.prompt_stats_view import display_accuracy_metrics

        con, buf = _make_console()
        metrics = _make_metrics()
        display_accuracy_metrics(con, metrics)
        output = buf.getvalue()
        assert "80" in output or "0.8" in output or "80.0%" in output


class DescribeDisplayLearnedPatterns:
    def it_should_render_nothing_for_empty_patterns(self):
        from gilt.cli.command.prompt_stats_view import display_learned_patterns

        con, buf = _make_console()
        display_learned_patterns(con, [])
        output = buf.getvalue()
        assert output.strip() == ""

    def it_should_render_pattern_description(self):
        from gilt.cli.command.prompt_stats_view import display_learned_patterns
        from gilt.transfer.prompt_learning import LearnedPattern

        con, buf = _make_console()
        patterns = [
            LearnedPattern(
                pattern_type="preference",
                description="Users prefer shorter descriptions",
                confidence=0.9,
                evidence_count=10,
            )
        ]
        display_learned_patterns(con, patterns)
        output = buf.getvalue()
        assert "shorter descriptions" in output
