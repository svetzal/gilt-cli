"""Auto-categorize transactions using rule inference and ML classifier.

Rules are tried first (deterministic, based on user history). ML is used
as a fallback for transactions that don't match any inferred rule.
"""

from __future__ import annotations

from rich.prompt import Prompt
from rich.table import Table

from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.model.account import Transaction
from gilt.model.category_io import load_categories_config, parse_category_path
from gilt.services.categorization_persistence_service import CategorizationUpdate
from gilt.services.rule_inference_service import RuleInferenceService
from gilt.workspace import Workspace

from .util import (
    console,
    fmt_amount_str,
    print_dry_run_message,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
)


def _train_classifier(workspace, min_samples):
    """Train the ML classifier. Returns (event_store, classifier) or exit code."""
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    console.print("[dim]Loading categorization history...[/dim]")
    event_store = ready.event_store

    try:
        classifier = CategorizationClassifier(event_store, min_samples_per_category=min_samples)
        metrics = classifier.train()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print(f"\nNeed at least {min_samples} categorized transactions per category.")
        console.print("Categorize more transactions first using:")
        console.print("  [cyan]gilt categorize --desc-prefix PATTERN --category CAT --write[/cyan]")
        return 1

    console.print("[green]✓[/green] Classifier trained successfully")
    console.print(f"  Categories: {metrics['num_categories']}")
    console.print(f"  Training samples: {metrics['total_samples']}")
    console.print(f"  Test accuracy: {metrics['test_accuracy']:.1%}")

    return event_store, classifier


def _load_uncategorized(workspace, account, limit):
    """Load uncategorized transactions. Returns (projection_builder, txns) or exit code."""
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    console.print("\n[dim]Loading uncategorized transactions...[/dim]")
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    uncategorized_rows = [
        row
        for row in all_transactions
        if row.get("category") is None and (account is None or row.get("account_id") == account)
    ]

    if not uncategorized_rows:
        console.print("[green]✓[/green] No uncategorized transactions found")
        return 0

    if limit and len(uncategorized_rows) > limit:
        uncategorized_rows = uncategorized_rows[:limit]
        console.print(f"[dim]Limited to first {limit} transactions[/dim]")

    console.print(f"Found {len(uncategorized_rows)} uncategorized transaction(s)")

    uncategorized_txns = [Transaction.from_projection_row(row) for row in uncategorized_rows]
    return projection_builder, uncategorized_txns


def _write_categorizations(approved, workspace, event_store, projection_builder):
    """Apply categorizations: emit events, update CSVs, rebuild projections."""
    console.print("\n[dim]Applying categorizations...[/dim]")

    persistence_svc = require_persistence_service(event_store, projection_builder, workspace)
    updates = []
    for account_id, txn_id, _, category_path, confidence in approved:
        cat_name, subcat_name = parse_category_path(category_path)
        updates.append(
            CategorizationUpdate(
                transaction_id=txn_id,
                account_id=account_id,
                category=cat_name,
                subcategory=subcat_name,
                source="llm",
                confidence=confidence,
            )
        )

    result = persistence_svc.persist_categorizations(updates)
    console.print(f"[green]✓[/green] Categorized {result.transactions_updated} transaction(s)")


