"""Initialize a new gilt workspace directory."""

from __future__ import annotations

from gilt.workspace import Workspace

from .util import console

_STARTER_ACCOUNTS_YML = """\
# Accounts configuration
# Define your bank accounts here so the ingest command can route raw CSVs.
#
# Example:
#   accounts:
#     - account_id: MYBANK_CHQ
#       institution: MyBank
#       product: Chequing
#       currency: CAD
#       description: MyBank Chequing
#       nature: asset          # asset or liability
#       source_patterns:
#         - '*mybank*chequing*.csv'
#       import_hints:
#         date_format: auto
#         decimal: .
#         thousands: ','
#         amount_sign: expenses_negative
#         possible_columns:
#           date: [Date, Transaction Date, Posted Date]
#           description: [Description, Memo, Details]
#           amount: [Amount]
#           currency: [Currency]

accounts: []
"""

_STARTER_CATEGORIES_YML = """\
# Category definitions
# Define your spending categories here. Use 'gilt category --add' to manage them,
# or edit this file directly.
#
# Example:
#   categories:
#     - name: Housing
#       description: Housing expenses
#       subcategories:
#         - name: Mortgage
#         - name: Utilities
#       budget:
#         amount: 2500.00
#         period: monthly

categories: []
"""


def run(*, workspace: Workspace) -> int:
    """Initialize a new gilt workspace with required directories and starter config.

    Creates the directory structure and starter configuration files.
    Skips anything that already exists (safe to run on an existing workspace).

    Args:
        workspace: Workspace to initialize

    Returns:
        Exit code (0 = success)
    """
    root = workspace.root
    console.print(f"[bold cyan]Initializing workspace:[/] {root}\n")

    created_dirs = []
    created_files = []
    skipped = []

    # Create directories
    for directory in [
        workspace.ledger_data_dir,  # data/accounts/
        workspace.ingest_dir,  # ingest/
        workspace.reports_dir,  # reports/
        root / "config",  # config/
    ]:
        if directory.exists():
            skipped.append(str(directory.relative_to(root)) + "/")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(directory.relative_to(root)) + "/")

    # Create starter config files
    config_files = [
        (workspace.accounts_config, _STARTER_ACCOUNTS_YML),
        (workspace.categories_config, _STARTER_CATEGORIES_YML),
    ]

    for path, content in config_files:
        if path.exists():
            skipped.append(str(path.relative_to(root)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created_files.append(str(path.relative_to(root)))

    # Report results
    if created_dirs or created_files:
        console.print("[green]Created:[/]")
        for d in created_dirs:
            console.print(f"  {d}")
        for f in created_files:
            console.print(f"  {f}")

    if skipped:
        console.print("[dim]Already exists (skipped):[/dim]")
        for s in skipped:
            console.print(f"  [dim]{s}[/dim]")

    if not created_dirs and not created_files:
        console.print("[green]Workspace already fully initialized.[/]")
    else:
        console.print(f"\n[green]Workspace ready at {root}[/]")
        console.print("\n[dim]Next steps:[/dim]")
        console.print("  1. Edit config/accounts.yml to define your bank accounts")
        console.print("  2. Drop raw bank CSVs into ingest/")
        console.print("  3. Run: gilt ingest --write")
        console.print("  4. Run: gilt migrate-to-events --write")

    return 0
