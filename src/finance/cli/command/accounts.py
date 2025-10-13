from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from rich.table import Table

from .util import console
from finance.ingest import load_accounts_config


def _collect_accounts(config_path: Path, data_dir: Path) -> Dict[str, str]:
    """Collect account_id -> description from config and existing ledgers.

    - Prefer description from config when available.
    - Include any unmanaged ledgers found under data_dir (fallback description to ID).
    """
    id_to_desc: Dict[str, str] = {}

    # 1) Configured accounts (best-effort)
    try:
        accounts = load_accounts_config(config_path)
    except Exception:
        accounts = []
    for a in accounts:
        aid = getattr(a, "account_id", None)
        if not aid:
            continue
        desc = getattr(a, "description", None)
        # If description missing, try a friendly composite
        if not desc:
            inst = getattr(a, "institution", None) or ""
            prod = getattr(a, "product", None) or ""
            combo = " ".join([s for s in [inst, prod] if s])
            desc = combo or aid
        id_to_desc[aid] = desc

    # 2) Unmanaged ledgers present on disk
    try:
        for p in sorted((data_dir or Path("data/accounts")).glob("*.csv")):
            aid = p.stem
            if aid not in id_to_desc:
                id_to_desc[aid] = aid
    except Exception:
        # Be resilient if directory doesn't exist or is unreadable
        pass

    return id_to_desc


def run(*, config: Path = Path("config/accounts.yml"), data_dir: Path = Path("data/accounts")) -> int:
    """List available accounts (IDs and descriptions) for use with other commands.

    Read-only; prints a simple table. Returns 0 always.
    """
    mapping = _collect_accounts(config, data_dir)

    if not mapping:
        console.print("[yellow]No accounts found.[/] Add entries to config/accounts.yml or ingest ledgers under data/accounts/.")
        return 0

    table = Table(title="Available Accounts", show_lines=False)
    table.add_column("Account ID", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    for aid in sorted(mapping.keys()):
        table.add_row(aid, mapping[aid])

    console.print(table)
    return 0
