"""Specs for infer_rules_view.py — Rich rendering for the infer-rules command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.infer_rules_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


def _make_rule(description="EXAMPLE UTILITY", category="Utilities", subcategory=None, evidence_count=5, total_count=5, confidence=1.0):
    from gilt.services.rule_inference_service import InferredRule

    return InferredRule(
        description=description,
        category=category,
        subcategory=subcategory,
        evidence_count=evidence_count,
        total_count=total_count,
        confidence=confidence,
    )


class DescribeDisplayRules:
    def it_should_show_rule_description(self):
        from gilt.cli.command.infer_rules_view import display_rules

        rules = [_make_rule(description="EXAMPLE UTILITY")]
        output = _capture(lambda: display_rules(rules))
        assert "EXAMPLE UTILITY" in output

    def it_should_show_category(self):
        from gilt.cli.command.infer_rules_view import display_rules

        rules = [_make_rule(category="Utilities")]
        output = _capture(lambda: display_rules(rules))
        assert "Utilities" in output

    def it_should_show_rules_count(self):
        from gilt.cli.command.infer_rules_view import display_rules

        rules = [_make_rule(description=f"VENDOR {i}") for i in range(7)]
        output = _capture(lambda: display_rules(rules))
        assert "7 rule(s)" in output
