"""Auto-categorize transactions using rule inference and ML classifier.

Rules are tried first (deterministic, based on user history). ML is used
as a fallback for transactions that don't match any inferred rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.prompt import Prompt

from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.model.account import Transaction
from gilt.model.category_io import (
    build_category_from_path,
    format_category_path,
    load_categories_config,
)
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.workspace import Workspace

from ..console import console, display_transaction_matches, print_dry_run_message, print_error
from ..event_sourcing_bootstrap import require_event_sourcing
from ..filtering import find_uncategorized
from ..formatting import base_match_row, fmt_amount_str
from ..loaders import load_account_transactions
from ..mutations import persist_row_categorizations


@dataclass
class _TrainResult:
    exit_code: int | None
    ready: EventSourcingReadyResult | None = None
    classifier: object = None
    metrics: dict | None = None
    error_message: str | None = None


@dataclass
class _LoadResult:
    exit_code: int | None
    projection_builder: object = None
    uncategorized_txns: list = field(default_factory=list)
    limited_to: int | None = None


def _train_classifier(workspace, min_samples) -> _TrainResult:
    """Train the ML classifier. Returns a _TrainResult with exit_code=None on success."""
    ready = require_event_sourcing(workspace)
    if ready is None:
        return _TrainResult(exit_code=1)

    try:
        classifier = CategorizationClassifier(
            ready.event_store, min_samples_per_category=min_samples
        )
        metrics = classifier.train()
    except ValueError as e:
        return _TrainResult(exit_code=1, error_message=str(e))

    return _TrainResult(exit_code=None, ready=ready, classifier=classifier, metrics=metrics)


def _load_uncategorized(workspace, account, limit) -> _LoadResult:
    """Load uncategorized transactions. Returns a _LoadResult with exit_code=None on success."""
    all_rows = load_account_transactions(workspace, None)
    if all_rows is None:
        return _LoadResult(exit_code=1)

    uncategorized_rows = find_uncategorized(all_rows)
    if account:
        uncategorized_rows = [r for r in uncategorized_rows if r.get("account_id") == account]

    if not uncategorized_rows:
        return _LoadResult(exit_code=0)

    limited_to = None
    if limit and len(uncategorized_rows) > limit:
        uncategorized_rows = uncategorized_rows[:limit]
        limited_to = limit

    uncategorized_txns = [Transaction.from_projection_row(row) for row in uncategorized_rows]
    return _LoadResult(
        exit_code=None,
        projection_builder=None,
        uncategorized_txns=uncategorized_txns,
        limited_to=limited_to,
    )


def _write_categorizations(approved, ready, workspace) -> int:
    """Apply categorizations: emit events, update CSVs, rebuild projections. Returns updated count."""
    result = persist_row_categorizations(
        (
            (txn_id, account_id) + build_category_from_path(path) + (conf,)
            for account_id, txn_id, _, path, conf, _source in approved
        ),
        ready,
        workspace,
        source="llm",
    )
    return result.transactions_updated


def _apply_rules_first(workspace, uncategorized_txns):
    """Try rule inference on uncategorized transactions.

    Returns (rule_approved, remaining_txns) where rule_approved is a list of
    (account_id, txn_id, txn, category_path, confidence, source) tuples and
    remaining_txns are transactions not matched by any rule.
    """
    if not workspace.projections_path.exists():
        return [], uncategorized_txns

    service = RuleInferenceService(workspace.projections_path)
    rules = service.infer_rules(min_evidence=3, min_confidence=0.9)

    if not rules:
        return [], uncategorized_txns

    # Build projection-style dicts for apply_rules
    txn_dicts = [
        {
            "transaction_id": t.transaction_id,
            "canonical_description": t.description,
            "category": t.category,
            "account_id": t.account_id,
            "transaction_date": str(t.date),
            "amount": t.amount,
        }
        for t in uncategorized_txns
    ]

    matches = service.run_rules(txn_dicts, rules)
    matched_ids = {m.transaction["transaction_id"] for m in matches}

    rule_approved: list[tuple[str, str, Transaction, str, float, str]] = []
    txn_by_id = {t.transaction_id: t for t in uncategorized_txns}
    for m in matches:
        txn = txn_by_id[m.transaction["transaction_id"]]
        cat_path = format_category_path(m.rule.category, m.rule.subcategory)
        rule_approved.append(
            (txn.account_id, txn.transaction_id, txn, cat_path, m.rule.confidence, "rule")
        )

    remaining = [t for t in uncategorized_txns if t.transaction_id not in matched_ids]

    return rule_approved, remaining


def _predict_with_ml(
    classifier: CategorizationClassifier,
    remaining_txns: list[Transaction],
    confidence: float,
) -> list[tuple]:
    """Build transaction dicts, run ML classifier, and return predictions above the confidence threshold."""
    transaction_data = [
        {
            "transaction_id": t.transaction_id,
            "description": t.description,
            "amount": t.amount,
            "account": t.account_id,
            "date": str(t.date),
        }
        for t in remaining_txns
    ]

    predictions = classifier.predict(transaction_data, confidence_threshold=confidence)

    result: list[tuple] = []
    for txn, (category, conf) in zip(remaining_txns, predictions, strict=False):
        if category:
            result.append((txn.account_id, txn.transaction_id, txn, category, conf, "ml"))
    return result


def _print_explain(
    classifier: CategorizationClassifier,
    all_predictions: list[tuple],
) -> None:
    """Print top-3 category candidates for each prediction when --explain is active."""
    txn_data = [
        {
            "transaction_id": account_id,
            "description": txn.description,
            "amount": txn.amount,
            "account": account_id,
            "date": str(txn.date),
        }
        for account_id, _, txn, *_ in all_predictions
    ]

    topk_results = classifier.predict_topk(txn_data, k=3)

    console.print("\n[bold]Top-3 candidates (--explain)[/bold]")
    for (_account_id, _txn_id, txn, category, _conf, _source), topk in zip(
        all_predictions, topk_results, strict=False
    ):
        console.print(
            f"\n  [cyan]{txn.description[:45]}[/cyan]  "
            f"[dim]{str(txn.date)}[/dim]  [yellow]{fmt_amount_str(txn.amount)}[/yellow]"
        )
        for i, (cat, c) in enumerate(topk, 1):
            marker = "[green]→[/green]" if cat == category else " "
            console.print(f"    {marker} {i}. {cat:<40} {c:.1%}")
    console.print()


def _print_train_failure(train_result: _TrainResult, min_samples: int) -> None:
    if train_result.error_message:
        print_error(train_result.error_message)
        console.print(f"\nNeed at least {min_samples} categorized transactions per category.")
        console.print("Categorize more transactions first using:")
        console.print("  [cyan]gilt categorize --desc-prefix PATTERN --category CAT --write[/cyan]")


def _print_train_success(train_result: _TrainResult) -> None:
    console.print("[green]✓[/green] Classifier trained successfully")
    console.print(f"  Categories: {train_result.metrics['num_categories']}")
    console.print(f"  Training samples: {train_result.metrics['total_samples']}")
    console.print(f"  Test accuracy: {train_result.metrics['test_accuracy']:.1%}")


def run(
    *,
    account: str | None = None,
    confidence: float = 0.7,
    min_samples: int = 5,
    interactive: bool = False,
    limit: int | None = None,
    explain: bool = False,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Auto-categorize uncategorized transactions using rules then ML."""
    console.print("[dim]Loading categorization history...[/dim]")
    train_result = _train_classifier(workspace, min_samples)
    if train_result.exit_code is not None:
        _print_train_failure(train_result, min_samples)
        return train_result.exit_code
    ready = train_result.ready
    classifier = train_result.classifier
    _print_train_success(train_result)

    category_config = load_categories_config(workspace.categories_config)

    console.print("\n[dim]Loading uncategorized transactions...[/dim]")
    load_result = _load_uncategorized(workspace, account, limit)
    if load_result.exit_code is not None:
        if load_result.exit_code == 0:
            console.print("[green]✓[/green] No uncategorized transactions found")
        return load_result.exit_code
    if load_result.limited_to:
        console.print(f"[dim]Limited to first {load_result.limited_to} transactions[/dim]")
    console.print(f"Found {len(load_result.uncategorized_txns)} uncategorized transaction(s)")
    uncategorized_txns = load_result.uncategorized_txns

    # Phase 1: Apply inferred rules (deterministic, high confidence)
    rule_approved, remaining_txns = _apply_rules_first(workspace, uncategorized_txns)
    if rule_approved:
        console.print(
            f"[green]{len(rule_approved)}[/green] transaction(s) matched by inferred rules"
        )

    # Phase 2: ML predictions for remaining uncategorized
    ml_predictions: list[tuple] = []
    if remaining_txns:
        console.print(f"\n[dim]Predicting categories (threshold: {confidence:.1%})...[/dim]")
        ml_predictions = _predict_with_ml(classifier, remaining_txns, confidence)
        if ml_predictions:
            console.print(f"[green]{len(ml_predictions)}[/green] ML predictions")

    # Combine results
    all_predictions = rule_approved + ml_predictions

    if not all_predictions:
        console.print(
            f"[yellow]No predictions above {confidence:.1%} confidence threshold[/yellow]"
        )
        console.print("\nTry:")
        console.print("  - Lowering threshold: [cyan]--confidence 0.5[/cyan]")
        console.print("  - Categorizing more transactions to improve training")
        return 0

    return _review_and_persist(
        all_predictions, category_config, workspace, ready, write, interactive, explain, classifier
    )


