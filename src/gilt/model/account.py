from __future__ import annotations

"""
Canonical data models for Finance workflows (review draft).

Scope
- Pure Pydantic v2 models; no I/O, no CLI integration yet.
- Mirrors current config/accounts.yml for Account.
- Proposes ledger-oriented models to represent transactions and split transactions,
  allowing clean grouping of related rows as transaction sets.

Privacy
- These models hold metadata fields but do not perform any network I/O.
- Keep usage local. Do not log raw descriptions externally.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import json

from pydantic import BaseModel, Field, computed_field, model_validator


# ------------------------------
# Accounts (mirrors config file)
# ------------------------------


class ImportHints(BaseModel):
    """Hints for CSV ingestion; mirrors the shape in config/accounts.yml.

    This structure is intentionally loose and optional; it's a guide rather than
    a strict schema. Values may be refined later.
    """

    date_format: Optional[str] = Field(default="auto", description="Date parsing format or 'auto'.")
    decimal: Optional[str] = Field(default=".")
    thousands: Optional[str] = Field(default=",")
    amount_sign: Optional[str] = Field(default="expenses_negative")
    possible_columns: Optional[Dict[str, List[str]]] = None


class AccountNature(str, Enum):
    asset = "asset"
    liability = "liability"


class Account(BaseModel):
    """Account definition aligned with config/accounts.yml entries.

    Fields intentionally match current config; we can evolve this later without
    breaking callers by keeping defaults optional.
    """

    account_id: str
    institution: Optional[str] = None
    product: Optional[str] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    source_patterns: Optional[List[str]] = None
    import_hints: Optional[ImportHints] = None
    nature: AccountNature = Field(
        default=AccountNature.asset,
        description="Account nature for sign semantics: asset or liability (credit)",
    )


# -----------------------------------------
# Ledger transactions and grouping proposals
# -----------------------------------------


class Transaction(BaseModel):
    """Standardized per-ledger transaction (one row in data/accounts/{ACCOUNT}.csv).

    Mirrors the current processed schema. Optional fields remain None unless
    populated by downstream enrichment steps.
    """

    transaction_id: str
    date: date
    description: str = ""
    amount: float
    currency: str = "CAD"
    account_id: str
    counterparty: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    notes: Optional[str] = None
    source_file: Optional[str] = None
    vendor: Optional[str] = None
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Freeform, local-only metadata"
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_debit(self) -> bool:
        return self.amount < 0

    @computed_field  # type: ignore[misc]
    @property
    def is_credit(self) -> bool:
        return self.amount > 0

    @computed_field  # type: ignore[misc]
    @property
    def desc_hash8(self) -> str:
        # Late import to avoid importing hashlib globally if not needed
        import hashlib

        return hashlib.sha256(self.description.encode("utf-8")).hexdigest()[:8]

    @classmethod
    def from_projection_row(cls, row: dict) -> "Transaction":
        """Construct a Transaction from a projection database row dict.

        Projection rows use different field names than the Transaction model:
        - 'transaction_date' → date (ISO string → date object)
        - 'canonical_description' → description
        - 'amount' → amount (string → float)

        Args:
            row: dict with projection column names (transaction_date,
                 canonical_description, etc.)

        Returns:
            Transaction object with proper type conversions applied.
        """
        metadata = row.get("metadata")
        if isinstance(metadata, str) and metadata:
            metadata = json.loads(metadata)
        elif not isinstance(metadata, dict):
            metadata = {}

        return cls(
            transaction_id=row["transaction_id"],
            date=datetime.fromisoformat(row["transaction_date"]).date(),
            description=row["canonical_description"],
            amount=float(row["amount"]),
            currency=row["currency"],
            account_id=row["account_id"],
            counterparty=row.get("counterparty"),
            category=row.get("category"),
            subcategory=row.get("subcategory"),
            notes=row.get("notes"),
            source_file=row.get("source_file"),
            vendor=row.get("vendor"),
            metadata=metadata,
        )


class SplitLine(BaseModel):
    """Represents a single split allocation of a transaction amount.

    Typical uses:
    - Allocate a single bank transaction across multiple categories (e.g., part expense, part asset).
    - Future: allocate to another internal account_id for direct transfer posting.
    """

    line_id: Optional[str] = None
    amount: float
    # Optional target account for double-entry style modeling (future-friendly)
    target_account_id: Optional[str] = None
    # Category tagging (coarse and fine)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    memo: Optional[str] = None
    percent: Optional[float] = Field(default=None, ge=0, le=100)


class TransactionGroup(BaseModel):
    """Groups a primary ledger transaction and its split lines.

    In many workflows, the ledger CSV stores the raw transaction row. Splits
    provide an orthogonal breakdown for reporting or double-entry style posting.

    Invariants enforced here:
    - If splits are present, their amounts should sum to the primary amount
      within a small tolerance (default 0.01). This allows minor rounding.
    """

    group_id: str
    primary: Transaction
    splits: List[SplitLine] = Field(default_factory=list)
    tolerance: float = Field(
        default=0.01, ge=0.0, description="Allowed difference between sum(splits) and amount"
    )

    @computed_field  # type: ignore[misc]
    @property
    def total_splits(self) -> float:
        return float(sum(s.amount for s in self.splits)) if self.splits else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def has_splits(self) -> bool:
        return bool(self.splits)

    @model_validator(mode="after")
    def _validate_splits_total(self) -> "TransactionGroup":
        if self.splits:
            diff = abs(self.total_splits - self.primary.amount)
            if diff > self.tolerance:
                raise ValueError(
                    f"Split totals ({self.total_splits:.2f}) do not equal primary amount "
                    f"({self.primary.amount:.2f}) within tolerance {self.tolerance:.2f}"
                )
        return self

    @classmethod
    def from_projection_row(cls, row: dict) -> "TransactionGroup":
        """Construct a TransactionGroup from a projection database row dict.

        Args:
            row: dict with projection column names.

        Returns:
            TransactionGroup with group_id matching transaction_id and primary
            transaction converted from the row.
        """
        txn = Transaction.from_projection_row(row)
        return cls(group_id=row["transaction_id"], primary=txn)


# Optional (future-facing) linking proposal — not wired
class TransferLink(BaseModel):
    """A lightweight link between two transactions judged to be a transfer.

    This model is provided for completeness of the domain, but is not used by
    any CLI yet. It mirrors the planning doc and allows private artifacts to
    refer to linked pairs without exposing raw descriptions.
    """

    link_id: Optional[str] = None
    debit_account_id: str
    debit_transaction_id: str
    credit_account_id: str
    credit_transaction_id: str
    amount: float
    method: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = None


__all__ = [
    "Account",
    "AccountNature",
    "ImportHints",
    "Transaction",
    "SplitLine",
    "TransactionGroup",
    "TransferLink",
]
