"""Rich rendering functions for the auto-categorize command.

All functions in this module perform console output only — no I/O,
no user prompts, no business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gilt.model.account import Transaction

from ..console import console, display_transaction_matches
from ..formatting import base_match_row, fmt_amount_str

if TYPE_CHECKING:
    from gilt.ml.categorization_classifier import CategorizationClassifier

    from .auto_categorize import Prediction, _TrainResult


def display_predictions(predictions: list[Prediction]) -> None:
    """Display predictions in a Rich table."""

    def row_fn(item: Prediction) -> tuple:
        return base_match_row(item.account_id, item.txn) + (
            item.category,
            f"{item.confidence:.1%}",
            item.source,
        )

    console.print("\n")
    display_transaction_matches(
        "Auto-Categorization Predictions",
        [
            ("→ Category", {"style": "green"}),
            ("Confidence", {"style": "blue", "justify": "right"}),
            ("Source", {"style": "dim"}),
        ],
        predictions,
        row_fn,
    )


def print_explain(
    classifier: CategorizationClassifier,
    all_predictions: list[Prediction],
) -> None:
    """Print top-3 category candidates for each prediction when --explain is active."""
    txn_data = [
        {
            "transaction_id": p.account_id,
            "description": p.txn.description,
            "amount": p.txn.amount,
            "account": p.account_id,
            "date": str(p.txn.date),
        }
        for p in all_predictions
    ]

    topk_results = classifier.predict_topk(txn_data, k=3)

    console.print("\n[bold]Top-3 candidates (--explain)[/bold]")
    for p, topk in zip(all_predictions, topk_results, strict=False):
        console.print(
            f"\n  [cyan]{p.txn.description[:45]}[/cyan]  "
            f"[dim]{str(p.txn.date)}[/dim]  [yellow]{fmt_amount_str(p.txn.amount)}[/yellow]"
        )
        for i, (cat, c) in enumerate(topk, 1):
            marker = "[green]→[/green]" if cat == p.category else " "
            console.print(f"    {marker} {i}. {cat:<40} {c:.1%}")
    console.print()


def print_train_failure(train_result: _TrainResult, min_samples: int) -> None:
    """Print training failure message with corrective guidance."""
    from ..console import print_error

    if train_result.error_message:
        print_error(train_result.error_message)
        console.print(f"\nNeed at least {min_samples} categorized transactions per category.")
        console.print("Categorize more transactions first using:")
        console.print("  [cyan]gilt categorize --desc-prefix PATTERN --category CAT --write[/cyan]")


def print_train_success(train_result: _TrainResult) -> None:
    """Print classifier training success metrics."""
    console.print("[green]✓[/green] Classifier trained successfully")
    console.print(f"  Categories: {train_result.metrics['num_categories']}")
    console.print(f"  Training samples: {train_result.metrics['total_samples']}")
    console.print(f"  Test accuracy: {train_result.metrics['test_accuracy']:.1%}")


def display_transaction_for_review(
    i: int,
    total: int,
    account_id: str,
    txn: Transaction,
    category: str,
    conf: float,
) -> None:
    """Print a single transaction with its suggested category for interactive review."""
    console.print(f"\n[bold cyan]Transaction {i}/{total}[/bold cyan]")
    console.print(f"  Account:     {account_id}")
    console.print(f"  Date:        {txn.date}")
    console.print(f"  Description: {txn.description}")
    console.print(f"  Amount:      {fmt_amount_str(txn.amount)}")
    console.print(f"  Suggested:   [green]{category}[/green] ([blue]{conf:.1%}[/blue] confident)")


__all__ = [
    "display_predictions",
    "print_explain",
    "print_train_failure",
    "print_train_success",
    "display_transaction_for_review",
]
