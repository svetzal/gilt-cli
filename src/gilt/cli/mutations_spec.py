from __future__ import annotations

from datetime import date
from unittest.mock import Mock

from gilt.cli.mutations import (
    build_categorization_updates,
    find_by_id_prefix,
    find_matches_by_criteria,
    persist_categorization_matches,
    persist_row_categorizations,
    run_categorization_updates,
    run_confirmed_mutation,
    run_persisted_mutation,
    search_by_criteria,
    validate_single_vs_batch_mode,
)
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceResult,
    CategorizationUpdate,
)
from gilt.services.event_sourcing_service import EventSourcingReadyResult
from gilt.services.transaction_operations_service import (
    BatchPreview,
    MatchResult,
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.testing import make_group
from gilt.workspace import Workspace


def _make_group(transaction_id: str, description: str = "Test", amount: float = -10.0):
    return make_group(
        transaction_id=transaction_id,
        date=date(2025, 1, 1),
        description=description,
        amount=amount,
        account_id="TEST_CHQ",
    )


class DescribeValidateSingleVsBatchMode:
    def it_should_return_true_for_single_mode(self, mocker):
        mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode("abcd1234", None, None, None)

        assert result is True

    def it_should_return_false_for_batch_mode_with_description(self, mocker):
        mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode(None, "SAMPLE STORE", None, None)

        assert result is False

    def it_should_return_false_for_batch_mode_with_desc_prefix(self, mocker):
        mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode(None, None, "SAMPLE", None)

        assert result is False

    def it_should_return_false_for_batch_mode_with_pattern(self, mocker):
        mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode(None, None, None, r"\d+")

        assert result is False

    def it_should_return_none_when_no_mode_specified(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode(None, None, None, None)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_return_none_when_multiple_modes_specified(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        result = validate_single_vs_batch_mode("abcd1234", "SAMPLE STORE", None, None)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_print_error_message_on_failure(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")

        validate_single_vs_batch_mode(None, None, None, None)

        args = mock_console.print.call_args[0][0]
        assert "--txid" in args
        assert "--description" in args


class DescribeResolveIdPrefix:
    def it_should_return_error_string_when_prefix_too_short(self):
        service = Mock(spec=TransactionOperationsService)
        groups = [_make_group("abcd1234abcd1234")]

        result = find_by_id_prefix(service, "abc", groups)

        assert isinstance(result, str)
        assert "8 characters" in result
        service.find_by_id_prefix.assert_not_called()

    def it_should_return_error_string_when_not_found(self):
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(type="not_found", matches=[])
        groups = [_make_group("abcd1234abcd1234")]

        result = find_by_id_prefix(service, "zzzzzzzz", groups)

        assert isinstance(result, str)
        assert "No transaction found" in result

    def it_should_return_error_string_when_ambiguous(self):
        g1 = _make_group("abcd1234abcd1234", description="First")
        g2 = _make_group("abcd1234eeff5566", description="Second")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(type="ambiguous", matches=[g1, g2])

        result = find_by_id_prefix(service, "abcd1234", [g1, g2])

        assert isinstance(result, str)
        assert "Ambiguous" in result
        assert "2" in result

    def it_should_return_matched_groups_on_exact_match(self):
        group = _make_group("abcd1234abcd1234")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(
            type="match", transaction=group, matches=[]
        )

        result = find_by_id_prefix(service, "abcd1234", [group])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] is group

    def it_should_normalize_prefix_to_lowercase(self):
        group = _make_group("abcd1234abcd1234")
        service = Mock(spec=TransactionOperationsService)
        service.find_by_id_prefix.return_value = MatchResult(
            type="match", transaction=group, matches=[]
        )

        find_by_id_prefix(service, "ABCD1234", [group])

        call_prefix = service.find_by_id_prefix.call_args[0][0]
        assert call_prefix == "abcd1234"


class DescribeSearchByCriteria:
    def it_should_return_preview_on_valid_search(self, mocker):
        mocker.patch("gilt.cli.console.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE")
        criteria = SearchCriteria(description="SAMPLE STORE")
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview

    def it_should_return_none_on_invalid_pattern(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        criteria = SearchCriteria(pattern=r"[invalid")
        preview = BatchPreview(
            matched_groups=[],
            total_count=0,
            criteria=criteria,
            invalid_pattern=True,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [], r"[invalid")

        assert result is None
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0][0]
        assert "Invalid regex pattern" in args

    def it_should_print_sign_insensitive_note_when_applicable(self, mocker):
        mock_console = mocker.patch("gilt.cli.mutations.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE", amount=-10.0)
        criteria = SearchCriteria(description="SAMPLE STORE", amount=10.0)
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
            used_sign_insensitive=True,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview
        mock_console.print.assert_called_once()
        args = mock_console.print.call_args[0][0]
        assert "absolute amount" in args

    def it_should_not_print_note_when_sign_sensitive_match(self, mocker):
        mock_console = mocker.patch("gilt.cli.mutations.console")
        group = _make_group("abcd1234abcd1234", description="SAMPLE STORE", amount=-10.0)
        criteria = SearchCriteria(description="SAMPLE STORE", amount=-10.0)
        preview = BatchPreview(
            matched_groups=[group],
            total_count=1,
            criteria=criteria,
            used_sign_insensitive=False,
        )
        service = Mock(spec=TransactionOperationsService)
        service.find_by_criteria.return_value = preview

        result = search_by_criteria(service, criteria, [group], None)

        assert result is preview
        mock_console.print.assert_not_called()


class DescribeFindMatchesByCriteria:
    def it_should_accumulate_pairs_across_multiple_accounts(self, mocker):
        mocker.patch("gilt.cli.console.console")
        g1 = _make_group("aaaa0001aaaa0001", description="SAMPLE STORE")
        g2 = _make_group("bbbb0002bbbb0002", description="ACME CORP")
        groups_by_account = {"ACC1": [g1], "ACC2": [g2]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.side_effect = [[g1], [g2]]

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result == [("ACC1", g1), ("ACC2", g2)]

    def it_should_return_none_and_print_error_when_service_returns_nonempty_string(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = "Invalid regex pattern"

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result is None
        mock_console.print.assert_called_once()

    def it_should_return_none_silently_when_service_returns_empty_string(self, mocker):
        mock_console = mocker.patch("gilt.cli.console.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria(description="SAMPLE STORE")
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = ""

        result = find_matches_by_criteria(groups_by_account, criteria, service)

        assert result is None
        mock_console.print.assert_not_called()

    def it_should_forward_txid_to_service(self, mocker):
        mocker.patch("gilt.cli.console.console")
        g1 = _make_group("aaaa0001aaaa0001")
        groups_by_account = {"ACC1": [g1]}
        criteria = SearchCriteria()
        service = Mock(spec=TransactionOperationsService)
        service.find_transaction_targets.return_value = [g1]

        find_matches_by_criteria(groups_by_account, criteria, service, txid="aaaa0001")

        service.find_transaction_targets.assert_called_once_with(
            [g1],
            txid="aaaa0001",
            description=None,
            desc_prefix=None,
            pattern=None,
            amount=None,
        )


class DescribeBuildCategorizationUpdates:
    def it_should_map_each_row_to_a_categorization_update(self):
        rows = [
            ("aaaa0001aaaa0001", "MYBANK_CHQ", "Food", "Groceries", 1.0),
            ("bbbb0002bbbb0002", "MYBANK_CC", "Bills", None, 0.8),
        ]

        result = build_categorization_updates(rows, source="user")

        assert len(result) == 2
        assert result[0].transaction_id == "aaaa0001aaaa0001"
        assert result[0].account_id == "MYBANK_CHQ"
        assert result[0].category == "Food"
        assert result[0].subcategory == "Groceries"
        assert result[0].source == "user"
        assert result[0].confidence == 1.0

    def it_should_propagate_source_to_all_updates(self):
        rows = [
            ("aaaa0001aaaa0001", "MYBANK_CHQ", "Food", None, 0.9),
            ("bbbb0002bbbb0002", "MYBANK_CC", "Bills", None, 0.7),
        ]

        result = build_categorization_updates(rows, source="llm")

        assert all(u.source == "llm" for u in result)

    def it_should_propagate_per_row_confidence(self):
        rows = [
            ("aaaa0001aaaa0001", "MYBANK_CHQ", "Food", None, 0.95),
            ("bbbb0002bbbb0002", "MYBANK_CC", "Bills", None, 0.75),
        ]

        result = build_categorization_updates(rows, source="llm")

        assert result[0].confidence == 0.95
        assert result[1].confidence == 0.75

    def it_should_return_empty_list_for_empty_input(self):
        result = build_categorization_updates([], source="user")

        assert result == []


class DescribeApplyCategorizationUpdates:
    def it_should_call_persist_categorizations_with_updates(self, tmp_path, mocker):
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Workspace(root=tmp_path)
        updates = [
            CategorizationUpdate(
                transaction_id="aaaa0001aaaa0001",
                account_id="MYBANK_CHQ",
                category="Food",
                subcategory=None,
                source="user",
                confidence=1.0,
            )
        ]
        expected_result = CategorizationPersistenceResult(transactions_updated=1, events_emitted=1)
        mock_svc = mocker.patch("gilt.cli.mutations.require_persistence_service")
        mock_svc.return_value.persist_categorizations.return_value = expected_result

        result = run_categorization_updates(ready, workspace, updates)

        mock_svc.return_value.persist_categorizations.assert_called_once_with(updates)
        assert result is expected_result


class DescribePersistCategorizationMatches:
    def it_should_build_and_apply_updates_returning_count(self, mocker):
        g = _make_group("aaaa0001aaaa0001")
        matches = [("MYBANK_CHQ", g)]
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Mock(spec=Workspace)
        mock_build = mocker.patch("gilt.cli.mutations.build_categorization_updates")
        mock_apply = mocker.patch("gilt.cli.mutations.run_categorization_updates")
        mock_apply.return_value = CategorizationPersistenceResult(
            transactions_updated=1, events_emitted=1
        )

        count = persist_categorization_matches(
            matches, "Food", "Groceries", ready, workspace, source="user"
        )

        assert count == 1
        mock_build.assert_called_once()
        mock_apply.assert_called_once()

    def it_should_pass_source_to_build_categorization_updates(self, mocker):
        g = _make_group("aaaa0001aaaa0001")
        matches = [("MYBANK_CHQ", g)]
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Mock(spec=Workspace)
        mock_build = mocker.patch("gilt.cli.mutations.build_categorization_updates")
        mock_apply = mocker.patch("gilt.cli.mutations.run_categorization_updates")
        mock_apply.return_value = CategorizationPersistenceResult(
            transactions_updated=1, events_emitted=1
        )

        persist_categorization_matches(matches, "Food", None, ready, workspace, source="llm")

        _, kwargs = mock_build.call_args
        assert kwargs.get("source") == "llm"


class DescribeRunConfirmedMutation:
    def it_should_call_display_and_apply_when_write_is_true_and_assume_yes(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        display = Mock()
        apply = Mock(return_value=0)

        result = run_confirmed_mutation(
            matches=[],
            display=display,
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=True,
            apply=apply,
        )

        display.assert_called_once()
        apply.assert_called_once()
        assert result == 0

    def it_should_return_apply_result_when_write_and_assume_yes(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)

        result = run_confirmed_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=True,
            apply=Mock(return_value=7),
        )

        assert result == 7

    def it_should_print_dry_run_and_not_apply_when_not_write(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mock_console = mocker.patch("gilt.cli.console.console")
        apply = Mock()

        result = run_confirmed_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=False,
            apply=apply,
        )

        apply.assert_not_called()
        assert result == 0
        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Dry-run" in printed or "dry-run" in printed

    def it_should_return_zero_and_not_apply_when_confirm_declines(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.console.typer.confirm", return_value=False)
        apply = Mock()

        result = run_confirmed_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=False,
            write=True,
            apply=apply,
        )

        apply.assert_not_called()
        assert result == 0

    def it_should_auto_confirm_when_stdin_is_not_a_tty(self, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=False)
        apply = Mock(return_value=0)

        result = run_confirmed_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=False,
            write=True,
            apply=apply,
        )

        apply.assert_called_once()
        assert result == 0


class DescribeRunPersistedMutation:
    def it_should_not_call_persist_when_write_is_false(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.mutations.require_event_sourcing")
        persist = Mock()
        workspace = Workspace(root=tmp_path)

        result = run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=False,
            workspace=workspace,
            persist=persist,
        )

        persist.assert_not_called()
        assert result == 0

    def it_should_print_dry_run_message_when_write_is_false(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mock_console = mocker.patch("gilt.cli.console.console")
        mocker.patch("gilt.cli.mutations.require_event_sourcing")
        workspace = Workspace(root=tmp_path)

        run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=False,
            workspace=workspace,
            persist=Mock(),
        )

        printed = " ".join(str(c) for c in mock_console.print.call_args_list)
        assert "Dry-run" in printed or "dry-run" in printed

    def it_should_not_call_persist_when_confirm_declines(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.console.typer.confirm", return_value=False)
        mock_require = mocker.patch("gilt.cli.mutations.require_event_sourcing")
        persist = Mock()
        workspace = Workspace(root=tmp_path)

        result = run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=False,
            write=True,
            workspace=workspace,
            persist=persist,
        )

        persist.assert_not_called()
        mock_require.assert_not_called()
        assert result == 0

    def it_should_call_persist_with_ready_when_write_is_true(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mock_ready = Mock()
        mocker.patch("gilt.cli.mutations.require_event_sourcing", return_value=mock_ready)
        persist = Mock()
        workspace = Workspace(root=tmp_path)

        result = run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=True,
            workspace=workspace,
            persist=persist,
        )

        persist.assert_called_once_with(mock_ready)
        assert result == 0

    def it_should_call_on_success_after_persist(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.mutations.require_event_sourcing", return_value=Mock())
        persist = Mock()
        on_success = Mock()
        workspace = Workspace(root=tmp_path)

        run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=True,
            workspace=workspace,
            persist=persist,
            on_success=on_success,
        )

        persist.assert_called_once()
        on_success.assert_called_once()

    def it_should_return_one_when_require_event_sourcing_returns_none(self, tmp_path, mocker):
        mocker.patch("gilt.cli.console.sys.stdin.isatty", return_value=True)
        mocker.patch("gilt.cli.mutations.require_event_sourcing", return_value=None)
        workspace = Workspace(root=tmp_path)

        result = run_persisted_mutation(
            matches=[],
            display=Mock(),
            confirm_prompt="Proceed?",
            assume_yes=True,
            write=True,
            workspace=workspace,
            persist=Mock(),
        )

        assert result == 1


class DescribePersistRowCategorizations:
    def it_should_forward_source_and_return_persistence_result(self, mocker):
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Mock(spec=Workspace)
        expected_result = CategorizationPersistenceResult(transactions_updated=2, events_emitted=0)

        mock_persist_service = Mock()
        mock_persist_service.persist_categorizations.return_value = expected_result
        mocker.patch(
            "gilt.cli.mutations.require_persistence_service", return_value=mock_persist_service
        )

        rows = [
            ("txn001", "MYBANK_CHQ", "Food", "Groceries", 1.0),
            ("txn002", "MYBANK_CHQ", "Transport", None, 0.9),
        ]
        result = persist_row_categorizations(rows, ready, workspace, source="user")

        assert result.transactions_updated == 2
        updates = mock_persist_service.persist_categorizations.call_args[0][0]
        assert all(u.source == "user" for u in updates)

    def it_should_forward_llm_source(self, mocker):
        ready = Mock(spec=EventSourcingReadyResult)
        workspace = Mock(spec=Workspace)
        expected_result = CategorizationPersistenceResult(transactions_updated=1, events_emitted=0)

        mock_persist_service = Mock()
        mock_persist_service.persist_categorizations.return_value = expected_result
        mocker.patch(
            "gilt.cli.mutations.require_persistence_service", return_value=mock_persist_service
        )

        rows = [("txn003", "MYBANK_CHQ", "Income", None, 0.95)]
        result = persist_row_categorizations(rows, ready, workspace, source="llm")

        assert result.transactions_updated == 1
        updates = mock_persist_service.persist_categorizations.call_args[0][0]
        assert updates[0].source == "llm"
