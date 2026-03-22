from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from gilt.model.duplicate import TransactionPair
from gilt.transfer.prompt_manager import PromptManager


def _make_pair(
    txn1_id: str = "txn001",
    txn2_id: str = "txn002",
    txn1_desc: str = "SAMPLE STORE EXAMPLEVILLE",
    txn2_desc: str = "SAMPLE STORE ANYTOWN",
    amount: float = 50.0,
) -> TransactionPair:
    return TransactionPair(
        txn1_id=txn1_id,
        txn1_date=date(2025, 6, 1),
        txn1_description=txn1_desc,
        txn1_amount=amount,
        txn1_account="MYBANK_CHQ",
        txn2_id=txn2_id,
        txn2_date=date(2025, 6, 1),
        txn2_description=txn2_desc,
        txn2_amount=amount,
        txn2_account="MYBANK_CHQ",
    )


class DescribePromptManagerInitialization:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def it_should_initialize_with_empty_history_when_no_file_exists(self, temp_dir):
        manager = PromptManager(temp_dir)
        assert manager.feedback_history == []

    def it_should_load_existing_feedback_from_json_file(self, temp_dir):
        data = {
            "version": 1,
            "last_updated": "2025-01-01T00:00:00",
            "feedback_history": [
                {
                    "timestamp": "2025-01-01T00:00:00",
                    "txn1_date": "2025-01-01",
                    "txn1_description": "SAMPLE STORE",
                    "txn1_amount": 50.0,
                    "txn2_date": "2025-01-01",
                    "txn2_description": "SAMPLE STORE",
                    "txn2_amount": 50.0,
                    "llm_said_duplicate": True,
                    "llm_confidence": 0.9,
                    "user_confirmed": True,
                    "llm_reasoning": "Same transaction",
                }
            ],
        }
        prompt_file = temp_dir / "duplicate_detection_prompt.json"
        prompt_file.write_text(json.dumps(data))
        manager = PromptManager(temp_dir)
        assert len(manager.feedback_history) == 1
        assert manager.feedback_history[0]["txn1_description"] == "SAMPLE STORE"

    def it_should_persist_feedback_to_json_round_trip(self, temp_dir):
        manager = PromptManager(temp_dir)
        pair = _make_pair()
        manager.add_feedback(pair, llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True)
        manager2 = PromptManager(temp_dir)
        assert len(manager2.feedback_history) == 1
        assert manager2.feedback_history[0]["llm_said_duplicate"] is True

    def it_should_create_directory_if_not_exists_on_save(self):
        with tempfile.TemporaryDirectory() as base:
            nested_dir = Path(base) / "subdir" / "deeper"
            manager = PromptManager(nested_dir)
            pair = _make_pair()
            manager.add_feedback(
                pair, llm_said_duplicate=True, llm_confidence=0.8, user_confirmed=False
            )
            assert (nested_dir / "duplicate_detection_prompt.json").exists()


class DescribePromptManagerFeedback:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        return PromptManager(temp_dir)

    def it_should_append_feedback_entry_with_all_fields(self, manager):
        pair = _make_pair()
        manager.add_feedback(
            pair,
            llm_said_duplicate=True,
            llm_confidence=0.85,
            user_confirmed=True,
            llm_reasoning="Same transaction",
        )
        entry = manager.feedback_history[0]
        assert "timestamp" in entry
        assert entry["txn1_date"] == "2025-06-01"
        assert entry["txn1_description"] == "SAMPLE STORE EXAMPLEVILLE"
        assert entry["txn1_amount"] == 50.0
        assert entry["txn2_date"] == "2025-06-01"
        assert entry["txn2_description"] == "SAMPLE STORE ANYTOWN"
        assert entry["txn2_amount"] == 50.0
        assert entry["llm_said_duplicate"] is True
        assert entry["llm_confidence"] == 0.85
        assert entry["user_confirmed"] is True
        assert entry["llm_reasoning"] == "Same transaction"

    def it_should_save_to_disk_after_each_feedback(self, manager, temp_dir):
        pair = _make_pair()
        manager.add_feedback(pair, llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True)
        prompt_file = temp_dir / "duplicate_detection_prompt.json"
        assert prompt_file.exists()
        data = json.loads(prompt_file.read_text())
        assert len(data["feedback_history"]) == 1


