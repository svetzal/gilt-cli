"""
Import Service - Business logic for CSV file import

Provides account detection, preview, duplicate checking, and import execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from gilt.model.account import Account, Transaction
from gilt.model.ledger_io import load_ledger_csv
from gilt.model.duplicate import DuplicateMatch, TransactionPair
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.transfer.linker import link_transfers
from gilt.ingest import (
    load_accounts_config,
    infer_account_for_file,
    plan_normalization,
    normalize_file,
    parse_file,
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


@dataclass
class CategorizationReviewItem:
    """Item for categorization review."""

    transaction: Transaction
    predicted_category: Optional[str]
    confidence: float
    assigned_category: Optional[str] = None
    assigned_subcategory: Optional[str] = None


class ImportService:
    """Service for handling CSV file imports."""

    def __init__(
        self,
        data_dir: Path,
        accounts_config: Path,
        duplicate_service: Optional[DuplicateService] = None,
        event_sourcing_service: Optional[EventSourcingService] = None,
        smart_category_service: Optional[SmartCategoryService] = None,
    ):
        """
        Initialize the import service.

        Args:
            data_dir: Directory where ledger CSV files are stored
            accounts_config: Path to accounts.yml configuration
            duplicate_service: Optional service for duplicate detection
            event_sourcing_service: Optional service for event sourcing
            smart_category_service: Optional service for smart categorization
        """
        self.data_dir = data_dir
        self.accounts_config = accounts_config
        self.duplicate_service = duplicate_service
        self.event_sourcing_service = event_sourcing_service
        self.smart_category_service = smart_category_service
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
                file_path, encoding="utf-8-sig", dtype=str, keep_default_na=False, nrows=max_rows
            )

            # Convert to list of dicts
            preview = df.to_dict("records")
            return preview, None

        except Exception as e:
            return [], str(e)

    def create_file_mapping(self, file_path: Path, max_preview_rows: int = 5) -> ImportFileMapping:
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

    def count_duplicates(self, file_path: Path, account_id: str) -> Tuple[int, int, Optional[str]]:
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
                existing_ids = set(existing_df["transaction_id"].astype(str))  # noqa: F841

            # For now, return rough estimate
            # In a full implementation, we'd compute transaction IDs for preview
            duplicate_count = 0
            new_count = total_rows

            return new_count, duplicate_count, None

        except Exception as e:
            return 0, 0, str(e)

    def scan_file_for_duplicates(self, file_path: Path, account_id: str) -> List[DuplicateMatch]:
        """
        Scan a file for potential duplicates against existing transactions.

        Args:
            file_path: Path to the CSV file
            account_id: Target account ID

        Returns:
            List of duplicate matches involving transactions from the file
        """
        if not self.duplicate_service:
            return []

        try:
            # 1. Parse file to transactions
            df = parse_file(file_path, account_id)
            new_transactions = []
            for _, row in df.iterrows():
                # Build metadata with source_file info
                metadata = {"source_file": row["source_file"]}

                txn = Transaction(
                    transaction_id=str(row["transaction_id"]),
                    date=datetime.strptime(str(row["date"]), "%Y-%m-%d").date(),
                    description=str(row["description"]),
                    amount=float(row["amount"]),
                    currency=str(row["currency"]),
                    account_id=str(row["account_id"]),
                    counterparty=str(row["counterparty"])
                    if pd.notna(row["counterparty"])
                    else None,
                    category=None,  # Categories not assigned yet
                    subcategory=None,
                    notes=None,
                    source_file=str(row["source_file"]),
                    metadata=metadata,
                )
                new_transactions.append(txn)

            if not new_transactions:
                return []

            # 2. Load existing transactions
            # We use the detector's load_all_transactions which gets everything from projections
            existing_transactions = self.duplicate_service.detector.load_all_transactions(
                self.data_dir
            )

            # 3. Combine (existing + new)
            # Note: We don't filter existing by account because duplicates might be cross-account transfers
            # (though duplicate detector currently enforces same account)
            all_transactions = existing_transactions + new_transactions

            # 4. Find duplicates
            matches = self.duplicate_service.scan_transactions(all_transactions)

            # 5. Filter matches to only those involving new transactions
            new_ids = {t.transaction_id for t in new_transactions}
            relevant_matches = []

            for m in matches:
                if m.pair.txn1_id in new_ids:
                    # txn1 is new, keep as is
                    relevant_matches.append(m)
                elif m.pair.txn2_id in new_ids:
                    # txn2 is new, swap so txn1 is always the new transaction
                    new_pair = TransactionPair(
                        txn1_id=m.pair.txn2_id,
                        txn1_date=m.pair.txn2_date,
                        txn1_description=m.pair.txn2_description,
                        txn1_amount=m.pair.txn2_amount,
                        txn1_account=m.pair.txn2_account,
                        txn1_source_file=m.pair.txn2_source_file,
                        txn2_id=m.pair.txn1_id,
                        txn2_date=m.pair.txn1_date,
                        txn2_description=m.pair.txn1_description,
                        txn2_amount=m.pair.txn1_amount,
                        txn2_account=m.pair.txn1_account,
                        txn2_source_file=m.pair.txn1_source_file,
                    )
                    new_match = m.model_copy(update={"pair": new_pair})
                    relevant_matches.append(new_match)

            return relevant_matches

        except Exception as e:
            print(f"Error scanning for duplicates: {e}")
            return []

    def scan_file_for_categorization(
        self, file_path: Path, account_id: str, exclude_ids: Optional[List[str]] = None
    ) -> List[CategorizationReviewItem]:
        """
        Scan a file for transactions that need categorization.

        Args:
            file_path: Path to the CSV file
            account_id: Target account ID
            exclude_ids: List of transaction IDs to skip (e.g. duplicates)

        Returns:
            List of items for review
        """
        if not self.smart_category_service:
            return []

        try:
            # 1. Parse file to transactions
            df = parse_file(file_path, account_id)
            items = []

            exclude_set = set(exclude_ids) if exclude_ids else set()

            for _, row in df.iterrows():
                txn_id = str(row["transaction_id"])
                if txn_id in exclude_set:
                    continue

                # Build metadata with source_file info
                metadata = {"source_file": row["source_file"]}

                txn = Transaction(
                    transaction_id=txn_id,
                    date=datetime.strptime(str(row["date"]), "%Y-%m-%d").date(),
                    description=str(row["description"]),
                    amount=float(row["amount"]),
                    currency=str(row["currency"]),
                    account_id=str(row["account_id"]),
                    counterparty=str(row["counterparty"])
                    if pd.notna(row["counterparty"])
                    else None,
                    category=None,
                    subcategory=None,
                    notes=None,
                    source_file=str(row["source_file"]),
                    metadata=metadata,
                )

                # Predict category
                predicted_cat, confidence = self.smart_category_service.predict_category(
                    description=txn.description, amount=txn.amount, account=txn.account_id
                )

                items.append(
                    CategorizationReviewItem(
                        transaction=txn,
                        predicted_category=predicted_cat,
                        confidence=confidence,
                        assigned_category=predicted_cat if confidence >= 0.8 else None,
                    )
                )

            return items

        except Exception as e:
            print(f"Error scanning for categorization: {e}")
            return []

    def import_file(
        self,
        file_path: Path,
        account_id: str,
        write: bool = False,
        progress_callback=None,
        exclude_ids: Optional[List[str]] = None,
        categorization_map: Optional[Dict[str, str]] = None,
    ) -> ImportResult:
        """
        Import a CSV file into the specified account's ledger.

        Args:
            file_path: Path to the CSV file
            account_id: Target account ID
            write: If True, actually write changes; if False, dry-run
            progress_callback: Optional callback function for progress updates (0-100)
            exclude_ids: List of transaction IDs to skip (e.g. confirmed duplicates)
            categorization_map: Map of transaction_id -> category to apply

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
                # Get event store if service is available
                event_store = None
                if self.event_sourcing_service:
                    event_store = self.event_sourcing_service.get_event_store()

                ledger_path = normalize_file(
                    file_path,
                    account_id,
                    self.data_dir,
                    event_store=event_store,
                    exclude_ids=exclude_ids,
                    categorization_map=categorization_map,
                )
                messages.append(f"Normalized {file_path.name} to {ledger_path}")

                # Link transfers
                if progress_callback:
                    progress_callback(90)

                linked_count = link_transfers(self.data_dir, write=True)
                if linked_count > 0:
                    messages.append(f"Linked {linked_count} transfers")

            else:
                # Dry-run: just validate
                messages.append(f"DRY-RUN: Would normalize {file_path.name}")
                ledger_path = None

                # Dry-run linking
                linked_count = link_transfers(self.data_dir, write=False)
                if linked_count > 0:
                    messages.append(f"DRY-RUN: Would link {linked_count} transfers")

            if progress_callback:
                progress_callback(100)

            # Get new count
            new_count = self.get_existing_transaction_count(account_id)
            imported = new_count - existing_count

            messages.append(f"Imported {imported} new transactions")

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

    def plan_imports(self, file_paths: List[Path]) -> List[Tuple[Path, Optional[str]]]:
        """
        Plan which files would be imported to which accounts (dry-run).

        Args:
            file_paths: List of file paths to import

        Returns:
            List of (file_path, account_id or None) tuples
        """
        accounts = self.get_accounts()
        return plan_normalization(file_paths, self.data_dir, accounts)