def _review_and_persist(
    all_predictions: list,
    category_config,
    workspace: Workspace,
    ready,
    write: bool,
    interactive: bool,
    explain: bool = False,
    classifier: CategorizationClassifier | None = None,
) -> int:
    """Run interactive or batch review, then persist approved categorizations."""
    if interactive:
        approved = _interactive_review(all_predictions, category_config)
    else:
        approved = all_predictions
        _display_predictions(all_predictions)

    if explain and classifier is not None:
        _print_explain(classifier, all_predictions)

    if not approved:
        console.print("\n[yellow]No predictions approved[/yellow]")
        return 0

    if not write:
        print_dry_run_message(detail=f"{len(approved)} transaction(s)")
        return 0

    console.print("\n[dim]Applying categorizations...[/dim]")
    count = _write_categorizations(approved, ready, workspace)
    console.print(f"[green]✓[/green] Categorized {count} transaction(s)")
    return 0


def _display_predictions(predictions: list[tuple[str, str, dict, str, float, str]]) -> None:
    """Display predictions in a table.

    Args:
        predictions: List of (account_id, transaction_id, txn, category, confidence, source)
    """

    def row_fn(item: tuple) -> tuple:
        account_id, _, txn, category, conf, source = item
        return base_match_row(account_id, txn) + (category, f"{conf:.1%}", source)

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


