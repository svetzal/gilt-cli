"""
Category diagnostics service - functional core for diagnosing category issues.

Extracts the logic for:
- Collecting which categories are used in transactions (with counts)
- Finding categories used in transactions but not defined in config (orphans)
- Detecting possible typos by comparing against defined category names

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions accept pre-loaded data (no file I/O).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from gilt.model.category import CategoryConfig


@dataclass
class OrphanedCategory:
    """A category found in transactions but not defined in config."""

    category: str
    subcategory: str | None
    transaction_count: int
    similar_categories: list[str] = field(default_factory=list)


@dataclass
class DiagnosticsResult:
    """Result of a category diagnostics scan."""

    orphaned_categories: list[OrphanedCategory]
    total_used: int
    total_defined: int


class CategoryDiagnosticsService:
    """
    Service for diagnosing category configuration issues.

    This is the functional core - accepts pre-loaded transaction data
    and configuration, performs no file I/O.

    Responsibilities:
    - Count (category, subcategory) usage across transactions
    - Find categories used but not in config (orphans)
    - Detect potential typos by prefix similarity
    """

    def __init__(self, category_config: CategoryConfig) -> None:
        self._category_config = category_config

    def collect_used_categories(
        self, transactions: list[dict]
    ) -> dict[tuple[str, str | None], int]:
        """Count how many transactions use each (category, subcategory) pair.

        Args:
            transactions: List of transaction dicts with 'category' and 'subcategory' keys.

        Returns:
            Dict mapping (category, subcategory) to transaction count.
            Only includes transactions that have a non-empty category.
        """
        used: dict[tuple[str, str | None], int] = defaultdict(int)
        for txn in transactions:
            cat = txn.get("category")
            if not cat:
                continue
            subcat = txn.get("subcategory") or None
            used[(cat, subcat)] += 1
        return dict(used)

    def find_orphaned_categories(
        self, used: dict[tuple[str, str | None], int]
    ) -> DiagnosticsResult:
        """Find categories that are used in transactions but not defined in config.

        Also checks for possible typos by comparing the first 3 characters of
        each orphaned category name against all defined category names.

        Args:
            used: Dict mapping (category, subcategory) to transaction count,
                  as returned by collect_used_categories().

        Returns:
            DiagnosticsResult with orphaned categories and totals.
        """
        defined = self._build_defined_set()

        orphaned: list[OrphanedCategory] = []
        for (cat, subcat), count in used.items():
            if (cat, subcat) not in defined:
                similar = self._find_similar(cat, defined)
                orphaned.append(
                    OrphanedCategory(
                        category=cat,
                        subcategory=subcat,
                        transaction_count=count,
                        similar_categories=similar,
                    )
                )

        return DiagnosticsResult(
            orphaned_categories=orphaned,
            total_used=len(used),
            total_defined=len(defined),
        )

    def _build_defined_set(self) -> set[tuple[str, str | None]]:
        """Build the set of all valid (category, subcategory) combinations."""
        defined: set[tuple[str, str | None]] = set()
        for cat in self._category_config.categories:
            defined.add((cat.name, None))
            for subcat in cat.subcategories:
                defined.add((cat.name, subcat.name))
        return defined

    def _find_similar(self, cat: str, defined: set[tuple[str, str | None]]) -> list[str]:
        """Find defined category names with the same 3-character prefix as cat."""
        if len(cat) < 3:
            return []
        prefix = cat[:3].lower()
        return list(
            {
                defined_cat
                for defined_cat, _ in defined
                if defined_cat != cat and defined_cat.lower().startswith(prefix)
            }
        )


__all__ = [
    "CategoryDiagnosticsService",
    "DiagnosticsResult",
    "OrphanedCategory",
]
