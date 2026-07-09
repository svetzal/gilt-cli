from __future__ import annotations

import logging
from pathlib import Path

from gilt.ingest import load_accounts_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.workspace import Workspace

from .accounts_view import display_accounts_table, print_no_accounts

logger = logging.getLogger(__name__)


def _collect_accounts(config_path: Path, data_dir: Path) -> dict[str, str]:
    """Collect account_id -> description from config and existing ledgers.

    - Prefer description from config when available.
    - Include any unmanaged ledgers found under data_dir (fallback description to ID).
    """
    id_to_desc: dict[str, str] = {}

    try:
        accounts = load_accounts_config(config_path)
    except OSError:
        logger.warning("Failed to load accounts config", exc_info=True)
        accounts = []
    for a in accounts:
        aid = getattr(a, "account_id", None)
        if not aid:
            continue
        desc = getattr(a, "description", None)
        if not desc:
            inst = getattr(a, "institution", None) or ""
            prod = getattr(a, "product", None) or ""
            combo = " ".join([s for s in [inst, prod] if s])
            desc = combo or aid
        id_to_desc[aid] = desc

    try:
        for aid in LedgerRepository(data_dir).available_account_ids():
            if aid not in id_to_desc:
                id_to_desc[aid] = aid
    except OSError:
        logger.debug("Could not scan data directory for unmanaged ledgers", exc_info=True)

    return id_to_desc


def run(*, workspace: Workspace) -> int:
    """List available accounts (IDs and descriptions) for use with other commands.

    Read-only; prints a simple table. Returns 0 always.
    """
    mapping = _collect_accounts(workspace.accounts_config, workspace.ledger_data_dir)

    if not mapping:
        print_no_accounts()
        return 0

    display_accounts_table(mapping)
    return 0
