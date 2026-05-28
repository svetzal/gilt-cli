"""
Tests for DuplicateDiagnosticsService.
"""

from __future__ import annotations

from gilt.services.duplicate_diagnostics_service import DuplicateDiagnosticsService


def _make_row(
    txn_id: str,
    is_duplicate: int = 0,
    primary_transaction_id: str | None = None,
    *,
    date: str = "2025-01-01",
    account_id: str = "MYBANK_CHQ",
    description: str = "EXAMPLE UTILITY",
    amount: float = -50.00,
) -> dict:
    return {
        "transaction_id": txn_id,
        "transaction_date": date,
        "account_id": account_id,
        "canonical_description": description,
        "amount": amount,
        "is_duplicate": is_duplicate,
        "primary_transaction_id": primary_transaction_id,
    }


class DescribeDuplicateDiagnosticsService:
    def it_should_return_no_issues_when_all_groups_are_well_formed(self):
        rows = [
            _make_row("aaaa0001", is_duplicate=0),
            _make_row("bbbb0002", is_duplicate=1, primary_transaction_id="aaaa0001"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert issues == []

    def it_should_detect_orphan_group_when_no_row_has_is_duplicate_zero(self):
        # Both rows claim to be duplicates — neither is the primary
        rows = [
            _make_row("aaaa0001", is_duplicate=1, primary_transaction_id="bbbb0002"),
            _make_row("bbbb0002", is_duplicate=1, primary_transaction_id="aaaa0001"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert len(issues) == 2
        issue_classes = {i.issue_class for i in issues}
        # self_referential or orphan_group — both rows are in the cycle
        # aaaa0001 -> bbbb0002 -> aaaa0001: not self-referential, so orphan_group
        assert issue_classes == {"orphan_group"}

    def it_should_detect_stale_primary_when_pointer_is_itself_a_duplicate(self):
        # T1 is primary, T2 is dup of T1, T3 is dup of T2 (stale — should point at T1)
        rows = [
            _make_row("t1000001", is_duplicate=0),
            _make_row("t2000002", is_duplicate=1, primary_transaction_id="t1000001"),
            _make_row("t3000003", is_duplicate=1, primary_transaction_id="t2000002"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        # t3 has stale primary (t2 is itself a dup)
        assert len(issues) == 1
        assert issues[0].transaction_id == "t3000003"
        assert issues[0].issue_class == "stale_primary"
        assert issues[0].primary_pointed_at == "t2000002"

    def it_should_detect_stale_primary_when_pointer_does_not_exist(self):
        rows = [
            _make_row("aaaa0001", is_duplicate=1, primary_transaction_id="nonexistent"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert len(issues) == 1
        assert issues[0].transaction_id == "aaaa0001"
        assert issues[0].issue_class == "stale_primary"
        assert issues[0].primary_pointed_at == "nonexistent"

    def it_should_detect_self_referential_primary(self):
        rows = [
            _make_row("aaaa0001", is_duplicate=1, primary_transaction_id="aaaa0001"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert len(issues) == 1
        assert issues[0].transaction_id == "aaaa0001"
        assert issues[0].issue_class == "self_referential"

    def it_should_prioritize_self_referential_over_orphan_classification(self):
        # A row that is self-referential is also in an "orphan" group,
        # but self_referential must win.
        rows = [
            _make_row("aaaa0001", is_duplicate=1, primary_transaction_id="aaaa0001"),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert len(issues) == 1
        assert issues[0].issue_class == "self_referential"

    def it_should_not_report_issues_for_non_duplicate_rows(self):
        rows = [
            _make_row("aaaa0001", is_duplicate=0),
            _make_row("bbbb0002", is_duplicate=0),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert issues == []

    def it_should_return_correct_metadata_on_issue(self):
        rows = [
            _make_row(
                "aaaa0001",
                is_duplicate=1,
                primary_transaction_id="nonexistent",
                date="2025-06-01",
                account_id="MYBANK_CC",
                description="SAMPLE STORE",
                amount=-99.99,
            ),
        ]
        service = DuplicateDiagnosticsService()
        issues = service.find_issues(rows)
        assert len(issues) == 1
        issue = issues[0]
        assert issue.transaction_date == "2025-06-01"
        assert issue.account_id == "MYBANK_CC"
        assert issue.canonical_description == "SAMPLE STORE"
        assert issue.amount == -99.99
