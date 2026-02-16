"""
Tests for category management service - functional core for category CRUD operations.

Following pytest-bdd-style naming with arrange-act-assert pattern.
Tests cover:
- Usage counting across transaction groups
- Removal planning with/without force
- Category addition with validation
- Budget setting with validation
- Edge cases (empty lists, missing categories, invalid inputs)
"""
from __future__ import annotations

from datetime import date

import pytest

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import (
    Budget,
    BudgetPeriod,
    Category,
    CategoryConfig,
    Subcategory,
)
from gilt.services.category_management_service import CategoryManagementService


@pytest.fixture
def sample_category_config() -> CategoryConfig:
    """Sample category configuration for testing."""
    return CategoryConfig(
        categories=[
            Category(
                name="Housing",
                description="Housing expenses",
                subcategories=[
                    Subcategory(name="Rent", description="Monthly rent"),
                    Subcategory(name="Utilities", description="Utilities"),
                ],
                budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Groceries",
                description="Food and groceries",
                budget=Budget(amount=500.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Transportation",
                description="Transport costs",
            ),
        ]
    )


@pytest.fixture
def sample_transactions() -> list[TransactionGroup]:
    """Sample transactions with various categorizations."""
    return [
        TransactionGroup(
            group_id="group1",
            primary=Transaction(
                transaction_id="txn00001",
                date=date(2025, 1, 15),
                description="Rent payment",
                amount=-1500.00,
                currency="CAD",
                account_id="CHQ",
                category="Housing",
                subcategory="Rent",
            ),
        ),
        TransactionGroup(
            group_id="group2",
            primary=Transaction(
                transaction_id="txn00002",
                date=date(2025, 1, 16),
                description="Example Utility Payment",
                amount=-85.50,
                currency="CAD",
                account_id="CHQ",
                category="Housing",
                subcategory="Utilities",
            ),
        ),
        TransactionGroup(
            group_id="group3",
            primary=Transaction(
                transaction_id="txn00003",
                date=date(2025, 1, 17),
                description="Grocery store",
                amount=-120.00,
                currency="CAD",
                account_id="MC",
                category="Groceries",
            ),
        ),
        TransactionGroup(
            group_id="group4",
            primary=Transaction(
                transaction_id="txn00004",
                date=date(2025, 1, 18),
                description="Transit pass",
                amount=-150.00,
                currency="CAD",
                account_id="MC",
                category="Transportation",
            ),
        ),
        TransactionGroup(
            group_id="group5",
            primary=Transaction(
                transaction_id="txn00005",
                date=date(2025, 1, 19),
                description="Uncategorized transaction",
                amount=-50.00,
                currency="CAD",
                account_id="CHQ",
            ),
        ),
    ]


class DescribeCountUsage:
    """Tests for count_usage() method."""

    def it_should_count_category_usage(
        self, sample_category_config, sample_transactions
    ):
        """Should count transactions using a category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        usage = service.count_usage("Housing", None, sample_transactions)

        # Assert
        assert usage.category == "Housing"
        assert usage.subcategory is None
        assert usage.transaction_count == 2  # Rent + Utilities
        assert len(usage.transaction_ids) == 2
        assert "txn00001" in usage.transaction_ids
        assert "txn00002" in usage.transaction_ids

    def it_should_count_subcategory_usage(
        self, sample_category_config, sample_transactions
    ):
        """Should count transactions using a specific subcategory."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        usage = service.count_usage("Housing", "Rent", sample_transactions)

        # Assert
        assert usage.category == "Housing"
        assert usage.subcategory == "Rent"
        assert usage.transaction_count == 1
        assert usage.transaction_ids == ["txn00001"]

    def it_should_return_zero_for_unused_category(
        self, sample_category_config, sample_transactions
    ):
        """Should return zero count for category not used in transactions."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        config = sample_category_config
        config.categories.append(Category(name="Entertainment", description="Fun stuff"))

        # Act
        usage = service.count_usage("Entertainment", None, sample_transactions)

        # Assert
        assert usage.category == "Entertainment"
        assert usage.transaction_count == 0
        assert usage.transaction_ids == []

    def it_should_handle_empty_transaction_list(self, sample_category_config):
        """Should handle empty transaction list gracefully."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        usage = service.count_usage("Housing", None, [])

        # Assert
        assert usage.transaction_count == 0
        assert usage.transaction_ids == []

    def it_should_ignore_transactions_without_category(
        self, sample_category_config, sample_transactions
    ):
        """Should not count uncategorized transactions."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act - count all categories
        housing_usage = service.count_usage("Housing", None, sample_transactions)
        groceries_usage = service.count_usage("Groceries", None, sample_transactions)
        transport_usage = service.count_usage("Transportation", None, sample_transactions)

        # Assert - total categorized = 4, uncategorized txn00005 not counted
        total_categorized = (
            housing_usage.transaction_count
            + groceries_usage.transaction_count
            + transport_usage.transaction_count
        )
        assert total_categorized == 4


class DescribePlanRemoval:
    """Tests for plan_removal() method."""

    def it_should_allow_removal_of_unused_category(
        self, sample_category_config, sample_transactions
    ):
        """Should allow removing category not used in transactions."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        config = sample_category_config
        config.categories.append(Category(name="Entertainment", description="Fun stuff"))

        # Act
        plan = service.plan_removal("Entertainment", None, sample_transactions, force=False)

        # Assert
        assert plan.can_remove is True
        assert plan.usage.transaction_count == 0
        assert plan.has_subcategories is False
        assert len(plan.warnings) == 0

    def it_should_block_removal_of_used_category_without_force(
        self, sample_category_config, sample_transactions
    ):
        """Should block removing used category without force flag."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Groceries", None, sample_transactions, force=False)

        # Assert
        assert plan.can_remove is False
        assert plan.usage.transaction_count == 1
        assert len(plan.warnings) == 1
        assert "used in 1 transaction" in plan.warnings[0]

    def it_should_allow_removal_of_used_category_with_force(
        self, sample_category_config, sample_transactions
    ):
        """Should allow removing used category with force flag."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Groceries", None, sample_transactions, force=True)

        # Assert
        assert plan.can_remove is True
        assert plan.usage.transaction_count == 1
        assert len(plan.warnings) == 1  # Warning still present

    def it_should_block_removal_of_category_with_subcategories_without_force(
        self, sample_category_config, sample_transactions
    ):
        """Should block removing category with subcategories without force."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Housing", None, sample_transactions, force=False)

        # Assert
        assert plan.can_remove is False
        assert plan.has_subcategories is True
        assert plan.usage.transaction_count == 2
        assert len(plan.warnings) == 2  # Used + has subcategories
        assert any("used in 2 transaction" in w for w in plan.warnings)
        assert any("2 subcategory" in w for w in plan.warnings)

    def it_should_allow_removal_of_category_with_subcategories_with_force(
        self, sample_category_config, sample_transactions
    ):
        """Should allow removing category with subcategories when forced."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Housing", None, sample_transactions, force=True)

        # Assert
        assert plan.can_remove is True
        assert plan.has_subcategories is True
        assert len(plan.warnings) == 2  # Warnings still present

    def it_should_allow_removal_of_unused_subcategory(
        self, sample_category_config, sample_transactions
    ):
        """Should allow removing unused subcategory."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        config = sample_category_config
        housing = config.find_category("Housing")
        housing.subcategories.append(Subcategory(name="Insurance", description="Home insurance"))

        # Act
        plan = service.plan_removal("Housing", "Insurance", sample_transactions, force=False)

        # Assert
        assert plan.can_remove is True
        assert plan.usage.transaction_count == 0
        assert plan.has_subcategories is False
        assert len(plan.warnings) == 0

    def it_should_block_removal_of_used_subcategory_without_force(
        self, sample_category_config, sample_transactions
    ):
        """Should block removing used subcategory without force."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Housing", "Rent", sample_transactions, force=False)

        # Assert
        assert plan.can_remove is False
        assert plan.usage.transaction_count == 1
        assert len(plan.warnings) == 1
        assert "used in 1 transaction" in plan.warnings[0]

    def it_should_handle_nonexistent_category(
        self, sample_category_config, sample_transactions
    ):
        """Should handle removal plan for nonexistent category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("NonExistent", None, sample_transactions, force=False)

        # Assert
        assert plan.can_remove is True  # Nothing to remove
        assert plan.usage.transaction_count == 0
        assert len(plan.warnings) == 1
        assert "not found" in plan.warnings[0]

    def it_should_handle_nonexistent_subcategory(
        self, sample_category_config, sample_transactions
    ):
        """Should handle removal plan for nonexistent subcategory."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Housing", "NonExistent", sample_transactions, force=False)

        # Assert
        assert plan.can_remove is True  # Nothing to remove
        assert plan.usage.transaction_count == 0
        assert len(plan.warnings) == 1
        assert "not found" in plan.warnings[0]


