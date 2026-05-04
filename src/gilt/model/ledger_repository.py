from __future__ import annotations

import logging
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv

logger = logging.getLogger(__name__)

LEDGER_IO_ERRORS: tuple[type[Exception], ...] = (OSError, ValueError, UnicodeDecodeError)


class LedgerRepository:
    """Gateway for all per-account CSV ledger I/O.

    Centralizes path resolution, file encoding, error handling,
    and the load_ledger_csv/dump_ledger_csv protocol.
    """

    def __init__(self, data_dir: Path, *, default_currency: str = "CAD"):
        self._data_dir = data_dir
        self._default_currency = default_currency

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def ledger_path(self, account_id: str) -> Path:
        return self._data_dir / f"{account_id}.csv"

    def exists(self, account_id: str) -> bool:
        return self.ledger_path(account_id).exists()

    def load(self, account_id: str) -> list[TransactionGroup]:
        """Load transaction groups for a single account.

        Returns empty list if the ledger file doesn't exist.
        Raises ValueError/UnicodeDecodeError on parse failure.
        """
        path = self.ledger_path(account_id)
        if not path.exists():
            return []
        text = path.read_text(encoding="utf-8")
        return load_ledger_csv(text, default_currency=self._default_currency)

    def save(self, account_id: str, groups: list[TransactionGroup]) -> None:
        """Write transaction groups to the account's CSV ledger."""
        path = self.ledger_path(account_id)
        path.write_text(dump_ledger_csv(groups), encoding="utf-8")

    def ledger_paths(self) -> list[Path]:
        """Return sorted list of all CSV ledger paths in the data directory."""
        if not self._data_dir.exists():
            return []
        return sorted(self._data_dir.glob("*.csv"))

    def load_all_raw_texts(self) -> dict[str, str]:
        """Return mapping of filename to raw UTF-8 text for all ledger CSVs."""
        return {p.name: p.read_text(encoding="utf-8") for p in self.ledger_paths()}

    def load_all(self) -> list[TransactionGroup]:
        """Load and combine all CSV ledger files from the data directory.

        Returns empty list if directory doesn't exist. Silently skips
        files that fail to parse.
        """
        all_groups: list[TransactionGroup] = []
        for ledger_path in self.ledger_paths():
            try:
                text = ledger_path.read_text(encoding="utf-8")
                all_groups.extend(load_ledger_csv(text, default_currency=self._default_currency))
            except LEDGER_IO_ERRORS:
                logger.warning("Skipping unparseable ledger file: %s", ledger_path)
                continue
        return all_groups

    def available_account_ids(self) -> list[str]:
        """Return sorted list of account IDs that have ledger files."""
        return [p.stem for p in self.ledger_paths()]


__all__ = ["LedgerRepository", "LEDGER_IO_ERRORS"]
