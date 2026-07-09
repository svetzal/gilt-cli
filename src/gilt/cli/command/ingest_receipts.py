"""
Command module for `gilt ingest-receipts`.

Reads mailctl.receipt.v1 JSON sidecar files, matches them to existing bank
transactions, and emits TransactionEnriched events.

Dry-run by default. Use --write to persist events.
"""

from __future__ import annotations

import json
from pathlib import Path

from gilt.services.receipt_ingestion_service import (
    DEFAULT_VENDOR_PATTERNS,
    MatchResult,
    batch_match_receipts,
    find_already_ingested_invoices,
    find_receipt_files,
    find_receipts_by_year,
    load_receipt_file,
)
from gilt.workspace import Workspace

from ..console import print_error
from .ingest_receipts_review import run_ambiguous_interactively
from .ingest_receipts_view import (
    display_results_table,
    display_summary,
    print_no_receipts,
    print_parse_warnings,
)


def _emit_enrichment_events(matched: list[MatchResult], store) -> int:
    """Construct and append a TransactionEnriched event for each matched receipt. Returns written count."""
    from gilt.model.events import TransactionEnriched

    written = 0
    for r in matched:
        receipt = r.receipt
        event = TransactionEnriched(
            transaction_id=r.transaction_id,
            vendor=receipt.vendor,
            service=receipt.service,
            invoice_number=receipt.invoice_number,
            tax_amount=receipt.tax_amount,
            tax_type=receipt.tax_type,
            currency=receipt.currency,
            receipt_file=receipt.receipt_file,
            enrichment_source=str(receipt.source_path),
            source_email=receipt.source_email,
            match_confidence=r.match_confidence,
        )
        store.append_event(event)
        written += 1
    return written


def _find_paths_by_year(json_paths: list[Path], year: int) -> tuple[list[Path], list[str]]:
    """Load and filter receipt files by year. Returns (filtered_paths, parse_warnings)."""
    all_receipts = []
    parse_warnings: list[str] = []
    for p in json_paths:
        try:
            all_receipts.append(load_receipt_file(p))
        except (json.JSONDecodeError, OSError, ValueError) as e:
            parse_warnings.append(f"skipping {p.name} — {e}")
    return [r.source_path for r in find_receipts_by_year(all_receipts, year)], parse_warnings


def run(
    *,
    workspace: Workspace,
    source: Path,
    write: bool = False,
    year: int | None = None,
    account: str | None = None,
    interactive: bool = False,
) -> int:
    """Run the ingest-receipts command."""
    from gilt.storage.event_store import EventStore
    from gilt.storage.projection import ProjectionBuilder

    # Validate source
    if not source.is_dir():
        print_error(f"Source directory not found: {source}")
        return 1

    # Scan files
    json_paths = find_receipt_files(source)
    if year is not None:
        json_paths, parse_warnings = _find_paths_by_year(json_paths, year)
        print_parse_warnings(parse_warnings)
    if not json_paths:
        print_no_receipts()
        return 0

    # Load projections
    store = EventStore(str(workspace.event_store_path))
    existing_events = store.get_events_by_type("TransactionEnriched")
    ingested_invoices = find_already_ingested_invoices(existing_events)
    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    # Batch match
    batch = batch_match_receipts(
        json_paths,
        all_transactions,
        ingested_invoices,
        account_id=account,
        vendor_patterns=DEFAULT_VENDOR_PATTERNS,
    )
    matched = list(batch.matched)
    ambiguous = list(batch.ambiguous)
    unmatched = batch.unmatched
    skipped_already_ingested = batch.skipped_already_ingested
    skipped_parse_errors = batch.skipped_parse_errors

    display_results_table(matched + ambiguous + unmatched)
    return _finalize_receipts(
        matched,
        ambiguous,
        unmatched,
        skipped_already_ingested,
        skipped_parse_errors,
        store,
        write,
        interactive,
    )


def _finalize_receipts(
    matched: list,
    ambiguous: list,
    unmatched: list,
    skipped_already_ingested: int,
    skipped_parse_errors: int,
    store,
    write: bool,
    interactive: bool,
) -> int:
    """Resolve ambiguous matches interactively, emit enrichment events, and display summary."""
    if interactive and ambiguous:
        resolved = run_ambiguous_interactively(ambiguous)
        matched.extend(resolved)
        ambiguous = [r for r in ambiguous if r not in resolved]

    written = 0
    if write and matched:
        written = _emit_enrichment_events(matched, store)

    display_summary(
        matched,
        ambiguous,
        unmatched,
        skipped_already_ingested,
        skipped_parse_errors,
        write,
        written,
    )
    return 0
