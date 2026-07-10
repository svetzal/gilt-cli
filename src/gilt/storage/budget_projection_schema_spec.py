"""Specs for gilt.storage.budget_projection_schema — DDL."""

from __future__ import annotations

import sqlite3

from gilt.storage.budget_projection_schema import ensure_budget_projection_schema


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {row[0] for row in rows}


class DescribeEnsureBudgetProjectionSchema:
    def it_should_create_the_budget_projections_table(self):
        conn = sqlite3.connect(":memory:")
        ensure_budget_projection_schema(conn)
        assert "budget_projections" in _table_names(conn)

    def it_should_create_the_budget_history_table(self):
        conn = sqlite3.connect(":memory:")
        ensure_budget_projection_schema(conn)
        assert "budget_history" in _table_names(conn)

    def it_should_create_required_indexes(self):
        conn = sqlite3.connect(":memory:")
        ensure_budget_projection_schema(conn)
        names = _index_names(conn)
        assert "idx_budget_proj_category" in names
        assert "idx_budget_proj_start_date" in names
        assert "idx_budget_proj_active" in names
        assert "idx_budget_hist_budget" in names
        assert "idx_budget_hist_dates" in names

    def it_should_be_idempotent_when_called_twice(self):
        conn = sqlite3.connect(":memory:")
        ensure_budget_projection_schema(conn)
        ensure_budget_projection_schema(conn)  # should not raise
        assert "budget_projections" in _table_names(conn)
        assert "budget_history" in _table_names(conn)
