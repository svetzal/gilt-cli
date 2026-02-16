"""
Ingestion service - functional core for file discovery and ingestion planning.

This service extracts ingestion planning logic from CLI commands,
making it testable without UI dependencies. It handles:
- File discovery based on account patterns
- Account matching for source files
- Ingestion planning (mapping files to accounts)

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
The actual file normalization (I/O) remains in the imperative shell.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gilt.model.account import Account


@dataclass
class IngestionPlan:
    """Plan for an ingestion operation.

    Contains files matched to accounts, unmatched files, and totals.
    """

    files: list[tuple[Path, Optional[str]]]  # [(file_path, account_id or None)]
    unmatched: list[Path]  # Files that couldn't be matched to any account
    total_files: int  # Total number of files discovered


class IngestionService:
    """Service for planning file ingestion operations.

    This service handles the functional core of ingestion:
    - Discovering CSV files based on account patterns
    - Matching files to accounts
    - Planning which files should be normalized to which accounts

    The actual normalization (reading/writing CSVs) remains in the imperative shell.
    """

    def __init__(self, accounts: list[Account]):
        """Initialize the ingestion service.

        Args:
            accounts: List of configured accounts with source patterns
        """
        self._accounts = accounts

    def discover_inputs(self, ingest_dir: Path) -> list[Path]:
        """Discover candidate input CSV files based on account patterns.

        If accounts have source_patterns, discover files matching those patterns.
        If no patterns are defined, discover all *.csv files in the directory.

        Args:
            ingest_dir: Directory containing source CSV files

        Returns:
            Sorted list of discovered CSV file paths
        """
        patterns: list[str] = []
        for acct in self._accounts:
            patterns.extend(acct.source_patterns or [])

        if not patterns:
            # No patterns defined - discover all CSV files
            return sorted(ingest_dir.glob("*.csv"))

        # Use patterns to discover files
        seen = set()
        inputs: list[Path] = []
        for pat in patterns:
            for p in ingest_dir.glob(pat):
                if p not in seen:
                    inputs.append(p)
                    seen.add(p)
        return sorted(inputs)

    def match_file_to_account(self, file_path: Path) -> Optional[str]:
        """Determine which account a file belongs to.

        Matches the filename against configured account source_patterns.
        If no match is found, attempts simple heuristic matching as fallback.

        Args:
            file_path: Path to the CSV file to match

        Returns:
            The account_id if a match is found, None otherwise
        """
        fname = file_path.name

        # 1) Config-driven matching (match by filename pattern)
        for acct in self._accounts:
            for pattern in acct.source_patterns or []:
                if fnmatch.fnmatch(fname, pattern) or fnmatch.fnmatch(
                    str(file_path), pattern
                ):
                    return acct.account_id

        return None

    def plan_ingestion(self, ingest_dir: Path) -> IngestionPlan:
        """Plan which files should be normalized to which accounts.

        Discovers all input files and maps each to its target account.
        Files that can't be matched are tracked as unmatched.

        Args:
            ingest_dir: Directory containing source CSV files

        Returns:
            IngestionPlan containing matched files, unmatched files, and totals
        """
        inputs = self.discover_inputs(ingest_dir)

        files: list[tuple[Path, Optional[str]]] = []
        unmatched: list[Path] = []

        for file_path in inputs:
            account_id = self.match_file_to_account(file_path)
            files.append((file_path, account_id))
            if account_id is None:
                unmatched.append(file_path)

        return IngestionPlan(
            files=files,
            unmatched=unmatched,
            total_files=len(inputs),
        )


__all__ = [
    "IngestionPlan",
    "IngestionService",
]
