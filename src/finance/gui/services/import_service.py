from __future__ import annotations

"""
Import Service - Business logic for CSV file import

Provides account detection, preview, duplicate checking, and import execution.
"""

from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import date

import pandas as pd

from finance.model.account import Account, TransactionGroup
from finance.model.ledger_io import load_ledger_csv
from finance.ingest import (
    load_accounts_config,
    infer_account_for_file,
    plan_normalization,
    normalize_file,
)


@dataclass
class FileInfo:
    """Information about a selected file."""
    path: Path
    name: str
    size: int  # bytes
    modified_date: date


@dataclass
class ImportFileMapping:
    """Mapping of a file to an account."""
    file_info: FileInfo
    detected_account: Optional[Account]
    selected_account_id: Optional[str]  # User can override
    preview_rows: List[Dict[str, Any]]  # First few rows of parsed data
    error: Optional[str] = None


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    imported_count: int
    duplicate_count: int
    error_count: int
    messages: List[str]
    ledger_path: Optional[Path] = None


class ImportService:
    """Service for handling CSV file imports."""

    def __init__(self, data_dir: Path, accounts_config: Path):
        """
        Initialize the import service.

        Args:
            data_dir: Directory where ledger CSV files are stored
            accounts_config: Path to accounts.yml configuration
        """
        self.data_dir = data_dir
        self.accounts_config = accounts_config
        self._accounts_cache: Optional[List[Account]] = None

    def get_accounts(self) -> List[Account]:
        """
        Get list of configured accounts.

        Returns:
            List of Account objects
        """
        if self._accounts_cache is None:
            self._accounts_cache = load_accounts_config(self.accounts_config)
        return self._accounts_cache

    def clear_accounts_cache(self):
        """Clear cached accounts (force reload on next access)."""
        self._accounts_cache = None

    def get_file_info(self, file_path: Path) -> FileInfo:
        """
        Get information about a file.

        Args:
            file_path: Path to the file

        Returns:
            FileInfo object
        """
        stat = file_path.stat()
        modified = date.fromtimestamp(stat.st_mtime)

        return FileInfo(
            path=file_path,
            name=file_path.name,
            size=stat.st_size,
            modified_date=modified,
        )

    def detect_account(self, file_path: Path) -> Optional[Account]:
        """
        Detect which account a file belongs to based on source patterns.

        Args:
            file_path: Path to the CSV file

        Returns:
            Account object if detected, None otherwise
        """
        accounts = self.get_accounts()
        return infer_account_for_file(accounts, file_path)

    def preview_file(
        self, file_path: Path, account_id: Optional[str] = None, max_rows: int = 10
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Preview the contents of a CSV file.

        Args:
            file_path: Path to the CSV file
            account_id: Optional account ID (for context)
            max_rows: Maximum number of rows to return

        Returns:
            Tuple of (preview rows, error message if any)
        """
        try:
            # Read first few rows
            df = pd.read_csv(
                file_path,
                encoding="utf-8-sig",
                dtype=str,
                keep_default_na=False,
                nrows=max_rows
            )

            # Convert to list of dicts
            preview = df.to_dict("records")
            return preview, None

        except Exception as e:
            return [], str(e)

    def create_file_mapping(
        self, file_path: Path, max_preview_rows: int = 5
    ) -> ImportFileMapping:
        """
        Create a mapping for a file with account detection and preview.

        Args:
            file_path: Path to the CSV file
            max_preview_rows: Number of rows to preview

        Returns:
            ImportFileMapping object
        """
        file_info = self.get_file_info(file_path)
        detected_account = self.detect_account(file_path)
        preview_rows, error = self.preview_file(file_path, max_rows=max_preview_rows)

        return ImportFileMapping(
            file_info=file_info,
            detected_account=detected_account,
            selected_account_id=detected_account.account_id if detected_account else None,
            preview_rows=preview_rows,
            error=error,
        )

    def get_existing_transaction_count(self, account_id: str) -> int:
        """
        Get the number of existing transactions for an account.

        Args:
            account_id: Account ID

        Returns:
            Count of existing transactions
        """
        ledger_path = self.data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            return 0

        try:
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text)
            return len(groups)
        except Exception:
            return 0

    def count_duplicates(
        self, file_path: Path, account_id: str
    ) -> Tuple[int, int, Optional[str]]:
        """
        Count how many transactions in the file are duplicates vs. new.

        Args:
            file_path: Path to the CSV file
            account_id: Target account ID

        Returns:
            Tuple of (new_count, duplicate_count, error message if any)
        """
        try:
            # Read the file and normalize it in memory (dry-run style)
            # This is a simplified version - in reality, we'd need to parse like normalize_file does
            df = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
            total_rows = len(df)

            # Get existing transaction IDs
            ledger_path = self.data_dir / f"{account_id}.csv"
            existing_ids = set()
            if ledger_path.exists():
                existing_df = pd.read_csv(ledger_path)
                existing_ids = set(existing_df["transaction_id"].astype(str))

            # For now, return rough estimate
            # In a full implementation, we'd compute transaction IDs for preview
            duplicate_count = 0
            new_count = total_rows

            return new_count, duplicate_count, None

        except Exception as e:
            return 0, 0, str(e)

    def import_file(
        self,
        file_path: Path,
        account_id: str,
        write: bool = False,
        progress_callback=None,
    ) -> ImportResult:
        """
        Import a CSV file into the specified account's ledger.

        Args:
            file_path: Path to the CSV file
            account_id: Target account ID
            write: If True, actually write changes; if False, dry-run
            progress_callback: Optional callback function for progress updates (0-100)

        Returns:
            ImportResult object
        """
        messages = []

        try:
            if progress_callback:
                progress_callback(10)

            # Get existing count
            existing_count = self.get_existing_transaction_count(account_id)
            messages.append(f"Account {account_id} has {existing_count} existing transactions")

            if progress_callback:
                progress_callback(30)

            # Perform normalization
            if write:
                ledger_path = normalize_file(file_path, account_id, self.data_dir)
                messages.append(f"Normalized {file_path.name} to {ledger_path}")
            else:
                # Dry-run: just validate
                messages.append(f"DRY-RUN: Would normalize {file_path.name}")
                ledger_path = None

            if progress_callback:
                progress_callback(80)

            # Get new count
            new_count = self.get_existing_transaction_count(account_id)
            imported = new_count - existing_count

            messages.append(f"Imported {imported} new transactions")

            if progress_callback:
                progress_callback(100)

            return ImportResult(
                success=True,
                imported_count=imported,
                duplicate_count=0,  # normalize_file handles this internally
                error_count=0,
                messages=messages,
                ledger_path=ledger_path,
            )

        except Exception as e:
            return ImportResult(
                success=False,
                imported_count=0,
                duplicate_count=0,
                error_count=1,
                messages=[str(e)],
            )

    def plan_imports(
        self, file_paths: List[Path]
    ) -> List[Tuple[Path, Optional[str]]]:
        """
        Plan which files would be imported to which accounts (dry-run).

        Args:
            file_paths: List of file paths to import

        Returns:
            List of (file_path, account_id or None) tuples
        """
        accounts = self.get_accounts()
        return plan_normalization(file_paths, self.data_dir, accounts)
