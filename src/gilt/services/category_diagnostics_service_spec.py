"""
Tests for CategoryDiagnosticsService.

These tests verify the functional core for category diagnosis:
- Counting category usage across transactions
- Identifying orphaned categories
- Detecting possible typos by prefix similarity
- Returning empty results when all categories are valid
"""

from __future__ import annotations

import pytest

from gilt.model.category import Category, CategoryConfig, Subcategory
from gilt.services.category_diagnostics_service import (
    CategoryDiagnosticsService,
)


def _make_config(*categories: tuple[str, list[str]]) -> CategoryConfig:
    """Build a CategoryConfig from (category_name, [subcategory_names]) tuples."""
    cats = []
    for name, subcats in categories:
        cats.append(
            Category(
                name=name,
                subcategories=[Subcategory(name=s) for s in subcats],
            )
        )
    return CategoryConfig(categories=cats)


def _txn(category: str | None, subcategory: str | None = None) -> dict:
    return {"category": category, "subcategory": subcategory}


class DescribeCategoryDiagnosticsService:
    @pytest.fixture
    def config(self) -> CategoryConfig:
        return _make_config(
            ("Utilities", ["Electric", "Water"]),
            ("Groceries", []),
            ("Transport", ["Gas", "Transit"]),
        )

    @pytest.fixture
    def service(self, config: CategoryConfig) -> CategoryDiagnosticsService:
        return CategoryDiagnosticsService(category_config=config)


class DescribeCollectUsedCategories(DescribeCategoryDiagnosticsService):
    """Tests for collect_used_categories method."""

    def it_should_count_category_usage_across_transactions(self, service):
        """Should count how many times each (category, subcategory) pair appears."""
        transactions = [
            _txn("Utilities", "Electric"),
            _txn("Utilities", "Electric"),
            _txn("Groceries"),
            _txn("Groceries"),
            _txn("Groceries"),
        ]

        used = service.collect_used_categories(transactions)

        assert used[("Utilities", "Electric")] == 2
        assert used[("Groceries", None)] == 3

    def it_should_skip_transactions_without_category(self, service):
        """Should not count transactions that have no category set."""
        transactions = [
            _txn(None),
            _txn(""),
            _txn("Groceries"),
        ]

        used = service.collect_used_categories(transactions)

        assert len(used) == 1
        assert ("Groceries", None) in used

    def it_should_return_empty_dict_for_no_transactions(self, service):
        """Should return empty dict when no transactions provided."""
        used = service.collect_used_categories([])
        assert used == {}


class DescribeFindOrphanedCategories(DescribeCategoryDiagnosticsService):
    """Tests for find_orphaned_categories method."""

    def it_should_identify_orphaned_categories_not_in_config(self, service):
        """Should flag categories that appear in transactions but not in config."""
        used = {
            ("Utilities", "Electric"): 5,  # valid
            ("OldCategory", None): 3,  # orphaned
        }

        result = service.find_orphaned_categories(used)

        assert result.total_used == 2
        orphan_cats = [o.category for o in result.orphaned_categories]
        assert "OldCategory" in orphan_cats
        assert "Utilities" not in orphan_cats

    def it_should_return_empty_orphans_when_all_categories_valid(self, service):
        """Should return no orphans when all used categories are defined in config."""
        used = {
            ("Utilities", "Electric"): 10,
            ("Groceries", None): 5,
        }

        result = service.find_orphaned_categories(used)

        assert result.orphaned_categories == []
        assert result.total_used == 2

    def it_should_detect_possible_typos_by_prefix_similarity(self, service):
        """Should flag similar category names as possible typos."""
        # "Utlities" is a typo for "Utilities" (starts with "Utl" vs "Uti")
        # "Utilitees" starts with "Uti" — same prefix as "Utilities"
        used = {
            ("Utilitees", None): 2,  # possible typo of "Utilities"
        }

        result = service.find_orphaned_categories(used)

        assert len(result.orphaned_categories) == 1
        orphan = result.orphaned_categories[0]
        assert orphan.category == "Utilitees"
        assert "Utilities" in orphan.similar_categories

    def it_should_include_transaction_count_in_orphan(self, service):
        """Should report the number of transactions using the orphaned category."""
        used = {("OldName", None): 7}

        result = service.find_orphaned_categories(used)

        assert result.orphaned_categories[0].transaction_count == 7