def _handle_modify_choice(category_config, default_category: str) -> str | None:
    """Prompt user for a new category and validate it. Returns category string or None if invalid."""
    console.print("\n[dim]Available categories:[/dim]")
    for cat in category_config.categories:
        console.print(f"  - {cat.name}")
        if cat.subcategories:
            for subcat in cat.subcategories:
                console.print(f"    - {cat.name}:{subcat.name}")

    new_category = Prompt.ask(
        "\nEnter category (Category or Category:Subcategory)",
        default=default_category,
    )

    cat_name, subcat_name = build_category_from_path(new_category)
    cat_obj = next((c for c in category_config.categories if c.name == cat_name), None)

    if not cat_obj:
        print_error(f"Invalid category: {cat_name}")
        return None

    if subcat_name:
        subcat_obj = next((s for s in (cat_obj.subcategories or []) if s.name == subcat_name), None)
        if not subcat_obj:
            print_error(f"Invalid subcategory: {subcat_name}")
            return None

    return new_category


def _display_transaction_for_review(
    console,
    i: int,
    total: int,
    account_id: str,
    txn: Transaction,
    category: str,
    conf: float,
) -> None:
    """Print a single transaction with its ML-suggested category for interactive review."""
    console.print(f"\n[bold cyan]Transaction {i}/{total}[/bold cyan]")
    console.print(f"  Account:     {account_id}")
    console.print(f"  Date:        {txn.date}")
    console.print(f"  Description: {txn.description}")
    console.print(f"  Amount:      {fmt_amount_str(txn.amount)}")
    console.print(f"  Suggested:   [green]{category}[/green] ([blue]{conf:.1%}[/blue] confident)")


def _interactive_review(
    predictions: list[tuple[str, str, Transaction, str, float, str]],
    category_config,
) -> list[tuple[str, str, Transaction, str, float, str]]:
    """Interactive review mode - approve, reject, or modify predictions.

    Args:
        predictions: List of (account_id, transaction_id, Transaction, category, confidence, source)
        category_config: Category configuration

    Returns:
        List of approved predictions (may have modified categories)
    """
    console.print("\n[bold]Interactive Review Mode[/bold]")
    console.print("[dim]For each prediction: (a)pprove, (r)eject, (m)odify, (q)uit[/dim]\n")

    approved: list[tuple[str, str, Transaction, str, float, str]] = []

    for i, (account_id, txn_id, txn, category, conf, source) in enumerate(predictions, 1):
        # Display transaction
        _display_transaction_for_review(
            console, i, len(predictions), account_id, txn, category, conf
        )

        # Get user decision
        while True:
            choice = Prompt.ask(
                "\nAction",
                choices=["a", "r", "m", "q"],
                default="a",
            ).lower()

            if choice == "a":
                # Approve
                approved.append((account_id, txn_id, txn, category, conf, source))
                console.print("[green]✓ Approved[/green]")
                break

            elif choice == "r":
                # Reject
                console.print("[yellow]✗ Rejected[/yellow]")
                break

            elif choice == "m":
                new_category = _handle_modify_choice(category_config, category)
                if new_category is None:
                    continue
                approved.append((account_id, txn_id, txn, new_category, conf, source))
                console.print(f"[green]✓ Modified to {new_category}[/green]")
                break

            elif choice == "q":
                # Quit
                console.print("\n[yellow]Review interrupted[/yellow]")
                return approved

    console.print(f"\n[green]Review complete: {len(approved)}/{len(predictions)} approved[/green]")
    return approved


__all__ = ["run"]
