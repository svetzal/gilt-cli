"""Specs for duplicates_review.py — interactive review for the duplicates command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console


def _make_review_ctx():
    from gilt.cli.command.duplicates import ReviewContext

    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)

    ctx = ReviewContext(
        console=con,
        review_service=MagicMock(),
        detector=MagicMock(),
        es_service=MagicMock(),
        event_store=MagicMock(),
        feedback=[],
    )
    ctx.detector.prompt_manager = None
    ctx.detector.learned_patterns = []
    ctx.detector.prompt_version = "v1"
    ctx.es_service.ensure_projections_up_to_date.return_value = 0
    return ctx, buf


def _make_match():
    from datetime import date

    from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair

    pair = TransactionPair(
        txn1_id="abcd1234efgh5678",
        txn1_date=date(2025, 1, 15),
        txn1_description="EXAMPLE UTILITY",
        txn1_amount=-50.0,
        txn1_account="MYBANK_CHQ",
        txn2_id="wxyz9876mnop5432",
        txn2_date=date(2025, 1, 15),
        txn2_description="EXAMPLE UTILITY PMT",
        txn2_amount=-50.0,
        txn2_account="MYBANK_CHQ",
    )
    assessment = DuplicateAssessment(
        is_duplicate=True,
        confidence=0.9,
        reasoning="Same amount, same date, similar description",
    )
    return DuplicateMatch(pair=pair, assessment=assessment)


class DescribeRunReviewLoop:
    def it_should_process_matches_without_interactive_review_when_not_interactive(self):
        from gilt.cli.command.duplicates_review import run_review_loop

        ctx, buf = _make_review_ctx()
        match = _make_match()
        ctx.review_service.build_suggestion_event.return_value = (MagicMock(), "evt-001")

        run_review_loop(ctx, [match], ctx.review_service, ctx.detector, "model", interactive=False)

        ctx.review_service.build_suggestion_event.assert_called_once()

    def it_should_not_error_with_empty_matches(self):
        from gilt.cli.command.duplicates_review import run_review_loop

        ctx, buf = _make_review_ctx()
        run_review_loop(ctx, [], ctx.review_service, ctx.detector, "model", interactive=False)
        ctx.review_service.build_suggestion_event.assert_not_called()
