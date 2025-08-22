from __future__ import annotations

from pathlib import Path
import csv

import typer

from .util import console, read_ledger_text
from finance.ingest import STANDARD_FIELDS


# --- Small helpers to reduce cognitive complexity while preserving behavior ---

def _validate_prefix(txid: str) -> tuple[bool, str]:
    p = (txid or "").strip().lower()
    if len(p) < 8:
        return False, p
    return True, p


def _load_header_and_rows(text: str, ledger_path: Path) -> tuple[list[str], list[dict]] | tuple[None, None]:
    reader = csv.DictReader(text.splitlines())
    header = list(reader.fieldnames or [])
    if not header:
        console.print(f"[red]Ledger file appears empty or malformed:[/] {ledger_path}")
        return None, None
    if "notes" not in header:
        header.append("notes")
    rows = list(reader)
    return header, rows


def _find_matches(rows: list[dict], prefix: str) -> list[int]:
    return [i for i, r in enumerate(rows) if (r.get("transaction_id", "").strip().lower().startswith(prefix))]


def _report_ambiguity(prefix: str, matches: list[int], rows: list[dict]) -> None:
    sample = []
    for i in matches[:5]:
        r = rows[i]
        sample.append(f"{(r.get('date') or '')} id={(r.get('transaction_id') or '')[:8]} amt={(r.get('amount') or '')}")
    console.print(
        f"[yellow]Ambiguous prefix[/] [bold]{prefix}[/]: matches {len(matches)} transactions. "
        + (" Examples: " + "; ".join(sample) if sample else "")
    )
    console.print("Refine --txid with more characters to disambiguate.")


def _write_rows(ledger_path: Path, header: list[str], rows: list[dict]) -> None:
    # Ensure all rows have all header keys to satisfy DictWriter
    for r in rows:
        for col in header:
            if col not in r:
                r[col] = ""
    fieldnames = header if header else STANDARD_FIELDS
    with open(ledger_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def run(
    *,
    account: str,
    txid: str,
    note_text: str,
    data_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Attach or update a note on a specific transaction in the account ledger.

    Returns an exit code (0 success; non-zero for errors). Dry-run when write=False.
    """
    ledger_path = data_dir / f"{account}.csv"

    ok, txid_prefix = _validate_prefix(txid)
    if not ok:
        console.print("[red]--txid must be at least 8 hex characters (TxnID8).[/]")
        return 2

    try:
        text = read_ledger_text(ledger_path)
    except FileNotFoundError:
        console.print(f"[yellow]No ledger found for account[/] [bold]{account}[/] at {ledger_path}")
        return 1

    header, rows = _load_header_and_rows(text, ledger_path)
    if header is None or rows is None:
        return 1

    matches = _find_matches(rows, txid_prefix)

    if not matches:
        console.print(
            f"[red]No transaction found[/] matching prefix [bold]{txid_prefix}[/] in account [bold]{account}[/]."
        )
        return 1

    if len(matches) > 1:
        _report_ambiguity(txid_prefix, matches, rows)
        return 2

    idx = matches[0]
    target = rows[idx]
    old_note = target.get("notes") or ""

    console.print(
        f"[cyan]Will set note[/] for [bold]{account}[/] txn [bold]{(target.get('transaction_id') or '')[:8]}[/] "
        f"on date {(target.get('date') or '')} amount {(target.get('amount') or '')}."
    )
    console.print(f"Current note: '{old_note}'")
    console.print(f"New note:     '{note_text}'")

    if not write:
        console.print("[green]Dry-run:[/] no changes written. Use --write to persist.")
        return 0

    # Apply and write back, preserving column order
    target["notes"] = note_text

    _write_rows(ledger_path, header, rows)

    console.print("[green]Saved note to ledger successfully.[/]")
    return 0
