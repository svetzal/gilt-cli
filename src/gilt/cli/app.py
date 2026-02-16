from __future__ import annotations

"""
Gilt CLI Wrapper (Typer + Rich)

Local-only, privacy-first CLI for managing personal financial data.

All paths are resolved from a single workspace root:
  --data-dir / GILT_DATA env var / current working directory
"""

from pathlib import Path
from typing import Optional

import typer

from gilt.workspace import Workspace

HELP_WRITE = "Persist changes (default: dry-run)"

APP_HELP = "Gilt CLI (local-only)"
HELP_ACCOUNT_DISPLAY = "Account ID to display (e.g., MYBANK_CHQ)"
HELP_ACCOUNT_WITH_TX = "Account ID containing the transaction (e.g., MYBANK_CHQ)"

app = typer.Typer(no_args_is_help=True, add_completion=False, help=APP_HELP)


@app.callback()
def main(
    ctx: typer.Context,
    data_dir: Optional[Path] = typer.Option(
        None,
        "--data-dir",
        envvar="GILT_DATA",
        help="Workspace root directory (default: current directory)",
    ),
):
    """Gilt CLI — all paths resolved from a single workspace root."""
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = Workspace.resolve(data_dir)


def _ws(ctx: typer.Context) -> Workspace:
    return ctx.obj["workspace"]


@app.command()
def init(ctx: typer.Context):
    """Initialize a new workspace with required directories and starter config.

    Creates the directory structure and starter configuration files.
    Safe to run on an existing workspace — skips anything that already exists.

    Examples:
      gilt --data-dir ~/finances init
      gilt init
    """
    from gilt.cli.command import init as cmd_init

    code = cmd_init.run(workspace=_ws(ctx))
    raise typer.Exit(code=code)


@app.command()
def accounts(ctx: typer.Context):
    """List available accounts (IDs and descriptions)."""
    from gilt.cli.command import accounts as cmd_accounts

    code = cmd_accounts.run(workspace=_ws(ctx))
    raise typer.Exit(code=code)


@app.command()
def categories(ctx: typer.Context):
    """List all defined categories with usage statistics."""
    from gilt.cli.command import categories as cmd_categories

    code = cmd_categories.run(workspace=_ws(ctx))
    raise typer.Exit(code=code)


