from __future__ import annotations

"""
Ledger CSV <-> Model graph conversion (pure text, no disk I/O).

This module defines a flat 2D CSV representation for per-account ledgers that can
be losslessly converted to/from the canonical Pydantic models defined in
gilt.model.account.

- Backward compatible with existing ledgers in data/accounts/*.csv that only
  contain primary transaction rows (no splits). Such CSVs are interpreted as
  one TransactionGroup per row with group_id := transaction_id and no splits.
- Forward schema allows split lines in the same flat CSV via a `row_type` column.

Privacy:
- Pure local text processing; no external I/O.
- No logging of raw data here; callers decide what to print.
"""

import csv
import io
import json
from collections.abc import Iterable

from pydantic import ValidationError

from .account import SplitLine, Transaction, TransactionGroup

# Row typing for flat CSV representation
ROW_TYPE_PRIMARY = "primary"
ROW_TYPE_SPLIT = "split"

# Columns for the flat ledger CSV. We union Transaction fields with split-only fields
# and a couple of control columns (row_type, group_id, metadata_json).
# Note: Keep order stable for deterministic outputs.
LEDGER_COLUMNS: list[str] = [
    # Control / linkage
    "row_type",  # "primary" or "split"; missing -> treat as primary (back-compat)
    "group_id",  # required for split rows; optional for primary (defaults to transaction_id)
    # Primary/Transaction fields
    "transaction_id",
    "date",
    "description",
    "amount",
    "currency",
    "account_id",
    "counterparty",
    "category",
    "subcategory",
    "notes",
    "source_file",
    "metadata_json",  # JSON for Transaction.metadata (dict) — may be empty
    # Split-only fields
    "line_id",
    "target_account_id",
    "split_category",
    "split_subcategory",
    "split_memo",
    "split_percent",
]


def _to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        # Keep plain repr; formatting to 2dp is handled by CSV consumer if needed
        return f"{v:f}".rstrip("0").rstrip(".") if not v.is_integer() else str(int(v))
    return str(v)


# ---- Parsing helpers to keep load_ledger_csv simple ----


def _parse_metadata_field(s: str) -> dict:
    s = (s or "").strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _normalize_row(
    r: dict, default_currency: str | None, legacy_mode: bool
) -> tuple[
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    dict,
]:
    """Extract and normalize common fields from a CSV row.
    Returns a tuple:
    (row_type, group_id, tid, date_str, description, amount_str, currency, account_id,
     counterparty, category, subcategory, notes, source_file, metadata)
    """
    row_type = (r.get("row_type") or "").strip().lower() if not legacy_mode else ROW_TYPE_PRIMARY
    tid = (r.get("transaction_id") or "").strip()
    group_id = (r.get("group_id") or "").strip() or tid
    date_str = (r.get("date") or "").strip()
    description = (r.get("description") or "").strip()
    amount_str = (r.get("amount") or "").strip()
    currency = (r.get("currency") or "").strip() or (default_currency or "CAD")
    account_id = (r.get("account_id") or "").strip()
    counterparty = (r.get("counterparty") or "").strip() or None
    category = (r.get("category") or "").strip() or None
    subcategory = (r.get("subcategory") or "").strip() or None
    notes = (r.get("notes") or "").strip() or None
    source_file = (r.get("source_file") or "").strip() or None
    metadata = _parse_metadata_field((r.get("metadata_json") or "").strip())
    return (
        row_type,
        group_id,
        tid,
        date_str,
        description,
        amount_str,
        currency,
        account_id,
        counterparty,
        category,
        subcategory,
        notes,
        source_file,
        metadata,
    )


def _build_primary_transaction(
    *,
    group_id: str,
    tid: str,
    date_str: str,
    description: str,
    amount_str: str,
    currency: str,
    account_id: str,
    counterparty: str | None,
    category: str | None,
    subcategory: str | None,
    notes: str | None,
    source_file: str | None,
    metadata: dict,
) -> Transaction:
    try:
        amount_val = float(amount_str) if amount_str else 0.0
        return Transaction(
            transaction_id=tid,
            date=date_str,  # type: ignore[arg-type]
            description=description,
            amount=amount_val,
            currency=currency,
            account_id=account_id,
            counterparty=counterparty,
            category=category,
            subcategory=subcategory,
            notes=notes,
            source_file=source_file,
            metadata=metadata,
        )
    except ValidationError as ve:
        raise ValueError(f"Invalid primary transaction in group {group_id}: {ve}") from ve


def _build_split_line(r: dict, amount_str: str) -> SplitLine:
    split_percent_raw = (r.get("split_percent") or "").strip()
    return SplitLine(
        line_id=(r.get("line_id") or "").strip() or None,
        amount=float(amount_str) if amount_str else 0.0,
        target_account_id=(r.get("target_account_id") or "").strip() or None,
        category=(r.get("split_category") or "").strip() or None,
        subcategory=(r.get("split_subcategory") or "").strip() or None,
        memo=(r.get("split_memo") or "").strip() or None,
        percent=float(split_percent_raw) if split_percent_raw else None,
    )


