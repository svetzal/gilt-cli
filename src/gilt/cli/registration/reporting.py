"""Reporting-domain CLI commands: ytd, status, summary, budget, report, show, history, note."""

from __future__ import annotations

from pathlib import Path

import typer

from gilt.cli.registration._dispatch import build_fy_range, command_kwargs, dispatch
from gilt.cli.registration._options import (
    HELP_ACCOUNT_DISPLAY,
    HELP_ACCOUNT_WITH_TX,
    account_option,
    amount_option,
    category_option,
    date_from_option,
    date_to_option,
    desc_prefix_option,
    description_option,
    fy_option,
    include_uncategorized_option,
    limit_option,
    month_option,
    pattern_option,
    txid_option,
    write_option,
    year_option,
    yes_option,
)


def register_ytd(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def ytd(
        ctx: typer.Context,
        account: str = account_option(HELP_ACCOUNT_DISPLAY, required=True),
        year: int | None = year_option("Year to filter (defaults to current year)"),
        limit: int | None = limit_option("Max number of rows to show (after sorting)", min=1),
        default_currency: str | None = typer.Option(
            None,
            "--default-currency",
            help="Fallback currency if missing in legacy rows (e.g., CAD)",
        ),
        include_duplicates: bool = typer.Option(
            False, "--include-duplicates", help="Include transactions marked as duplicates"
        ),
        raw: bool = typer.Option(
            False, "--raw", help="Show original bank descriptions instead of vendor names"
        ),
        compare: bool = typer.Option(
            False,
            "--compare",
            help="Show enriched transactions with bank description and vendor side by side",
        ),
    ):
        """Show year-to-date transactions for a single account as a Rich table.

        Loads transactions from projections database. Duplicates are automatically excluded
        unless --include-duplicates is specified. Enriched transactions show vendor names
        by default; use --raw to see original bank descriptions. Use --compare to show
        enriched transactions with both bank description and vendor name side by side.

        Examples:
          gilt ytd --account MYBANK_CHQ
          gilt ytd -a MYBANK_CC --year 2024 --limit 50
          gilt ytd -a BANK2_LOC --include-duplicates
          gilt ytd -a MYBANK_CHQ --raw
          gilt ytd -a MYBANK_CC --compare
        """
        from gilt.cli.command import ytd as cmd_ytd

        dispatch(cmd_ytd.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))


