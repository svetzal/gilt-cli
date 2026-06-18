"""Config I/O for ingest: loads accounts configuration from YAML.

Imperative shell — reads from disk.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

try:
    import yaml  # optional; used for local config parsing
except ImportError:  # pragma: no cover
    yaml = None

from gilt.model.account import Account

logger = logging.getLogger(__name__)


def load_accounts_config(path: Path) -> list[Account]:
    """Load accounts config from YAML locally (safe loader).

    Returns a list of Account models. If YAML is unavailable or file missing,
    returns an empty list. No network access is performed.
    """
    accounts: list[Account] = []
    try:
        if yaml is None:
            # Proceed without config
            return accounts
        if not path.exists():
            return accounts
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for item in data.get("accounts") or []:
            try:
                accounts.append(Account.model_validate(item))
            except ValidationError:  # pragma: no cover
                # Skip invalid entries; keep local processing resilient
                continue
    except (yaml.YAMLError, OSError):  # pragma: no cover
        # Swallow and return best-effort empty config
        logger.warning("Failed to load accounts config from %s", path, exc_info=True)
        return accounts
    return accounts
