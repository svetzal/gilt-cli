"""Events-domain CLI commands: rebuild-projections, backfill-events, migrate-to-events."""

from __future__ import annotations

from pathlib import Path

import typer

HELP_WRITE = "Persist changes (default: dry-run)"


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register event-sourcing commands on *app*."""

    @app.command(name="rebuild-projections")
    def build_projections(
        ctx: typer.Context,
        from_scratch: bool = typer.Option(
            False,
            "--from-scratch",
            help="Delete existing projections and rebuild from all events",
        ),
        incremental: bool = typer.Option(
            False,
            "--incremental",
            help="Only apply new events since last rebuild (default behavior)",
        ),
        events_db: Path | None = typer.Option(
            None, "--events-db", help="Path to events database (advanced override)"
        ),
        projections_db: Path | None = typer.Option(
            None, "--projections-db", help="Path to projections database (advanced override)"
        ),
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
            workspace=ws_fn(ctx),
            from_scratch=from_scratch,
            incremental=incremental,
            events_db=events_db,
            projections_db=projections_db,
        )
        raise typer.Exit(code=code)

    @app.command(name="backfill-events")
    def backfill_events(
        ctx: typer.Context,
        events_db: Path | None = typer.Option(
            None,
            "--event-store",
            help="Path to event store database (advanced override)",
        ),
        projections_db: Path | None = typer.Option(
            None,
            "--projections-db",
            help="Path to transaction projections database (advanced override)",
        ),
        budget_projections_db: Path | None = typer.Option(
            None,
            "--budget-projections-db",
            help="Path to budget projections database (advanced override)",
        ),
        write: bool = typer.Option(
            False, "--write", help="Actually write events (default: dry-run)"
        ),
    ):
        """Backfill events from existing data (advanced/debugging).

        Most users should use 'gilt migrate-to-events --write' instead.

        Examples:
          gilt backfill-events
          gilt backfill-events --write

        Safety: dry-run by default. Use --write to persist events.
        """
        from gilt.cli.command import backfill_events as cmd_backfill_events

        ws = ws_fn(ctx)
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
        events_db: Path | None = typer.Option(
            None, "--event-store", help="Path to event store database (advanced override)"
        ),
        projections_db: Path | None = typer.Option(
            None,
            "--projections-db",
            help="Path to transaction projections database (advanced override)",
        ),
        budget_projections_db: Path | None = typer.Option(
            None,
            "--budget-projections-db",
            help="Path to budget projections database (advanced override)",
        ),
        write: bool = typer.Option(
            False, "--write", help="Actually perform migration (default: dry-run)"
        ),
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

        ws = ws_fn(ctx)
        code = cmd_migrate_to_events.run(
            workspace=ws,
            event_store_path=events_db,
            projections_db_path=projections_db,
            budget_projections_db_path=budget_projections_db,
            write=write,
            force=force,
        )
        raise typer.Exit(code=code)
