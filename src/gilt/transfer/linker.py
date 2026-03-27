from __future__ import annotations

"""
Transfer linker: identify and mark inter-account transfers in per-account ledgers.

- Pure local processing: reads/writes data/accounts/*.csv only when write=True.
- Uses existing detection heuristics from gilt.transfer.matching.
- Marks matches by enriching Transaction.metadata with a 'transfer' sub-object.

Metadata shape stored on each matched primary transaction:
transfer = {
    'role': 'debit' | 'credit',
    'counterparty_account_id': str,
    'counterparty_transaction_id': str,
    'amount': float,                # absolute amount of the transfer
    'method': str,                  # 'direct_same_day' | 'window_interac' | etc.
    'score': float,                 # 0..1
    'fee_txn_ids': List[str],       # any nearby fees (attached on the debit side)
}

Idempotent: if the same counterpart is already recorded, it will not duplicate.
"""

from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.transfer._constants import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_AMOUNT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_COUNTERPARTY_TRANSACTION_ID,
    TRANSFER_FEE_TXN_IDS,
    TRANSFER_META_KEY,
    TRANSFER_METHOD,
    TRANSFER_ROLE,
    TRANSFER_SCORE,
)

# We reuse the matching logic from the matching module (no CLI deps)
from gilt.transfer.matching import Match, compute_matches


def _build_indexes(
    processed_dir: Path,
) -> tuple[dict[str, list[TransactionGroup]], dict[str, tuple[str, TransactionGroup]]]:
    """Load all ledgers and build indexes.

    Returns:
      - file_groups: mapping ledger file path -> list of TransactionGroup
      - txn_index: mapping transaction_id -> (ledger_file_path, TransactionGroup)
    """
    file_groups: dict[str, list[TransactionGroup]] = {}
    txn_index: dict[str, tuple[str, TransactionGroup]] = {}

    for csv_path in sorted((processed_dir).glob("*.csv")):
        try:
            text = csv_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
        except Exception:
            groups = []
        file_groups[str(csv_path)] = groups
        for g in groups:
            tid = g.primary.transaction_id
            if tid:
                txn_index[tid] = (str(csv_path), g)
    return file_groups, txn_index


def _ensure_transfer_metadata(group: TransactionGroup, payload: dict) -> bool:
    """Ensure the group's primary.metadata contains a 'transfer' dict matching payload.

    Returns True if metadata was modified, False otherwise.
    """
    meta = group.primary.metadata or {}
    existing = meta.get(TRANSFER_META_KEY)
    # If existing matches the same counterparty txn id, consider idempotent
    if (
        isinstance(existing, dict)
        and existing.get(TRANSFER_COUNTERPARTY_TRANSACTION_ID)
        == payload.get(TRANSFER_COUNTERPARTY_TRANSACTION_ID)
        and existing.get(TRANSFER_ROLE) == payload.get(TRANSFER_ROLE)
    ):
        # Update score/method if changed (non-destructive)
        changed = False
        for k in (TRANSFER_SCORE, TRANSFER_METHOD, TRANSFER_FEE_TXN_IDS):
            if payload.get(k) is not None and existing.get(k) != payload.get(k):
                existing[k] = payload.get(k)
                changed = True
        # Write back only if changed
        if changed:
            meta[TRANSFER_META_KEY] = existing
            group.primary.metadata = meta
        return changed
    # Otherwise set fresh
    meta[TRANSFER_META_KEY] = payload
    group.primary.metadata = meta
    return True


# Default parameters for transfer linking. Both ingest and reingest use these values.
TRANSFER_LINK_WINDOW_DAYS: int = 3
TRANSFER_LINK_EPSILON_DIRECT: float = 0.0
TRANSFER_LINK_EPSILON_INTERAC: float = 0.0
TRANSFER_LINK_FEE_MAX_AMOUNT: float = 3.00
TRANSFER_LINK_FEE_DAY_WINDOW: int = 1


def link_transfers(
    processed_dir: Path = Path("data/accounts"),
    *,
    window_days: int = TRANSFER_LINK_WINDOW_DAYS,
    epsilon_direct: float = TRANSFER_LINK_EPSILON_DIRECT,
    epsilon_interac: float = TRANSFER_LINK_EPSILON_INTERAC,
    fee_max_amount: float = TRANSFER_LINK_FEE_MAX_AMOUNT,
    fee_day_window: int = TRANSFER_LINK_FEE_DAY_WINDOW,
    write: bool = False,
) -> int:
    """Identify transfers across ledgers and mark them in-place via metadata.

    Returns the number of ledger files modified.
    """
    processed_dir = Path(processed_dir)
    # 1) Find matches using existing logic (operates on processed_dir files)
    matches: list[Match] = compute_matches(
        processed_dir=processed_dir,
        window_days=window_days,
        epsilon_direct=epsilon_direct,
        epsilon_interac=epsilon_interac,
        fee_max_amount=fee_max_amount,
        fee_day_window=fee_day_window,
    )
    if not matches:
        return 0

    # 2) Load ledgers and index by transaction_id
    file_groups, txn_index = _build_indexes(processed_dir)

    # 3) Apply metadata marks for each side of each match
    modified_files: set[str] = set()

    for m in matches:
        d = m.debit
        c = m.credit
        debit_entry = txn_index.get(d.transaction_id)
        credit_entry = txn_index.get(c.transaction_id)
        if not debit_entry or not credit_entry:
            # Skip if we somehow can't find these in current ledgers
            continue
        d_path, d_group = debit_entry
        c_path, c_group = credit_entry

        # Build payloads
        debit_payload = {
            TRANSFER_ROLE: ROLE_DEBIT,
            TRANSFER_COUNTERPARTY_ACCOUNT_ID: c.account_id,
            TRANSFER_COUNTERPARTY_TRANSACTION_ID: c.transaction_id,
            TRANSFER_AMOUNT: abs(d.amount),
            TRANSFER_METHOD: m.method,
            TRANSFER_SCORE: m.score,
            TRANSFER_FEE_TXN_IDS: list(m.fee_txn_ids or []),
        }
        credit_payload = {
            TRANSFER_ROLE: ROLE_CREDIT,  # counterpart to the initiating debit is always the receiving side for this pair
            TRANSFER_COUNTERPARTY_ACCOUNT_ID: d.account_id,
            TRANSFER_COUNTERPARTY_TRANSACTION_ID: d.transaction_id,
            TRANSFER_AMOUNT: abs(d.amount),
            TRANSFER_METHOD: m.method,
            TRANSFER_SCORE: m.score,
            TRANSFER_FEE_TXN_IDS: [],  # fees only attached on debit side for now
        }

        if _ensure_transfer_metadata(d_group, debit_payload):
            modified_files.add(d_path)
        if _ensure_transfer_metadata(c_group, credit_payload):
            modified_files.add(c_path)

    # 4) Persist changes if requested
    if write and modified_files:
        for path_str in sorted(modified_files):
            groups = file_groups.get(path_str, [])
            csv_text = dump_ledger_csv(groups)
            Path(path_str).write_text(csv_text, encoding="utf-8")

    return len(modified_files)


__all__ = ["link_transfers"]