def register_status(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def status(
        ctx: typer.Context,
        fy: str | None = fy_option(
            "Fiscal year for Mojility columns (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        stale_threshold: int = typer.Option(
            14,
            "--stale-threshold",
            min=0,
            help="Days since latest transaction before account is flagged stale",
        ),
    ):
        """Display per-account freshness and coverage dashboard.

        Shows latest transaction date, days since last transaction, total transactions,
        uncategorized count, and Mojility-specific coverage metrics per account.

        Examples:
          gilt status
          gilt status --fy FY25
          gilt status --stale-threshold 30
        """
        from gilt.cli.command import status as cmd_status

        dispatch(
            cmd_status.run,
            **command_kwargs(
                ctx,
                drop={"fy"},
                fy_range=build_fy_range(fy),
                fy_label=fy,
                workspace=ws_fn(ctx),
            ),
        )


def register_summary(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def summary(
        ctx: typer.Context,
        category: str | None = category_option("Drill into one category's subcategories"),
        year: int | None = year_option("Calendar year (default: current)"),
        fy: str | None = fy_option(
            "Fiscal year (Nov 1 – Oct 31). Accepts FY25, fy25, FY2025.",
        ),
        account: str | None = account_option("Account ID to filter"),
        include_uncategorized: bool = include_uncategorized_option(
            "Include rows where category is null"
        ),
    ):
        """Display category or subcategory spending summary.

        Without --category: shows top-level category breakdown for the selected year,
        sorted by absolute net descending.

        With --category <name>: drills into that category's subcategories, showing
        count, net, and percentage of the category total.

        Examples:
          gilt summary
          gilt summary --year 2025
          gilt summary --fy FY25
          gilt summary --category Housing
          gilt summary --category Housing --fy FY25
          gilt summary --account MYBANK_CHQ --year 2025
          gilt summary --include-uncategorized
        """
        from gilt.cli.command import summary as cmd_summary
        from gilt.cli.console import console

        if fy is not None and year is not None:
            console.print(
                "[red]Error:[/] --fy and --year cannot be used together. Use one or the other."
            )
            raise typer.Exit(code=1)

        dispatch(
            cmd_summary.run,
            **command_kwargs(
                ctx,
                drop={"fy"},
                fy_range=build_fy_range(fy),
                fy_label=fy,
                workspace=ws_fn(ctx),
            ),
        )


def register_budget(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def budget(
        ctx: typer.Context,
        year: int | None = year_option("Year to report (default: current year)"),
        month: int | None = month_option("Month to report (1-12, requires --year)"),
        category: str | None = category_option("Filter to specific category"),
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

        dispatch(cmd_budget.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))


def register_report(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def report(
        ctx: typer.Context,
        year: int | None = year_option("Year to report (default: current year)"),
        month: int | None = month_option("Month to report (1-12, requires --year)"),
        output: Path | None = typer.Option(
            None,
            "--output",
            "-o",
            help="Output path (without extension, default: reports/budget_report_YYYY[-MM])",
        ),
        write: bool = write_option(),
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

        # output is a Path option: ctx.params holds the raw string typer parsed it from,
        # not the Path typer's own argument-binding converts it to, so it's passed
        # explicitly here (the already-converted local variable).
        dispatch(
            cmd_report.run,
            **command_kwargs(ctx, workspace=ws_fn(ctx), output=output),
        )


def register_show(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def show(
        ctx: typer.Context,
        txid: str = txid_option("Transaction ID prefix (8+ characters)", required=True),
    ):
        """Show all stored fields for a single transaction.

        Displays the full projection record for a transaction identified by an
        8+ character ID prefix, including description history, enrichment fields,
        duplicate status, and event metadata.

        Examples:
          gilt show --txid a1b2c3d4
          gilt show -t a1b2c3d4e5f6g7h8
        """
        from gilt.cli.command import show as cmd_show

        dispatch(cmd_show.run, txid=txid, workspace=ws_fn(ctx))


def register_history(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def history(
        ctx: typer.Context,
        pattern: str = typer.Argument(..., help="Substring to search in transaction descriptions"),
        account: str | None = account_option("Restrict to this account ID"),
        include_uncategorized: bool = include_uncategorized_option(
            "Include uncategorized transactions"
        ),
        limit: int = limit_option("Maximum result rows (default 10)", default=10),
        date_from: str | None = date_from_option("Start date (YYYY-MM-DD, inclusive)"),
        date_to: str | None = date_to_option("End date (YYYY-MM-DD, inclusive)"),
    ):
        """Show categorization history for transactions matching a description pattern.

        Groups matching transactions by category/subcategory and displays counts,
        sums, min/max amounts, and the latest date seen. Useful for deciding how to
        categorize a new transaction based on how similar ones were handled before.

        Read-only — no --write flag needed.

        Examples:
          gilt history "EXAMPLE PHARMACY"
          gilt history "ACME" --account MYBANK_CHQ
          gilt history "UTILITY" --include-uncategorized --limit 10
          gilt history "SAMPLE STORE" --date-from 2025-01-01 --date-to 2025-12-31
        """
        from gilt.cli.command import history as cmd_history

        dispatch(cmd_history.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))


def register_note(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def note(
        ctx: typer.Context,
        account: str = account_option(HELP_ACCOUNT_WITH_TX, required=True),
        txid: str | None = txid_option("Transaction ID prefix (TxnID8 as shown in tables)"),
        description: str | None = description_option("Exact description to match (batch mode)"),
        desc_prefix: str | None = desc_prefix_option(
            "Description prefix to match (batch mode, case-insensitive)",
        ),
        pattern: str | None = pattern_option(
            "Regex pattern to match description (batch mode, case-insensitive)",
        ),
        amount: float | None = amount_option("Exact amount to match (batch mode)"),
        note_text: str = typer.Option(
            ..., "--note", "-n", help="Note text to set on the transaction(s)"
        ),
        yes: bool = yes_option(
            "Assume 'yes' for all confirmations in batch mode", extra_opts=("-r",)
        ),
        write: bool = write_option(),
    ):
        """Attach or update notes on transactions in the account ledger.

        Modes:
        - Single: use --txid/-t to target one transaction.
        - Batch: use --description/-d, --desc-prefix/-p, or --pattern (optionally with --amount/-m) to target recurring transactions.

        Safety: dry-run by default. Use --write to persist changes.
        """
        from gilt.cli.command import note as cmd_note

        dispatch(
            cmd_note.run,
            **command_kwargs(ctx, rename={"yes": "assume_yes"}, workspace=ws_fn(ctx)),
        )


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register all reporting commands on *app*."""
    register_ytd(app, ws_fn)
    register_status(app, ws_fn)
    register_summary(app, ws_fn)
    register_budget(app, ws_fn)
    register_report(app, ws_fn)
    register_show(app, ws_fn)
    register_history(app, ws_fn)
    register_note(app, ws_fn)
