"""
CLI command to audit ML classifier decisions and training data.

Provides visibility into:
- Training data used by ML classifier
- Feature importance
- Predictions on current candidates
- Past user decisions that shaped the model
"""


from rich.console import Console
from rich.table import Table

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.ml.duplicate_classifier import DuplicateClassifier
from gilt.ml.training_data_builder import TrainingDataBuilder
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.workspace import Workspace


def run(
    workspace: Workspace,
    mode: str = "summary",
    filter_pattern: str | None = None,
    limit: int = 20,
) -> int:
    """Audit ML classifier training data and decisions.

    Args:
        workspace: Workspace for resolving data paths
        mode: Audit mode - "summary", "training", "predictions", or "features"
        filter_pattern: Optional regex pattern to filter descriptions
        limit: Maximum number of examples to show (default 20)

    Returns:
        Exit code (0 = success)
    """
    console = Console()

    # Initialize services
    es_service = EventSourcingService(workspace=workspace)

    if not es_service.event_store_path.exists():
        console.print("[red]Error:[/red] Event store not found")
        console.print("Run 'gilt migrate-to-events --write' first")
        return 1

    event_store = es_service.get_event_store()
    builder = TrainingDataBuilder(event_store)

    if mode == "summary":
        return show_summary(console, builder)
    elif mode == "training":
        return show_training_data(console, builder, filter_pattern, limit)
    elif mode == "predictions":
        return show_predictions(console, workspace, es_service, filter_pattern, limit)
    elif mode == "features":
        return show_features(console, builder)
    else:
        console.print(f"[red]Error:[/red] Unknown mode '{mode}'")
        console.print("Valid modes: summary, training, predictions, features")
        return 1


def show_summary(console: Console, builder: TrainingDataBuilder) -> int:
    """Show summary statistics of training data."""
    stats = builder.get_statistics()

    console.print("\n[cyan]ML Classifier Training Data Summary[/cyan]\n")

    summary_table = Table(show_header=False)
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", style="bold")

    summary_table.add_row("Total training examples", str(stats["total_examples"]))
    summary_table.add_row("Positive examples (duplicates)", str(stats["positive_examples"]))
    summary_table.add_row("Negative examples (not duplicates)", str(stats["negative_examples"]))
    summary_table.add_row("Class balance", f"{stats['class_balance']:.1%} positive")
    summary_table.add_row(
        "Sufficient for training",
        "[green]Yes[/green]"
        if stats["sufficient_for_training"]
        else "[yellow]No (need 10+)[/yellow]",
    )

    console.print(summary_table)

    if stats["total_examples"] > 0:
        console.print("\n[dim]Use 'gilt audit-ml --mode training' to see examples[/dim]")
        console.print("[dim]Use 'gilt audit-ml --mode features' to see feature importance[/dim]")
        console.print("[dim]Use 'gilt audit-ml --mode predictions' to test on current data[/dim]")

    return 0


def show_training_data(
    console: Console, builder: TrainingDataBuilder, filter_pattern: str | None, limit: int
) -> int:
    """Show training examples used to train the classifier."""
    import re

    pairs, labels = builder.load_from_events()

    if len(pairs) == 0:
        console.print("[yellow]No training data available[/yellow]")
        return 0

    # Apply filter if provided
    if filter_pattern:
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        filtered = [
            (p, lab)
            for p, lab in zip(pairs, labels, strict=False)
            if pattern.search(p.txn1_description) or pattern.search(p.txn2_description)
        ]
        pairs, labels = zip(*filtered, strict=False) if filtered else ([], [])
        console.print(
            f"\n[cyan]Filtered to {len(pairs)} examples matching '{filter_pattern}'[/cyan]\n"
        )

    # Show positive examples
    positive_pairs = [(p, lab) for p, lab in zip(pairs, labels, strict=False) if lab]
    if positive_pairs:
        console.print(
            f"[green]Positive Examples (Marked as Duplicates) - Showing {min(limit, len(positive_pairs))} of {len(positive_pairs)}[/green]\n"
        )

        for i, (pair, _) in enumerate(positive_pairs[:limit]):
            table = Table(show_header=True, header_style="bold green")
            table.add_column("Field", style="dim")
            table.add_column("Transaction 1")
            table.add_column("Transaction 2")

            table.add_row("Description", pair.txn1_description, pair.txn2_description)
            table.add_row("Date", str(pair.txn1_date), str(pair.txn2_date))
            table.add_row("Amount", f"${pair.txn1_amount:.2f}", f"${pair.txn2_amount:.2f}")
            table.add_row("Account", pair.txn1_account, pair.txn2_account)

            console.print(f"\n[dim]Example {i + 1}[/dim]")
            console.print(table)

    # Show negative examples
    negative_pairs = [(p, lab) for p, lab in zip(pairs, labels, strict=False) if not lab]
    if negative_pairs:
        console.print(
            f"\n[yellow]Negative Examples (Marked as NOT Duplicates) - Showing {min(limit, len(negative_pairs))} of {len(negative_pairs)}[/yellow]\n"
        )

        for i, (pair, _) in enumerate(negative_pairs[:limit]):
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("Field", style="dim")
            table.add_column("Transaction 1")
            table.add_column("Transaction 2")

            table.add_row("Description", pair.txn1_description, pair.txn2_description)
            table.add_row("Date", str(pair.txn1_date), str(pair.txn2_date))
            table.add_row("Amount", f"${pair.txn1_amount:.2f}", f"${pair.txn2_amount:.2f}")
            table.add_row("Account", pair.txn1_account, pair.txn2_account)

            console.print(f"\n[dim]Example {i + 1}[/dim]")
            console.print(table)

    return 0