class DescribeAddCategory:
    """Tests for add_category() method."""

    def it_should_add_new_category(self, sample_category_config):
        """Should successfully add a new category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        initial_count = len(sample_category_config.categories)

        # Act
        result = service.add_category("Entertainment", None, "Fun stuff")

        # Assert
        assert result.success is True
        assert result.already_exists is False
        assert result.added_category == "Entertainment"
        assert result.added_subcategory is None
        assert len(result.errors) == 0
        assert len(sample_category_config.categories) == initial_count + 1

        # Verify category was added with correct properties
        cat = sample_category_config.find_category("Entertainment")
        assert cat is not None
        assert cat.name == "Entertainment"
        assert cat.description == "Fun stuff"

    def it_should_add_new_subcategory(self, sample_category_config):
        """Should successfully add a new subcategory to existing category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        housing = sample_category_config.find_category("Housing")
        initial_subcat_count = len(housing.subcategories)

        # Act
        result = service.add_category("Housing", "Insurance", "Home insurance")

        # Assert
        assert result.success is True
        assert result.already_exists is False
        assert result.added_category == "Housing"
        assert result.added_subcategory == "Insurance"
        assert len(result.errors) == 0
        assert len(housing.subcategories) == initial_subcat_count + 1

        # Verify subcategory was added with correct properties
        subcat = housing.get_subcategory("Insurance")
        assert subcat is not None
        assert subcat.name == "Insurance"
        assert subcat.description == "Home insurance"

    def it_should_reject_adding_duplicate_category(self, sample_category_config):
        """Should reject adding a category that already exists."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        initial_count = len(sample_category_config.categories)

        # Act
        result = service.add_category("Housing", None, "Duplicate")

        # Assert
        assert result.success is False
        assert result.already_exists is True
        assert len(result.errors) == 1
        assert "already exists" in result.errors[0]
        assert len(sample_category_config.categories) == initial_count

    def it_should_reject_adding_duplicate_subcategory(self, sample_category_config):
        """Should reject adding a subcategory that already exists."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        housing = sample_category_config.find_category("Housing")
        initial_subcat_count = len(housing.subcategories)

        # Act
        result = service.add_category("Housing", "Rent", "Duplicate")

        # Assert
        assert result.success is False
        assert result.already_exists is True
        assert len(result.errors) == 1
        assert "already exists" in result.errors[0]
        assert len(housing.subcategories) == initial_subcat_count

    def it_should_reject_subcategory_without_parent_category(self, sample_category_config):
        """Should reject adding subcategory when parent category doesn't exist."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.add_category("NonExistent", "Subcategory", "Test")

        # Assert
        assert result.success is False
        assert result.already_exists is False
        assert len(result.errors) == 2
        assert "does not exist" in result.errors[0]
        assert "Create parent category first" in result.errors[1]

    def it_should_reject_empty_category_name(self, sample_category_config):
        """Should reject adding category with empty name."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.add_category("", None, "Test")

        # Assert
        assert result.success is False
        assert len(result.errors) == 1
        assert "cannot be empty" in result.errors[0]

    def it_should_reject_whitespace_only_category_name(self, sample_category_config):
        """Should reject adding category with whitespace-only name."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.add_category("   ", None, "Test")

        # Assert
        assert result.success is False
        assert len(result.errors) == 1
        assert "cannot be empty" in result.errors[0]

    def it_should_add_category_without_description(self, sample_category_config):
        """Should successfully add category without description."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.add_category("Miscellaneous", None, None)

        # Assert
        assert result.success is True
        assert result.already_exists is False
        cat = sample_category_config.find_category("Miscellaneous")
        assert cat is not None
        assert cat.description is None


