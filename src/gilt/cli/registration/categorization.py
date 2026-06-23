"""Categorization-domain CLI commands: categorize, recategorize, auto-categorize,
uncategorized, diagnose-categories, infer-rules."""

from __future__ import annotations

from pathlib import Path

import typer

from gilt.cli.registration._dispatch import HELP_WRITE, dispatch, resolve_fy_range


def register_categorize(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def categorize(
        ctx: typer.Context,
        account: str | None = typer.Option(
            None, "--account", "-a", help="Account ID (omit to categorize across all accounts)"
        ),
        txid: str | None = typer.Option(
            None, "--txid", "-t", help="Transaction ID prefix (single mode)"
        ),
        description: str | None = typer.Option(
            None, "--description", "-d", help="Exact description to match (batch mode)"
        ),
        desc_prefix: str | None = typer.Option(
            None,
            "--desc-prefix",
            "-p",
            help="Description prefix to match (batch mode, case-insensitive)",
        ),
        pattern: str | None = typer.Option(
            None,
            "--pattern",
            help="Regex pattern to match description (batch mode, case-insensitive)",
        ),
        amount: float | None = typer.Option(
            None, "--amount", "-m", help="Exact amount to match (batch mode)"
        ),
        category: str | None = typer.Option(
            None,
            "--category",
            "-c",
            help="Category name (supports 'Category:Subcategory' syntax)",
        ),
        subcategory: str | None = typer.Option(
            None, "--subcategory", "-s", help="Subcategory name (alternative to colon syntax)"
        ),
        yes: bool = typer.Option(
            False, "--yes", "-y", help="Assume 'yes' for all confirmations in batch mode"
        ),
        txid_file: Path | None = typer.Option(
            None,
            "--txid-file",
            help="File of '<txid-prefix> <category>' pairs to apply in one batch",
        ),
        from_stdin: bool = typer.Option(
            False,
            "--from-stdin",
            help="Read '<txid-prefix> <category>' pairs from stdin",
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
    ):
        """Categorize transactions (single, batch, or file-batch mode).

        Modes:
        - Single: use --txid/-t to target one transaction
        - Batch: use --description/-d, --desc-prefix/-p, or --pattern to target multiple transactions
        - File batch: use --txid-file or --from-stdin to apply many txid→category mappings at once

        File/stdin format (one entry per line):
          # Comments start with #
          <txid-or-prefix> <category-string>
          7f860a03 Housing:Utilities
          9bc16ce1 Banking:Fees

        Examples:
          gilt categorize --account MYBANK_CHQ --txid a1b2c3d4 --category "Housing:Utilities" --write
          gilt categorize --desc-prefix "SPOTIFY" --category "Entertainment:Music" --yes --write
          gilt categorize --pattern "Payment.*EXAMPLE UTILITY" --category "Housing:Utilities" --yes --write
          gilt categorize --account MYBANK_CC --description "Monthly Fee" --category "Banking:Fees" --write
          gilt categorize --txid-file batch.txt --write
          gilt categorize --from-stdin --write < batch.txt

        Safety: dry-run by default. Use --write to persist changes.
        """
        from gilt.cli.command import categorize as cmd_categorize

        dispatch(
            cmd_categorize.run,
            account=account,
            txid=txid,
            description=description,
            desc_prefix=desc_prefix,
            pattern=pattern,
            amount=amount,
            category=category,
            subcategory=subcategory,
            assume_yes=yes,
            txid_file=txid_file,
            from_stdin=from_stdin,
            workspace=ws_fn(ctx),
            write=write,
        )


def register_recategorize(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def recategorize(
        ctx: typer.Context,
        from_cat: str | None = typer.Option(
            None, "--from", help="Original category name (supports 'Category:Subcategory')"
        ),
        to_cat: str = typer.Option(
            ..., "--to", help="New category name (supports 'Category:Subcategory')"
        ),
        account: str | None = typer.Option(
            None, "--account", "-a", help="Restrict selection to this account ID"
        ),
        desc_prefix: str | None = typer.Option(
            None, "--desc-prefix", "-p", help="Description prefix filter (case-insensitive)"
        ),
        pattern: str | None = typer.Option(
            None, "--pattern", help="Regex pattern filter on descriptions"
        ),
        amount_eq: float | None = typer.Option(
            None, "--amount-eq", help="Exact signed amount to match"
        ),
        amount_min: float | None = typer.Option(
            None, "--amount-min", help="Minimum signed amount (inclusive)"
        ),
        amount_max: float | None = typer.Option(
            None, "--amount-max", help="Maximum signed amount (inclusive)"
        ),
        date_from_str: str | None = typer.Option(
            None, "--date-from", help="Start date (YYYY-MM-DD, inclusive)"
        ),
        date_to_str: str | None = typer.Option(
            None, "--date-to", help="End date (YYYY-MM-DD, inclusive)"
        ),
        fy: str | None = typer.Option(
            None,
            "--fy",
            help="Fiscal year to filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
    ):
        """Rename a category or recategorize a filtered selection.

        Without selection flags, renames every transaction with --from to --to.
        With selection flags, applies --to to the filtered subset (--from is optional).

        Selection flags: --account, --desc-prefix, --pattern, --amount-eq,
        --amount-min, --amount-max, --date-from, --date-to, --fy.

        Examples:
          gilt recategorize --from "Business" --to "Work" --write
          gilt recategorize --from "Business:Meals" --to "Work:Meals" --write
          gilt recategorize --desc-prefix "ACME" --to "Work:Supplies" --write
          gilt recategorize --desc-prefix "ACME" --amount-eq -18.30 --account MYBANK_CC --to "Work:Subscriptions" --write

        Safety: dry-run by default. Use --write to persist changes.
        """
        from gilt.cli.command import recategorize as cmd_recategorize
        from gilt.cli.console import console as _console

        date_selection = cmd_recategorize.build_date_selection(date_from_str, date_to_str, fy)
        if isinstance(date_selection, str):
            _console.print(f"[red]Error:[/] {date_selection}")
            raise typer.Exit(code=1)
        date_from, date_to, fy_range = date_selection

        dispatch(
            cmd_recategorize.run,
            from_category=from_cat,
            to_category=to_cat,
            account=account,
            desc_prefix=desc_prefix,
            pattern=pattern,
            amount_eq=amount_eq,
            amount_min=amount_min,
            amount_max=amount_max,
            date_from=date_from,
            date_to=date_to,
            fy_range=fy_range,
            workspace=ws_fn(ctx),
            write=write,
        )


def register_auto_categorize(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="auto-categorize")
    def auto_categorize(
        ctx: typer.Context,
        account: str | None = typer.Option(
            None, "--account", "-a", help="Account ID to filter (omit for all accounts)"
        ),
        confidence: float = typer.Option(
            0.7,
            "--confidence",
            "-c",
            min=0.0,
            max=1.0,
            help="Minimum confidence threshold (0.0-1.0)",
        ),
        min_samples: int = typer.Option(
            5, "--min-samples", min=1, help="Minimum samples per category for training"
        ),
        interactive: bool = typer.Option(
            False, "--interactive", "-i", help="Enable interactive review mode"
        ),
        limit: int | None = typer.Option(
            None, "--limit", "-n", min=1, help="Max number of transactions to auto-categorize"
        ),
        explain: bool = typer.Option(
            False, "--explain", help="Print top-3 category candidates with calibrated confidences"
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
    ):
        """Auto-categorize transactions using ML classifier.

        Trains a classifier from your categorization history and predicts
        categories for uncategorized transactions. Rules inferred from history
        are applied first (deterministic); ML is used as a fallback.

        Examples:
          gilt auto-categorize
          gilt auto-categorize --confidence 0.8 --write
          gilt auto-categorize --interactive --write
          gilt auto-categorize --account MYBANK_CHQ --confidence 0.6 --write
          gilt auto-categorize --explain

        Safety: dry-run by default. Use --write to persist changes.
        """
        from gilt.cli.command import auto_categorize as cmd_auto_categorize

        dispatch(
            cmd_auto_categorize.run,
            account=account,
            confidence=confidence,
            min_samples=min_samples,
            interactive=interactive,
            limit=limit,
            explain=explain,
            workspace=ws_fn(ctx),
            write=write,
        )


def register_uncategorized(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def uncategorized(
        ctx: typer.Context,
        account: str | None = typer.Option(
            None, "--account", "-a", help="Account ID to filter (omit for all accounts)"
        ),
        year: int | None = typer.Option(None, "--year", "-y", help="Calendar year to filter"),
        fy: str | None = typer.Option(
            None,
            "--fy",
            help="Fiscal year to filter (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        limit: int | None = typer.Option(
            None, "--limit", "-n", min=1, help="Max number of transactions to show"
        ),
        min_amount: float | None = typer.Option(
            None, "--min-amount", help="Minimum absolute amount to include"
        ),
    ):
        """Display transactions without categories.

        Shows uncategorized transactions sorted by account, then date.
        Defaults to all accounts; use --account to narrow to one.
        Includes a per-account count summary below the main table.

        Examples:
          gilt uncategorized
          gilt uncategorized --account MYBANK_CHQ --year 2025
          gilt uncategorized --fy FY25
          gilt uncategorized --min-amount 100 --limit 50
        """
        from gilt.cli.command import uncategorized as cmd_uncategorized
        from gilt.cli.console import console

        if fy is not None and year is not None:
            console.print(
                "[red]Error:[/] --fy and --year cannot be used together. Use one or the other."
            )
            raise typer.Exit(code=1)

        dispatch(
            cmd_uncategorized.run,
            account=account,
            year=year,
            limit=limit,
            min_amount=min_amount,
            fy_range=resolve_fy_range(fy),
            fy_label=fy,
            workspace=ws_fn(ctx),
        )


def register_diagnose_categories(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
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

        dispatch(cmd_diagnose_categories.run, workspace=ws_fn(ctx))


def register_infer_rules(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="infer-rules")
    def infer_rules(
        ctx: typer.Context,
        apply: bool = typer.Option(
            False, "--apply", help="Apply rules to uncategorized transactions"
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
        min_evidence: int = typer.Option(
            3, "--min-evidence", min=1, help="Minimum categorizations to infer a rule"
        ),
        min_confidence: float = typer.Option(
            0.9,
            "--min-confidence",
            min=0.0,
            max=1.0,
            help="Minimum consistency to infer a rule",
        ),
        export: str | None = typer.Option(None, "--export", help="Export rules to JSON file"),
    ):
        """Infer categorization rules from transaction history.

        Scans categorization history for descriptions consistently categorized the
        same way. Use --apply to match rules against uncategorized transactions.

        Examples:
          gilt infer-rules
          gilt infer-rules --apply
          gilt infer-rules --apply --write
          gilt infer-rules --min-evidence 5 --min-confidence 0.95
          gilt infer-rules --export rules.json

        Safety: dry-run by default. Use --apply --write to persist changes.
        """
        from gilt.cli.command import infer_rules as cmd_infer_rules

        dispatch(
            cmd_infer_rules.run,
            workspace=ws_fn(ctx),
            apply=apply,
            write=write,
            min_evidence=min_evidence,
            min_confidence=min_confidence,
            export=export,
        )


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register categorization commands on *app*."""
    register_categorize(app, ws_fn)
    register_recategorize(app, ws_fn)
    register_auto_categorize(app, ws_fn)
    register_uncategorized(app, ws_fn)
    register_diagnose_categories(app, ws_fn)
    register_infer_rules(app, ws_fn)