@app.command()
def category(
    ctx: typer.Context,
    add: Optional[str] = typer.Option(None, "--add", help="Add a new category (supports 'Category:Subcategory')"),
    remove: Optional[str] = typer.Option(None, "--remove", help="Remove a category"),
    set_budget: Optional[str] = typer.Option(None, "--set-budget", help="Set budget for a category"),
    description: Optional[str] = typer.Option(None, "--description", help="Description for new category"),
    amount: Optional[float] = typer.Option(None, "--amount", help="Budget amount"),
    period: str = typer.Option("monthly", "--period", help="Budget period (monthly or yearly)"),
    force: bool = typer.Option(False, "--force", help="Skip confirmations when removing used categories"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Manage categories: add, remove, or set budget.

    Examples:
      gilt category --add "Housing" --description "Housing expenses" --write
      gilt category --add "Housing:Utilities" --write
      gilt category --set-budget "Dining Out" --amount 400 --write
      gilt category --remove "Old Category" --write

    Safety: dry-run by default. Use --write to persist changes.
    """
    from gilt.cli.command import category as cmd_category

    code = cmd_category.run(
        add=add,
        remove=remove,
        set_budget=set_budget,
        description=description,
        amount=amount,
        period=period,
        force=force,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def ytd(
    ctx: typer.Context,
    account: str = typer.Option(..., "--account", "-a", help=HELP_ACCOUNT_DISPLAY),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to filter (defaults to current year)"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", min=1, help="Max number of rows to show (after sorting)"),
    default_currency: Optional[str] = typer.Option(None, "--default-currency", help="Fallback currency if missing in legacy rows (e.g., CAD)"),
    include_duplicates: bool = typer.Option(False, "--include-duplicates", help="Include transactions marked as duplicates"),
):
    """Show year-to-date transactions for a single account as a Rich table.

    Loads transactions from projections database. Duplicates are automatically excluded
    unless --include-duplicates is specified.

    Examples:
      gilt ytd --account MYBANK_CHQ
      gilt ytd -a MYBANK_CC --year 2024 --limit 50
      gilt ytd -a BANK2_LOC --include-duplicates
    """
    from gilt.cli.command import ytd as cmd_ytd

    code = cmd_ytd.run(
        account=account,
        year=year,
        workspace=_ws(ctx),
        limit=limit,
        default_currency=default_currency,
        include_duplicates=include_duplicates,
    )
    raise typer.Exit(code=code)


@app.command()
def categorize(
    ctx: typer.Context,
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account ID (omit to categorize across all accounts)"),
    txid: Optional[str] = typer.Option(None, "--txid", "-t", help="Transaction ID prefix (single mode)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Exact description to match (batch mode)"),
    desc_prefix: Optional[str] = typer.Option(None, "--desc-prefix", "-p", help="Description prefix to match (batch mode, case-insensitive)"),
    pattern: Optional[str] = typer.Option(None, "--pattern", help="Regex pattern to match description (batch mode, case-insensitive)"),
    amount: Optional[float] = typer.Option(None, "--amount", "-m", help="Exact amount to match (batch mode)"),
    category: str = typer.Option(..., "--category", "-c", help="Category name (supports 'Category:Subcategory' syntax)"),
    subcategory: Optional[str] = typer.Option(None, "--subcategory", "-s", help="Subcategory name (alternative to colon syntax)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Assume 'yes' for all confirmations in batch mode"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Categorize transactions (single or batch mode).

    Modes:
    - Single: use --txid/-t to target one transaction
    - Batch: use --description/-d, --desc-prefix/-p, or --pattern to target multiple transactions

    Examples:
      gilt categorize --account MYBANK_CHQ --txid a1b2c3d4 --category "Housing:Utilities" --write
      gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
      gilt categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write
      gilt categorize --account MYBANK_CC --description "Monthly Fee" --category "Banking:Fees" --write

    Safety: dry-run by default. Use --write to persist changes.
    """
    from gilt.cli.command import categorize as cmd_categorize

    code = cmd_categorize.run(
        account=account,
        txid=txid,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
        category=category,
        subcategory=subcategory,
        assume_yes=yes,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def recategorize(
    ctx: typer.Context,
    from_cat: str = typer.Option(..., "--from", help="Original category name (supports 'Category:Subcategory')"),
    to_cat: str = typer.Option(..., "--to", help="New category name (supports 'Category:Subcategory')"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Rename a category across all ledger files.

    Useful when renaming categories in categories.yml to update existing
    transaction categorizations in ledger files.

    Examples:
      gilt recategorize --from "Business" --to "Work" --write
      gilt recategorize --from "Business:Meals" --to "Work:Meals" --write

    Safety: dry-run by default. Use --write to persist changes.
    """
    from gilt.cli.command import recategorize as cmd_recategorize

    code = cmd_recategorize.run(
        from_category=from_cat,
        to_category=to_cat,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command(name="auto-categorize")
def auto_categorize(
    ctx: typer.Context,
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account ID to filter (omit for all accounts)"),
    confidence: float = typer.Option(0.7, "--confidence", "-c", min=0.0, max=1.0, help="Minimum confidence threshold (0.0-1.0)"),
    min_samples: int = typer.Option(5, "--min-samples", min=1, help="Minimum samples per category for training"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Enable interactive review mode"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", min=1, help="Max number of transactions to auto-categorize"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Auto-categorize transactions using ML classifier.

    Trains a classifier from your categorization history and predicts
    categories for uncategorized transactions.

    Examples:
      gilt auto-categorize
      gilt auto-categorize --confidence 0.8 --write
      gilt auto-categorize --interactive --write
      gilt auto-categorize --account MYBANK_CHQ --confidence 0.6 --write

    Safety: dry-run by default. Use --write to persist changes.
    """
    from gilt.cli.command import auto_categorize as cmd_auto_categorize

    code = cmd_auto_categorize.run(
        account=account,
        confidence=confidence,
        min_samples=min_samples,
        interactive=interactive,
        limit=limit,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def uncategorized(
    ctx: typer.Context,
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account ID to filter (omit for all accounts)"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to filter"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", min=1, help="Max number of transactions to show"),
    min_amount: Optional[float] = typer.Option(None, "--min-amount", help="Minimum absolute amount to include"),
):
    """Display transactions without categories.

    Shows uncategorized transactions sorted by description (for grouping similar ones), then date.
    Helps identify which transactions still need categorization.

    Examples:
      gilt uncategorized
      gilt uncategorized --account MYBANK_CHQ --year 2025
      gilt uncategorized --min-amount 100 --limit 50
    """
    from gilt.cli.command import uncategorized as cmd_uncategorized

    code = cmd_uncategorized.run(
        account=account,
        year=year,
        limit=limit,
        min_amount=min_amount,
        workspace=_ws(ctx),
    )
    raise typer.Exit(code=code)


@app.command()
def budget(
    ctx: typer.Context,
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to report (default: current year)"),
    month: Optional[int] = typer.Option(None, "--month", "-m", help="Month to report (1-12, requires --year)"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Filter to specific category"),
):
    """Display budget summary comparing actual spending vs budgeted amounts.

    Shows spending by category with budget comparison when budgets are defined.
    Automatically prorates monthly/yearly budgets based on report period.

    Examples:
      gilt budget
      gilt budget --year 2025
      gilt budget --year 2025 --month 10
      gilt budget --category "Dining Out"
    """
    from gilt.cli.command import budget as cmd_budget

    code = cmd_budget.run(
        year=year,
        month=month,
        category=category,
        workspace=_ws(ctx),
    )
    raise typer.Exit(code=code)


@app.command()
def diagnose_categories(ctx: typer.Context):
    """Diagnose category issues by finding categories in transactions not in config.

    Scans all ledger files and reports any categories used in transactions that
    aren't defined in categories.yml. Helps identify orphaned, misspelled, or
    forgotten categories.

    Examples:
      gilt diagnose-categories
    """
    from gilt.cli.command import diagnose_categories as cmd_diagnose_categories

    code = cmd_diagnose_categories.run(workspace=_ws(ctx))
    raise typer.Exit(code=code)


@app.command()
def report(
    ctx: typer.Context,
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Year to report (default: current year)"),
    month: Optional[int] = typer.Option(None, "--month", "-m", help="Month to report (1-12, requires --year)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path (without extension, default: reports/budget_report_YYYY[-MM])"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Generate budget report as markdown and Word document (.docx).

    Creates a comprehensive budget report comparing actual spending vs budgeted amounts.
    Outputs both markdown (.md) and Word (.docx) formats using pandoc.

    Examples:
      gilt report
      gilt report --year 2025 --write
      gilt report --year 2025 --month 10 --write
      gilt report --output custom/report --write

    Safety: dry-run by default. Use --write to persist files.
    Note: Requires pandoc for .docx generation (brew install pandoc on macOS).
    """
    from gilt.cli.command import report as cmd_report

    code = cmd_report.run(
        year=year,
        month=month,
        output=output,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def note(
    ctx: typer.Context,
    account: str = typer.Option(..., "--account", "-a", help=HELP_ACCOUNT_WITH_TX),
    txid: Optional[str] = typer.Option(None, "--txid", "-t", help="Transaction ID prefix (TxnID8 as shown in tables)"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Exact description to match (batch mode)"),
    desc_prefix: Optional[str] = typer.Option(None, "--desc-prefix", "-p", help="Description prefix to match (batch mode, case-insensitive)"),
    pattern: Optional[str] = typer.Option(None, "--pattern", help="Regex pattern to match description (batch mode, case-insensitive)"),
    amount: Optional[float] = typer.Option(None, "--amount", "-m", help="Exact amount to match (batch mode)"),
    note: str = typer.Option(..., "--note", "-n", help="Note text to set on the transaction(s)"),
    yes: bool = typer.Option(False, "--yes", "-y", "-r", help="Assume 'yes' for all confirmations in batch mode"),
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Attach or update notes on transactions in the account ledger.

    Modes:
    - Single: use --txid/-t to target one transaction.
    - Batch: use --description/-d, --desc-prefix/-p, or --pattern (optionally with --amount/-m) to target recurring transactions.

    Safety: dry-run by default. Use --write to persist changes.
    """
    from gilt.cli.command import note as cmd_note

    code = cmd_note.run(
        account=account,
        txid=txid,
        note_text=note,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
        assume_yes=yes,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def ingest(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help=HELP_WRITE),
):
    """Ingest and normalize raw CSVs into standardized per-account ledgers.

    Safety: dry-run by default. Use --write to write outputs under data/accounts/.
    """
    from gilt.cli.command import ingest as cmd_ingest

    code = cmd_ingest.run(
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command(name="mark-duplicate")
def mark_duplicate(
    ctx: typer.Context,
    primary_txid: str = typer.Option(..., "--primary", "-p", help="Transaction ID to keep (8+ char prefix)"),
    duplicate_txid: str = typer.Option(..., "--duplicate", "-d", help="Transaction ID to mark as duplicate (8+ char prefix)"),
    write: bool = typer.Option(False, "--write", help="Persist changes (default: dry-run)"),
):
    """Manually mark a specific pair of transactions as duplicates.

    Use this when you discover a duplicate that wasn't automatically detected
    or when you want to mark a specific pair without reviewing all candidates.

    The primary transaction is kept and shown in budgets/reports. The duplicate
    transaction is hidden from all calculations but preserved in the event store.

    You'll be prompted to choose which description to keep for the primary transaction.

    Examples:
      gilt mark-duplicate --primary a1b2c3d4 --duplicate e5f6g7h8
      gilt mark-duplicate -p a1b2c3d4 -d e5f6g7h8 --write

    Transaction IDs:
      You can use 8-character prefixes instead of full transaction IDs.
      View transaction IDs with: gilt ytd --account <ACCOUNT_ID>

    Note: Changes are recorded as events and projections are automatically rebuilt.
    """
    from gilt.cli.command import mark_duplicate as cmd_mark_duplicate

    code = cmd_mark_duplicate.run(
        primary_txid=primary_txid,
        duplicate_txid=duplicate_txid,
        workspace=_ws(ctx),
        write=write,
    )
    raise typer.Exit(code=code)


@app.command()
def duplicates(
    ctx: typer.Context,
    model: str = typer.Option("qwen3:30b", "--model", help="Ollama model for LLM duplicate detection"),
    max_days_apart: int = typer.Option(1, "--max-days", help="Maximum days between potential duplicates"),
    amount_tolerance: float = typer.Option(0.001, "--amount-tolerance", help="Acceptable difference in amounts"),
    min_confidence: float = typer.Option(0.0, "--min-confidence", help="Minimum confidence threshold to display (0.0-1.0)"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Enable interactive mode to confirm/deny each duplicate"),
    use_llm: bool = typer.Option(False, "--llm", help="Use LLM instead of ML (slower, no training needed)"),
):
    """Scan ledgers for duplicate transactions using ML or LLM analysis.

    By default, uses fast ML-based classification trained on your feedback.
    Falls back to LLM if insufficient training data (<10 examples).

    Examples:
      gilt duplicates
      gilt duplicates --llm
      gilt duplicates --interactive
      gilt duplicates -i --min-confidence 0.7
      gilt duplicates --llm --model qwen3:30b

    Note: LLM mode requires Ollama with specified model installed locally.
    """
    from gilt.cli.command import duplicates as cmd_duplicates

    code = cmd_duplicates.run(
        workspace=_ws(ctx),
        model=model,
        max_days_apart=max_days_apart,
        amount_tolerance=amount_tolerance,
        min_confidence=min_confidence,
        interactive=interactive,
        use_llm=use_llm,
    )
    raise typer.Exit(code=code)


@app.command(name="audit-ml")
def audit_ml(
    ctx: typer.Context,
    mode: str = typer.Option("summary", "--mode", "-m", help="Audit mode: summary, training, predictions, or features"),
    filter_pattern: Optional[str] = typer.Option(None, "--filter", "-f", help="Regex pattern to filter descriptions"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum examples to show"),
):
    """Audit ML classifier training data and decisions.

    Modes:
      summary      - Show training data statistics (default)
      training     - Display actual training examples (positive/negative)
      predictions  - Show ML predictions on current candidate pairs
      features     - Show feature importance and model performance

    Examples:
      gilt audit-ml
      gilt audit-ml --mode training
      gilt audit-ml --mode training --filter "PRESTO"
      gilt audit-ml --mode predictions --limit 10
      gilt audit-ml --mode features
    """
    from gilt.cli.command import audit_ml as cmd_audit_ml

    code = cmd_audit_ml.run(
        workspace=_ws(ctx),
        mode=mode,
        filter_pattern=filter_pattern,
        limit=limit,
    )
    raise typer.Exit(code=code)


@app.command(name="prompt-stats")
def prompt_stats(
    ctx: typer.Context,
    generate_update: bool = typer.Option(False, "--generate-update", "-g", help="Generate a new PromptUpdated event based on learned patterns"),
):
    """Show prompt learning statistics and generate updates.

    Examples:
      gilt prompt-stats
      gilt prompt-stats --generate-update

    Note: Requires interactive duplicate detection feedback (gilt duplicates --interactive).
    """
    from gilt.cli.command import prompt_stats as cmd_prompt_stats

    code = cmd_prompt_stats.run(
        workspace=_ws(ctx),
        generate_update=generate_update,
    )
    raise typer.Exit(code=code)


@app.command(name="rebuild-projections")
def rebuild_projections(
    ctx: typer.Context,
    from_scratch: bool = typer.Option(False, "--from-scratch", help="Delete existing projections and rebuild from all events"),
    incremental: bool = typer.Option(False, "--incremental", help="Only apply new events since last rebuild (default behavior)"),
    events_db: Optional[Path] = typer.Option(None, "--events-db", help="Path to events database (advanced override)"),
    projections_db: Optional[Path] = typer.Option(None, "--projections-db", help="Path to projections database (advanced override)"),
):
    """Rebuild transaction projections from event store.

    By default, applies only new events since last rebuild (incremental mode).
    Use --from-scratch to rebuild everything from all events.

    Examples:
      gilt rebuild-projections
      gilt rebuild-projections --from-scratch
      gilt rebuild-projections --events-db custom/events.db
    """
    from gilt.cli.command import rebuild_projections as cmd_rebuild_projections

    code = cmd_rebuild_projections.run(
        workspace=_ws(ctx),
        from_scratch=from_scratch,
        incremental=incremental,
        events_db=events_db,
        projections_db=projections_db,
    )
    raise typer.Exit(code=code)


@app.command(name="backfill-events")
def backfill_events(
    ctx: typer.Context,
    events_db: Optional[Path] = typer.Option(None, "--event-store", help="Path to event store database (advanced override)"),
    projections_db: Optional[Path] = typer.Option(None, "--projections-db", help="Path to transaction projections database (advanced override)"),
    budget_projections_db: Optional[Path] = typer.Option(None, "--budget-projections-db", help="Path to budget projections database (advanced override)"),
    write: bool = typer.Option(False, "--write", help="Actually write events (default: dry-run)"),
):
    """Backfill events from existing data (advanced/debugging).

    Most users should use 'gilt migrate-to-events --write' instead.

    Examples:
      gilt backfill-events
      gilt backfill-events --write

    Safety: dry-run by default. Use --write to persist events.
    """
    from gilt.cli.command import backfill_events as cmd_backfill_events

    ws = _ws(ctx)
    code = cmd_backfill_events.run(
        workspace=ws,
        event_store_path=events_db,
        projections_db_path=projections_db,
        budget_projections_db_path=budget_projections_db,
        dry_run=not write,
    )
    raise typer.Exit(code=code)


@app.command(name="migrate-to-events")
def migrate_to_events(
    ctx: typer.Context,
    events_db: Optional[Path] = typer.Option(None, "--event-store", help="Path to event store database (advanced override)"),
    projections_db: Optional[Path] = typer.Option(None, "--projections-db", help="Path to transaction projections database (advanced override)"),
    budget_projections_db: Optional[Path] = typer.Option(None, "--budget-projections-db", help="Path to budget projections database (advanced override)"),
    write: bool = typer.Option(False, "--write", help="Actually perform migration (default: dry-run)"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing event store"),
):
    """One-command migration to event sourcing (recommended for upgrades).

    This command automates the complete migration process:
    1. Validates you have CSV data to migrate
    2. Creates event store from your existing data
    3. Builds transaction and budget projections
    4. Validates everything matches original data

    Examples:
      gilt migrate-to-events
      gilt migrate-to-events --write
      gilt migrate-to-events --write --force

    Safety: dry-run by default. Use --write to perform migration.
    """
    from gilt.cli.command import migrate_to_events as cmd_migrate_to_events

    ws = _ws(ctx)
    code = cmd_migrate_to_events.run(
        workspace=ws,
        event_store_path=events_db,
        projections_db_path=projections_db,
        budget_projections_db_path=budget_projections_db,
        write=write,
        force=force,
    )
    raise typer.Exit(code=code)


if __name__ == "__main__":
    app()  # pragma: no cover
