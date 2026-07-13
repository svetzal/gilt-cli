from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.category_io import save_categories_config
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.model.ledger_repository import LedgerRepository
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def make_workspace(tmp_path: Path, *, init_dirs: list[str] | None = None) -> Workspace:
    ws = Workspace(root=tmp_path)
    for attr in init_dirs or []:
        path: Path = getattr(ws, attr)
        target = path if not path.suffix else path.parent
        target.mkdir(parents=True, exist_ok=True)
    return ws


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
    builder.build_from_scratch(store)


def capture_view(view_module_name: str, fn) -> str:
    """Swap the module-level console in a view module, call fn(), and return captured output.

    Usage::

        output = capture_view("gilt.cli.command.accounts_view", lambda: display_accounts_table(mapping))
    """
    import importlib
    from io import StringIO

    from rich.console import Console

    import gilt.cli.console as console_mod

    view_mod = importlib.import_module(view_module_name)

    buf = StringIO()
    new_console = Console(file=buf, highlight=False, width=200)

    old_view = getattr(view_mod, "console", None)
    old_mod = console_mod.console
    if old_view is not None:
        view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        if old_view is not None:
            view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


def build_workspace_with_ledger(
    tmp_path: Path,
    *,
    groups=(),
    config=None,
    projections: bool = False,
) -> Workspace:
    """Build a temporary workspace with optional ledger data and projections.

    Args:
        tmp_path: Temporary directory path (e.g., pytest's tmp_path fixture).
        groups: Optional sequence of TransactionGroup objects to write as ledger CSV files.
        config: Optional CategoryConfig to write; defaults to make_category_config().
        projections: If True, build projection DB from the written ledger files.

    Returns:
        Configured Workspace instance.
    """
    from gilt.testing.fixtures import make_category_config

    ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir", "categories_config"])
    if config is None:
        config = make_category_config()
    save_categories_config(ws.categories_config, config)
    if groups:
        by_account: dict[str, list[TransactionGroup]] = defaultdict(list)
        for g in groups:
            by_account[g.primary.account_id].append(g)
        for account_id, acct_groups in by_account.items():
            write_ledger(ws.ledger_data_dir / f"{account_id}.csv", acct_groups)
    if projections:
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)
    return ws


__all__ = [
    "make_workspace",
    "write_ledger",
    "build_projections_from_csvs",
    "capture_view",
    "build_workspace_with_ledger",
]