def _apply_rules_first(workspace, uncategorized_txns):
    """Try rule inference on uncategorized transactions.

    Returns (rule_approved, remaining_txns) where rule_approved is a list of
    (account_id, txn_id, txn, category_path, confidence) tuples and
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

    matches = service.apply_rules(txn_dicts, rules)
    matched_ids = {m.transaction["transaction_id"] for m in matches}

    rule_approved: list[tuple[str, str, Transaction, str, float]] = []
    txn_by_id = {t.transaction_id: t for t in uncategorized_txns}
    for m in matches:
        txn = txn_by_id[m.transaction["transaction_id"]]
        cat_path = m.rule.category
        if m.rule.subcategory:
            cat_path = f"{m.rule.category}:{m.rule.subcategory}"
        rule_approved.append((txn.account_id, txn.transaction_id, txn, cat_path, m.rule.confidence))

    remaining = [t for t in uncategorized_txns if t.transaction_id not in matched_ids]

    if rule_approved:
        console.print(
            f"[green]{len(rule_approved)}[/green] transaction(s) matched by inferred rules"
        )

    return rule_approved, remaining


def run(
    *,
    account: str | None = None,
    confidence: float = 0.7,
    min_samples: int = 5,
    interactive: bool = False,
    limit: int | None = None,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Auto-categorize uncategorized transactions using rules then ML."""
    train_result = _train_classifier(workspace, min_samples)
    if isinstance(train_result, int):
        return train_result
    event_store, classifier = train_result

    category_config = load_categories_config(workspace.categories_config)

    load_result = _load_uncategorized(workspace, account, limit)
    if isinstance(load_result, int):
        return load_result
    projection_builder, uncategorized_txns = load_result

    # Phase 1: Apply inferred rules (deterministic, high confidence)
    rule_approved, remaining_txns = _apply_rules_first(workspace, uncategorized_txns)

    # Phase 2: ML predictions for remaining uncategorized
    ml_predictions: list[tuple[str, str, Transaction, str, float]] = []
    if remaining_txns:
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

        console.print(f"\n[dim]Predicting categories (threshold: {confidence:.1%})...[/dim]")
        predictions = classifier.predict(transaction_data, confidence_threshold=confidence)

        for txn, (category, conf) in zip(remaining_txns, predictions, strict=False):
            if category:
                ml_predictions.append((txn.account_id, txn.transaction_id, txn, category, conf))

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

    if interactive:
        approved = _interactive_review(all_predictions, category_config)
    else:
        approved = all_predictions
        _display_predictions(all_predictions)

    if not approved:
        console.print("\n[yellow]No predictions approved[/yellow]")
        return 0

    if not write:
        print_dry_run_message(detail=f"{len(approved)} transaction(s)")
        return 0

    _write_categorizations(approved, workspace, event_store, projection_builder)
    return 0


def _display_predictions(predictions: list[tuple[str, str, dict, str, float]]) -> None:
    """Display predictions in a table.

    Args:
        predictions: List of (account_id, transaction_id, row_dict, category, confidence)
    """
    table = Table(title="Auto-Categorization Predictions", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("Date", style="dim")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("→ Category", style="green")
    table.add_column("Confidence", style="blue", justify="right")

    for account_id, _, txn, category, conf in predictions:
        table.add_row(
            account_id,
            str(txn.date),
            txn.description[:50],
            fmt_amount_str(txn.amount),
            category,
            f"{conf:.1%}",
        )

    console.print("\n")
    console.print(table)


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

    cat_name, subcat_name = parse_category_path(new_category)
    cat_obj = next((c for c in category_config.categories if c.name == cat_name), None)

    if not cat_obj:
        console.print(f"[red]Invalid category: {cat_name}[/red]")
        return None

    if subcat_name:
        subcat_obj = next((s for s in (cat_obj.subcategories or []) if s.name == subcat_name), None)
        if not subcat_obj:
            console.print(f"[red]Invalid subcategory: {subcat_name}[/red]")
            return None

    return new_category


def _interactive_review(
    predictions: list[tuple[str, str, Transaction, str, float]],
    category_config,
) -> list[tuple[str, str, Transaction, str, float]]:
    """Interactive review mode - approve, reject, or modify predictions.

    Args:
        predictions: List of (account_id, transaction_id, Transaction, category, confidence)
        category_config: Category configuration

    Returns:
        List of approved predictions (may have modified categories)
    """
    console.print("\n[bold]Interactive Review Mode[/bold]")
    console.print("[dim]For each prediction: (a)pprove, (r)eject, (m)odify, (q)uit[/dim]\n")

    approved: list[tuple[str, str, Transaction, str, float]] = []

    for i, (account_id, txn_id, txn, category, conf) in enumerate(predictions, 1):
        # Display transaction
        console.print(f"\n[bold cyan]Transaction {i}/{len(predictions)}[/bold cyan]")
        console.print(f"  Account:     {account_id}")
        console.print(f"  Date:        {txn.date}")
        console.print(f"  Description: {txn.description}")
        console.print(f"  Amount:      ${txn.amount:,.2f}")
        console.print(
            f"  Suggested:   [green]{category}[/green] ([blue]{conf:.1%}[/blue] confident)"
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
                approved.append((account_id, txn_id, txn, category, conf))
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
                approved.append((account_id, txn_id, txn, new_category, conf))
                console.print(f"[green]✓ Modified to {new_category}[/green]")
                break

            elif choice == "q":
                # Quit
                console.print("\n[yellow]Review interrupted[/yellow]")
                return approved

    console.print(f"\n[green]Review complete: {len(approved)}/{len(predictions)} approved[/green]")
    return approved


__all__ = ["run"]
