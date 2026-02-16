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
from typing import Dict, List, Tuple

from gilt.model.ledger_io import load_ledger_csv, dump_ledger_csv
from gilt.model.account import TransactionGroup

# We reuse the matching logic from the matching module (no CLI deps)
from gilt.transfer.matching import compute_matches, Match


def _build_indexes(
    processed_dir: Path,
) -> Tuple[Dict[str, List[TransactionGroup]], Dict[str, Tuple[str, TransactionGroup]]]:
    """Load all ledgers and build indexes.

    Returns:
      - file_groups: mapping ledger file path -> list of TransactionGroup
      - txn_index: mapping transaction_id -> (ledger_file_path, TransactionGroup)
    """
    file_groups: Dict[str, List[TransactionGroup]] = {}
    txn_index: Dict[str, Tuple[str, TransactionGroup]] = {}

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
    existing = meta.get("transfer")
    # If existing matches the same counterparty txn id, consider idempotent
    if isinstance(existing, dict):
        if existing.get("counterparty_transaction_id") == payload.get(
            "counterparty_transaction_id"
        ) and existing.get("role") == payload.get("role"):
            # Update score/method if changed (non-destructive)
            changed = False
            for k in ("score", "method", "fee_txn_ids"):
                if payload.get(k) is not None and existing.get(k) != payload.get(k):
                    existing[k] = payload.get(k)
                    changed = True
            # Write back only if changed
            if changed:
                meta["transfer"] = existing
                group.primary.metadata = meta
            return changed
    # Otherwise set fresh
    meta["transfer"] = payload
    group.primary.metadata = meta
    return True


def link_transfers(
    processed_dir: Path = Path("data/accounts"),
    *,
    window_days: int = 3,
    epsilon_direct: float = 0.0,
    epsilon_interac: float = 0.0,
    fee_max_amount: float = 3.00,
    fee_day_window: int = 1,
    write: bool = False,
) -> int:
    """Identify transfers across ledgers and mark them in-place via metadata.

    Returns the number of ledger files modified.
    """
    processed_dir = Path(processed_dir)
    # 1) Find matches using existing logic (operates on processed_dir files)
    matches: List[Match] = compute_matches(
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
            "role": "debit",
            "counterparty_account_id": c.account_id,
            "counterparty_transaction_id": c.transaction_id,
            "amount": abs(d.amount),
            "method": m.method,
            "score": m.score,
            "fee_txn_ids": list(m.fee_txn_ids or []),
        }
        credit_payload = {
            "role": "credit",  # counterpart to the initiating debit is always the receiving side for this pair
            "counterparty_account_id": d.account_id,
            "counterparty_transaction_id": d.transaction_id,
            "amount": abs(d.amount),
            "method": m.method,
            "score": m.score,
            "fee_txn_ids": [],  # fees only attached on debit side for now
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
