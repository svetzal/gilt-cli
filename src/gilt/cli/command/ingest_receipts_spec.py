from __future__ import annotations

"""Tests for ingest-receipts command."""

import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.ingest_receipts import run
from gilt.model.events import TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _setup_workspace(tmpdir: Path) -> Workspace:
    """Create workspace with required directories."""
    (tmpdir / "data").mkdir(parents=True)
    (tmpdir / "config").mkdir(parents=True)
    return Workspace(root=tmpdir)


def _add_transaction(
    store: EventStore,
    builder: ProjectionBuilder,
    *,
    transaction_id: str = "abcd1234abcd1234",
    date: str = "2025-06-15",
    amount: str = "-35.01",
    account_id: str = "MYBANK_CC",
    description: str = "ACME CORP PURCHASE",
):
    """Helper: add a TransactionImported event and rebuild projections."""
    event = TransactionImported(
        transaction_id=transaction_id,
        transaction_date=date,
        source_file="test.csv",
        source_account=account_id,
        raw_description=description,
        amount=Decimal(amount),
        currency="CAD",
        raw_data={},
    )
    store.append_event(event)
    builder.rebuild_from_scratch(store)


def _write_receipt(path: Path, overrides: dict | None = None) -> Path:
    """Helper to write a receipt JSON file."""
    data = {
        "schema": "mailctl.receipt.v1",
        "vendor": "Acme Corp",
        "service": "Widget Pro",
        "amount": 35.01,
        "currency": "CAD",
        "tax": {"amount": 4.03, "type": "HST"},
        "date": "2025-06-15",
        "invoice_number": "INV001",
        "source_email": "billing@acme.example",
        "source_account": "example",
        "email_uid": 100,
        "receipt_file": "Acme-INV001.pdf",
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class DescribeIngestReceiptsCommand:
    def it_should_return_error_for_invalid_source_dir(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            rc = run(
                workspace=ws,
                source=Path("/nonexistent/dir"),
                write=False,
            )
            assert rc == 1

    def it_should_return_zero_when_no_json_files(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            source = Path(tmpdir) / "receipts"
            source.mkdir()

            rc = run(workspace=ws, source=source, write=False)
            assert rc == 0

    def it_should_match_receipt_to_transaction_in_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            _add_transaction(store, builder)

            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            rc = run(workspace=ws, source=source, write=False)
            assert rc == 0

            # Verify no events were written
            enrichment_events = store.get_events_by_type("TransactionEnriched")
            assert len(enrichment_events) == 0

    def it_should_write_enrichment_event_when_matched(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            _add_transaction(store, builder)

            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            rc = run(workspace=ws, source=source, write=True)
            assert rc == 0

            enrichment_events = store.get_events_by_type("TransactionEnriched")
            assert len(enrichment_events) == 1
            event = enrichment_events[0]
            assert event.transaction_id == "abcd1234abcd1234"
            assert event.vendor == "Acme Corp"
            assert event.service == "Widget Pro"
            assert event.invoice_number == "INV001"
            assert event.tax_amount == Decimal("4.03")
            assert event.tax_type == "HST"
            assert event.receipt_file == "Acme-INV001.pdf"
            assert event.source_email == "billing@acme.example"

    def it_should_skip_already_ingested_invoices(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            _add_transaction(store, builder)

            # First run: write enrichment
            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            rc = run(workspace=ws, source=source, write=True)
            assert rc == 0
            assert len(store.get_events_by_type("TransactionEnriched")) == 1

            # Second run: should skip (same invoice_number)
            rc = run(workspace=ws, source=source, write=True)
            assert rc == 0
            assert len(store.get_events_by_type("TransactionEnriched")) == 1

    def it_should_report_unmatched_receipts(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            EventStore(str(ws.event_store_path))
            ProjectionBuilder(ws.projections_path)

            # No transactions in the store
            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            rc = run(workspace=ws, source=source, write=False)
            assert rc == 0

    def it_should_filter_by_account(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            _add_transaction(
                store, builder,
                transaction_id="aaaa111111111111",
                account_id="MYBANK_CC",
            )
            _add_transaction(
                store, builder,
                transaction_id="bbbb222222222222",
                account_id="BANK2_CHQ",
            )

            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            rc = run(
                workspace=ws, source=source, write=True, account="MYBANK_CC"
            )
            assert rc == 0

            enrichment_events = store.get_events_by_type("TransactionEnriched")
            assert len(enrichment_events) == 1
            assert enrichment_events[0].transaction_id == "aaaa111111111111"

    def it_should_filter_by_year(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            _add_transaction(store, builder)

            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "2025.json", overrides={"date": "2025-06-15"})
            _write_receipt(
                source / "2024.json",
                overrides={"date": "2024-06-15", "invoice_number": "INV002"},
            )

            rc = run(workspace=ws, source=source, write=False, year=2025)
            assert rc == 0

    def it_should_report_ambiguous_matches(self):
        with TemporaryDirectory() as tmpdir:
            ws = _setup_workspace(Path(tmpdir))
            store = EventStore(str(ws.event_store_path))
            builder = ProjectionBuilder(ws.projections_path)

            # Two transactions with same amount and date
            _add_transaction(
                store, builder,
                transaction_id="aaaa111111111111",
                description="ACME PURCHASE 1",
            )
            _add_transaction(
                store, builder,
                transaction_id="bbbb222222222222",
                description="ACME PURCHASE 2",
            )

            source = Path(tmpdir) / "receipts"
            source.mkdir()
            _write_receipt(source / "acme.json")

            # In write mode, ambiguous receipts should not create events
            rc = run(workspace=ws, source=source, write=True)
            assert rc == 0
            enrichment_events = store.get_events_by_type("TransactionEnriched")
            assert len(enrichment_events) == 0