class DescribeSetBudget:
    """Tests for set_budget() method."""

    def it_should_set_budget_for_category(self, sample_category_config):
        """Should successfully set budget for category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        transport = sample_category_config.find_category("Transportation")
        assert transport.budget is None

        # Act
        result = service.set_budget("Transportation", 300.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is True
        assert result.previous_budget is None
        assert result.new_budget is not None
        assert result.new_budget.amount == 300.0
        assert result.new_budget.period == BudgetPeriod.monthly
        assert len(result.errors) == 0

        # Verify budget was set on category
        assert transport.budget is not None
        assert transport.budget.amount == 300.0
        assert transport.budget.period == BudgetPeriod.monthly

    def it_should_update_existing_budget(self, sample_category_config):
        """Should update existing budget for category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        groceries = sample_category_config.find_category("Groceries")
        old_budget = groceries.budget
        assert old_budget.amount == 500.0

        # Act
        result = service.set_budget("Groceries", 600.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is True
        assert result.previous_budget is not None
        assert result.previous_budget.amount == 500.0
        assert result.new_budget is not None
        assert result.new_budget.amount == 600.0
        assert groceries.budget.amount == 600.0

    def it_should_set_yearly_budget(self, sample_category_config):
        """Should set yearly budget period."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.set_budget("Transportation", 3600.0, BudgetPeriod.yearly)

        # Assert
        assert result.success is True
        assert result.new_budget is not None
        assert result.new_budget.period == BudgetPeriod.yearly
        transport = sample_category_config.find_category("Transportation")
        assert transport.budget.period == BudgetPeriod.yearly

    def it_should_reject_budget_for_nonexistent_category(self, sample_category_config):
        """Should reject setting budget for category that doesn't exist."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.set_budget("NonExistent", 100.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is False
        assert len(result.errors) == 2
        assert "not found" in result.errors[0]
        assert "Create category first" in result.errors[1]

    def it_should_reject_zero_budget(self, sample_category_config):
        """Should reject zero budget amount."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.set_budget("Transportation", 0.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is False
        assert len(result.errors) == 1
        assert "must be positive" in result.errors[0]

    def it_should_reject_negative_budget(self, sample_category_config):
        """Should reject negative budget amount."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.set_budget("Transportation", -100.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is False
        assert len(result.errors) == 1
        assert "must be positive" in result.errors[0]

    def it_should_reject_empty_category_name(self, sample_category_config):
        """Should reject empty category name."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.set_budget("", 100.0, BudgetPeriod.monthly)

        # Assert
        assert result.success is False
        assert len(result.errors) == 1
        assert "cannot be empty" in result.errors[0]


class DescribeRemoveCategory:
    """Tests for remove_category() method."""

    def it_should_remove_category(self, sample_category_config):
        """Should successfully remove a category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        initial_count = len(sample_category_config.categories)

        # Act
        result = service.remove_category("Transportation")

        # Assert
        assert result is True
        assert len(sample_category_config.categories) == initial_count - 1
        assert sample_category_config.find_category("Transportation") is None

    def it_should_remove_subcategory(self, sample_category_config):
        """Should successfully remove a subcategory."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        housing = sample_category_config.find_category("Housing")
        initial_subcat_count = len(housing.subcategories)

        # Act
        result = service.remove_category("Housing", "Utilities")

        # Assert
        assert result is True
        assert len(housing.subcategories) == initial_subcat_count - 1
        assert not housing.has_subcategory("Utilities")

    def it_should_return_false_for_nonexistent_category(self, sample_category_config):
        """Should return False when trying to remove nonexistent category."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.remove_category("NonExistent")

        # Assert
        assert result is False

    def it_should_return_false_for_nonexistent_subcategory(self, sample_category_config):
        """Should return False when trying to remove nonexistent subcategory."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        result = service.remove_category("Housing", "NonExistent")

        # Assert
        assert result is False


class DescribeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def it_should_handle_empty_category_config(self):
        """Should handle operations on empty category config."""
        # Arrange
        empty_config = CategoryConfig(categories=[])
        service = CategoryManagementService(empty_config)

        # Act
        usage = service.count_usage("Any", None, [])
        plan = service.plan_removal("Any", None, [], force=False)
        add_result = service.add_category("New", None)

        # Assert
        assert usage.transaction_count == 0
        assert plan.can_remove is True  # Nothing to remove
        assert add_result.success is True  # Can add to empty config

    def it_should_handle_category_with_no_subcategories(self, sample_category_config):
        """Should handle category operations when category has no subcategories."""
        # Arrange
        service = CategoryManagementService(sample_category_config)

        # Act
        plan = service.plan_removal("Groceries", None, [], force=False)

        # Assert
        assert plan.has_subcategories is False
        assert plan.can_remove is True  # No usage, no subcategories

    def it_should_count_only_exact_category_matches(self, sample_category_config):
        """Should count only exact category matches, not partial matches."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        transactions = [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="t1",
                    date=date(2025, 1, 1),
                    description="Test",
                    amount=-100.0,
                    currency="CAD",
                    account_id="CHQ",
                    category="Housing",
                ),
            ),
            TransactionGroup(
                group_id="g2",
                primary=Transaction(
                    transaction_id="t2",
                    date=date(2025, 1, 2),
                    description="Test",
                    amount=-100.0,
                    currency="CAD",
                    account_id="CHQ",
                    category="HousingOther",  # Different category
                ),
            ),
        ]

        # Act
        usage = service.count_usage("Housing", None, transactions)

        # Assert
        assert usage.transaction_count == 1  # Only exact match

    def it_should_preserve_other_categories_when_adding(self, sample_category_config):
        """Should not affect existing categories when adding new ones."""
        # Arrange
        service = CategoryManagementService(sample_category_config)
        initial_categories = [c.name for c in sample_category_config.categories]

        # Act
        service.add_category("NewCategory", None)

        # Assert
        current_categories = [c.name for c in sample_category_config.categories]
        for cat in initial_categories:
            assert cat in current_categories
