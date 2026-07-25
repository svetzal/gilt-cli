"""Specs for gilt.storage.budget_projection_queries — read-model queries and BudgetProjection."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from gilt.model.events import BudgetCreated, BudgetDeleted, BudgetUpdated
from gilt.storage.budget_projection_queries import (
    BudgetProjection,
    get_active_budgets,
    get_budget,
    get_budget_history,
    get_budgets_at_date,
)
from gilt.storage.budget_projection_reducer import apply_budget_events
from gilt.storage.budget_projection_schema import ensure_budget_projection_schema


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "budget_projections.db"
    conn = sqlite3.connect(db_path)
    ensure_budget_projection_schema(conn)
    conn.close()
    return db_path


def _apply(db_path: Path, events: list) -> None:
    conn = sqlite3.connect(db_path)
    try:
        apply_budget_events(conn, events)
    finally:
        conn.close()


def _created(
    budget_id: str,
    category: str = "Transportation",
    subcategory: str | None = None,
    amount: Decimal = Decimal("200.00"),
    start_date: str = "2025-01-01",
) -> BudgetCreated:
    return BudgetCreated(
        budget_id=budget_id,
        category=category,
        subcategory=subcategory,
        period_type="monthly",
        start_date=start_date,
        amount=amount,
        currency="CAD",
    )


def _deleted(
    budget_id: str,
    category: str,
    subcategory: str | None = None,
    final_amount: Decimal = Decimal("200.00"),
    final_period_type: str = "monthly",
    final_start_date: str = "2025-01-01",
) -> BudgetDeleted:
    return BudgetDeleted(
        budget_id=budget_id,
        category=category,
        subcategory=subcategory,
        final_amount=final_amount,
        final_period_type=final_period_type,
        final_start_date=final_start_date,
    )


class DescribeGetBudget:
    def it_should_return_projection_for_existing_budget(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        _apply(db_path, [_created(budget_id, category="Housing")])

        result = get_budget(db_path, budget_id)

        assert isinstance(result, BudgetProjection)
        assert result.budget_id == budget_id
        assert result.category == "Housing"

    def it_should_return_none_for_missing_budget(self, tmp_path):
        db_path = _setup_db(tmp_path)

        result = get_budget(db_path, str(uuid4()))

        assert result is None


class DescribeGetActiveBudgets:
    def it_should_return_all_active_budgets_when_unfiltered(self, tmp_path):
        db_path = _setup_db(tmp_path)
        id1, id2 = str(uuid4()), str(uuid4())
        _apply(db_path, [_created(id1, category="Housing"), _created(id2, category="Food")])

        result = get_active_budgets(db_path)

        categories = {b.category for b in result}
        assert categories == {"Housing", "Food"}

    def it_should_filter_by_category(self, tmp_path):
        db_path = _setup_db(tmp_path)
        id1, id2 = str(uuid4()), str(uuid4())
        _apply(db_path, [_created(id1, category="Housing"), _created(id2, category="Food")])

        result = get_active_budgets(db_path, category="Housing")

        assert [b.budget_id for b in result] == [id1]

    def it_should_exclude_deleted_budgets(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        created = _created(budget_id, category="Entertainment")
        deleted = _deleted(budget_id, category="Entertainment")
        _apply(db_path, [created, deleted])

        result = get_active_budgets(db_path)

        assert result == []


class DescribeGetBudgetsAtDate:
    def it_should_return_budget_active_within_window(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        _apply(db_path, [_created(budget_id, category="Housing", start_date="2025-01-01")])

        result = get_budgets_at_date(db_path, date(2025, 6, 1))

        assert [b.budget_id for b in result] == [budget_id]

    def it_should_exclude_budget_outside_window(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        _apply(db_path, [_created(budget_id, category="Housing", start_date="2025-06-01")])

        result = get_budgets_at_date(db_path, date(2025, 1, 1))

        assert result == []

    def it_should_exclude_deleted_budget_events(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        created = _created(budget_id, category="Entertainment", start_date="2025-01-01")
        deleted = _deleted(budget_id, category="Entertainment", final_start_date="2025-01-01")
        _apply(db_path, [created, deleted])

        result = get_budgets_at_date(db_path, date.today() + timedelta(days=1))

        assert result == []


class DescribeGetBudgetHistory:
    def it_should_order_history_by_event_timestamp(self, tmp_path):
        db_path = _setup_db(tmp_path)
        budget_id = str(uuid4())
        created = _created(budget_id, category="Housing", amount=Decimal("1500.00"))
        updated = BudgetUpdated(
            budget_id=budget_id,
            category="Housing",
            subcategory=None,
            new_amount=Decimal("1600.00"),
            previous_amount=Decimal("1500.00"),
            currency="CAD",
        )
        _apply(db_path, [created, updated])

        result = get_budget_history(db_path, budget_id)

        assert [row["event_type"] for row in result] == ["BudgetCreated", "BudgetUpdated"]


class DescribeBudgetProjection:
    def it_should_convert_to_dict(self):
        from datetime import datetime

        projection = BudgetProjection(
            budget_id="test-123",
            category="Transportation",
            subcategory="Public Transit",
            amount=Decimal("200.00"),
            period_type="monthly",
            start_date="2025-01-01",
            currency="CAD",
            is_deleted=False,
            created_at=datetime(2025, 1, 1, 10, 0, 0),
            updated_at=datetime(2025, 1, 1, 10, 0, 0),
            last_event_id="event-456",
        )

        result = projection.to_dict()

        assert result["budget_id"] == "test-123"
        assert result["category"] == "Transportation"
        assert result["subcategory"] == "Public Transit"
        assert result["amount"] == "200.00"
        assert result["period_type"] == "monthly"
        assert result["start_date"] == "2025-01-01"
        assert result["currency"] == "CAD"
        assert result["is_deleted"] is False
        assert result["last_event_id"] == "event-456"
