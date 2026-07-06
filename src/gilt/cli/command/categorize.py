from __future__ import annotations

"""Categorize transactions (single or batch mode)."""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_service import CategorizationService
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.workspace import Workspace

from ..console import print_error
from ..event_sourcing_bootstrap import load_event_store, require_event_sourcing
from ..filtering import group_by_account
from ..formatting import build_category_path, format_prefix_lookup_error
from ..loaders import load_account_transactions
from ..mutations import (
    find_matches_by_criteria,
    persist_row_categorizations,
    run_confirmed_mutation,
    run_persisted_mutation,
    validate_single_vs_batch_mode,
)
from . import categorize_view
from ._errors import CommandAbort

logger = logging.getLogger(__name__)


@dataclass
class BatchEntry:
    line_no: int
    txid_prefix: str
    category_path: str


@dataclass
class ResolvedEntry:
    transaction_id: str
    account_id: str
    category: str
    subcategory: str | None


def _find_account_ledgers(data_dir: Path, account: str | None) -> list[Path]:
    """Find ledger files to process."""
    repo = LedgerRepository(data_dir)
    if account:
        if not repo.exists(account):
            return []
        return [repo.ledger_path(account)]
    else:
        return repo.ledger_paths()


def _find_single_txid(
    all_transactions: list[dict],
    txid: str,
    service: TransactionOperationsService,
) -> list[tuple[str, TransactionGroup]] | None:
    """Resolve a single txid prefix globally across all transactions.

    Uses the projection-based prefix resolver — the same one used by ``gilt show``
    and the ``--txid-file`` batch path — so all three paths behave identically.
    Returns None on any error (prefix too short, not found, ambiguous).
    """
    normalized = (txid or "").strip().lower()
    result = service.find_projection_by_prefix(normalized, all_transactions)
    if result.error is not None:
        print_error(format_prefix_lookup_error(result, normalized))
        return None
    row = result.transaction
    group = TransactionGroup.from_projection_row(row)
    return [(row["account_id"], group)]


def _find_targets(
    all_transactions: list[dict],
    single_mode: bool,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
    service: TransactionOperationsService,
) -> list[tuple[str, TransactionGroup]] | None:
    """Build groups, apply search criteria, and return matched (account_id, group) pairs.

    Returns None on error (invalid pattern, ambiguous ID, etc.).
    """
    if single_mode and txid is not None:
        return _find_single_txid(all_transactions, txid, service)

    criteria = SearchCriteria(
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
    )
    groups_by_account = group_by_account(all_transactions)
    return find_matches_by_criteria(groups_by_account, criteria, service, txid=None)


def _confirm_and_apply(
    all_matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
    single_mode: bool,
    assume_yes: bool,
    write: bool,
    workspace: Workspace,
    categorization_service: CategorizationService,
) -> int:
    """Display matches, confirm, apply categorization, and write back. Returns exit code."""
    total_matched = len(all_matches)
    auto_yes = single_mode or total_matched <= 1 or assume_yes

    def persist(ready) -> None:
        result = categorization_service.run_categorization(
            [group for _, group in all_matches],
            category,
            subcategory,
        )
        account_by_txn_id = {group.primary.transaction_id: acct for acct, group in all_matches}
        updated_pairs = [
            (account_by_txn_id.get(group.primary.transaction_id, ""), group)
            for group in result.updated_transactions
        ]
        _persist_categorizations(updated_pairs, ready, workspace)

    return run_persisted_mutation(
        matches=all_matches,
        display=lambda: categorize_view.display_categorization_matches(all_matches, category, subcategory),
        confirm_prompt=f"Categorize {total_matched} transaction(s)?",
        assume_yes=auto_yes,
        write=write,
        workspace=workspace,
        persist=persist,
    )


def _persist_categorizations(
    updated_pairs: list[tuple[str, TransactionGroup]],
    ready,
    workspace: Workspace,
) -> None:
    """Emit events, update CSVs, and rebuild projections for categorized transactions."""
    persist_row_categorizations(
        (
            (g.primary.transaction_id, acct, g.primary.category or "", g.primary.subcategory, 1.0)
            for acct, g in updated_pairs
        ),
        ready,
        workspace,
        source="user",
    )


