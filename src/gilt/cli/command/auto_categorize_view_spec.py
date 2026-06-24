"""Specs for auto_categorize_view — Rich rendering functions."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console

from gilt.cli.command.auto_categorize import Prediction, _TrainResult
from gilt.cli.command.auto_categorize_view import (
    display_transaction_for_review,
    print_train_failure,
    print_train_success,
)
from gilt.model.account import Transaction


def _make_transaction(
    txn_id: str = "abcd1234abcd1234",
    description: str = "EXAMPLE UTILITY",
    amount: float = -42.50,
    account_id: str = "MYBANK_CHQ",
) -> Transaction:
    return Transaction(
        transaction_id=txn_id,
        date=date(2025, 1, 15),
        description=description,
        amount=amount,
        currency="CAD",
        account_id=account_id,
    )


def _make_prediction(
    txn_id: str = "abcd1234abcd1234",
    category: str = "Utilities",
    confidence: float = 0.90,
    source: str = "ml",
) -> Prediction:
    txn = _make_transaction(txn_id=txn_id)
    return Prediction(
        account_id="MYBANK_CHQ",
        transaction_id=txn_id,
        txn=txn,
        category=category,
        confidence=confidence,
        source=source,
    )


def _capture(fn) -> str:
    """Run fn() and capture console output to a string."""
    buf = StringIO()
    import gilt.cli.command.auto_categorize_view as view_mod

    old_console = view_mod.console
    view_mod.console = Console(file=buf, highlight=False)
    try:
        fn()
    finally:
        view_mod.console = old_console
    return buf.getvalue()


class DescribeDisplayTransactionForReview:
    def it_should_print_account_date_description_amount_and_category(self):
        txn = _make_transaction(description="ACME CORP BILL", amount=-99.00, account_id="MYBANK_CC")
        output = _capture(
            lambda: display_transaction_for_review(
                i=1,
                total=3,
                account_id="MYBANK_CC",
                txn=txn,
                category="Utilities",
                conf=0.88,
            )
        )

        assert "Transaction 1/3" in output
        assert "MYBANK_CC" in output
        assert "ACME CORP BILL" in output
        assert "-99.00" in output
        assert "Utilities" in output
        assert "88.0%" in output

    def it_should_include_transaction_index_and_total(self):
        txn = _make_transaction()
        output = _capture(
            lambda: display_transaction_for_review(
                i=5,
                total=10,
                account_id="MYBANK_CHQ",
                txn=txn,
                category="Shopping",
                conf=0.75,
            )
        )

        assert "5/10" in output


class DescribePrintTrainSuccess:
    def it_should_print_classifier_metrics(self):
        train_result = _TrainResult(
            exit_code=None,
            metrics={"num_categories": 5, "total_samples": 120, "test_accuracy": 0.92},
        )
        output = _capture(lambda: print_train_success(train_result))

        assert "trained successfully" in output.lower() or "Classifier" in output
        assert "5" in output
        assert "120" in output
        assert "92.0%" in output


class DescribePrintTrainFailure:
    def it_should_print_guidance_text_when_error_present(self):
        """Guidance lines (min_samples hint and remedy command) go to the main console."""
        train_result = _TrainResult(
            exit_code=1,
            error_message="Not enough samples to train",
        )
        output = _capture(lambda: print_train_failure(train_result, min_samples=5))

        # Guidance text is written to console (captured); error message goes to print_error
        assert "5" in output
        assert "gilt categorize" in output

    def it_should_print_nothing_when_error_message_is_absent(self):
        train_result = _TrainResult(exit_code=1, error_message=None)
        output = _capture(lambda: print_train_failure(train_result, min_samples=5))

        assert output.strip() == ""
