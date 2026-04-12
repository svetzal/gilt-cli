from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.model.ledger_repository import LedgerRepository
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


def write_ledger(path: Path, groups: list[TransactionGroup]):
    repo = LedgerRepository(path.parent)
    repo.save(path.stem, groups)


def build_projections_from_csvs(data_dir: Path, projections_path: Path):
    # Create event store at the workspace-standard path (sibling of projections.db)
    store_path = projections_path.parent / "events.db"
    store_path.parent.mkdir(parents=True, exist_ok=True)

    store = EventStore(str(store_path))
    repo = LedgerRepository(data_dir)
    for account_id in repo.available_account_ids():
        groups = repo.load(account_id)
        for group in groups:
            txn = group.primary
            import_event = TransactionImported(
                transaction_id=txn.transaction_id,
                transaction_date=str(txn.date),
                source_file=f"{account_id}.csv",
                source_account=txn.account_id,
                raw_description=txn.description,
                amount=Decimal(str(txn.amount)),
                currency=txn.currency,
                raw_data={},
            )
            store.append_event(import_event)

            if txn.category:
                cat_event = TransactionCategorized(
                    transaction_id=txn.transaction_id,
                    category=txn.category,
                    subcategory=txn.subcategory,
                    source="user",
                )
                store.append_event(cat_event)

    builder = ProjectionBuilder(projections_path)
    builder.rebuild_from_scratch(store)
