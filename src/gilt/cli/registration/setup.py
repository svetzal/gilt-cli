"""Setup-domain CLI commands: init, accounts, categories, category, skill-init."""

from __future__ import annotations

import typer

from gilt.cli.registration._dispatch import command_kwargs, dispatch
from gilt.cli.registration._options import (
    amount_option,
    description_option,
    force_option,
    write_option,
)


def register(app: typer.Typer, ws_fn) -> None:  # type: ignore[type-arg]
    """Register setup commands on *app*. *ws_fn* is the ``_ws`` helper from app.py."""

    @app.command(name="skill-init")
    def skill_init(
        ctx: typer.Context,
        global_install: bool = typer.Option(
            False, "--global", help="Install to ~/.claude/skills/gilt/ (global)"
        ),
        force: bool = force_option(
            "Bypass version guard (overrides the refusal to overwrite a newer installed version)",
        ),
        json_output: bool = typer.Option(
            False, "--json", help="Emit machine-readable JSON output to stdout"
        ),
    ):
        """Install gilt skill files for Claude Code.

        Copies the gilt skill definition and command reference to .claude/skills/gilt/
        in the current directory (or globally with --global). Stamps the package version
        into the installed SKILL.md frontmatter.

        A version guard prevents overwriting a newer installed version unless --force is used.
        Use --force to downgrade or overwrite a newer installed version.

        Examples:
          gilt skill-init
          gilt skill-init --global
          gilt skill-init --force
          gilt skill-init --json
        """
        from gilt.cli.command import skill_init as cmd_skill_init

        dispatch(cmd_skill_init.run, **command_kwargs(ctx))

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

        dispatch(cmd_init.run, workspace=ws_fn(ctx))

    @app.command()
    def accounts(ctx: typer.Context):
        """List available accounts (IDs and descriptions)."""
        from gilt.cli.command import accounts as cmd_accounts

        dispatch(cmd_accounts.run, workspace=ws_fn(ctx))

    @app.command()
    def categories(ctx: typer.Context):
        """List all defined categories with usage statistics."""
        from gilt.cli.command import categories as cmd_categories

        dispatch(cmd_categories.run, workspace=ws_fn(ctx))

    @app.command()
    def category(
        ctx: typer.Context,
        add: str | None = typer.Option(
            None, "--add", help="Add a new category (supports 'Category:Subcategory')"
        ),
        remove: str | None = typer.Option(None, "--remove", help="Remove a category"),
        set_budget: str | None = typer.Option(
            None, "--set-budget", help="Set budget for a category"
        ),
        description: str | None = description_option("Description for new category", short=None),
        amount: float | None = amount_option("Budget amount", short=None),
        period: str = typer.Option("monthly", "--period", help="Budget period (monthly or yearly)"),
        force: bool = force_option("Skip confirmations when removing used categories"),
        write: bool = write_option(),
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

        dispatch(cmd_category.run, **command_kwargs(ctx, workspace=ws_fn(ctx)))
