"""Single declaration site for CLI flag identity.

Each factory here owns a flag's long name, short flag, Python type, and any
min/max constraints. Registration modules call these factories and supply only
the per-command ``help`` text (and, where relevant, a ``required``/``default``
override) — they never restate ``"--account"``, ``"-a"``, etc. inline.

Flags that appear exactly once across ``registration/*.py`` stay declared inline
in their own module (YAGNI) — this module holds only flags shared by two or
more commands.
"""

from __future__ import annotations

import typer

HELP_WRITE = "Persist changes (default: dry-run)"
HELP_ACCOUNT_DISPLAY = "Account ID to display (e.g., MYBANK_CHQ)"
HELP_ACCOUNT_WITH_TX = "Account ID containing the transaction (e.g., MYBANK_CHQ)"


def write_option(help: str = HELP_WRITE):
    return typer.Option(False, "--write", help=help)


def account_option(help: str, *, required: bool = False):
    default = ... if required else None
    return typer.Option(default, "--account", "-a", help=help)


def year_option(help: str):
    return typer.Option(None, "--year", "-y", help=help)


def txid_option(help: str, *, required: bool = False):
    default = ... if required else None
    return typer.Option(default, "--txid", "-t", help=help)


def limit_option(help: str, *, default: int | None = None, min: int | None = None):
    return typer.Option(default, "--limit", "-n", min=min, help=help)


def fy_option(help: str):
    return typer.Option(None, "--fy", help=help)


def category_option(help: str, *, default: str | None = None):
    return typer.Option(default, "--category", "-c", help=help)


def projections_db_option(help: str):
    return typer.Option(None, "--projections-db", help=help)


def event_store_option(help: str = "Path to event store database (advanced override)"):
    return typer.Option(None, "--event-store", help=help)


def budget_projections_db_option(
    help: str = "Path to budget projections database (advanced override)",
):
    return typer.Option(None, "--budget-projections-db", help=help)


def pattern_option(help: str):
    return typer.Option(None, "--pattern", help=help)


def interactive_option(help: str):
    return typer.Option(False, "--interactive", "-i", help=help)


def force_option(help: str):
    return typer.Option(False, "--force", help=help)


def description_option(help: str, *, short: str | None = "-d"):
    opts = ("--description", *((short,) if short else ()))
    return typer.Option(None, *opts, help=help)


def desc_prefix_option(help: str):
    return typer.Option(None, "--desc-prefix", "-p", help=help)


def amount_option(help: str, *, short: str | None = "-m"):
    opts = ("--amount", *((short,) if short else ()))
    return typer.Option(None, *opts, help=help)


def yes_option(help: str, *, extra_opts: tuple[str, ...] = ()):
    return typer.Option(False, "--yes", "-y", *extra_opts, help=help)


def month_option(help: str):
    return typer.Option(None, "--month", "-m", help=help)


def min_confidence_option(
    help: str,
    *,
    default: float = 0.0,
    min: float | None = None,
    max: float | None = None,
):
    return typer.Option(default, "--min-confidence", min=min, max=max, help=help)


def include_uncategorized_option(help: str):
    return typer.Option(False, "--include-uncategorized", help=help)


def date_from_option(help: str):
    return typer.Option(None, "--date-from", help=help)


def date_to_option(help: str):
    return typer.Option(None, "--date-to", help=help)


__all__ = [
    "HELP_ACCOUNT_DISPLAY",
    "HELP_ACCOUNT_WITH_TX",
    "HELP_WRITE",
    "account_option",
    "amount_option",
    "budget_projections_db_option",
    "category_option",
    "date_from_option",
    "date_to_option",
    "desc_prefix_option",
    "description_option",
    "event_store_option",
    "force_option",
    "fy_option",
    "include_uncategorized_option",
    "interactive_option",
    "limit_option",
    "min_confidence_option",
    "month_option",
    "pattern_option",
    "projections_db_option",
    "txid_option",
    "write_option",
    "year_option",
    "yes_option",
]
