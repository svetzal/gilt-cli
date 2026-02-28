"""
Tests for TransactionOperationsService.

These tests verify the functional core logic for transaction operations,
ensuring that all business logic is testable without CLI/GUI dependencies.
"""

from __future__ import annotations

from datetime import date

import pytest

from gilt.model.account import Transaction, TransactionGroup
from gilt.services.transaction_operations_service import (
    NoteMode,
    SearchCriteria,
    TransactionOperationsService,
)


class DescribeTransactionOperationsService:
    """Tests for TransactionOperationsService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return TransactionOperationsService()

    @pytest.fixture
    def sample_groups(self):
        """Create sample transaction groups for testing."""
        return [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="abc123def456",
                    date=date(2025, 11, 1),
                    description="SPOTIFY PREMIUM",
                    amount=-10.99,
                    account_id="MYBANK_CHQ",
                ),
            ),
            TransactionGroup(
                group_id="g2",
                primary=Transaction(
                    transaction_id="abc999xyz888",
                    date=date(2025, 11, 2),
                    description="SPOTIFY PREMIUM SUBSCRIPTION",
                    amount=-10.99,
                    account_id="MYBANK_CHQ",
                ),
            ),
            TransactionGroup(
                group_id="g3",
                primary=Transaction(
                    transaction_id="def456ghi789",
                    date=date(2025, 11, 3),
                    description="NETFLIX SUBSCRIPTION",
                    amount=-15.99,
                    account_id="MYBANK_CHQ",
                ),
            ),
            TransactionGroup(
                group_id="g4",
                primary=Transaction(
                    transaction_id="xyz789uvw012",
                    date=date(2025, 11, 15),
                    description="EXAMPLE UTILITY PAYMENT",
                    amount=-125.00,
                    account_id="MYBANK_CHQ",
                ),
            ),
            TransactionGroup(
                group_id="g5",
                primary=Transaction(
                    transaction_id="mno345pqr678",
                    date=date(2025, 11, 20),
                    description="SALARY DEPOSIT",
                    amount=2500.00,
                    account_id="MYBANK_CHQ",
                ),
            ),
        ]


class DescribeFindByIdPrefix(DescribeTransactionOperationsService):
    """Tests for find_by_id_prefix method."""

    def it_should_find_exact_match_by_prefix(self, service, sample_groups):
        """Should find transaction with unique prefix."""
        result = service.find_by_id_prefix("abc123de", sample_groups)

        assert result.is_match
        assert result.transaction is not None
        assert result.transaction.primary.transaction_id == "abc123def456"
        assert result.matches is None or result.matches == []

    def it_should_be_case_insensitive(self, service, sample_groups):
        """Should match prefix case-insensitively."""
        result = service.find_by_id_prefix("ABC123DE", sample_groups)

        assert result.is_match
        assert result.transaction is not None
        assert result.transaction.primary.transaction_id == "abc123def456"

    def it_should_detect_ambiguous_prefix(self, service, sample_groups):
        """Should detect when prefix matches multiple transactions."""
        result = service.find_by_id_prefix("abc", sample_groups, min_length=3)

        assert result.is_ambiguous
        assert result.transaction is None
        assert result.matches is not None
        assert len(result.matches) == 2
        # Check both "abc123..." and "abc999..." are in matches
        ids = {m.primary.transaction_id for m in result.matches}
        assert "abc123def456" in ids
        assert "abc999xyz888" in ids

    def it_should_return_not_found_for_no_matches(self, service, sample_groups):
        """Should return not_found when no transactions match."""
        result = service.find_by_id_prefix("zzz99999", sample_groups)

        assert result.is_not_found
        assert result.transaction is None
        assert result.matches is not None
        assert len(result.matches) == 0

    def it_should_require_minimum_prefix_length(self, service, sample_groups):
        """Should require at least 8 characters by default."""
        result = service.find_by_id_prefix("abc", sample_groups, min_length=8)

        assert result.is_not_found

    def it_should_allow_custom_minimum_length(self, service, sample_groups):
        """Should allow custom minimum prefix length."""
        result = service.find_by_id_prefix("abc", sample_groups, min_length=3)

        assert result.is_ambiguous
        assert len(result.matches) == 2

    def it_should_handle_empty_prefix(self, service, sample_groups):
        """Should handle empty prefix gracefully."""
        result = service.find_by_id_prefix("", sample_groups)

        assert result.is_not_found

    def it_should_handle_whitespace_prefix(self, service, sample_groups):
        """Should strip whitespace from prefix."""
        result = service.find_by_id_prefix("  abc123de  ", sample_groups)

        assert result.is_match
        assert result.transaction is not None
        assert result.transaction.primary.transaction_id == "abc123def456"


class DescribeFindByCriteria(DescribeTransactionOperationsService):
    """Tests for find_by_criteria method."""

    def it_should_find_by_exact_description(self, service, sample_groups):
        """Should find transactions with exact description match."""
        criteria = SearchCriteria(description="SPOTIFY PREMIUM")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 1
        assert len(preview.matched_groups) == 1
        assert preview.matched_groups[0].primary.description == "SPOTIFY PREMIUM"
        assert preview.used_sign_insensitive is False

    def it_should_find_by_description_prefix(self, service, sample_groups):
        """Should find transactions with description prefix match."""
        criteria = SearchCriteria(desc_prefix="SPOTIFY")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 2
        assert len(preview.matched_groups) == 2
        # Both spotify transactions
        descs = {g.primary.description for g in preview.matched_groups}
        assert "SPOTIFY PREMIUM" in descs
        assert "SPOTIFY PREMIUM SUBSCRIPTION" in descs

    def it_should_be_case_insensitive_for_prefix(self, service, sample_groups):
        """Should match description prefix case-insensitively."""
        criteria = SearchCriteria(desc_prefix="spotify")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 2

    def it_should_find_by_regex_pattern(self, service, sample_groups):
        """Should find transactions matching regex pattern."""
        criteria = SearchCriteria(pattern=r"PREMIUM|PAYMENT")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 3
        # SPOTIFY PREMIUM, SPOTIFY PREMIUM SUBSCRIPTION, EXAMPLE UTILITY PAYMENT
        descs = {g.primary.description for g in preview.matched_groups}
        assert "SPOTIFY PREMIUM" in descs
        assert "SPOTIFY PREMIUM SUBSCRIPTION" in descs
        assert "EXAMPLE UTILITY PAYMENT" in descs

    def it_should_handle_invalid_regex_pattern(self, service, sample_groups):
        """Should handle invalid regex pattern gracefully."""
        criteria = SearchCriteria(pattern="[invalid(")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 0
        assert len(preview.matched_groups) == 0

    def it_should_filter_by_exact_amount_signed(self, service, sample_groups):
        """Should filter by exact amount (signed)."""
        criteria = SearchCriteria(desc_prefix="SPOTIFY", amount=-10.99)

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 2
        assert preview.used_sign_insensitive is False

    def it_should_fallback_to_absolute_amount(self, service, sample_groups):
        """Should fallback to absolute amount if no signed matches."""
        criteria = SearchCriteria(desc_prefix="SPOTIFY", amount=10.99)

        preview = service.find_by_criteria(criteria, sample_groups)

        # Should match by absolute value since ledger has -10.99
        assert preview.total_count == 2
        assert preview.used_sign_insensitive is True

    def it_should_not_use_sign_insensitive_if_signed_matches_exist(self, service, sample_groups):
        """Should prefer signed matches over absolute value."""
        criteria = SearchCriteria(desc_prefix="SPOTIFY", amount=-10.99)

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.used_sign_insensitive is False

    def it_should_handle_no_matches(self, service, sample_groups):
        """Should handle no matches gracefully."""
        criteria = SearchCriteria(description="NONEXISTENT")

        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.total_count == 0
        assert len(preview.matched_groups) == 0

    def it_should_match_without_amount_filter(self, service, sample_groups):
        """Should match all transactions matching description criteria."""
        criteria = SearchCriteria(desc_prefix="S")  # No amount filter

        preview = service.find_by_criteria(criteria, sample_groups)

        # SPOTIFY PREMIUM, SPOTIFY PREMIUM SUBSCRIPTION, SALARY DEPOSIT
        assert preview.total_count == 3


class DescribeAddNote(DescribeTransactionOperationsService):
    """Tests for add_note method."""

    @pytest.fixture
    def group_with_note(self):
        """Create group with existing note."""
        return TransactionGroup(
            group_id="g1",
            primary=Transaction(
                transaction_id="abc123def456",
                date=date(2025, 11, 1),
                description="TEST",
                amount=-10.0,
                account_id="TEST_ACC",
                notes="Existing note",
            ),
        )

    @pytest.fixture
    def group_without_note(self):
        """Create group without note."""
        return TransactionGroup(
            group_id="g2",
            primary=Transaction(
                transaction_id="xyz789uvw012",
                date=date(2025, 11, 2),
                description="TEST2",
                amount=-20.0,
                account_id="TEST_ACC",
            ),
        )

    def it_should_replace_note(self, service, group_with_note):
        """Should replace existing note."""
        updated = service.add_note(group_with_note, "New note", mode=NoteMode.REPLACE)

        assert updated.primary.notes == "New note"
        # Original group should be unchanged (immutability)
        assert group_with_note.primary.notes == "Existing note"

    def it_should_replace_when_no_existing_note(self, service, group_without_note):
        """Should set note when none exists (replace mode)."""
        updated = service.add_note(group_without_note, "New note", mode=NoteMode.REPLACE)

        assert updated.primary.notes == "New note"

    def it_should_append_note(self, service, group_with_note):
        """Should append to existing note."""
        updated = service.add_note(group_with_note, "Additional", mode=NoteMode.APPEND)

        assert updated.primary.notes == "Existing note Additional"

    def it_should_append_when_no_existing_note(self, service, group_without_note):
        """Should set note when none exists (append mode)."""
        updated = service.add_note(group_without_note, "New note", mode=NoteMode.APPEND)

        assert updated.primary.notes == "New note"

    def it_should_prepend_note(self, service, group_with_note):
        """Should prepend to existing note."""
        updated = service.add_note(group_with_note, "Prefix", mode=NoteMode.PREPEND)

        assert updated.primary.notes == "Prefix Existing note"

    def it_should_prepend_when_no_existing_note(self, service, group_without_note):
        """Should set note when none exists (prepend mode)."""
        updated = service.add_note(group_without_note, "New note", mode=NoteMode.PREPEND)

        assert updated.primary.notes == "New note"

    def it_should_preserve_other_transaction_fields(self, service, group_with_note):
        """Should not modify other transaction fields."""
        updated = service.add_note(group_with_note, "New", mode=NoteMode.REPLACE)

        # Check all other fields preserved
        assert updated.primary.transaction_id == group_with_note.primary.transaction_id
        assert updated.primary.date == group_with_note.primary.date
        assert updated.primary.description == group_with_note.primary.description
        assert updated.primary.amount == group_with_note.primary.amount
        assert updated.primary.account_id == group_with_note.primary.account_id

    def it_should_preserve_group_id_and_splits(self, service, group_with_note):
        """Should preserve group ID and splits."""
        updated = service.add_note(group_with_note, "New", mode=NoteMode.REPLACE)

        assert updated.group_id == group_with_note.group_id
        assert updated.splits == group_with_note.splits

    def it_should_default_to_replace_mode(self, service, group_with_note):
        """Should use replace mode by default."""
        updated = service.add_note(group_with_note, "New note")

        assert updated.primary.notes == "New note"


class DescribePreviewBatchUpdate(DescribeTransactionOperationsService):
    """Tests for preview_batch_update method."""

    @pytest.fixture
    def groups_for_batch(self):
        """Create groups for batch testing."""
        return [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="t1",
                    date=date(2025, 11, 1),
                    description="DESC1",
                    amount=-10.0,
                    account_id="ACC",
                    notes="Old note 1",
                ),
            ),
            TransactionGroup(
                group_id="g2",
                primary=Transaction(
                    transaction_id="t2",
                    date=date(2025, 11, 2),
                    description="DESC2",
                    amount=-20.0,
                    account_id="ACC",
                    notes="Old note 2",
                ),
            ),
            TransactionGroup(
                group_id="g3",
                primary=Transaction(
                    transaction_id="t3",
                    date=date(2025, 11, 3),
                    description="DESC3",
                    amount=-30.0,
                    account_id="ACC",
                ),
            ),
        ]

    def it_should_preview_batch_updates(self, service, groups_for_batch):
        """Should preview updates for all groups."""
        previews = service.preview_batch_update(groups_for_batch, "New note", mode=NoteMode.REPLACE)

        assert len(previews) == 3
        for _original, updated in previews:
            assert updated.primary.notes == "New note"

    def it_should_return_original_and_updated_pairs(self, service, groups_for_batch):
        """Should return (original, updated) tuples."""
        previews = service.preview_batch_update(groups_for_batch, "New note", mode=NoteMode.REPLACE)

        for original, updated in previews:
            assert original in groups_for_batch
            assert updated.primary.transaction_id == original.primary.transaction_id
            # Original should be unchanged
            assert original.primary.notes != "New note" or original.primary.notes is None

    def it_should_apply_append_mode_in_batch(self, service, groups_for_batch):
        """Should apply append mode to all groups."""
        previews = service.preview_batch_update(groups_for_batch, "Suffix", mode=NoteMode.APPEND)

        # First two have existing notes
        assert previews[0][1].primary.notes == "Old note 1 Suffix"
        assert previews[1][1].primary.notes == "Old note 2 Suffix"
        # Third has no existing note
        assert previews[2][1].primary.notes == "Suffix"

    def it_should_apply_prepend_mode_in_batch(self, service, groups_for_batch):
        """Should apply prepend mode to all groups."""
        previews = service.preview_batch_update(groups_for_batch, "Prefix", mode=NoteMode.PREPEND)

        assert previews[0][1].primary.notes == "Prefix Old note 1"
        assert previews[1][1].primary.notes == "Prefix Old note 2"
        assert previews[2][1].primary.notes == "Prefix"

    def it_should_handle_empty_batch(self, service):
        """Should handle empty batch gracefully."""
        previews = service.preview_batch_update([], "Note", mode=NoteMode.REPLACE)

        assert len(previews) == 0


class DescribeEdgeCases(DescribeTransactionOperationsService):
    """Tests for edge cases and error conditions."""

    def it_should_handle_empty_groups_list(self, service):
        """Should handle empty groups list gracefully."""
        result = service.find_by_id_prefix("abc12345", [])
        assert result.is_not_found

        criteria = SearchCriteria(description="TEST")
        preview = service.find_by_criteria(criteria, [])
        assert preview.total_count == 0

    def it_should_handle_groups_with_empty_descriptions(self, service):
        """Should handle groups with empty or None descriptions."""
        groups = [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="t1",
                    date=date(2025, 11, 1),
                    description="",
                    amount=-10.0,
                    account_id="ACC",
                ),
            ),
            TransactionGroup(
                group_id="g2",
                primary=Transaction(
                    transaction_id="t2",
                    date=date(2025, 11, 2),
                    description="VALID DESC",
                    amount=-20.0,
                    account_id="ACC",
                ),
            ),
        ]

        criteria = SearchCriteria(desc_prefix="VALID")
        preview = service.find_by_criteria(criteria, groups)

        assert preview.total_count == 1
        assert preview.matched_groups[0].primary.description == "VALID DESC"

    def it_should_handle_amount_comparison_with_floating_point(self, service):
        """Should handle floating point comparison correctly."""
        groups = [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="t1",
                    date=date(2025, 11, 1),
                    description="TEST",
                    amount=-10.999,
                    account_id="ACC",
                ),
            ),
        ]

        # Should match within 0.01 tolerance
        criteria = SearchCriteria(description="TEST", amount=-10.99)
        preview = service.find_by_criteria(criteria, groups)

        assert preview.total_count == 1

    def it_should_strip_whitespace_from_descriptions(self, service):
        """Should strip whitespace when comparing descriptions."""
        groups = [
            TransactionGroup(
                group_id="g1",
                primary=Transaction(
                    transaction_id="t1",
                    date=date(2025, 11, 1),
                    description="  TEST DESC  ",
                    amount=-10.0,
                    account_id="ACC",
                ),
            ),
        ]

        criteria = SearchCriteria(description="TEST DESC")
        preview = service.find_by_criteria(criteria, groups)

        assert preview.total_count == 1

    def it_should_preserve_criteria_in_preview(self, service, sample_groups):
        """Should preserve original criteria in preview result."""
        criteria = SearchCriteria(desc_prefix="SPOTIFY", amount=-10.99)
        preview = service.find_by_criteria(criteria, sample_groups)

        assert preview.criteria == criteria
        assert preview.criteria.desc_prefix == "SPOTIFY"
        assert preview.criteria.amount == -10.99