class DescribePromptManagerLearnedPatterns:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        return PromptManager(temp_dir)

    def it_should_return_empty_string_with_no_feedback(self, manager):
        result = manager._generate_learned_patterns()
        assert result == ""

    def it_should_include_false_positive_section_when_fp_exists(self, manager):
        pair = _make_pair(txn1_desc="SAMPLE STORE EXAMPLEVILLE", txn2_desc="SAMPLE STORE ANYTOWN")
        manager.add_feedback(
            pair, llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=False
        )
        result = manager._generate_learned_patterns()
        assert "FALSE POSITIVES" in result

    def it_should_include_confirmed_duplicate_section(self, manager):
        pair = _make_pair(txn1_desc="ACME CORP", txn2_desc="ACME CORP")
        manager.add_feedback(pair, llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True)
        result = manager._generate_learned_patterns()
        assert "TRUE DUPLICATES" in result
        assert "ACME CORP" in result

    def it_should_include_missed_duplicates_section(self, manager):
        pair = _make_pair(txn1_desc="EXAMPLE UTILITY", txn2_desc="EXAMPLE UTIL")
        manager.add_feedback(
            pair, llm_said_duplicate=False, llm_confidence=0.2, user_confirmed=True
        )
        result = manager._generate_learned_patterns()
        assert "previously missed duplicates" in result

    def it_should_detect_location_pattern_from_symmetric_difference(self, manager):
        pair = _make_pair(
            txn1_desc="SAMPLE STORE EXAMPLEVILLE",
            txn2_desc="SAMPLE STORE ANYTOWN",
        )
        manager.add_feedback(
            pair, llm_said_duplicate=True, llm_confidence=0.8, user_confirmed=False
        )
        result = manager._generate_learned_patterns()
        assert "location" in result.lower() or "tokens" in result.lower()


class DescribePromptManagerStats:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        return PromptManager(temp_dir)

    def it_should_return_zero_stats_with_no_feedback(self, manager):
        stats = manager.get_stats()
        assert stats["total_feedback"] == 0
        assert stats["accuracy"] == 0.0
        assert stats["true_positives"] == 0
        assert stats["false_positives"] == 0
        assert stats["true_negatives"] == 0
        assert stats["false_negatives"] == 0

    def it_should_calculate_tp_fp_tn_fn_correctly(self, manager):
        manager.add_feedback(
            _make_pair("a", "b"), llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True
        )
        manager.add_feedback(
            _make_pair("c", "d"), llm_said_duplicate=True, llm_confidence=0.8, user_confirmed=False
        )
        manager.add_feedback(
            _make_pair("e", "f"), llm_said_duplicate=False, llm_confidence=0.1, user_confirmed=False
        )
        manager.add_feedback(
            _make_pair("g", "h"), llm_said_duplicate=False, llm_confidence=0.2, user_confirmed=True
        )
        stats = manager.get_stats()
        assert stats["true_positives"] == 1
        assert stats["false_positives"] == 1
        assert stats["true_negatives"] == 1
        assert stats["false_negatives"] == 1
        assert stats["total_feedback"] == 4

    def it_should_calculate_accuracy_as_correct_over_total(self, manager):
        manager.add_feedback(
            _make_pair("a", "b"), llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True
        )
        manager.add_feedback(
            _make_pair("c", "d"), llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True
        )
        manager.add_feedback(
            _make_pair("e", "f"), llm_said_duplicate=True, llm_confidence=0.8, user_confirmed=False
        )
        manager.add_feedback(
            _make_pair("g", "h"), llm_said_duplicate=False, llm_confidence=0.2, user_confirmed=False
        )
        stats = manager.get_stats()
        assert stats["accuracy"] == pytest.approx(0.75)


class DescribePromptManagerPromptAssembly:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, temp_dir):
        return PromptManager(temp_dir)

    def it_should_return_template_with_substituted_patterns_placeholder(self, manager):
        prompt = manager.get_prompt()
        assert "{learned_patterns}" not in prompt

    def it_should_preserve_single_brace_placeholders_after_format(self, manager):
        # get_prompt() calls .format(learned_patterns=...) on the template,
        # which converts {{txn1_date}} -> {txn1_date} in the output.
        prompt = manager.get_prompt()
        assert "{txn1_date}" in prompt
        assert "{txn2_date}" in prompt
        assert "{txn1_description}" in prompt
        assert "{txn2_description}" in prompt

    def it_should_embed_learned_patterns_into_template(self, manager):
        pair = _make_pair(txn1_desc="ACME CORP", txn2_desc="ACME CORP")
        manager.add_feedback(pair, llm_said_duplicate=True, llm_confidence=0.9, user_confirmed=True)
        prompt = manager.get_prompt()
        assert "ACME CORP" in prompt
