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


def _highlight_prefix(desc: str, prefix: str, style: str = "bold yellow") -> str:
    """Return description with the matching prefix highlighted using Rich markup.

    Case-insensitive match at the start only; preserves original casing in the output.
    If prefix does not match, returns desc unchanged.
    """
    d = desc or ""
    p = (prefix or "").strip().lower()
    if not p:
        return d
    if d.lower().startswith(p):
        n = len(p)
        return f"[{style}]{d[:n]}[/]{d[n:]}"
    return d


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
        sample.append(
            f"{(r.get('date') or '')} id={(r.get('transaction_id') or '')[:8]} amt={(r.get('amount') or '')} desc='{(r.get('description') or '').strip()}'"
        )
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
    txid: str | None = None,
    note_text: str,
    description: str | None = None,
    desc_prefix: str | None = None,
    amount: float | None = None,
    assume_yes: bool = False,
    data_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Attach or update notes on transactions in the account ledger.

    Modes:
    - Single: specify --txid/-t (TxnID8 prefix) to update a single transaction.
    - Batch: specify --description/-d (and optionally --amount/-m) to update all matching rows.

    Returns an exit code (0 success; non-zero for errors). Dry-run when write=False.
    """
    ledger_path = data_dir / f"{account}.csv"

    # Validate mode selection
    single_mode = bool((txid or "").strip())
    batch_exact_mode = (description is not None)
    batch_prefix_mode = (desc_prefix is not None)

    modes_selected = sum([1 if single_mode else 0, 1 if batch_exact_mode else 0, 1 if batch_prefix_mode else 0])
    if modes_selected != 1:
        console.print("[red]Specify exactly one of --txid, --description, or --desc-prefix.[/]")
        return 2

    try:
        text = read_ledger_text(ledger_path)
    except FileNotFoundError:
        console.print(f"[yellow]No ledger found for account[/] [bold]{account}[/] at {ledger_path}")
        return 1

    header, rows = _load_header_and_rows(text, ledger_path)
    if header is None or rows is None:
        return 1

    if single_mode:
        ok, txid_prefix = _validate_prefix(txid or "")
        if not ok:
            console.print("[red]--txid must be at least 8 hex characters (TxnID8).[/]")
            return 2

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
        console.print(f"Description: '{(target.get('description') or '').strip()}'")
        console.print(f"Current note: '{old_note}'")
        console.print(f"New note:     '{note_text}'")

        if not write:
            console.print("[green]Dry-run:[/] no changes written. Use --write to persist.")
            return 0

        # Confirm in single mode unless --yes provided
        if not assume_yes:
            import sys
            if sys.stdin.isatty():
                tx_preview = f"{(target.get('date') or '')} id={(target.get('transaction_id') or '')[:8]} amt={(target.get('amount') or '')}"
                # Show description (no highlighting needed in single mode)
                console.print(f"Description: '{(target.get('description') or '').strip()}'")
                msg = (
                    f"Apply note to {tx_preview}?\n"
                    f"  Current note: '{old_note}'\n"
                    f"  New note:     '{note_text}'"
                )
                if not typer.confirm(msg, default=False):
                    console.print(f"[yellow]Skipped[/] {tx_preview}")
                    return 0
            else:
                # Non-interactive environment (e.g., tests): proceed without prompting to maintain backward compatibility
                pass

        # Apply and write back, preserving column order
        target["notes"] = note_text

        _write_rows(ledger_path, header, rows)

        console.print("[green]Saved note to ledger successfully.[/]")
        return 0

    # Batch mode (exact description or description prefix)
    desc_norm = (description or "").strip()

    def _to_float(v: str | float | int | None) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            try:
                return float(str(v).strip())
            except Exception:
                return None

    amt_target = amount
    match_indexes: list[int] = []

    if batch_exact_mode:
        for i, r in enumerate(rows):
            r_desc = (r.get("description") or "").strip()
            if r_desc != desc_norm:
                continue
            if amt_target is None:
                match_indexes.append(i)
                continue
            r_amt = _to_float(r.get("amount"))
            if r_amt is None:
                continue
            if r_amt == amt_target:
                match_indexes.append(i)

        # Fallback: if no exact signed matches, try sign-insensitive match by absolute amount
        used_sign_insensitive = False
        if not match_indexes and amt_target is not None:
            for i, r in enumerate(rows):
                r_desc = (r.get("description") or "").strip()
                if r_desc != desc_norm:
                    continue
                r_amt = _to_float(r.get("amount"))
                if r_amt is None:
                    continue
                if abs(r_amt) == abs(amt_target):
                    match_indexes.append(i)
            if match_indexes:
                used_sign_insensitive = True

        if not match_indexes:
            if amt_target is None:
                console.print(
                    f"[red]No transactions found[/] in [bold]{account}[/] with description exactly '{desc_norm}'."
                )
            else:
                console.print(
                    f"[red]No transactions found[/] in [bold]{account}[/] with description exactly '{desc_norm}' and amount {amount}."
                )
                console.print("Hint: amounts are signed in the ledger (debits negative, credits positive). Try negating --amount if this was a debit.")
            return 1

        if used_sign_insensitive:
            console.print(
                "[yellow]Note:[/] matched by absolute amount since no signed matches were found. Ledger stores debits as negative amounts."
            )

        if amt_target is None:
            console.print(
                f"[cyan]Will set note[/] for [bold]{len(match_indexes)}[/] transactions in [bold]{account}[/] "
                f"matching description='{desc_norm}'."
            )
        else:
            console.print(
                f"[cyan]Will set note[/] for [bold]{len(match_indexes)}[/] transactions in [bold]{account}[/] "
                f"matching description='{desc_norm}' and amount={amount}."
            )

    elif batch_prefix_mode:
        prefix = (desc_prefix or "").strip().lower()
        used_sign_insensitive = False  # Only relevant for amount filtering fallback
        for i, r in enumerate(rows):
            r_desc = (r.get("description") or "").strip()
            if not r_desc.lower().startswith(prefix):
                continue
            if amt_target is None:
                match_indexes.append(i)
                continue
            r_amt = _to_float(r.get("amount"))
            if r_amt is None:
                continue
            if r_amt == amt_target:
                match_indexes.append(i)
        # Fallback by absolute value if needed
        if not match_indexes and amt_target is not None:
            for i, r in enumerate(rows):
                r_desc = (r.get("description") or "").strip()
                if not r_desc.lower().startswith(prefix):
                    continue
                r_amt = _to_float(r.get("amount"))
                if r_amt is None:
                    continue
                if abs(r_amt) == abs(amt_target):
                    match_indexes.append(i)
            if match_indexes:
                used_sign_insensitive = True

        if not match_indexes:
            if amt_target is None:
                console.print(
                    f"[red]No transactions found[/] in [bold]{account}[/] with description prefix '{desc_prefix}'."
                )
            else:
                console.print(
                    f"[red]No transactions found[/] in [bold]{account}[/] with description prefix '{desc_prefix}' and amount {amount}."
                )
                console.print("Hint: amounts are signed in the ledger (debits negative, credits positive). Try negating --amount if this was a debit.")
            return 1

        if used_sign_insensitive:
            console.print(
                "[yellow]Note:[/] matched by absolute amount since no signed matches were found. Ledger stores debits as negative amounts."
            )

        if amt_target is None:
            console.print(
                f"[cyan]Will set note[/] for [bold]{len(match_indexes)}[/] transactions in [bold]{account}[/] "
                f"matching description prefix='{desc_prefix}'."
            )
        else:
            console.print(
                f"[cyan]Will set note[/] for [bold]{len(match_indexes)}[/] transactions in [bold]{account}[/] "
                f"matching description prefix='{desc_prefix}' and amount={amount}."
            )

    # Show up to 5 examples (include description; highlight prefix in prefix mode)
    for i in match_indexes[:5]:
        r = rows[i]
        raw_desc = (r.get('description') or '').strip()
        desc_display = _highlight_prefix(raw_desc, desc_prefix) if batch_prefix_mode else raw_desc
        console.print(
            f" - {(r.get('date') or '')} id={(r.get('transaction_id') or '')[:8]} amt={(r.get('amount') or '')} desc='{desc_display}' current_note='{r.get('notes') or ''}'"
        )
    console.print(f"New note: '{note_text}'")

    if not write:
        console.print("[green]Dry-run:[/] no changes written. Use --write to persist.")
        return 0

    # Apply with optional per-transaction confirmation
    applied = 0
    if assume_yes:
        for i in match_indexes:
            rows[i]["notes"] = note_text
            applied += 1
    else:
        for i in match_indexes:
            r = rows[i]
            tx_preview = f"{(r.get('date') or '')} id={(r.get('transaction_id') or '')[:8]} amt={(r.get('amount') or '')}"
            old_note = r.get('notes') or ''
            # Show description with highlight if prefix mode is active
            raw_desc = (r.get('description') or '').strip()
            desc_display = _highlight_prefix(raw_desc, desc_prefix) if batch_prefix_mode else raw_desc
            console.print(f"Description: '{desc_display}'")
            msg = (
                f"Apply note to {tx_preview}?\n"
                f"  Current note: '{old_note}'\n"
                f"  New note:     '{note_text}'"
            )
            if typer.confirm(msg, default=False):
                rows[i]["notes"] = note_text
                applied += 1
            else:
                console.print(f"[yellow]Skipped[/] {tx_preview}")

    _write_rows(ledger_path, header, rows)
    console.print(f"[green]Saved notes to ledger successfully.[/] Applied to {applied} of {len(match_indexes)} matches.")
    return 0
