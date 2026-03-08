from __future__ import annotations

from datetime import date
from pathlib import Path

from gilt.gui.services.intelligence_cache import IntelligenceCache
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair


def _make_match() -> DuplicateMatch:
    pair = TransactionPair(
        txn1_id="aaa11111",
        txn1_date=date(2025, 3, 1),
        txn1_description="SAMPLE STORE",
        txn1_amount=-10.0,
        txn1_account="MYBANK_CHQ",
        txn2_id="bbb22222",
        txn2_date=date(2025, 3, 1),
        txn2_description="SAMPLE STORE ANYTOWN",
        txn2_amount=-10.0,
        txn2_account="MYBANK_CHQ",
    )
    assessment = DuplicateAssessment(
        is_duplicate=True, confidence=0.9, reasoning="Same store same day"
    )
    return DuplicateMatch(pair=pair, assessment=assessment)


class DescribeIntelligenceCache:
    def it_should_store_and_retrieve_prediction_metadata(self, tmp_path: Path):
        cache = IntelligenceCache(tmp_path / "cache.json")
        metadata = {
            "txn1": {"confidence": 0.85, "predicted_category": "Food: Groceries"},
        }
        cache.update(metadata)

        loaded = IntelligenceCache(tmp_path / "cache.json")
        entry = loaded.get("txn1")
        assert entry is not None
        assert entry["confidence"] == 0.85
        assert entry["predicted_category"] == "Food: Groceries"

    def it_should_store_and_retrieve_duplicate_match(self, tmp_path: Path):
        cache = IntelligenceCache(tmp_path / "cache.json")
        match = _make_match()
        metadata = {
            "aaa11111": {"risk": True, "duplicate_match": match},
        }
        cache.update(metadata)

        loaded = IntelligenceCache(tmp_path / "cache.json")
        entry = loaded.get("aaa11111")
        assert entry is not None
        assert entry["risk"] is True
        assert isinstance(entry["duplicate_match"], DuplicateMatch)
        assert entry["duplicate_match"].pair.txn1_id == "aaa11111"

    def it_should_identify_uncached_transactions(self, tmp_path: Path):
        cache = IntelligenceCache(tmp_path / "cache.json")
        cache.update({"txn1": {"confidence": 0.5}})

        uncached = cache.uncached_transaction_ids(["txn1", "txn2", "txn3"])
        assert uncached == {"txn2", "txn3"}

    def it_should_handle_missing_cache_file(self, tmp_path: Path):
        cache = IntelligenceCache(tmp_path / "nonexistent.json")
        assert cache.get("txn1") is None
        assert cache.get_all() == {}

    def it_should_handle_corrupt_cache_file(self, tmp_path: Path):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("not valid json")
        cache = IntelligenceCache(cache_path)
        assert cache.get_all() == {}

    def it_should_clear_cache(self, tmp_path: Path):
        cache_path = tmp_path / "cache.json"
        cache = IntelligenceCache(cache_path)
        cache.update({"txn1": {"confidence": 0.5}})
        assert cache_path.exists()

        cache.clear()
        assert not cache_path.exists()
        assert cache.get_all() == {}
