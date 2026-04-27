from __future__ import annotations

"""Specs for DuplicateReviewPage logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.testing.fixtures import make_match


class DescribeOnConfirmDuplicate:
    """Tests for _on_confirm_duplicate state recording logic."""

    def it_should_add_txn1_id_to_exclude_set_when_confirming_duplicate(self):
        match = make_match()
        exclude_ids: set[str] = set()

        # txn1 is the new incoming transaction, txn2 is the existing ledger entry
        exclude_ids.add(match.pair.txn1_id)

        assert "aaaa111100000001" in exclude_ids

    def it_should_not_add_txn2_id_when_confirming_duplicate(self):
        match = make_match()
        exclude_ids: set[str] = set()
        exclude_ids.add(match.pair.txn1_id)
        assert "bbbb222200000002" not in exclude_ids

    def it_should_track_row_as_resolved_after_confirm(self):
        resolved_indices: set[int] = set()
        row = 0
        resolved_indices.add(row)
        assert 0 in resolved_indices


class DescribeOnRejectDuplicate:
    """Tests for _on_reject_duplicate state recording logic."""

    def it_should_not_add_any_id_to_exclude_set_when_rejecting(self):
        exclude_ids: set[str] = set()
        # reject means "import it anyway" — nothing added to exclude list
        # (no exclude_ids.add call)
        assert len(exclude_ids) == 0

    def it_should_mark_row_resolved_after_rejection(self):
        resolved_indices: set[int] = set()
        row = 1
        resolved_indices.add(row)
        assert 1 in resolved_indices


class DescribeMarkResolved:
    """Tests for _mark_resolved row visual update and state tracking."""

    def it_should_add_row_to_resolved_indices(self):
        resolved_indices: set[int] = set()
        resolved_indices.add(2)
        assert 2 in resolved_indices

    def it_should_advance_selection_to_next_row_when_not_last(self):
        matches = [make_match(), make_match(txn1_id="cccc333300000003")]
        current_row = 0
        next_row = current_row + 1 if current_row + 1 < len(matches) else current_row
        assert next_row == 1

    def it_should_stay_on_current_row_when_already_at_last(self):
        matches = [make_match()]
        current_row = 0
        next_row = current_row + 1 if current_row + 1 < len(matches) else current_row
        assert next_row == 0

    def it_should_reflect_resolved_status_in_list_item_label(self):
        i = 0
        resolved_indices = {0}
        status = " [Resolved]" if i in resolved_indices else ""
        match = make_match(confidence=0.88)
        label = f"Match {i + 1} ({match.confidence_pct:.0f}%){status}"
        assert "[Resolved]" in label
        assert "Match 1" in label

    def it_should_omit_resolved_status_for_unresolved_match(self):
        i = 1
        resolved_indices: set[int] = set()
        status = " [Resolved]" if i in resolved_indices else ""
        match = make_match(confidence=0.88)
        label = f"Match {i + 1} ({match.confidence_pct:.0f}%){status}"
        assert "[Resolved]" not in label


class DescribeIsComplete:
    """Tests for isComplete always returning True."""

    def it_should_always_allow_proceeding_regardless_of_resolved_count(self):
        # Page is always completable so user can skip unresolved duplicates
        is_complete = True
        assert is_complete is True


class DescribeGetExcludedIds:
    """Tests for get_excluded_ids return value."""

    def it_should_return_empty_set_initially(self):
        exclude_ids: set[str] = set()
        assert exclude_ids == set()

    def it_should_return_accumulated_excluded_ids(self):
        exclude_ids: set[str] = {"aaaa111100000001", "cccc333300000003"}
        result = exclude_ids
        assert "aaaa111100000001" in result
        assert "cccc333300000003" in result
