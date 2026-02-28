"""Auto-categorize transactions using ML classifier."""

from __future__ import annotations

from rich.prompt import Prompt
from rich.table import Table

from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.model.account import Transaction
from gilt.model.category_io import load_categories_config, parse_category_path
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.services.categorization_service import CategorizationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console


def _train_classifier(workspace, min_samples):
    """Train the ML classifier. Returns (event_store, classifier) or exit code."""
    event_sourcing_service = EventSourcingService(workspace=workspace)
    event_store_status = event_sourcing_service.check_event_store_status(workspace.ledger_data_dir)

    if not event_store_status.exists:
        console.print("[red]Error:[/red] Event store not found.")
        console.print("\nAuto-categorization requires event sourcing to be initialized.")
        console.print("Run this command first:")
        console.print("  [cyan]gilt migrate-to-events --write[/cyan]")
        return 1

    console.print("[dim]Loading categorization history...[/dim]")
    event_store = event_sourcing_service.get_event_store()

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
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return 1

    console.print("\n[dim]Loading uncategorized transactions...[/dim]")
    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    uncategorized_rows = [
        row for row in all_transactions
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


def _write_categorizations(approved, workspace, category_config, event_store, projection_builder):
    """Apply categorizations and write back to CSV files."""
    console.print("\n[dim]Applying categorizations...[/dim]")
    categorization_service = CategorizationService(category_config, event_store=event_store)

    by_account: dict[str, list[tuple[str, str]]] = {}
    for account_id, txn_id, _, category, _ in approved:
        by_account.setdefault(account_id, []).append((txn_id, category))

    for account_id, items in by_account.items():
        ledger_path = workspace.ledger_data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            console.print(f"[yellow]Warning: Ledger not found for {account_id}[/yellow]")
            continue

        text = ledger_path.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")

        updates = {}
        for txn_id, category_path in items:
            cat_name, subcat_name = parse_category_path(category_path)
            updates[txn_id] = (cat_name, subcat_name)

        for i, g in enumerate(groups):
            if g.primary.transaction_id in updates:
                cat_name, subcat_name = updates[g.primary.transaction_id]
                result = categorization_service.apply_categorization([g], cat_name, subcat_name)
                groups[i] = result.updated_transactions[0]

        updated_csv = dump_ledger_csv(groups)
        ledger_path.write_text(updated_csv, encoding="utf-8")

    console.print("\n[dim]Updating projections...[/dim]")
    projection_builder.rebuild_incremental(event_store)
    console.print(f"[green]✓[/green] Categorized {len(approved)} transaction(s)")


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
    """Auto-categorize uncategorized transactions using ML classifier."""
    train_result = _train_classifier(workspace, min_samples)
    if isinstance(train_result, int):
        return train_result
    event_store, classifier = train_result

    category_config = load_categories_config(workspace.categories_config)

    load_result = _load_uncategorized(workspace, account, limit)
    if isinstance(load_result, int):
        return load_result
    projection_builder, uncategorized_txns = load_result

    transaction_data = [
        {"transaction_id": t.transaction_id, "description": t.description,
         "amount": t.amount, "account": t.account_id, "date": str(t.date)}
        for t in uncategorized_txns
    ]

    console.print(f"\n[dim]Predicting categories (threshold: {confidence:.1%})...[/dim]")
    predictions = classifier.predict(transaction_data, confidence_threshold=confidence)

    confident_predictions: list[tuple[str, str, Transaction, str, float]] = []
    for txn, (category, conf) in zip(uncategorized_txns, predictions, strict=False):
        if category:
            confident_predictions.append((txn.account_id, txn.transaction_id, txn, category, conf))

    if not confident_predictions:
        console.print(f"[yellow]No predictions above {confidence:.1%} confidence threshold[/yellow]")
        console.print("\nTry:")
        console.print("  - Lowering threshold: [cyan]--confidence 0.5[/cyan]")
        console.print("  - Categorizing more transactions to improve training")
        return 0

    console.print(f"[green]{len(confident_predictions)}[/green] confident predictions")

    if interactive:
        approved = _interactive_review(confident_predictions, category_config)
    else:
        approved = confident_predictions
        _display_predictions(confident_predictions)

    if not approved:
        console.print("\n[yellow]No predictions approved[/yellow]")
        return 0

    if not write:
        console.print(f"\n[dim]Dry-run: {len(approved)} transaction(s) would be categorized[/dim]")
        console.print("[dim]Use --write to persist changes[/dim]")
        return 0

    _write_categorizations(approved, workspace, category_config, event_store, projection_builder)
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
            f"${txn.amount:,.2f}",
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
        subcat_obj = next(
            (s for s in (cat_obj.subcategories or []) if s.name == subcat_name), None
        )
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
