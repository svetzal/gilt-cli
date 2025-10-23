from __future__ import annotations

"""
Display uncategorized transactions.
"""

from datetime import date
from pathlib import Path
from typing import List, Optional

from rich.table import Table

from .util import console
from finance.model.ledger_io import load_ledger_csv
from finance.model.account import TransactionGroup


def run(
    *,
    account: Optional[str] = None,
    year: Optional[int] = None,
    limit: Optional[int] = None,
    min_amount: Optional[float] = None,
    data_dir: Path = Path("data/accounts"),
) -> int:
    """Display transactions without categories.
    
    Helps identify which transactions still need categorization.
    Sorted by description (for grouping similar transactions), then date.
    
    Args:
        account: Optional account ID to filter
        year: Optional year to filter
        limit: Optional max number of transactions to show
        min_amount: Optional minimum absolute amount filter
        data_dir: Directory containing ledger CSVs
        
    Returns:
        Exit code (always 0)
    """
    # Determine which ledgers to read
    if account:
        ledger_paths = [data_dir / f"{account}.csv"]
        if not ledger_paths[0].exists():
            console.print(f"[red]Error:[/] Ledger not found for account '{account}'")
            return 1
    else:
        ledger_paths = sorted(data_dir.glob("*.csv"))
    
    if not ledger_paths:
        console.print("[yellow]No ledger files found[/]")
        return 0
    
    # Collect all uncategorized transactions
    uncategorized: List[tuple[str, TransactionGroup]] = []
    
    for ledger_path in ledger_paths:
        try:
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency="CAD")
            account_id = ledger_path.stem
            
            for group in groups:
                t = group.primary
                
                # Filter: must not have category
                if t.category:
                    continue
                
                # Filter: year if specified
                if year is not None:
                    if isinstance(t.date, date):
                        if t.date.year != year:
                            continue
                    else:
                        # Skip if date is not parseable
                        continue
                
                # Filter: min_amount if specified
                if min_amount is not None:
                    if abs(t.amount) < min_amount:
                        continue
                
                uncategorized.append((account_id, group))
        except Exception as e:
            console.print(f"[yellow]Warning:[/] Failed to read {ledger_path.name}: {e}")
            continue
    
    if not uncategorized:
        console.print("[green]All transactions are categorized![/]")
        return 0
    
    # Sort by description (for grouping), then date
    uncategorized.sort(key=lambda x: (x[1].primary.description or "", x[1].primary.date))
    
    # Apply limit if specified
    if limit:
        displayed = uncategorized[:limit]
        remaining = len(uncategorized) - limit
    else:
        displayed = uncategorized
        remaining = 0
    
    # Build table
    title = "Uncategorized Transactions"
    if year:
        title += f" ({year})"
    
    table = Table(title=title, show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Notes", style="dim")
    
    for account_id, group in displayed:
        t = group.primary
        table.add_row(
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:50],
            f"${t.amount:,.2f}",
            (t.notes or "")[:30] if t.notes else "",
        )
    
    console.print(table)
    
    # Summary
    console.print(f"\n[bold]Total uncategorized:[/] {len(uncategorized)} transaction(s)")
    if remaining > 0:
        console.print(f"[dim]Showing first {limit}, {remaining} more not displayed[/]")
    
    # Helpful hint
    console.print("\n[dim]Tip: Use 'finance categorize' to assign categories to these transactions[/]")
    
    return 0
