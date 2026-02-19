"""
Receipt ingestion service — pure logic for matching receipt JSON files to bank transactions.

Reads mailctl.receipt.v1 JSON sidecar files, matches them to existing bank transactions
by amount and date, and prepares TransactionEnriched events.

Privacy: All processing is local-only. No network I/O.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class ReceiptData:
    """Parsed receipt from a mailctl.receipt.v1 JSON sidecar file."""

    vendor: str
    service: Optional[str]
    amount: Decimal
    currency: str
    tax_amount: Optional[Decimal]
    tax_type: Optional[str]
    receipt_date: date
    invoice_number: Optional[str]
    source_email: Optional[str]
    receipt_file: Optional[str]
    source_path: Path  # path to the JSON file itself

    @classmethod
    def from_json_file(cls, path: Path) -> ReceiptData:
        """Parse a mailctl.receipt.v1 JSON file into a ReceiptData.

        Raises:
            ValueError: If schema is not mailctl.receipt.v1 or required fields are missing.
            json.JSONDecodeError: If file is not valid JSON.
        """
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)

        schema = data.get("schema")
        if schema != "mailctl.receipt.v1":
            raise ValueError(f"Unsupported schema: {schema}")

        if "vendor" not in data or "amount" not in data or "date" not in data:
            raise ValueError("Missing required fields: vendor, amount, date")

        tax = data.get("tax")
        tax_amount = None
        tax_type = None
        if isinstance(tax, dict):
            tax_amount = Decimal(str(tax["amount"])) if "amount" in tax else None
            tax_type = tax.get("type")

        return cls(
            vendor=data["vendor"],
            service=data.get("service"),
            amount=Decimal(str(data["amount"])) if data.get("amount") is not None else None,
            currency=data.get("currency", "CAD"),
            tax_amount=tax_amount,
            tax_type=tax_type,
            receipt_date=date.fromisoformat(data["date"]),
            invoice_number=data.get("invoice_number"),
            source_email=data.get("source_email"),
            receipt_file=data.get("receipt_file"),
            source_path=path,
        )


@dataclass
class MatchResult:
    """Result of attempting to match a receipt to a bank transaction."""

    receipt: ReceiptData
    status: str  # "matched", "ambiguous", "unmatched"
    transaction_id: Optional[str] = None
    candidate_count: int = 0
    current_description: Optional[str] = None
    candidates: list[dict] = field(default_factory=list)
    match_confidence: Optional[str] = None  # "exact", "fx-adjusted", "pattern-assisted"


def scan_receipt_files(source_dir: Path, year: Optional[int] = None) -> list[Path]:
    """Recursively find all JSON files in source_dir.

    Args:
        source_dir: Root directory to scan.
        year: If provided, only return receipts from this year (by parsing the JSON).

    Returns:
        Sorted list of JSON file paths.
    """
    if not source_dir.is_dir():
        return []
    paths = sorted(source_dir.rglob("*.json"))
    if year is None:
        return paths

    filtered = []
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("schema") != "mailctl.receipt.v1":
                continue
            receipt_date = date.fromisoformat(data["date"])
            if receipt_date.year == year:
                filtered.append(p)
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return filtered


def find_already_ingested_invoices(enrichment_events: list) -> set[str]:
    """Extract invoice numbers already present in TransactionEnriched events.

    Args:
        enrichment_events: List of TransactionEnriched event objects.

    Returns:
        Set of invoice_number strings that have been ingested.
    """
    invoices: set[str] = set()
    for event in enrichment_events:
        inv = getattr(event, "invoice_number", None)
        if inv:
            invoices.add(inv)
    return invoices


def _resolve_candidates(
    receipt: ReceiptData,
    candidates: list[dict],
    confidence: str,
) -> MatchResult:
    """Build a MatchResult from a list of candidates at a given confidence level."""
    if len(candidates) == 1:
        txn = candidates[0]
        return MatchResult(
            receipt=receipt,
            status="matched",
            transaction_id=txn["transaction_id"],
            candidate_count=1,
            current_description=txn.get("canonical_description", ""),
            candidates=candidates,
            match_confidence=confidence,
        )
    else:
        return MatchResult(
            receipt=receipt,
            status="ambiguous",
            candidate_count=len(candidates),
            candidates=candidates,
            match_confidence=confidence,
        )


_FX_AMOUNT_PCT = Decimal("0.08")  # 8% tolerance for FX matches
_FX_DATE_WINDOW = 2
_PATTERN_AMOUNT_PCT = Decimal("0.08")  # 8% tolerance for vendor-pattern matches


def match_receipt_to_transactions(
    receipt: ReceiptData,
    transactions: list[dict],
    account_id: Optional[str] = None,
    amount_tolerance: Decimal = Decimal("0.02"),
    date_window_days: int = 3,
    vendor_patterns: Optional[dict[str, list[str]]] = None,
) -> MatchResult:
    """Match a receipt to bank transactions using multi-strategy matching.

    Strategies (tried in priority order):
    1. Exact: amount within tolerance, date within window.
    2. FX-tolerant: receipt currency differs from transaction currency,
       amount within 8%, date within ±2 days.
    3. Vendor-pattern: vendor maps to a description substring,
       amount within 8%, date within window.

    Args:
        receipt: Parsed receipt data.
        transactions: List of projection row dicts.
        account_id: If provided, only match transactions in this account.
        amount_tolerance: Maximum absolute amount difference for exact match.
        date_window_days: Maximum days between receipt and transaction for exact/pattern.
        vendor_patterns: Map of lowercase vendor name to description substrings.

    Returns:
        MatchResult with match_confidence indicating which strategy matched.
    """
    exact_candidates = []
    fx_candidates = []
    pattern_candidates = []

    receipt_total = receipt.amount + receipt.tax_amount if receipt.tax_amount else receipt.amount
    receipt_amount = abs(receipt_total)
    vendor_key = receipt.vendor.lower() if vendor_patterns else None
    vendor_substrings = vendor_patterns.get(vendor_key, []) if vendor_patterns and vendor_key else []
    # When the vendor has known patterns, exact/FX must also verify description
    vendor_has_patterns = bool(vendor_substrings)

    for txn in transactions:
        if account_id and txn.get("account_id") != account_id:
            continue

        txn_amount = abs(Decimal(str(txn["amount"])))
        amount_diff = abs(txn_amount - receipt_amount)

        txn_date_str = txn.get("transaction_date", "")
        try:
            txn_date = date.fromisoformat(txn_date_str)
        except ValueError:
            continue
        days_diff = abs((txn_date - receipt.receipt_date).days)

        # Check vendor description match (used by exact and FX strategies)
        desc = txn.get("canonical_description", "").upper()
        desc_matches_vendor = (
            not vendor_has_patterns
            or any(s.upper() in desc for s in vendor_substrings)
        )

        # Strategy 1: Exact match (vendor-filtered when patterns exist)
        if amount_diff <= amount_tolerance and days_diff <= date_window_days:
            if desc_matches_vendor:
                exact_candidates.append(txn)

        # Strategy 2: FX-tolerant match (vendor-filtered when patterns exist)
        txn_currency = txn.get("currency", "CAD")
        if receipt.currency != txn_currency:
            pct_diff = amount_diff / receipt_amount if receipt_amount else Decimal("999")
            if pct_diff <= _FX_AMOUNT_PCT and days_diff <= _FX_DATE_WINDOW:
                if desc_matches_vendor:
                    fx_candidates.append(txn)

        # Strategy 3: Vendor-pattern match
        if vendor_substrings:
            if any(s.upper() in desc for s in vendor_substrings):
                pct_diff = amount_diff / receipt_amount if receipt_amount else Decimal("999")
                if pct_diff <= _PATTERN_AMOUNT_PCT and days_diff <= date_window_days:
                    pattern_candidates.append(txn)

    # Return best strategy (highest confidence first)
    for candidates, confidence in [
        (exact_candidates, "exact"),
        (fx_candidates, "fx-adjusted"),
        (pattern_candidates, "pattern-assisted"),
    ]:
        if candidates:
            return _resolve_candidates(receipt, candidates, confidence)

    return MatchResult(
        receipt=receipt,
        status="unmatched",
        candidate_count=0,
    )