def show_predictions(
    console: Console,
    workspace: Workspace,
    es_service: EventSourcingService,
    filter_pattern: str | None,
    limit: int,
) -> int:
    """Show ML predictions on current candidate pairs."""
    import re

    data_dir = workspace.ledger_data_dir

    # Initialize detector with ML
    detector = DuplicateDetector(
        model=DEFAULT_OLLAMA_MODEL,
        event_store_path=workspace.event_store_path,
        use_ml=True,
    )

    if not detector._ml_classifier:
        console.print("[yellow]ML classifier not available (insufficient training data)[/yellow]")
        return 0

    # Load transactions and find candidates
    console.print("\n[cyan]Loading transactions and finding candidates...[/cyan]")
    transactions = detector.load_all_transactions(data_dir)
    candidates = detector.find_potential_duplicates(transactions)

    # Apply filter if provided
    if filter_pattern:
        pattern = re.compile(filter_pattern, re.IGNORECASE)
        candidates = [
            p
            for p in candidates
            if pattern.search(p.txn1_description) or pattern.search(p.txn2_description)
        ]
        console.print(
            f"[dim]Filtered to {len(candidates)} candidates matching '{filter_pattern}'[/dim]\n"
        )
    else:
        console.print(f"[dim]Found {len(candidates)} candidate pairs[/dim]\n")

    if len(candidates) == 0:
        console.print("[yellow]No candidates found[/yellow]")
        return 0

    # Analyze and show predictions
    console.print(
        f"[cyan]ML Predictions - Showing {min(limit, len(candidates))} of {len(candidates)}[/cyan]\n"
    )

    for i, pair in enumerate(candidates[:limit]):
        assessment = detector.assess_duplicate(pair)

        # Color based on prediction
        if assessment.is_duplicate:
            style = "green"
            prediction = "✓ DUPLICATE"
        else:
            style = "yellow"
            prediction = "✗ NOT DUPLICATE"

        table = Table(show_header=True, header_style=f"bold {style}")
        table.add_column("Field", style="dim")
        table.add_column("Transaction 1")
        table.add_column("Transaction 2")

        table.add_row("Description", pair.txn1_description, pair.txn2_description)
        table.add_row("Date", str(pair.txn1_date), str(pair.txn2_date))
        table.add_row("Amount", f"${pair.txn1_amount:.2f}", f"${pair.txn2_amount:.2f}")
        table.add_row("Account", pair.txn1_account, pair.txn2_account)

        console.print(
            f"\n[dim]Candidate {i + 1}[/dim] - [{style}]{prediction}[/{style}] (Confidence: {assessment.confidence:.1%})"
        )
        console.print(f"[dim]{assessment.reasoning}[/dim]")
        console.print(table)

    return 0


def show_features(console: Console, builder: TrainingDataBuilder) -> int:
    """Show feature importance from trained classifier."""
    pairs, labels = builder.load_from_events()

    if len(pairs) < 10:
        console.print("[yellow]Insufficient training data for feature analysis[/yellow]")
        return 0

    # Train classifier to get feature importance

    console.print("\n[cyan]Training classifier to analyze feature importance...[/cyan]\n")
    classifier = DuplicateClassifier()
    metrics = classifier.train(pairs, labels)

    # Show metrics
    console.print("[cyan]Model Performance:[/cyan]")
    metrics_table = Table(show_header=False)
    metrics_table.add_column("Metric", style="dim")
    metrics_table.add_column("Value", style="bold")

    metrics_table.add_row("Training accuracy", f"{metrics['train_accuracy']:.1%}")
    metrics_table.add_row("Validation accuracy", f"{metrics['val_accuracy']:.1%}")
    metrics_table.add_row("Precision", f"{metrics['precision']:.1%}")
    metrics_table.add_row("Recall", f"{metrics['recall']:.1%}")

    console.print(metrics_table)

    # Show feature importance
    console.print("\n[cyan]Feature Importance:[/cyan]")
    importance = classifier.get_feature_importance()

    importance_table = Table(show_header=True)
    importance_table.add_column("Rank", style="dim", justify="right")
    importance_table.add_column("Feature", style="cyan")
    importance_table.add_column("Importance", justify="right")
    importance_table.add_column("Bar", style="blue")

    max_importance = max(importance.values()) if importance else 1
    for rank, (feature, score) in enumerate(importance.items(), 1):
        bar_length = int((score / max_importance) * 30)
        bar = "█" * bar_length
        importance_table.add_row(str(rank), feature, f"{score:.1f}", bar)

    console.print(importance_table)

    console.print("\n[dim]Feature descriptions:[/dim]")
    console.print("  [dim]cosine_similarity:[/dim] TF-IDF similarity between descriptions")
    console.print("  [dim]levenshtein_ratio:[/dim] Edit distance similarity (0-1)")
    console.print("  [dim]token_overlap:[/dim] Fraction of shared words")
    console.print("  [dim]amount_exact_match:[/dim] Whether amounts match exactly")
    console.print("  [dim]date_difference_days:[/dim] Days between transactions")
    console.print("  [dim]same_account:[/dim] Whether accounts match")
    console.print("  [dim]length_difference:[/dim] Difference in description lengths")
    console.print("  [dim]common_prefix_ratio:[/dim] Fraction of common prefix")

    return 0


__all__ = ["run"]
