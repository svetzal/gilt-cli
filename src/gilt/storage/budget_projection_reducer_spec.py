"""Specs for gilt.storage.budget_projection_reducer — write-side event application."""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from uuid import uuid4

import pytest

from gilt.model.events import BudgetCreated, BudgetDeleted, BudgetUpdated
from gilt.storage.budget_projection_reducer import apply_budget_events
from gilt.storage.budget_projection_schema import ensure_budget_projection_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    ensure_budget_projection_schema(c)
    yield c
    c.close()


def _make_created(budget_id: str, **kwargs) -> BudgetCreated:
    defaults = dict(
        budget_id=budget_id,
        category="Transportation",
        subcategory=None,
        period_type="monthly",
        start_date="2025-01-01",
        amount=Decimal("100.00"),
        currency="CAD",
    )
    defaults.update(kwargs)
    return BudgetCreated(**defaults)


class DescribeApplyBudgetEvents:
    def it_should_insert_a_projection_on_budget_created(self, conn):
        budget_id = str(uuid4())
        apply_budget_events(conn, [_make_created(budget_id)])
        row = conn.execute(
            "SELECT category, amount FROM budget_projections WHERE budget_id = ?", (budget_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == "Transportation"
        assert row[1] == 100.0

    def it_should_ignore_a_duplicate_budget_created(self, conn):
        budget_id = str(uuid4())
        event = _make_created(budget_id)
        apply_budget_events(conn, [event])
        apply_budget_events(conn, [event])
        count = conn.execute(
            "SELECT COUNT(*) FROM budget_projections WHERE budget_id = ?", (budget_id,)
        ).fetchone()[0]
        assert count == 1

    def it_should_close_the_open_history_row_on_budget_updated(self, conn):
        budget_id = str(uuid4())
        created = _make_created(budget_id)
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Transportation",
            subcategory=None,
            new_amount=Decimal("150.00"),
            previous_amount=Decimal("100.00"),
            currency="CAD",
        )
        apply_budget_events(conn, [created, updated])
        rows = conn.execute(
            "SELECT end_date FROM budget_history WHERE budget_id = ? ORDER BY history_id",
            (budget_id,),
        ).fetchall()
        assert rows[0][0] is not None  # first history row closed
        assert rows[1][0] is None  # second history row open

    def it_should_preserve_current_values_when_update_fields_are_none(self, conn):
        budget_id = str(uuid4())
        created = _make_created(budget_id)
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Transportation",
            subcategory=None,
            new_amount=None,
            previous_amount=Decimal("100.00"),
            currency="CAD",
        )
        apply_budget_events(conn, [created, updated])
        amount = conn.execute(
            "SELECT amount FROM budget_projections WHERE budget_id = ?", (budget_id,)
        ).fetchone()[0]
        assert amount == 100.0

    def it_should_skip_an_update_for_an_unknown_budget(self, conn):
        unknown_id = str(uuid4())
        updated = BudgetUpdated(
            budget_id=unknown_id,
            category="Transportation",
            subcategory=None,
            new_amount=Decimal("200.00"),
            previous_amount=Decimal("100.00"),
            currency="CAD",
        )
        apply_budget_events(conn, [updated])  # should not raise
        count = conn.execute(
            "SELECT COUNT(*) FROM budget_projections WHERE budget_id = ?", (unknown_id,)
        ).fetchone()[0]
        assert count == 0

    def it_should_mark_deleted_and_close_history_on_budget_deleted(self, conn):
        budget_id = str(uuid4())
        created = _make_created(budget_id)
        deleted = BudgetDeleted(
            budget_id=budget_id,
            category="Transportation",
            subcategory=None,
            final_amount=Decimal("100.00"),
            final_period_type="monthly",
            final_start_date="2025-01-01",
            currency="CAD",
        )
        apply_budget_events(conn, [created, deleted])
        is_deleted = conn.execute(
            "SELECT is_deleted FROM budget_projections WHERE budget_id = ?", (budget_id,)
        ).fetchone()[0]
        assert is_deleted == 1
        open_rows = conn.execute(
            "SELECT COUNT(*) FROM budget_history WHERE budget_id = ? AND end_date IS NULL",
            (budget_id,),
        ).fetchone()[0]
        assert open_rows == 0