def _init_services(
    workspace: Workspace,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> tuple[TransactionOperationsService, CategorizationService]:
    """Initialize services if not provided."""
    if service is None:
        service = TransactionOperationsService()

    category_config = load_categories_config(workspace.categories_config)

    event_store = load_event_store(workspace)

    if categorization_service is None:
        categorization_service = CategorizationService(
            category_config=category_config,
            transaction_service=service,
            event_store=event_store,
        )

    return service, categorization_service


def _load_batch_input(txid_file: Path | None, from_stdin: bool) -> str:
    """Read batch input from file or stdin. Raises CommandAbort(1) if file not found."""
    if txid_file is not None:
        if not txid_file.exists():
            print_error(f"Batch file not found: {txid_file}")
            raise CommandAbort(1)
        return txid_file.read_text(encoding="utf-8")
    # from_stdin
    return sys.stdin.read()


def _build_batch_lines(text: str) -> tuple[list[BatchEntry], list[str]]:
    """Parse batch input text.

    Returns (entries, errors).
    Lines starting with '#' or blank after stripping are skipped.
    Errors include the line number for malformed lines (fewer than two tokens).
    """
    entries: list[BatchEntry] = []
    errors: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)  # split on first whitespace, rest is category
        if len(parts) < 2:
            errors.append(
                f"Line {line_no}: malformed — expected '<txid> <category>', got: {line!r}"
            )
            continue
        txid_prefix, category_path = parts[0], parts[1].strip()
        entries.append(
            BatchEntry(line_no=line_no, txid_prefix=txid_prefix, category_path=category_path)
        )
    return entries, errors


def _find_batch_entries(
    entries: list[BatchEntry],
    all_transactions: list[dict],
    account: str | None,
    categorization_service: CategorizationService,
    service: TransactionOperationsService,
) -> tuple[list[ResolvedEntry], list[str]]:
    """Resolve txid prefixes and validate categories for all batch entries.

    Returns (resolved, errors).
    Errors include line numbers for any problem lines.
    """
    resolved: list[ResolvedEntry] = []
    errors: list[str] = []

    for entry in entries:
        # Validate category first
        cat_name, subcat_name, _ = build_category_path(entry.category_path)
        validation = categorization_service.validate_category(cat_name, subcat_name)
        if not validation.is_valid:
            errors.append(f"Line {entry.line_no}: {'; '.join(validation.errors)}")
            continue

        # Resolve txid prefix
        result = service.find_projection_by_prefix(entry.txid_prefix, all_transactions)
        if result.error is not None:
            errors.append(
                f"Line {entry.line_no}: {format_prefix_lookup_error(result, entry.txid_prefix)}"
            )
            continue

        txn = result.transaction
        resolved.append(
            ResolvedEntry(
                transaction_id=txn["transaction_id"],
                account_id=txn["account_id"],
                category=cat_name,
                subcategory=subcat_name,
            )
        )

    return resolved, errors


