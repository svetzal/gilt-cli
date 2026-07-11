"""
Receipt ingestion service — matching receipt JSON files to bank transactions.

This module is the pure core side of the receipt core/shell split:
  receipt_loading.py         — ReceiptData model + I/O boundary (shell)
  receipt_ingestion_service.py — pure matching logic + re-exports (core + facade)

Pure business logic (no I/O, fully testable with in-memory data):
  ReceiptData.from_dict, find_receipts_by_year, match_receipt_to_transactions,
  batch_match_receipts, find_already_ingested_invoices

I/O boundary functions (re-exported from receipt_loading for backward compat):
  find_receipt_files, load_receipt_file

Privacy: All processing is local-only. No network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

from gilt.services.receipt_loading import (
    ReceiptData,
    find_receipt_files,
    load_receipt_file,
)


def find_receipts_by_year(receipts: list[ReceiptData], year: int) -> list[ReceiptData]:
    """Return only receipts whose receipt_date falls in the given year. Pure function.

    Args:
        receipts: Parsed receipt objects to filter.
        year: Four-digit year to keep.

    Returns:
        Filtered list preserving input order.
    """
    return [r for r in receipts if r.receipt_date.year == year]


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


def _find_candidates(
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


DEFAULT_VENDOR_PATTERNS: dict[str, list[str]] = {
    "apple": ["APPLE.COM/BILL", "APPLE.COM"],
    "github": ["GITHUB"],
    "paddle": ["PADDLE"],
    "zoom": ["ZOOM"],
    "suno": ["SUNO"],
    "costco": ["COSTCO"],
    "vevor": ["VEVOR"],
    "lyft": ["LYFT"],
    "feel heal grow": ["FEELHEALGRO"],
    "anthropic": ["ANTHROPIC", "CLAUDE"],
    "paypal": ["PAYPAL"],
    "microsoft": ["MICROSOFT"],
    "canadian tire": ["CANADIAN TIRE"],
    "best buy": ["BEST BUY"],
}

_FX_AMOUNT_PCT = Decimal("0.08")  # 8% tolerance for FX matches
_FX_DATE_WINDOW = 2
_PATTERN_AMOUNT_PCT = Decimal("0.08")  # 8% tolerance for vendor-pattern matches
_DEFAULT_DATE_WINDOW_DAYS = 3
_DEFAULT_AMOUNT_TOLERANCE = Decimal("0.02")


def _is_exact_match(
    amount_diff: Decimal,
    days_diff: int,
    desc_matches_vendor: bool,
    amount_tolerance: Decimal,
    date_window_days: int,
) -> bool:
    """Return True when amount and date are within tolerance and vendor description matches."""
    return amount_diff <= amount_tolerance and days_diff <= date_window_days and desc_matches_vendor


def _is_fx_match(
    receipt: ReceiptData,
    txn: dict,
    amount_diff: Decimal,
    days_diff: int,
    desc_matches_vendor: bool,
    receipt_amount: Decimal,
) -> bool:
    """Return True when currencies differ and amount/date fall within FX tolerances."""
    txn_currency = txn.get("currency", "CAD")
    if receipt.currency == txn_currency:
        return False
    pct_diff = amount_diff / receipt_amount if receipt_amount else Decimal("999")
    return pct_diff <= _FX_AMOUNT_PCT and days_diff <= _FX_DATE_WINDOW and desc_matches_vendor


def _is_pattern_match(
    amount_diff: Decimal,
    days_diff: int,
    vendor_substrings: list[str],
    desc: str,
    receipt_amount: Decimal,
    date_window_days: int,
) -> bool:
    """Return True when the description contains a vendor keyword and amount/date are within tolerances."""
    if not vendor_substrings:
        return False
    if not any(s.upper() in desc for s in vendor_substrings):
        return False
    pct_diff = amount_diff / receipt_amount if receipt_amount else Decimal("999")
    return pct_diff <= _PATTERN_AMOUNT_PCT and days_diff <= date_window_days


def _collect_candidates(
    receipt: ReceiptData,
    transactions: list[dict],
    account_id: str | None,
    amount_tolerance: Decimal,
    date_window_days: int,
    vendor_substrings: list[str],
    vendor_has_patterns: bool,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Scan transactions and bucket them into exact, FX, and pattern candidate lists.

    Returns:
        (exact_candidates, fx_candidates, pattern_candidates)
    """
    receipt_total = receipt.amount + receipt.tax_amount if receipt.tax_amount else receipt.amount
    receipt_amount = abs(receipt_total)

    exact_candidates: list[dict] = []
    fx_candidates: list[dict] = []
    pattern_candidates: list[dict] = []

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

        desc = txn.get("canonical_description", "").upper()
        desc_matches_vendor = not vendor_has_patterns or any(
            s.upper() in desc for s in vendor_substrings
        )

        if _is_exact_match(
            amount_diff, days_diff, desc_matches_vendor, amount_tolerance, date_window_days
        ):
            exact_candidates.append(txn)

        if _is_fx_match(receipt, txn, amount_diff, days_diff, desc_matches_vendor, receipt_amount):
            fx_candidates.append(txn)

        if _is_pattern_match(
            amount_diff, days_diff, vendor_substrings, desc, receipt_amount, date_window_days
        ):
            pattern_candidates.append(txn)

    return exact_candidates, fx_candidates, pattern_candidates


