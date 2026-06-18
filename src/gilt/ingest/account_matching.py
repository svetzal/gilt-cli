"""Pure account matching and normalization planning.

No I/O or side effects.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import Path

from gilt.model.account import Account


def infer_account_for_file(accounts: Sequence[Account], file_path: Path) -> Account | None:
    """Infer which configured account a file likely belongs to.

    Priority:
    1) If accounts are provided, match filename against source_patterns.
    2) If no accounts are available, apply simple filename heuristics as a fallback.
    """
    fname = file_path.name
    # 1) Config-driven matching (match by filename; patterns are name-only, ingest/ is fixed)
    for acct in accounts:
        for pattern in acct.source_patterns or []:
            if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(str(file_path), pattern):
                return acct

    # 2) Heuristic fallback (no config loaded)
    lower = fname.lower()
    if "rbc" in lower and "chequ" in lower:
        return Account(account_id="RBC_CHQ")
    if "scotia" in lower and "current" in lower:
        return Account(account_id="SCOTIA_CURR")
    if "scotia" in lower and "line" in lower:
        return Account(account_id="SCOTIA_LOC")

    return None


def build_normalization_plan(
    inputs: Sequence[Path], output_dir: Path, accounts: Sequence[Account]
) -> list[tuple[Path, str | None]]:
    """Plan which files would be normalized and the target account_id.

    Returns a list of (input_path, account_id_or_none) without performing IO.
    """
    plan: list[tuple[Path, str | None]] = []
    for p in inputs:
        acct = infer_account_for_file(accounts, p)
        plan.append((p, acct.account_id if acct else None))
    return plan
