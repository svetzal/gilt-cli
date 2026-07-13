"""Specs for auto_categorize_review.py — interactive review for the auto-categorize command."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch


def _make_transaction(account_id="MYBANK_CHQ", amount=-50.0, category=None):
    from gilt.model.account import Transaction

    return Transaction(
        transaction_id="abcd1234efgh5678",
        date=date(2025, 6, 1),
        description="EXAMPLE UTILITY PAYMENT",
        amount=amount,
        currency="CAD",
        account_id=account_id,
        category=category,
        subcategory=None,
    )


def _make_prediction(category="Utilities"):
    from gilt.cli.command.auto_categorize import Prediction

    return Prediction(
        account_id="MYBANK_CHQ",
        transaction_id="abcd1234efgh5678",
        txn=_make_transaction(),
        category=category,
        confidence=0.9,
        source="ml",
    )


def _make_category_config():
    from gilt.model.category import Category, CategoryConfig, Subcategory

    return CategoryConfig(
        categories=[
            Category(
                name="Utilities",
                subcategories=[Subcategory(name="Internet")],
            )
        ]
    )


class DescribeHandleModifyChoice:
    def it_should_return_none_for_invalid_category(self):
        from gilt.cli.command.auto_categorize_review import handle_modify_choice

        config = _make_category_config()
        with patch(
            "gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="NonExistent"
        ):
            result = handle_modify_choice(config, "Utilities")
        assert result is None

    def it_should_return_category_string_for_valid_category(self):
        from gilt.cli.command.auto_categorize_review import handle_modify_choice

        config = _make_category_config()
        with patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="Utilities"):
            result = handle_modify_choice(config, "Utilities")
        assert result == "Utilities"


class DescribeRunInteractiveReview:
    def it_should_return_approved_predictions_when_user_approves(self):
        from gilt.cli.command.auto_categorize_review import run_interactive_review

        config = _make_category_config()
        predictions = [_make_prediction()]

        with (
            patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="a"),
            patch("gilt.cli.command.auto_categorize_view.display_transaction_for_review"),
        ):
            approved = run_interactive_review(predictions, config)

        assert len(approved) == 1

    def it_should_return_empty_list_when_user_rejects_all(self):
        from gilt.cli.command.auto_categorize_review import run_interactive_review

        config = _make_category_config()
        predictions = [_make_prediction()]

        with (
            patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="r"),
            patch("gilt.cli.command.auto_categorize_view.display_transaction_for_review"),
        ):
            approved = run_interactive_review(predictions, config)

        assert len(approved) == 0
