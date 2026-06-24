"""Specs for duplicates_view — Rich rendering functions for the duplicates command.

All data is synthetic (AGENTS.md privacy rules): MyBank, MYBANK_CHQ,
EXAMPLE UTILITY, ACME CORP, Exampleville, etc.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console

from gilt.cli.command.duplicates_view import (
    display_match_options,
    display_non_interactive_results,
    print_detection_info,
)
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair


def _make_pair(
    txn1_id: str = "aaaa0001aaaa0001",
    txn2_id: str = "bbbb0002bbbb0002",
    description: str = "EXAMPLE UTILITY PAYMENT",
    amount: float = -75.00,
    account_id: str = "MYBANK_CHQ",
) -> TransactionPair:
    return TransactionPair(
        txn1_id=txn1_id,
        txn2_id=txn2_id,
        txn1_description=description,
        txn2_description=description + " (DUP)",
        txn1_date="2025-01-10",
        txn2_date="2025-01-11",
        txn1_amount=amount,
        txn2_amount=amount,
        txn1_account=account_id,
        txn2_account=account_id,
    )


def _make_assessment(is_duplicate: bool = True, confidence: float = 0.90) -> DuplicateAssessment:
    return DuplicateAssessment(
        is_duplicate=is_duplicate,
        confidence=confidence,
        reasoning="Same merchant, same amount, one day apart",
    )


def _make_match(confidence: float = 0.90) -> DuplicateMatch:
    return DuplicateMatch(pair=_make_pair(), assessment=_make_assessment(confidence=confidence))


def _capture_console(fn, console_obj: Console) -> str:
    buf = StringIO()
    tmp = Console(file=buf, highlight=False)

    import gilt.cli.command.duplicates_view as view_mod

    old = view_mod.console
    view_mod.console = tmp
    try:
        fn(tmp)
    finally:
        view_mod.console = old
    return buf.getvalue()


class DescribeDisplayMatchOptions:
    def it_should_print_all_three_choices(self):
        buf = StringIO()
        console_obj = Console(file=buf, highlight=False)

        smart_default = MagicMock()
        smart_default.default_choice = "1"
        smart_default.hint = " ← recommended"

        display_match_options(console_obj, smart_default)
        output = buf.getvalue()

        assert "1)" in output
        assert "2)" in output
        assert "N)" in output
        assert "← recommended" in output

    def it_should_attach_hint_to_choice_2_when_default_is_2(self):
        buf = StringIO()
        console_obj = Console(file=buf, highlight=False)

        smart_default = MagicMock()
        smart_default.default_choice = "2"
        smart_default.hint = " ← default"

        display_match_options(console_obj, smart_default)
        output = buf.getvalue()

        lines = [line for line in output.splitlines() if "2)" in line]
        assert any("← default" in line for line in lines)


class DescribeDisplayNonInteractiveResults:
    def it_should_print_each_match_with_confidence_and_description(self):
        buf = StringIO()
        matches = [_make_match(0.88), _make_match(0.76)]

        import gilt.cli.command.duplicates_view as view_mod

        old = view_mod.console
        view_mod.console = Console(file=buf, highlight=False)
        try:
            display_non_interactive_results(matches)
        finally:
            view_mod.console = old

        output = buf.getvalue()
        assert "Match 1/2" in output
        assert "Match 2/2" in output
        assert "88.0%" in output
        assert "76.0%" in output

    def it_should_include_transaction_id_prefixes(self):
        buf = StringIO()
        match = _make_match()

        import gilt.cli.command.duplicates_view as view_mod

        old = view_mod.console
        view_mod.console = Console(file=buf, highlight=False)
        try:
            display_non_interactive_results([match])
        finally:
            view_mod.console = old

        output = buf.getvalue()
        # Short (8-char) prefix of txn2_id
        assert "bbbb0002" in output


class DescribePrintDetectionInfo:
    def it_should_print_data_dir_and_detection_method(self):
        buf = StringIO()
        console_obj = Console(file=buf, highlight=False)

        detector = MagicMock()
        detector._ml_classifier = None
        detector.prompt_version = "v2"
        detector.learned_patterns = []

        print_detection_info(
            console_obj=console_obj,
            data_dir="/data/accounts",
            detection_method="LLM",
            use_llm=True,
            model="llama3",
            detector=detector,
            max_days_apart=2,
            amount_tolerance=0.01,
            interactive=False,
        )
        output = buf.getvalue()

        assert "/data/accounts" in output
        assert "LLM" in output
        assert "llama3" in output
        assert "2" in output

    def it_should_note_interactive_mode_when_enabled(self):
        buf = StringIO()
        console_obj = Console(file=buf, highlight=False)

        detector = MagicMock()
        detector._ml_classifier = None
        detector.prompt_version = "v1"
        detector.learned_patterns = []

        print_detection_info(
            console_obj=console_obj,
            data_dir="/data/accounts",
            detection_method="LLM",
            use_llm=True,
            model="llama3",
            detector=detector,
            max_days_apart=1,
            amount_tolerance=0.001,
            interactive=True,
        )
        output = buf.getvalue()

        assert "Interactive mode" in output or "interactive" in output.lower()