def dump_ledger_csv(groups: Iterable[TransactionGroup]) -> str:
    """Serialize TransactionGroup objects into a flat CSV string.

    - Emits a header with LEDGER_COLUMNS.
    - For each group: one primary row (row_type=primary), followed by zero or more split rows.
    - Uses JSON to serialize Transaction.metadata into metadata_json.
    - Does not perform any file I/O.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=LEDGER_COLUMNS, lineterminator="\n")
    writer.writeheader()

    for g in groups:
        t = g.primary
        group_id = g.group_id or t.transaction_id
        # Primary row
        writer.writerow(
            {
                "row_type": ROW_TYPE_PRIMARY,
                "group_id": group_id,
                "transaction_id": t.transaction_id,
                "date": _to_str(t.date),
                "description": t.description or "",
                "amount": _to_str(t.amount),
                "currency": t.currency or "",
                "account_id": t.account_id,
                "counterparty": t.counterparty or "",
                "category": t.category or "",
                "subcategory": t.subcategory or "",
                "notes": t.notes or "",
                "source_file": t.source_file or "",
                "metadata_json": json.dumps(t.metadata or {}, separators=(",", ":")),
                "line_id": "",
                "target_account_id": "",
                "split_category": "",
                "split_subcategory": "",
                "split_memo": "",
                "split_percent": "",
            }
        )
        # Split rows
        for i, s in enumerate(g.splits):
            writer.writerow(
                {
                    "row_type": ROW_TYPE_SPLIT,
                    "group_id": group_id,
                    "transaction_id": t.transaction_id,
                    "date": _to_str(t.date),  # Repeat date for convenience when viewing
                    "description": "",  # keep primary description only on primary row
                    "amount": _to_str(s.amount),  # split amount value
                    "currency": t.currency or "",
                    "account_id": t.account_id,
                    "counterparty": "",
                    "category": "",
                    "subcategory": "",
                    "notes": "",
                    "source_file": t.source_file or "",
                    "metadata_json": "",
                    "line_id": s.line_id or f"{group_id}-L{i + 1}",
                    "target_account_id": s.target_account_id or "",
                    "split_category": s.category or "",
                    "split_subcategory": s.subcategory or "",
                    "split_memo": s.memo or "",
                    "split_percent": _to_str(s.percent) if s.percent is not None else "",
                }
            )

    return output.getvalue()


def load_ledger_csv(text: str, *, default_currency: str | None = None) -> list[TransactionGroup]:
    """Parse a flat ledger CSV string into TransactionGroup objects.

    - Accepts both the forward schema (row_type present) and legacy schema
      (no row_type/group_id). Legacy rows become groups with group_id=transaction_id.
    - Unknown columns are ignored.
    - metadata_json is parsed when present; invalid JSON results in an empty dict.
    - default_currency is used when currency is blank on a primary row.
    """
    buf = io.StringIO(text)
    reader = csv.DictReader(buf)
    rows = list(reader)

    # Detect legacy mode (no row_type column)
    legacy_mode = (reader.fieldnames is not None) and ("row_type" not in reader.fieldnames)

    # Buckets per group_id
    groups: dict[str, dict[str, object]] = {}

    for r in rows:
        (
            row_type,
            group_id,
            tid,
            date_str,
            description,
            amount_str,
            currency,
            account_id,
            counterparty,
            category,
            subcategory,
            notes,
            source_file,
            metadata,
        ) = _normalize_row(r, default_currency, legacy_mode)

        bucket = groups.setdefault(group_id, {"primary": None, "splits": []})

        if row_type in (ROW_TYPE_PRIMARY, ""):
            primary = _build_primary_transaction(
                group_id=group_id,
                tid=tid,
                date_str=date_str,
                description=description,
                amount_str=amount_str,
                currency=currency,
                account_id=account_id,
                counterparty=counterparty,
                category=category,
                subcategory=subcategory,
                notes=notes,
                source_file=source_file,
                metadata=metadata,
            )
            bucket["primary"] = primary  # type: ignore[index-assignment]
        elif row_type == ROW_TYPE_SPLIT:
            line = _build_split_line(r, amount_str)
            (bucket["splits"]).append(line)  # type: ignore[index]
        else:
            # Unknown row type => ignore
            continue

    # Build TransactionGroup objects and validate
    result: list[TransactionGroup] = []
    for gid, parts in groups.items():
        primary: Transaction | None = parts.get("primary")  # type: ignore[assignment]
        splits: list[SplitLine] = parts.get("splits") or []  # type: ignore[assignment]
        if primary is None:
            # Only splits without a primary -> skip as malformed
            continue
        try:
            tg = TransactionGroup(group_id=gid, primary=primary, splits=splits)
        except ValidationError as ve:
            raise ValueError(f"Invalid TransactionGroup {gid}: {ve}") from ve
        result.append(tg)

    # Deterministic order: by date, then account_id, then abs(amount), then group_id
    result.sort(
        key=lambda g: (g.primary.date, g.primary.account_id, abs(g.primary.amount), g.group_id)
    )
    return result


__all__ = [
    "dump_ledger_csv",
    "load_ledger_csv",
    "LEDGER_COLUMNS",
    "ROW_TYPE_PRIMARY",
    "ROW_TYPE_SPLIT",
]
