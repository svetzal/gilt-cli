"""
Workspace - centralized data path resolution for the Finance application.

A Workspace represents the root directory containing all financial data.
All paths (event store, projections, config, etc.) are computed relative
to this root.

Resolution priority:
1. Explicit path (--data-dir CLI option)
2. FINANCE_DATA environment variable
3. Current working directory
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Workspace:
    """Root directory for all financial data paths."""

    root: Path

    @classmethod
    def resolve(cls, explicit: Path | None = None) -> Workspace:
        """Resolve workspace root from explicit path, env var, or CWD.

        Args:
            explicit: Explicitly provided path (highest priority)

        Returns:
            Workspace with resolved root
        """
        if explicit is not None:
            return cls(root=explicit)
        env = os.environ.get("FINANCE_DATA")
        if env:
            return cls(root=Path(env))
        return cls(root=Path.cwd())

    @property
    def event_store_path(self) -> Path:
        return self.root / "data" / "events.db"

    @property
    def projections_path(self) -> Path:
        return self.root / "data" / "projections.db"

    @property
    def budget_projections_path(self) -> Path:
        return self.root / "data" / "budget_projections.db"

    @property
    def ledger_data_dir(self) -> Path:
        return self.root / "data" / "accounts"

    @property
    def ingest_dir(self) -> Path:
        return self.root / "ingest"

    @property
    def categories_config(self) -> Path:
        return self.root / "config" / "categories.yml"

    @property
    def accounts_config(self) -> Path:
        return self.root / "config" / "accounts.yml"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"


__all__ = ["Workspace"]
