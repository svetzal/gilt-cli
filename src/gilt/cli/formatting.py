from __future__ import annotations

from rich.text import Text

from gilt.model.account import Transaction
from gilt.model.category_io import build_category_from_path
from gilt.services.transaction_operations_service import TransactionLookupResult


def fmt_amount(amt: float) -> Text:
    s = f"{amt:,.2f}"
    if amt < 0:
        return Text(s, style="bold red")
    elif amt > 0:
        return Text(s, style="bold green")
    return Text(s)


def fmt_amount_str(amt: float, *, prefix: str = "$") -> str:
    """Format an amount as a plain string with dollar sign and thousands separator."""
    return f"{prefix}{amt:,.2f}"


def fmt_colored_amount(amt: float, *, prefix: str = "$", bold: bool = False) -> str:
    """Format an amount as a Rich markup string with sign-based color (red/green)."""
    s = fmt_amount_str(amt, prefix=prefix)
    weight = " bold" if bold else ""
    if amt < 0:
        return f"[red{weight}]{s}[/]"
    elif amt > 0:
        return f"[green{weight}]{s}[/]"
    return f"[bold]{s}[/]" if bold else s


def format_prefix_lookup_error(result: TransactionLookupResult, prefix: str) -> str:
    """Format a TransactionLookupResult error into a human-readable message."""
    if result.error == "prefix_too_short":
        return f"Transaction ID prefix must be at least 8 characters: '{prefix}'"
    elif result.error == "not_found":
        return f"No transaction found matching ID prefix '{prefix}'"
    else:
        sample = ", ".join(result.ambiguous_matches or [])
        return f"Ambiguous prefix '{prefix}': matches multiple transactions ({sample})"


def base_match_row(account_id: str, t: Transaction) -> tuple:
    """Build the 5-column base row used by match-display functions."""
    return (
        account_id,
        t.transaction_id[:8],
        str(t.date),
        (t.description or "")[:40],
        fmt_amount_str(t.amount),
    )


def category_preview_row(account_id: str, t: Transaction, category_path: str) -> tuple:
    """Build the 6-column category-preview row: base 5 columns + formatted category path."""
    return base_match_row(account_id, t) + (category_path,)


def build_category_path(
    category: str,
    subcategory: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Split 'Category:Subcategory' syntax and resolve --subcategory conflicts.

    Returns (cat_name, subcat_name, warning).
    cat_name is empty string when the input has no valid category part.
    warning is a non-None string when --subcategory conflicts with the ':' syntax.
    """
    cat_name, subcat_from_path = build_category_from_path(category)
    if not cat_name:
        return "", None, None

    if ":" in category and subcategory and subcategory != subcat_from_path:
        warning = (
            f"Both --category contains ':' and --subcategory specified. "
            f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
        )
        return cat_name, subcat_from_path, warning

    if ":" in category:
        return cat_name, subcat_from_path, None

    return cat_name, subcategory, None


__all__ = [
    "fmt_amount",
    "fmt_amount_str",
    "fmt_colored_amount",
    "format_prefix_lookup_error",
    "base_match_row",
    "category_preview_row",
    "build_category_path",
]
