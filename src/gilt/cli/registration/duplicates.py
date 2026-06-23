"""Duplicates-domain CLI commands: duplicates, mark-duplicate, diagnose-duplicates,
audit-ml, prompt-stats."""

from __future__ import annotations

import typer

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.cli.registration._dispatch import HELP_WRITE, dispatch


def register_duplicates(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command()
    def duplicates(
        ctx: typer.Context,
        model: str = typer.Option(
            DEFAULT_OLLAMA_MODEL, "--model", help="Ollama model for LLM duplicate detection"
        ),
        max_days_apart: int = typer.Option(
            1, "--max-days", help="Maximum days between potential duplicates"
        ),
        amount_tolerance: float = typer.Option(
            0.001, "--amount-tolerance", help="Acceptable difference in amounts"
        ),
        min_confidence: float = typer.Option(
            0.0, "--min-confidence", help="Minimum confidence threshold to display (0.0-1.0)"
        ),
        interactive: bool = typer.Option(
            False,
            "--interactive",
            "-i",
            help="Enable interactive mode to confirm/deny each duplicate",
        ),
        use_llm: bool = typer.Option(
            False, "--llm", help="Use LLM instead of ML (slower, no training needed)"
        ),
    ):
        """Scan ledgers for duplicate transactions using ML or LLM analysis.

        By default, uses fast ML-based classification trained on your feedback.
        Falls back to LLM if insufficient training data (<10 examples).

        Examples:
          gilt duplicates
          gilt duplicates --llm
          gilt duplicates --interactive
          gilt duplicates -i --min-confidence 0.7
          gilt duplicates --llm --model qwen3.6:35b-a3b-coding-nvfp4

        Note: LLM mode requires Ollama with specified model installed locally.
        """
        from gilt.cli.command import duplicates as cmd_duplicates

        dispatch(
            cmd_duplicates.run,
            workspace=ws_fn(ctx),
            model=model,
            max_days_apart=max_days_apart,
            amount_tolerance=amount_tolerance,
            min_confidence=min_confidence,
            interactive=interactive,
            use_llm=use_llm,
        )


def register_mark_duplicate(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="mark-duplicate")
    def mark_duplicate(
        ctx: typer.Context,
        primary_txid: str = typer.Option(
            ..., "--primary", "-p", help="Transaction ID to keep (8+ char prefix)"
        ),
        duplicate_txid: str = typer.Option(
            ..., "--duplicate", "-d", help="Transaction ID to mark as duplicate (8+ char prefix)"
        ),
        write: bool = typer.Option(False, "--write", help=HELP_WRITE),
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

        dispatch(
            cmd_mark_duplicate.run,
            primary_txid=primary_txid,
            duplicate_txid=duplicate_txid,
            workspace=ws_fn(ctx),
            write=write,
        )


def register_diagnose_duplicates(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="diagnose-duplicates")
    def diagnose_duplicates(ctx: typer.Context):
        """Diagnose duplicate-projection issues.

        Scans the projections database and reports orphan duplicate groups,
        stale primary references, and self-referential primaries.

        Examples:
          gilt diagnose-duplicates
        """
        from gilt.cli.command import diagnose_duplicates as cmd_diagnose_duplicates

        dispatch(cmd_diagnose_duplicates.run, workspace=ws_fn(ctx))


def register_audit_ml(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="audit-ml")
    def audit_ml(
        ctx: typer.Context,
        mode: str = typer.Option(
            "summary",
            "--mode",
            "-m",
            help="Audit mode: summary, training, predictions, or features",
        ),
        filter_pattern: str | None = typer.Option(
            None, "--filter", "-f", help="Regex pattern to filter descriptions"
        ),
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

        dispatch(
            cmd_audit_ml.run,
            workspace=ws_fn(ctx),
            mode=mode,
            filter_pattern=filter_pattern,
            limit=limit,
        )


def register_prompt_stats(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    @app.command(name="prompt-stats")
    def prompt_stats(
        ctx: typer.Context,
        generate_update: bool = typer.Option(
            False,
            "--generate-update",
            "-g",
            help="Generate a new PromptUpdated event based on learned patterns",
        ),
    ):
        """Show prompt learning statistics and generate updates.

        Examples:
          gilt prompt-stats
          gilt prompt-stats --generate-update

        Note: Requires interactive duplicate detection feedback (gilt duplicates --interactive).
        """
        from gilt.cli.command import prompt_stats as cmd_prompt_stats

        code = cmd_prompt_stats.run(
            workspace=ws_fn(ctx),
            generate_update=generate_update,
        )
        raise typer.Exit(code=code)


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register duplicate-management commands on *app*."""
    register_duplicates(app, ws_fn)
    register_mark_duplicate(app, ws_fn)
    register_diagnose_duplicates(app, ws_fn)
    register_audit_ml(app, ws_fn)
    register_prompt_stats(app, ws_fn)
