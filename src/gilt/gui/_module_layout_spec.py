"""
Static guard: GUI shell modules must respect the functional-core/imperative-shell boundary,
follow the QThread worker lifecycle conventions, and have companion spec files.

GUI shell modules are those in views/, dialogs/, widgets/, delegates/, controllers/,
and workers/. The services/ subdirectory is already governed by the services layer guard.

Rules enforced:
  1. UI modules (views, dialogs, widgets, delegates, workers) must not call ledger/file I/O
     functions directly — all persistence goes through the service layer. Controllers are
     exempt as the documented imperative-shell coordination layer (transaction_mutation_controller
     is the canonical reference implementation for GUI mutations).
  2. QThread-owning modules that call requestInterruption() must declare the worker attribute
     safely: either with a typed `WorkerType | None = None` default, or guarded with `hasattr`.
  3. QWizardPage subclasses that start a worker (assign self.worker) must implement cleanupPage,
     reject, or closeEvent to prevent segfaults on cancel/back navigation.
  4. Every shell module must have a companion *_spec.py.

All allowlists below are empty by design — all shell modules comply at the time this guard
was introduced. Add entries only as temporary scaffolding for active migrations, and remove
them as soon as the module is brought into compliance.
"""

from __future__ import annotations

from pathlib import Path

GUI_DIR = Path(__file__).parent

# All shell subdirectories; services/ is covered by the services layer guard.
_ALL_SHELL_DIRS = ["views", "dialogs", "widgets", "delegates", "controllers", "workers"]

# UI-only subdirectories (controllers exempt — they are the imperative shell for mutations).
_UI_SHELL_DIRS = ["views", "dialogs", "widgets", "delegates", "workers"]

LEDGER_IO_PATTERNS = [
    "load_ledger_csv",
    "dump_ledger_csv",
    "ledger_io",
    "LedgerRepository",
    "open(",
]

# Empty by design — all shell modules comply. Add entries only for active migrations.
LEDGER_IO_ALLOWLIST: set[str] = set()
WORKER_LIFECYCLE_ALLOWLIST: set[str] = set()
CLEANUP_PAGE_ALLOWLIST: set[str] = set()
MISSING_SPEC_ALLOWLIST: set[str] = set()


def _find_modules_in(dirs: list[str]) -> list[tuple[str, Path]]:
    """Return all non-spec, non-private Python modules in the given shell subdirectories."""
    modules = []
    for dir_name in dirs:
        search_dir = GUI_DIR / dir_name
        if not search_dir.is_dir():
            continue
        for path in sorted(search_dir.rglob("*.py")):
            stem = path.stem
            if stem.startswith("_") or stem.endswith("_spec"):
                continue
            modules.append((stem, path))
    return modules


def _find_shell_modules() -> list[tuple[str, Path]]:
    """Return all non-spec, non-private Python modules across all shell directories."""
    return _find_modules_in(_ALL_SHELL_DIRS)


def _find_ui_modules() -> list[tuple[str, Path]]:
    """Return shell modules in UI-only directories (controllers excluded)."""
    return _find_modules_in(_UI_SHELL_DIRS)


def _scan(path: Path, patterns: list[str]) -> list[str]:
    """Return lines containing any of the given patterns."""
    content = path.read_text(encoding="utf-8")
    hits = []
    for line in content.splitlines():
        stripped = line.strip()
        if any(p in stripped for p in patterns):
            hits.append(stripped)
    return hits


class DescribeGuiModuleLayout:
    def it_should_not_do_direct_ledger_io(self):
        """UI shell modules must not call ledger/file I/O functions directly."""
        violations: list[str] = []
        for stem, path in _find_ui_modules():
            if stem in LEDGER_IO_ALLOWLIST:
                continue
            hits = _scan(path, LEDGER_IO_PATTERNS)
            for hit in hits:
                violations.append(f"{path.name}: {hit}")
        assert violations == [], (
            "GUI UI modules must not do direct ledger I/O — route through services:\n"
            + "\n".join(violations)
        )

    def it_should_declare_worker_attrs_with_none_default(self):
        """Modules that manage QThread workers must guard worker attribute access safely."""
        violations: list[str] = []
        for stem, path in _find_shell_modules():
            if stem in WORKER_LIFECYCLE_ALLOWLIST:
                continue
            source = path.read_text(encoding="utf-8")
            if "requestInterruption()" not in source:
                continue
            # Worker is safe if declared with a typed None default or guarded with hasattr.
            has_none_default = "| None = None" in source
            has_hasattr_guard = (
                'hasattr(self, "worker")' in source or "hasattr(self, 'worker')" in source
            )
            if not has_none_default and not has_hasattr_guard:
                violations.append(
                    f"{path.name}: calls requestInterruption() but has no safe worker guard"
                    " (add `self.worker: WorkerType | None = None` or `hasattr` guard)"
                )
        assert violations == [], (
            "QThread-owning modules must declare worker attributes safely:\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    def it_should_clean_up_worker_starting_wizard_pages(self):
        """QWizardPage subclasses that start workers must implement cleanupPage."""
        violations: list[str] = []
        for stem, path in _find_ui_modules():
            if stem in CLEANUP_PAGE_ALLOWLIST:
                continue
            source = path.read_text(encoding="utf-8")
            if "QWizardPage" not in source:
                continue
            if "self.worker =" not in source:
                continue
            has_cleanup = (
                "def cleanupPage" in source
                or "def reject" in source
                or "def closeEvent" in source
            )
            if not has_cleanup:
                violations.append(
                    f"{path.name}: QWizardPage with worker but no cleanupPage/reject/closeEvent"
                )
        assert violations == [], (
            "QWizardPage subclasses that start workers must implement cleanupPage:\n"
            + "\n".join(f"  {v}" for v in violations)
        )


class DescribeSpecCoverage:
    def it_should_have_a_spec_for_every_shell_module(self):
        """Every GUI shell module must have a companion *_spec.py."""
        missing_specs: list[str] = []
        for stem, path in _find_shell_modules():
            if stem in MISSING_SPEC_ALLOWLIST:
                continue
            spec_path = path.parent / f"{stem}_spec.py"
            if not spec_path.exists():
                missing_specs.append(str(path.relative_to(GUI_DIR)))
        assert missing_specs == [], (
            "Missing spec files for GUI shell modules:\n"
            + "\n".join(f"  {s}" for s in missing_specs)
        )

    def it_should_keep_allowlists_empty(self):
        """All allowlists must remain empty — the invariant, not the goal."""
        assert not LEDGER_IO_ALLOWLIST, (
            f"LEDGER_IO_ALLOWLIST should be empty: {LEDGER_IO_ALLOWLIST}"
        )
        assert not WORKER_LIFECYCLE_ALLOWLIST, (
            f"WORKER_LIFECYCLE_ALLOWLIST should be empty: {WORKER_LIFECYCLE_ALLOWLIST}"
        )
        assert not CLEANUP_PAGE_ALLOWLIST, (
            f"CLEANUP_PAGE_ALLOWLIST should be empty: {CLEANUP_PAGE_ALLOWLIST}"
        )
        assert not MISSING_SPEC_ALLOWLIST, (
            f"MISSING_SPEC_ALLOWLIST should be empty: {MISSING_SPEC_ALLOWLIST}"
        )
