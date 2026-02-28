from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.text import Text

console = Console()


def read_ledger_text(ledger_path: Path) -> str:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")
    return ledger_path.read_text(encoding="utf-8")


def fmt_amount(amt: float) -> Text:
    s = f"{amt:,.2f}"
    if amt < 0:
        return Text(s, style="bold red")
    elif amt > 0:
        return Text(s, style="bold green")
    return Text(s)