def _run_file_batch(
    workspace: Workspace,
    account: str | None,
    txid_file: Path | None,
    from_stdin: bool,
    write: bool,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> int:
    """Orchestrate the file batch flow: read → parse → resolve → preview → persist."""
    text = _load_batch_input(txid_file, from_stdin)
    entries, parse_errors = _build_batch_lines(text)
    if parse_errors:
        for err in parse_errors:
            print_error(err)
        raise CommandAbort(1)

    if not entries:
        categorize_view.print_no_entries()
        return 0

    all_transactions = load_account_transactions(workspace, account)
    svc, cat_svc = _init_services(workspace, service, categorization_service)

    resolved, resolve_errors = _find_batch_entries(
        entries, all_transactions, account, cat_svc, svc
    )
    if resolve_errors:
        for err in resolve_errors:
            print_error(err)
        raise CommandAbort(1)

    return _persist_file_batch(resolved, all_transactions, workspace, write)


def _persist_file_batch(
    resolved: list[ResolvedEntry],
    all_transactions: list[dict],
    workspace: Workspace,
    write: bool,
) -> int:
    """Build preview, display, confirm, and persist file-batch categorizations."""
    txn_by_id = {row["transaction_id"]: row for row in all_transactions}
    preview_matches: list[tuple[str, TransactionGroup]] = []
    for entry in resolved:
        row = txn_by_id.get(entry.transaction_id)
        if row is None:
            continue
        group = TransactionGroup.from_projection_row(row)
        updated_txn = group.primary.model_copy(
            update={"category": entry.category, "subcategory": entry.subcategory}
        )
        updated_group = TransactionGroup(
            group_id=group.group_id,
            primary=updated_txn,
            splits=group.splits,
        )
        preview_matches.append((entry.account_id, updated_group))

    def persist(ready) -> None:
        persist_row_categorizations(
            ((e.transaction_id, e.account_id, e.category, e.subcategory, 1.0) for e in resolved),
            ready,
            workspace,
            source="user",
        )
        categorize_view.print_categorized_success(len(resolved))

    return run_confirmed_mutation(
        matches=preview_matches,
        display=lambda: categorize_view.display_batch_preview(preview_matches, resolved),
        confirm_prompt=f"Categorize {len(resolved)} transaction(s)?",
        assume_yes=True,
        write=write,
        apply=lambda: _run_batch_persist(persist, workspace),
    )


def _run_batch_persist(persist, workspace: Workspace) -> int:
    """Resolve event sourcing and run persist callback. Returns exit code."""
    ready = require_event_sourcing(workspace)
    persist(ready)
    return 0


def _run_single_batch(
    *,
    workspace: Workspace,
    account: str | None,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
    category: str,
    subcategory: str | None,
    assume_yes: bool,
    write: bool,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> int:
    """Validate inputs, resolve matching transactions, confirm, and apply categorization."""
    service, categorization_service, category, subcategory, single_mode = _validate_inputs(
        workspace,
        service,
        categorization_service,
        category,
        subcategory,
        txid,
        description,
        desc_prefix,
        pattern,
    )

    all_transactions = load_account_transactions(workspace, account)
    all_matches = _find_targets(
        all_transactions, single_mode, txid, description, desc_prefix, pattern, amount, service
    )
    if all_matches is None:
        raise CommandAbort(1)

    if len(all_matches) == 0:
        categorize_view.print_no_matches()
        return 0

    recategorized_count = sum(
        1 for _, g in all_matches if g.primary.category is not None and g.primary.category != ""
    )
    if not single_mode and len(all_matches) > 1 and not assume_yes and not write:
        categorize_view.print_batch_mode_notice(len(all_matches))

    result = _confirm_and_apply(
        all_matches,
        category,
        subcategory,
        single_mode,
        assume_yes,
        write,
        workspace,
        categorization_service,
    )
    return categorize_view.report_categorization_result(all_matches, result, recategorized_count, write)


def run(
    *,
    account: str | None = None,
    txid: str | None = None,
    description: str | None = None,
    desc_prefix: str | None = None,
    pattern: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    assume_yes: bool = False,
    workspace: Workspace,
    write: bool = False,
    service: TransactionOperationsService | None = None,
    categorization_service: CategorizationService | None = None,
    txid_file: Path | None = None,
    from_stdin: bool = False,
) -> int:
    """Categorize transactions in ledger files.

    Modes:
    - Single: --txid to target one transaction
    - Batch: --description, --desc-prefix, or --pattern
      (optionally with --amount) to target multiple
    - File batch: --txid-file or --from-stdin to apply many txid→category mappings at once

    Category specification:
    - Use --category "Category" for category only
    - Use --category "Category" --subcategory "Subcategory" OR
    - Use --category "Category:Subcategory" (shorthand)

    Scope:
    - --account ACCOUNT: Categorize in one account
    - (no --account): Categorize across all accounts

    Safety: dry-run by default. Use --write to persist changes.

    Returns:
        Exit code (0 success, 1 error)
    """
    file_batch_mode = txid_file is not None or from_stdin

    if file_batch_mode:
        # Reject combinations of file-batch with single/batch flags
        if any(
            v is not None for v in [txid, description, desc_prefix, pattern, category, subcategory]
        ):
            print_error(
                "--txid-file / --from-stdin cannot be combined with "
                "--txid, --description, --desc-prefix, --pattern, --category, or --subcategory"
            )
            raise CommandAbort(1)
        return _run_file_batch(
            workspace=workspace,
            account=account,
            txid_file=txid_file,
            from_stdin=from_stdin,
            write=write,
            service=service,
            categorization_service=categorization_service,
        )

    if category is None:
        print_error(
            "--category is required (or use --txid-file / --from-stdin for file batch mode)"
        )
        raise CommandAbort(1)

    return _run_single_batch(
        workspace=workspace,
        account=account,
        txid=txid,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
        category=category,
        subcategory=subcategory,
        assume_yes=assume_yes,
        write=write,
        service=service,
        categorization_service=categorization_service,
    )


def _validate_inputs(
    workspace: Workspace,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
    category: str,
    subcategory: str | None,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> tuple[TransactionOperationsService, CategorizationService, str, str | None, bool]:
    """Initialize services and validate inputs. Returns initialized tuple or raises CommandAbort(1)."""
    service, categorization_service = _init_services(workspace, service, categorization_service)
    category, subcategory, cat_warning = build_category_path(category, subcategory)
    if cat_warning:
        categorize_view.print_category_warning(cat_warning)

    mode_result = validate_single_vs_batch_mode(txid, description, desc_prefix, pattern)
    if mode_result is None:
        raise CommandAbort(1)
    single_mode = mode_result

    validation = categorization_service.validate_category(category, subcategory)
    if not validation.is_valid:
        for error in validation.errors:
            print_error(error)
        categorize_view.print_category_add_hint(category)
        raise CommandAbort(1)

    return service, categorization_service, category, subcategory, single_mode


__all__ = ["run"]
