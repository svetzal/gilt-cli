from __future__ import annotations

"""
Categorize transactions (single or batch mode).
"""

from pathlib import Path
from typing import List, Optional
import re

import typer
from rich.table import Table

from .util import console
from finance.model.category_io import load_categories_config, parse_category_path
from finance.model.ledger_io import dump_ledger_csv, load_ledger_csv
from finance.model.account import TransactionGroup


def _find_account_ledgers(data_dir: Path, account: Optional[str]) -> List[Path]:
    """Find ledger files to process."""
    if account:
        ledger_path = data_dir / f"{account}.csv"
        if not ledger_path.exists():
            return []
        return [ledger_path]
    else:
        # All accounts
        return sorted(data_dir.glob("*.csv"))


def _matches_criteria(
    group: TransactionGroup,
    txid: Optional[str],
    description: Optional[str],
    desc_prefix: Optional[str],
    pattern: Optional[re.Pattern],
    amount: Optional[float],
) -> bool:
    """Check if a transaction matches the given criteria."""
    t = group.primary
    
    if txid:
        return t.transaction_id.lower().startswith(txid.lower())
    
    if description:
        return (t.description or "").strip() == description.strip()
    
    if desc_prefix:
        return (t.description or "").lower().startswith(desc_prefix.lower())
    
    if pattern:
        return bool(pattern.search((t.description or "").strip()))
    
    return False


def _apply_amount_filter(groups: List[TransactionGroup], amount: Optional[float]) -> List[TransactionGroup]:
    """Filter groups by amount if specified."""
    if amount is None:
        return groups
    return [g for g in groups if abs(g.primary.amount - amount) < 0.01]


def run(
    *,
    account: Optional[str] = None,
    txid: Optional[str] = None,
    description: Optional[str] = None,
    desc_prefix: Optional[str] = None,
    pattern: Optional[str] = None,
    amount: Optional[float] = None,
    category: str,
    subcategory: Optional[str] = None,
    assume_yes: bool = False,
    config: Path = Path("config/categories.yml"),
    data_dir: Path = Path("data/accounts"),
    write: bool = False,
) -> int:
    """Categorize transactions in ledger files.
    
    Modes:
    - Single: --txid to target one transaction
    - Batch: --description, --desc-prefix, or --pattern (optionally with --amount) to target multiple
    
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
    # Parse category path (supports "Category:Subcategory" syntax)
    if ":" in category:
        cat_name, subcat_from_path = parse_category_path(category)
        if subcategory and subcategory != subcat_from_path:
            console.print(
                f"[yellow]Warning:[/] Both --category contains ':' and --subcategory specified. "
                f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
            )
        subcategory = subcat_from_path
        category = cat_name
    
    # Validate mode selection
    single_mode = bool((txid or "").strip())
    batch_exact_mode = description is not None
    batch_prefix_mode = desc_prefix is not None
    batch_pattern_mode = pattern is not None
    
    modes_selected = sum([single_mode, batch_exact_mode, batch_prefix_mode, batch_pattern_mode])
    if modes_selected != 1:
        console.print("[red]Error:[/] Specify exactly one of --txid, --description, --desc-prefix, or --pattern")
        return 1
    
    # Compile regex pattern if provided
    compiled_pattern = None
    if batch_pattern_mode:
        try:
            compiled_pattern = re.compile(pattern or "", re.IGNORECASE)
        except re.error as e:
            console.print(f"[red]Invalid regex pattern:[/] {e}")
            return 1
    
    # Validate category exists
    category_config = load_categories_config(config)
    if not category_config.validate_category_path(category, subcategory):
        if subcategory:
            console.print(f"[red]Error:[/] Category '{category}:{subcategory}' not found in config")
        else:
            console.print(f"[red]Error:[/] Category '{category}' not found in config")
        console.print(f"Add it first: finance category --add '{category}' --write")
        return 1
    
    # Find ledgers to process
    ledger_paths = _find_account_ledgers(data_dir, account)
    if not ledger_paths:
        if account:
            console.print(f"[red]Error:[/] Ledger not found for account '{account}'")
        else:
            console.print("[red]Error:[/] No ledger files found in data directory")
        return 1
    
    # Process each ledger
    total_matched = 0
    all_matches: List[tuple[Path, TransactionGroup]] = []
    
    for ledger_path in ledger_paths:
        try:
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
            
            # Find matches
            matches = [
                g for g in groups
                if _matches_criteria(g, txid, description, desc_prefix, compiled_pattern, amount)
            ]
            
            # Apply amount filter if specified
            if amount is not None:
                matches = _apply_amount_filter(matches, amount)
            
            for match in matches:
                all_matches.append((ledger_path, match))
                total_matched += 1
        except Exception as e:
            console.print(f"[yellow]Warning:[/] Failed to read {ledger_path.name}: {e}")
            continue
    
    if total_matched == 0:
        console.print("[yellow]No matching transactions found[/]")
        return 0
    
    # Single mode: check for ambiguity
    if single_mode and total_matched > 1:
        console.print(
            f"[yellow]Ambiguous --txid '{txid}':[/] matches {total_matched} transactions"
        )
        console.print("Refine with more characters or specify --account")
        return 1
    
    # Show what will be categorized
    _display_matches(all_matches, category, subcategory)
    
    # Check for re-categorization
    recategorized_count = sum(
        1 for _, g in all_matches
        if g.primary.category is not None and g.primary.category != ""
    )
    
    if recategorized_count > 0:
        console.print(
            f"[yellow]Warning:[/] {recategorized_count} transaction(s) already have a category "
            f"and will be re-categorized"
        )
    
    # Batch mode: require confirmation
    if not single_mode and total_matched > 1 and not assume_yes:
        if not write:
            console.print(
                f"[yellow]Batch mode:[/] {total_matched} transactions would be categorized. "
                f"Use --yes to auto-confirm (dry-run)"
            )
        else:
            import sys
            # Only prompt if in an interactive terminal
            if sys.stdin.isatty():
                if not typer.confirm(f"Categorize {total_matched} transaction(s)?"):
                    console.print("Cancelled")
                    return 0
            # Non-interactive environment (e.g., tests): proceed without prompting
    
    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0
    
    # Apply categorization
    _apply_categorization(all_matches, category, subcategory)
    
    console.print(f"[green]✓[/] Categorized {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: List[tuple[Path, TransactionGroup]],
    category: str,
    subcategory: Optional[str],
) -> None:
    """Display matched transactions in a table."""
    table = Table(title="Matched Transactions", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Current Cat", style="dim")
    table.add_column("→ New Cat", style="green")
    
    for ledger_path, group in matches[:50]:  # Limit display to 50
        t = group.primary
        account_id = ledger_path.stem
        
        current_cat = ""
        if t.category:
            current_cat = t.category
            if t.subcategory:
                current_cat += f":{t.subcategory}"
        
        new_cat = category
        if subcategory:
            new_cat += f":{subcategory}"
        
        table.add_row(
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            f"${t.amount:,.2f}",
            current_cat or "—",
            new_cat,
        )
    
    console.print(table)
    
    if len(matches) > 50:
        console.print(f"[dim]... and {len(matches) - 50} more[/]")


def _apply_categorization(
    matches: List[tuple[Path, TransactionGroup]],
    category: str,
    subcategory: Optional[str],
) -> None:
    """Apply categorization to matched transactions and write back to ledger files."""
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
                    group.primary.category = category
                    group.primary.subcategory = subcategory
            
            # Write back
            updated_csv = dump_ledger_csv(all_groups)
            ledger_path.write_text(updated_csv, encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Error:[/] Failed to update {ledger_path.name}: {e}")
