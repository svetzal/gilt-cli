"""
Static guard: spec files must not hand-roll temporary directories or construct
Transaction / TransactionGroup models directly.

Preferred replacements:
  - TemporaryDirectory  → pytest's ``tmp_path`` fixture
  - Transaction(...)    → ``make_transaction(...)`` from ``gilt.testing``
  - TransactionGroup(…) → ``make_group(...)`` from ``gilt.testing``
  - Full workspace setup → ``build_workspace_with_ledger`` from ``gilt.testing``

The allowlists below name files that do not yet satisfy a convention.  They are
scaffolding: entries are removed as each spec file is brought into compliance.
An empty allowlist is the goal.
"""

from __future__ import annotations

from pathlib import Path

SRC_DIR = Path(__file__).parent.parent.parent  # src/

# ---------------------------------------------------------------------------
# Allowlist: specs still using TemporaryDirectory.
# Goal: zero entries.  Remove each file after migrating it to tmp_path.
# ---------------------------------------------------------------------------
TEMPORARY_DIRECTORY_ALLOWLIST: set[str] = set()

# ---------------------------------------------------------------------------
# Allowlist: specs that still construct Transaction( or TransactionGroup(
# directly instead of using make_transaction / make_group.
# Goal: zero entries.  Remove each file after migrating it to the helpers.
# ---------------------------------------------------------------------------
DIRECT_MODEL_CONSTRUCTION_ALLOWLIST: set[str] = {
    # ingest layer
    "gilt/ingest/ledger_pipeline_spec.py",
    "gilt/ingest/transaction_mapping_spec.py",
    # cli shared
    "gilt/cli/console_spec.py",
    "gilt/cli/formatting_spec.py",
    "gilt/cli/mutations_spec.py",
    # cli commands
    "gilt/cli/command/auto_categorize_review_spec.py",
    "gilt/cli/command/auto_categorize_view_spec.py",
    "gilt/cli/command/categorize_view_spec.py",
    "gilt/cli/command/duplicates_spec.py",
    "gilt/cli/command/history_spec.py",
    "gilt/cli/command/ingest_spec.py",
    "gilt/cli/command/migrate_to_events_spec.py",
    "gilt/cli/command/note_spec.py",
    "gilt/cli/command/note_view_spec.py",
    "gilt/cli/command/recategorize_view_spec.py",
    "gilt/cli/command/receipts_spec.py",
    "gilt/cli/command/report_spec.py",
    "gilt/cli/command/show_spec.py",
    "gilt/cli/command/status_spec.py",
    "gilt/cli/command/summary_spec.py",
    "gilt/cli/command/summary_view_spec.py",
    "gilt/cli/command/uncategorized_spec.py",
    "gilt/cli/command/uncategorized_view_spec.py",
    "gilt/cli/command/ytd_spec.py",
    "gilt/cli/command/ytd_view_spec.py",
    # gui
    "gilt/gui/dialogs/transaction_detail_dialog_spec.py",
    "gilt/gui/models/transaction_proxy_model_spec.py",
    "gilt/gui/services/receipt_match_service_spec.py",
    "gilt/gui/widgets/transaction_sections_spec.py",
    "gilt/gui/workers/intelligence_worker_spec.py",
    # services
    "gilt/services/categorization_service_spec.py",
    "gilt/services/category_management_service_spec.py",
    "gilt/services/summary_service_spec.py",
    "gilt/services/transaction_operations_service_spec.py",
}

# Spec files under the testing package itself are permitted to construct models
# directly — they test the factory helpers.
_TESTING_PACKAGE_PREFIX = "gilt/testing/"


def _all_spec_files() -> list[tuple[str, Path]]:
    """Return (repo-relative-path, absolute-path) for every *_spec.py under src/.

    Files whose stems start with ``_`` (e.g. ``_spec_hygiene_spec.py``,
    ``_module_layout_spec.py``) are excluded — they are meta-specs that
    intentionally mention the patterns they guard against.
    """
    results = []
    for path in sorted(SRC_DIR.rglob("*_spec.py")):
        if path.stem.startswith("_"):
            continue
        rel = path.relative_to(SRC_DIR).as_posix()
        results.append((rel, path))
    return results


class DescribeTemporaryDirectoryConvention:
    def it_should_not_use_TemporaryDirectory_in_spec_files(self):
        """Specs must use pytest's tmp_path fixture instead of TemporaryDirectory."""
        failures = []
        for rel, path in _all_spec_files():
            if rel in TEMPORARY_DIRECTORY_ALLOWLIST:
                continue
            source = path.read_text(encoding="utf-8")
            if "TemporaryDirectory" in source:
                failures.append(rel)

        assert not failures, (
            "Spec files must use pytest's tmp_path fixture instead of TemporaryDirectory.\n"
            "Migrate each file and remove it from TEMPORARY_DIRECTORY_ALLOWLIST:\n"
            + "\n".join(f"  {f}" for f in failures)
        )


class DescribeDirectModelConstructionConvention:
    def it_should_not_construct_Transaction_directly_in_spec_files(self):
        """Specs must use make_transaction / make_group from gilt.testing."""
        failures = []
        for rel, path in _all_spec_files():
            if rel in DIRECT_MODEL_CONSTRUCTION_ALLOWLIST:
                continue
            if rel.startswith(_TESTING_PACKAGE_PREFIX):
                continue
            source = path.read_text(encoding="utf-8")
            if "Transaction(" in source or "TransactionGroup(" in source:
                failures.append(rel)

        assert not failures, (
            "Spec files must build Transaction / TransactionGroup via make_transaction / "
            "make_group from gilt.testing, not by hand-rolling constructors.\n"
            "Migrate each file and remove it from DIRECT_MODEL_CONSTRUCTION_ALLOWLIST:\n"
            + "\n".join(f"  {f}" for f in failures)
        )