@dataclass
class MatchResult:
    """Result of attempting to match a receipt to a bank transaction."""

    receipt: ReceiptData
    status: str  # "matched", "ambiguous", "unmatched"
    transaction_id: str | None = None
    candidate_count: int = 0
    current_description: str | None = None
    candidates: list[dict] = field(default_factory=list)
    match_confidence: str | None = None  # "exact", "fx-adjusted", "pattern-assisted"


def match_receipt_to_transactions(
    receipt: ReceiptData,
    transactions: list[dict],
    account_id: str | None = None,
    amount_tolerance: Decimal = _DEFAULT_AMOUNT_TOLERANCE,
    date_window_days: int = _DEFAULT_DATE_WINDOW_DAYS,
    vendor_patterns: dict[str, list[str]] | None = None,
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
    vendor_key = receipt.vendor.lower() if vendor_patterns else None
    vendor_substrings = (
        vendor_patterns.get(vendor_key, []) if vendor_patterns and vendor_key else []
    )
    vendor_has_patterns = bool(vendor_substrings)

    exact_candidates, fx_candidates, pattern_candidates = _collect_candidates(
        receipt,
        transactions,
        account_id,
        amount_tolerance,
        date_window_days,
        vendor_substrings,
        vendor_has_patterns,
    )

    for candidates, confidence in [
        (exact_candidates, "exact"),
        (fx_candidates, "fx-adjusted"),
        (pattern_candidates, "pattern-assisted"),
    ]:
        if candidates:
            return _find_candidates(receipt, candidates, confidence)

    return MatchResult(
        receipt=receipt,
        status="unmatched",
        candidate_count=0,
    )


@dataclass
class BatchMatchResult:
    """Categorised results of a batch receipt matching run."""

    matched: list[MatchResult]
    ambiguous: list[MatchResult]
    unmatched: list[MatchResult]
    skipped_already_ingested: int
    skipped_parse_errors: int


def batch_match_receipts(
    json_paths: Iterable[Path],
    transactions: list[dict],
    ingested_invoices: set[str],
    *,
    account_id: str | None = None,
    vendor_patterns: dict[str, list[str]] | None = None,
) -> BatchMatchResult:
    """Parse receipt files and match against transactions.

    This is the core orchestration loop shared by CLI and GUI.
    """
    results: list[MatchResult] = []
    skipped_already_ingested = 0
    skipped_parse_errors = 0

    for path in json_paths:
        try:
            receipt = load_receipt_file(path)
        except (ValueError, OSError, UnicodeDecodeError):
            # ValueError covers json.JSONDecodeError (its subclass) and schema errors
            skipped_parse_errors += 1
            continue

        if receipt.amount is None:
            skipped_parse_errors += 1
            continue

        if receipt.invoice_number and receipt.invoice_number in ingested_invoices:
            skipped_already_ingested += 1
            continue

        result = match_receipt_to_transactions(
            receipt,
            transactions,
            account_id=account_id,
            vendor_patterns=vendor_patterns,
        )
        results.append(result)

    matched = [r for r in results if r.status == "matched"]
    ambiguous = [r for r in results if r.status == "ambiguous"]
    unmatched = [r for r in results if r.status == "unmatched"]

    return BatchMatchResult(
        matched=matched,
        ambiguous=ambiguous,
        unmatched=unmatched,
        skipped_already_ingested=skipped_already_ingested,
        skipped_parse_errors=skipped_parse_errors,
    )


__all__ = [
    "BatchMatchResult",
    "DEFAULT_VENDOR_PATTERNS",
    "MatchResult",
    "ReceiptData",
    "batch_match_receipts",
    "find_receipts_by_year",
    "find_already_ingested_invoices",
    "find_receipt_files",
    "load_receipt_file",
    "match_receipt_to_transactions",
]
