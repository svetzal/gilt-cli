from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Iterable, Tuple

from .util import console
from finance.ingest import load_accounts_config, plan_normalization, normalize_file
from finance.model.ledger_io import load_ledger_csv
from finance.transfer.linker import link_transfers


def _discover_inputs(ingest_dir: Path, accounts) -> List[Path]:
    """Discover candidate input CSV files based on account patterns, or all *.csv."""
    patterns: List[str] = []
    for acct in accounts:
        patterns.extend(acct.source_patterns or [])

    if not patterns:
        return sorted(ingest_dir.glob("*.csv"))

    seen = set()
    inputs: List[Path] = []
    for pat in patterns:
        for p in ingest_dir.glob(pat):
            if p not in seen:
                inputs.append(p)
                seen.add(p)
    return sorted(inputs)


def _print_plan(plan: Iterable[Tuple[Path, str | None]], inputs: List[Path]) -> None:
    console.print("[bold]Ingestion/Normalization Plan (dry-run)[/]")
    console.print(f"Inputs matched: {len(inputs)}")
    for p, acct_id in plan:
        console.print(f"  - {p.name} -> account_id={acct_id or 'UNKNOWN'}")
    console.print("No files were read. No outputs were written.")


def _ledger_paths_to_load(output_dir: Path, accounts) -> List[Path]:
    paths: List[Path] = []
    # Prefer configured accounts if available
    if accounts:
        for acct in accounts:
            p = output_dir / f"{acct.account_id}.csv"
            if p.exists():
                paths.append(p)
    # Also include any other *.csv present (to cover unmanaged accounts)
    for p in sorted(output_dir.glob("*.csv")):
        if p not in paths:
            paths.append(p)
    return paths


def _load_ledger_counts(paths: Iterable[Path]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for lp in paths:
        try:
            text = lp.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
            counts[lp.name] = len(groups)
        except Exception:
            counts[lp.name] = 0
    return counts


def _perform_normalization(plan: Iterable[Tuple[Path, str | None]], output_dir: Path) -> Tuple[int, int]:
    written = 0
    skipped = 0
    for p, acct_id in plan:
        if not acct_id:
            console.print(
                f"[yellow][skip][/yellow] Could not infer account for {p.name}; update config/accounts.yml"
            )
            skipped += 1
            continue
        try:
            out_path = normalize_file(p, acct_id, output_dir)
            console.print(f"[green][ok][/green] Wrote {out_path}")
            written += 1
        except Exception as e:
            console.print(f"[red][error][/red] Failed to normalize {p.name}: {e}")
            skipped += 1
    return written, skipped


def _link_transfers_and_report(output_dir: Path) -> int:
    console.print("[bold]Linking transfers across ledgers[/]")
    modified = link_transfers(
        processed_dir=output_dir,
        window_days=3,
        epsilon_direct=0.0,
        epsilon_interac=0.0,
        fee_max_amount=3.00,
        fee_day_window=1,
        write=True,
    )
    if modified:
        console.print(
            f"[green][ok][/green] Updated {modified} ledger file(s) with transfer metadata"
        )
    else:
        console.print("[dim]No transfer links identified or no updates needed[/]")
    return modified


def run(
    *,
    config: Path = Path("config/accounts.yml"),
    ingest_dir: Path = Path("ingest"),
    output_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Ingest and normalize raw CSVs into standardized per-account ledgers.

    Dry-run by default (write=False). Returns an exit code.
    """
    # Load account config (best-effort)
    accounts = load_accounts_config(config)

    # Discover candidate inputs
    inputs: List[Path] = _discover_inputs(ingest_dir, accounts)
    plan = plan_normalization(inputs, output_dir, accounts)

    if not write:
        _print_plan(plan, inputs)
        return 0

    # Write mode
    # 1) Load existing ledgers from disk into models for all accounts (validation-only)
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_paths = _ledger_paths_to_load(output_dir, accounts)

    pre_counts = _load_ledger_counts(ledger_paths)
    if pre_counts:
        console.print("[bold]Loaded existing ledgers (pre-ingest)[/]")
        for name, cnt in sorted(pre_counts.items()):
            console.print(f"  - {name}: {cnt} transactions (groups)")

    # 2) Perform normalization/writes
    written, skipped = _perform_normalization(plan, output_dir)

    # 3) Reload ledgers after ingest to ensure serialization back to disk
    post_counts = _load_ledger_counts(ledger_paths)
    if post_counts:
        console.print("[bold]Reloaded ledgers (post-ingest)[/]")
        for name, cnt in sorted(post_counts.items()):
            delta = cnt - pre_counts.get(name, 0)
            sign = "+" if delta >= 0 else ""
            console.print(f"  - {name}: {cnt} groups ({sign}{delta} change)")

    # 4) Identify and mark transfers between accounts
    _link_transfers_and_report(output_dir)

    console.print(f"Done. Written={written}, Skipped={skipped}")
    return 0
