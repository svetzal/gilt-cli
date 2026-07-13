from __future__ import annotations

"""
Tests for category command.
"""

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.category import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import load_categories_config
from gilt.testing import build_workspace_with_ledger, make_group


class DescribeCategoryAdd:
    """Tests for category --add command."""

    def it_should_add_new_category_with_write(self, tmp_path):
        ws = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        # Dry-run should not modify
        rc = run(
            add="Housing",
            description="Housing expenses",
            workspace=ws,
            write=False,
        )
        assert rc == 0
        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 0

        # Write should add category
        rc = run(
            add="Housing",
            description="Housing expenses",
            workspace=ws,
            write=True,
        )
        assert rc == 0
        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 1
        assert config.categories[0].name == "Housing"
        assert config.categories[0].description == "Housing expenses"

    def it_should_add_subcategory_to_existing_category(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path, config=CategoryConfig(categories=[Category(name="Housing")])
        )

        # Add subcategory
        rc = run(
            add="Housing:Utilities",
            description="Electric, gas, water",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 1
        assert len(config.categories[0].subcategories) == 1
        assert config.categories[0].subcategories[0].name == "Utilities"

    def it_should_error_when_adding_subcategory_without_parent(self, tmp_path, capsys):
        ws = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        with pytest.raises(CommandAbort) as exc_info:
            run(
                add="Housing:Utilities",
                workspace=ws,
                write=True,
            )
        assert exc_info.value.code == 1

        # The error must name the missing parent and tell the user how to
        # create it, so the failure is actionable rather than silent.
        output = capsys.readouterr().out
        assert "Housing" in output
        assert "does not exist" in output
        assert "gilt category --add 'Housing' --write" in output

        # Critically, the config must not have been written with an orphan
        # subcategory entry.
        config = load_categories_config(ws.categories_config)
        assert config.categories == []

    def it_should_skip_when_category_already_exists(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path, config=CategoryConfig(categories=[Category(name="Housing")])
        )

        rc = run(
            add="Housing",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        # Should still have only one category
        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 1


class DescribeCategoryRemove:
    """Tests for category --remove command."""

    def it_should_remove_category_with_write(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(
                categories=[
                    Category(name="Housing"),
                    Category(name="Transportation"),
                ]
            ),
        )

        # Dry-run should not modify
        rc = run(
            remove="Housing",
            workspace=ws,
            write=False,
        )
        assert rc == 0
        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 2

        # Write with force should remove
        rc = run(
            remove="Housing",
            force=True,
            workspace=ws,
            write=True,
        )
        assert rc == 0
        config = load_categories_config(ws.categories_config)
        assert len(config.categories) == 1
        assert config.categories[0].name == "Transportation"

    def it_should_remove_subcategory(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[
                            Subcategory(name="Rent"),
                            Subcategory(name="Utilities"),
                        ],
                    ),
                ]
            ),
        )

        rc = run(
            remove="Housing:Utilities",
            force=True,
            workspace=ws,
            write=True,
        )
        assert rc == 0

        config = load_categories_config(ws.categories_config)
        assert len(config.categories[0].subcategories) == 1
        assert config.categories[0].subcategories[0].name == "Rent"

    def it_should_require_force_when_category_is_used(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    account_id="TEST",
                    category="Housing",
                )
            ],
            config=CategoryConfig(categories=[Category(name="Housing")]),
        )

        # Without force should fail in dry-run
        with pytest.raises(CommandAbort) as exc_info:
            run(
                remove="Housing",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1

        # With force should succeed
        rc = run(
            remove="Housing",
            force=True,
            workspace=ws,
            write=True,
        )
        assert rc == 0


class DescribeCategorySetBudget:
    """Tests for category --set-budget command."""

    def it_should_set_budget_for_category(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Dining Out")]),
        )

        # Dry-run should not modify
        rc = run(
            set_budget="Dining Out",
            amount=400.0,
            period="monthly",
            workspace=ws,
            write=False,
        )
        assert rc == 0
        config = load_categories_config(ws.categories_config)
        assert config.categories[0].budget is None

        # Write should set budget
        rc = run(
            set_budget="Dining Out",
            amount=400.0,
            period="monthly",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        config = load_categories_config(ws.categories_config)
        assert config.categories[0].budget is not None
        assert config.categories[0].budget.amount == 400.0
        assert config.categories[0].budget.period == BudgetPeriod.monthly

    def it_should_update_existing_budget(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Dining Out",
                        budget=Budget(amount=300.0, period=BudgetPeriod.monthly),
                    )
                ]
            ),
        )

        rc = run(
            set_budget="Dining Out",
            amount=500.0,
            period="yearly",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        config = load_categories_config(ws.categories_config)
        assert config.categories[0].budget.amount == 500.0
        assert config.categories[0].budget.period == BudgetPeriod.yearly

    def it_should_error_when_setting_budget_for_nonexistent_category(self, tmp_path):
        ws = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        with pytest.raises(CommandAbort) as exc_info:
            run(
                set_budget="NonExistent",
                amount=100.0,
                workspace=ws,
                write=True,
            )
        assert exc_info.value.code == 1

    def it_should_error_when_setting_budget_for_subcategory(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[Subcategory(name="Utilities")],
                    )
                ]
            ),
        )

        with pytest.raises(CommandAbort) as exc_info:
            run(
                set_budget="Housing:Utilities",
                amount=100.0,
                workspace=ws,
                write=True,
            )
        assert exc_info.value.code == 1

    def it_should_require_amount_parameter(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Housing")]),
        )

        with pytest.raises(CommandAbort) as exc_info:
            run(
                set_budget="Housing",
                amount=None,
                workspace=ws,
                write=True,
            )
        assert exc_info.value.code == 1

    def it_should_reject_negative_amount(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Housing")]),
        )

        with pytest.raises(CommandAbort) as exc_info:
            run(
                set_budget="Housing",
                amount=-100.0,
                workspace=ws,
                write=True,
            )
        assert exc_info.value.code == 1


class DescribeCategoryValidation:
    """Tests for category command validation."""

    def it_should_require_exactly_one_action(self, tmp_path):
        ws = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        # No action
        with pytest.raises(CommandAbort) as exc_info_no_action:
            run(
                workspace=ws,
                write=False,
            )
        assert exc_info_no_action.value.code == 1

        # Multiple actions
        with pytest.raises(CommandAbort) as exc_info_multi:
            run(
                add="Housing",
                remove="Transportation",
                workspace=ws,
                write=False,
            )
        assert exc_info_multi.value.code == 1
