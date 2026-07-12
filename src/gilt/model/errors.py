"""Domain error hierarchy for Gilt data loading failures.

These exceptions are raised at data-loading boundaries when inputs are invalid
or unreadable. They carry the offending path so callers can display a meaningful
message without re-parsing the exception chain.

No local imports — this module is a leaf with no dependencies on other gilt modules.
"""

from __future__ import annotations

from pathlib import Path


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


__all__ = [
    "GiltDataError",
    "ConfigLoadError",
    "LedgerLoadError",
    "IntelligenceCacheError",
]
