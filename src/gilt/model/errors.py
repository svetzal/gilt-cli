"""Domain error hierarchy for Gilt data loading failures.

These exceptions are raised at data-loading boundaries when inputs are invalid
or unreadable. They carry the offending path so callers can display a meaningful
message without re-parsing the exception chain.

No local imports — this module is a leaf with no dependencies on other *gilt*
modules (third-party libraries such as ``yaml`` are fine).
"""

from __future__ import annotations

from pathlib import Path

import yaml


class GiltDataError(Exception):
    """Base class for all Gilt data loading errors.

    All subclasses carry the offending ``path`` and set ``str(exc)`` to a
    message that names the path, so CLI/GUI boundaries can surface it directly.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(str(path))


class ConfigLoadError(GiltDataError):
    """Raised when a configuration file cannot be loaded or parsed."""


class LedgerLoadError(GiltDataError):
    """Raised when a ledger CSV file cannot be loaded or parsed."""


class IntelligenceCacheError(GiltDataError):
    """Raised when the intelligence cache file cannot be read or parsed."""


# Canonical "recoverable data read/parse failure" vocabulary. Callers at I/O
# boundaries catch these instead of hand-rolling equivalent tuples. UnicodeDecodeError
# and json.JSONDecodeError are ValueError subclasses and are listed here (or omitted
# at a given call site) for readability, not necessity.
DATA_IO_ERRORS: tuple[type[Exception], ...] = (OSError, ValueError, UnicodeDecodeError)

# For YAML config load/save boundaries, where a malformed document raises yaml.YAMLError
# in addition to the DATA_IO_ERRORS set. RuntimeError is included because
# CategoryService.save_categories (gilt.gui.services.category_service) raises it when
# called before categories have been loaded.
CONFIG_IO_ERRORS: tuple[type[Exception], ...] = DATA_IO_ERRORS + (yaml.YAMLError, RuntimeError)

# Alias kept for the ledger I/O boundary; identical to DATA_IO_ERRORS.
LEDGER_IO_ERRORS: tuple[type[Exception], ...] = DATA_IO_ERRORS


__all__ = [
    "GiltDataError",
    "ConfigLoadError",
    "LedgerLoadError",
    "IntelligenceCacheError",
    "DATA_IO_ERRORS",
    "CONFIG_IO_ERRORS",
    "LEDGER_IO_ERRORS",
]
