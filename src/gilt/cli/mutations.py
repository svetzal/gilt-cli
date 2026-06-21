from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from gilt.cli.console import confirm_interactively, console, print_dry_run_message, print_error
from gilt.cli.event_sourcing_bootstrap import require_event_sourcing, require_persistence_service
from gilt.model.account import TransactionGroup
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceResult,
    CategorizationUpdate,
)
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.services.transaction_operations_service import (
    BatchPreview,
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.workspace import Workspace


def build_categorization_updates(
    rows: Iterable[tuple[str, str, str, str | None, float]],
    *,
    source: str,
) -> list[CategorizationUpdate]:
    """Build CategorizationUpdate objects from (transaction_id, account_id, category, subcategory, confidence) tuples."""
    return [
        CategorizationUpdate(
            transaction_id=transaction_id,
            account_id=account_id,
            category=category,
            subcategory=subcategory,
            source=source,
            confidence=confidence,
        )
        for transaction_id, account_id, category, subcategory, confidence in rows
    ]


def run_categorization_updates(
    ready: EventSourcingReadyResult,
    workspace: Workspace,
    updates: list,
) -> CategorizationPersistenceResult:
    """Construct persistence service and forward updates to persist_categorizations."""
    return require_persistence_service(ready, workspace).persist_categorizations(updates)


def persist_categorization_matches(
    matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
    ready: EventSourcingReadyResult,
    workspace: Workspace,
    *,
    source: str,
) -> int:
    """Build and apply categorization updates for a list of (account_id, group) matches."""
    updates = build_categorization_updates(
        ((g.primary.transaction_id, acct, category, subcategory, 1.0) for acct, g in matches),
        source=source,
    )
    result = run_categorization_updates(ready, workspace, updates)
    return result.transactions_updated


def persist_row_categorizations(
    rows: Iterable[tuple[str, str, str, str | None, float]],
    ready: EventSourcingReadyResult,
    workspace: Workspace,
    *,
    source: str,
) -> CategorizationPersistenceResult:
    """Build categorization updates from rows and persist them."""
    return run_categorization_updates(ready, workspace, build_categorization_updates(rows, source=source))


def run_persisted_mutation(
    *,
    matches: Sequence,
    display: Callable[[], None],
    confirm_prompt: str,
    assume_yes: bool,
    write: bool,
    workspace: Workspace,
    persist: Callable[[EventSourcingReadyResult], None],
    on_success: Callable[[], None] | None = None,
) -> int:
    """Orchestrate confirm → dry-run gate → require_event_sourcing → persist → on_success."""
    def apply() -> int:
        ready = require_event_sourcing(workspace)
        if ready is None:
            return 1
        persist(ready)
        if on_success is not None:
            on_success()
        return 0

    return run_confirmed_mutation(
        matches=matches,
        display=display,
        confirm_prompt=confirm_prompt,
        assume_yes=assume_yes,
        write=write,
        apply=apply,
    )


def run_confirmed_mutation(
    *,
    matches: Sequence,
    display: Callable[[], None],
    confirm_prompt: str,
    assume_yes: bool,
    write: bool,
    apply: Callable[[], int],
) -> int:
    """Orchestrate the confirm → dry-run gate → apply mutation sequence."""
    display()
    if not assume_yes and not confirm_interactively(confirm_prompt):
        console.print("Cancelled")
        return 0
    if not write:
        print_dry_run_message()
        return 0
    return apply()


def find_matches_by_criteria(
    groups_by_account: dict[str, list[TransactionGroup]],
    criteria: SearchCriteria,
    service: TransactionOperationsService,
    *,
    txid: str | None = None,
) -> list[tuple[str, TransactionGroup]] | None:
    all_matches: list[tuple[str, TransactionGroup]] = []
    for account_id, groups in groups_by_account.items():
        result = service.find_transaction_targets(
            groups,
            txid=txid,
            description=criteria.description,
            desc_prefix=criteria.desc_prefix,
            pattern=criteria.pattern,
            amount=criteria.amount,
        )
        if isinstance(result, str):
            if result:
                print_error(result)
            return None
        for match in result:
            all_matches.append((account_id, match))
    return all_matches


def search_by_criteria(
    service: TransactionOperationsService,
    criteria: SearchCriteria,
    groups: list[TransactionGroup],
    pattern: str | None,
) -> BatchPreview | None:
    """Search for transactions by criteria, printing warnings and errors as needed.

    Calls find_by_criteria on the service. If the pattern is invalid, prints an error
    and returns None. If sign-insensitive matching was used, prints a note.

    Args:
        service: Service used to perform the search.
        criteria: Search criteria (description, desc_prefix, pattern, amount).
        groups: Transaction groups to search within.
        pattern: The raw pattern string (used only in the error message).

    Returns:
        A BatchPreview on success, or None if the pattern was invalid.
    """
    preview = service.find_by_criteria(criteria, groups)

    if preview.invalid_pattern:
        print_error(f"Invalid regex pattern: {pattern}")
        return None

    if preview.used_sign_insensitive:
        console.print(
            "[yellow]Note:[/] matched by absolute amount "
            "since no signed matches were found. "
            "Ledger stores debits as negative amounts."
        )

    return preview


def validate_single_vs_batch_mode(
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> bool | None:
    """Validate exactly one of txid/description/desc_prefix/pattern is specified.

    Returns True if single mode (txid), False if batch mode, or None on error.
    Prints an error message when no mode or multiple modes are specified.
    """
    single_mode = bool((txid or "").strip())
    modes_selected = sum(
        [single_mode, description is not None, desc_prefix is not None, pattern is not None]
    )
    if modes_selected != 1:
        print_error("Specify exactly one of --txid, --description, --desc-prefix, or --pattern")
        return None
    return single_mode


def find_by_id_prefix(
    service: TransactionOperationsService,
    prefix: str,
    groups: list[TransactionGroup],
) -> list[TransactionGroup] | str:
    """Find transactions by ID prefix with validation and formatted error messages.

    Validates the prefix is at least 8 characters, calls find_by_id_prefix,
    and returns either the matched groups or an error string describing the problem.

    Args:
        service: Service used to perform the lookup.
        prefix: Transaction ID prefix to look up.
        groups: Transaction groups to search within.

    Returns:
        A list of matching TransactionGroup objects on success, or a non-empty
        error string describing the problem (not_found or ambiguous).
    """
    normalized = prefix.strip().lower()
    if len(normalized) < 8:
        return f"Transaction ID prefix must be at least 8 characters. Got: {len(normalized)}"

    result = service.find_by_id_prefix(normalized, groups)

    if result.type == "not_found":
        return f"No transaction found matching ID prefix '{normalized}'"

    if result.type == "ambiguous":
        sample = []
        for g in (result.matches or [])[:5]:
            t = g.primary
            sample.append(
                f"{t.date} id={t.transaction_id[:8]} amt={t.amount} desc='{(t.description or '').strip()}'"
            )
        detail = (" Examples: " + "; ".join(sample)) if sample else ""
        return (
            f"Ambiguous prefix '{normalized}': matches {len(result.matches or [])} transactions."
            + detail
        )

    return [result.transaction] if result.transaction else []


__all__ = [
    "build_categorization_updates",
    "run_categorization_updates",
    "persist_categorization_matches",
    "persist_row_categorizations",
    "run_persisted_mutation",
    "run_confirmed_mutation",
    "find_matches_by_criteria",
    "search_by_criteria",
    "validate_single_vs_batch_mode",
    "find_by_id_prefix",
]
