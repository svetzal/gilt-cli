"""Config I/O for ingest: loads accounts configuration from YAML.

Imperative shell — reads from disk.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

try:
    import yaml  # optional; used for local config parsing
except ImportError:  # pragma: no cover
    yaml = None

from gilt.model.account import Account
from gilt.model.errors import ConfigLoadError


def load_accounts_config(path: Path) -> list[Account]:
    """Load accounts config from YAML locally (safe loader).

    Returns a list of Account models. Returns an empty list only when YAML is
    unavailable (library import failed) or the file does not exist. Raises
    ConfigLoadError for any file-level parse failure or per-entry validation
    failure so callers cannot silently receive incomplete data from a corrupt
    config. No network access is performed.

    Raises:
        ConfigLoadError: If the file exists but cannot be parsed, or if any
            account entry fails Pydantic validation.
    """
    if yaml is None:
        # Proceed without config
        return []
    if not path.exists():
        return []

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError) as exc:
        raise ConfigLoadError(path) from exc

    accounts: list[Account] = []
    for item in data.get("accounts") or []:
        try:
            accounts.append(Account.model_validate(item))
        except ValidationError as exc:
            raise ConfigLoadError(path) from exc

    return accounts
