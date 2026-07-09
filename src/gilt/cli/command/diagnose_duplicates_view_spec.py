"""Specs for diagnose_duplicates_view.py — Rich rendering for the diagnose-duplicates command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.diagnose_duplicates_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


def _make_issue(
    txn_id="abcd1234efgh5678",
    date="2025-01-15",
    account="MYBANK_CHQ",
    description="EXAMPLE UTILITY PAYMENT",
    amount=-50.0,
    issue_class="orphan_group",
    primary_pointed_at=None,
):
    from gilt.services.duplicate_diagnostics_service import DuplicateIssue

    return DuplicateIssue(
        transaction_id=txn_id,
        transaction_date=date,
        account_id=account,
        canonical_description=description,
        amount=amount,
        issue_class=issue_class,
        primary_pointed_at=primary_pointed_at,
    )


class DescribeDisplayIssues:
    def it_should_render_issue_class_in_table(self):
        from gilt.cli.command.diagnose_duplicates_view import display_issues

        issues = [_make_issue(issue_class="orphan_group")]
        output = _capture(lambda: display_issues(issues))
        assert "orphan_group" in output

    def it_should_show_issue_count_summary(self):
        from gilt.cli.command.diagnose_duplicates_view import display_issues

        issues = [_make_issue(issue_class="orphan_group"), _make_issue(issue_class="stale_primary")]
        output = _capture(lambda: display_issues(issues))
        assert "2" in output

    def it_should_display_account_id(self):
        from gilt.cli.command.diagnose_duplicates_view import display_issues

        issues = [_make_issue(account="MYBANK_CHQ")]
        output = _capture(lambda: display_issues(issues))
        assert "MYBANK_CHQ" in output


class DescribePrintNoIssues:
    def it_should_report_no_issues(self):
        from gilt.cli.command.diagnose_duplicates_view import print_no_issues

        output = _capture(print_no_issues)
        assert "No duplicate-projection issues" in output
