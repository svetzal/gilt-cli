from __future__ import annotations

"""
Intelligence Cache - Persists duplicate scan and category prediction results.

Stores metadata (risk flags, confidence scores, predicted categories, duplicate
matches) keyed by transaction ID so that the slow intelligence scan only needs
to process new or changed transactions.
"""

import json
from pathlib import Path

from gilt.model.duplicate import DuplicateMatch


def _serialize_entry(entry: dict) -> dict:
    """Convert a metadata entry to a JSON-safe dict."""
    out = {}
    if "risk" in entry:
        out["risk"] = entry["risk"]
    if "confidence" in entry:
        out["confidence"] = entry["confidence"]
    if "predicted_category" in entry:
        out["predicted_category"] = entry["predicted_category"]
    if "duplicate_match" in entry:
        out["duplicate_match"] = entry["duplicate_match"].model_dump(mode="json")
    return out


def _deserialize_entry(raw: dict) -> dict:
    """Convert a JSON dict back to a metadata entry."""
    out = {}
    if "risk" in raw:
        out["risk"] = raw["risk"]
    if "confidence" in raw:
        out["confidence"] = raw["confidence"]
    if "predicted_category" in raw:
        out["predicted_category"] = raw["predicted_category"]
    if "duplicate_match" in raw:
        out["duplicate_match"] = DuplicateMatch.model_validate(raw["duplicate_match"])
    return out


class IntelligenceCache:
    """Persistent cache for intelligence scan results."""

    def __init__(self, cache_path: Path):
        self._path = cache_path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Load cache from disk."""
        if not self._path.exists():
            self._data = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = {tid: _deserialize_entry(entry) for tid, entry in raw.items()}
        except (json.JSONDecodeError, KeyError, ValueError):
            self._data = {}

    def save(self):
        """Persist cache to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        raw = {tid: _serialize_entry(entry) for tid, entry in self._data.items()}
        self._path.write_text(json.dumps(raw), encoding="utf-8")

    def get(self, transaction_id: str) -> dict | None:
        """Get cached metadata for a transaction, or None if not cached."""
        return self._data.get(transaction_id)

    def get_all(self) -> dict[str, dict]:
        """Get all cached metadata."""
        return dict(self._data)

    def update(self, metadata: dict[str, dict]):
        """Merge new metadata into the cache and persist."""
        self._data.update(metadata)
        self.save()

    def uncached_transaction_ids(self, transaction_ids: list[str]) -> set[str]:
        """Return the subset of IDs that have no cached metadata."""
        return set(transaction_ids) - set(self._data.keys())

    def clear(self):
        """Clear all cached data and remove the file."""
        self._data = {}
        if self._path.exists():
            self._path.unlink()
