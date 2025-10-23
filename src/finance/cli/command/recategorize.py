from __future__ import annotations

"""
Rename categories across all ledger files.

Useful when renaming categories in categories.yml to update existing
transaction categorizations.
"""

from pathlib import Path
from typing import List, Optional

import typer
from rich.table import Table

from .util import console
from finance.model.category_io import parse_category_path
from finance.model.ledger_io import dump_ledger_csv, load_ledger_csv
from finance.model.account import TransactionGroup


def run(
    *,
    from_category: str,
    to_category: str,
    data_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Rename a category across all ledger files.
    
    Useful when renaming categories in categories.yml to update existing
    transaction categorizations.
    
    Args:
        from_category: Original category name (supports "Category:Subcategory" syntax)
        to_category: New category name (supports "Category:Subcategory" syntax)
        data_dir: Directory containing ledger CSVs
        write: Persist changes (default: dry-run)
        
    Returns:
        Exit code (0 success, 1 error)
    """
    # Parse category paths
    from_cat, from_subcat = parse_category_path(from_category)
    to_cat, to_subcat = parse_category_path(to_category)
    
    if not from_cat:
        console.print("[red]Error:[/] --from category cannot be empty")
        return 1
    
    if not to_cat:
        console.print("[red]Error:[/] --to category cannot be empty")
        return 1
    
    # Find all ledger files
    ledger_paths = sorted(data_dir.glob("*.csv"))
    if not ledger_paths:
        console.print("[yellow]No ledger files found[/]")
        return 0
    
    # Process each ledger
    total_matched = 0
    all_matches: List[tuple[Path, TransactionGroup]] = []
    
    for ledger_path in ledger_paths:
        try:
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
            
            # Find matches
            for group in groups:
                t = group.primary
                
                # Match category
                if t.category != from_cat:
                    continue
                
                # Match subcategory if specified in --from
                if from_subcat is not None:
                    if t.subcategory != from_subcat:
                        continue
                
                all_matches.append((ledger_path, group))
                total_matched += 1
        except Exception as e:
            console.print(f"[yellow]Warning:[/] Failed to read {ledger_path.name}: {e}")
            continue
    
    if total_matched == 0:
        console.print(f"[yellow]No transactions found with category '{from_category}'[/]")
        return 0
    
    # Show what will be renamed
    _display_matches(all_matches, from_category, to_category)
    
    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0
    
    # Confirm
    import sys
    if sys.stdin.isatty():
        if not typer.confirm(f"Rename category in {total_matched} transaction(s)?"):
            console.print("Cancelled")
            return 0
    
    # Apply renaming
    _apply_renaming(all_matches, to_cat, to_subcat)
    
    console.print(f"[green]✓[/] Renamed category in {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: List[tuple[Path, TransactionGroup]],
    from_category: str,
    to_category: str,
) -> None:
    """Display matched transactions in a table."""
    table = Table(title="Transactions to Recategorize", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Current", style="dim")
    table.add_column("→ New", style="green")
    
    for ledger_path, group in matches[:50]:  # Limit display to 50
        t = group.primary
        account_id = ledger_path.stem
        
        current_cat = from_category
        new_cat = to_category
        
        table.add_row(
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            f"${t.amount:,.2f}",
            current_cat,
            new_cat,
        )
    
    console.print(table)
    
    if len(matches) > 50:
        console.print(f"[dim]... and {len(matches) - 50} more[/]")
    
    console.print(f"\n[bold]Total:[/] {len(matches)} transaction(s)")


def _apply_renaming(
    matches: List[tuple[Path, TransactionGroup]],
    to_category: str,
    to_subcategory: Optional[str],
) -> None:
    """Apply category renaming to matched transactions and write back to ledger files."""
    # Group matches by ledger file
    ledgers_to_update: dict[Path, List[TransactionGroup]] = {}
    for ledger_path, group in matches:
        if ledger_path not in ledgers_to_update:
            ledgers_to_update[ledger_path] = []
        ledgers_to_update[ledger_path].append(group)
    
    # Update each ledger file
    for ledger_path, matched_groups in ledgers_to_update.items():
        try:
            # Reload full ledger
            text = ledger_path.read_text(encoding="utf-8")
            all_groups = load_ledger_csv(text, default_currency="CAD")
            
            # Update matched groups
            matched_ids = {g.primary.transaction_id for g in matched_groups}
            for group in all_groups:
                if group.primary.transaction_id in matched_ids:
                    group.primary.category = to_category
                    # Only update subcategory if explicitly specified in --to
                    # Otherwise preserve the existing subcategory
                    if to_subcategory is not None:
                        group.primary.subcategory = to_subcategory
            
            # Write back
            updated_csv = dump_ledger_csv(all_groups)
            ledger_path.write_text(updated_csv, encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Error:[/] Failed to update {ledger_path.name}: {e}")
