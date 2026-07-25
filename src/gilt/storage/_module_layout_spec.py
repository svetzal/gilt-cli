"""
Static guard: SQLite connection lifecycle must go through the shared helper.

`gilt.storage.sqlite_connection.connect` is the single place connection open/close
lifecycle is defined. No module anywhere under src/gilt/ may hand-roll
`sqlite3.connect(...)` / `conn.close()` outside that module — doing so duplicates
the lifecycle logic the shared helper exists to centralize.

Rules enforced:
  1. No module outside storage/sqlite_connection.py may call sqlite3.connect(.
  2. No module outside storage/sqlite_connection.py may call conn.close() inline.
  3. Every non-private module under storage/ has a companion *_spec.py.

The allowlists below are empty by design — all modules comply at the time this
guard was introduced. Add entries only as temporary scaffolding for active
migrations, and remove them as soon as the module is brought into compliance.
"""

from __future__ import annotations

from pathlib import Path

STORAGE_DIR = Path(__file__).parent
SRC_ROOT = STORAGE_DIR.parent

SQLITE_CONNECTION_MODULE = STORAGE_DIR / "sqlite_connection.py"

# Empty by design — all modules comply. Add entries only for active migrations.
CONNECT_ALLOWLIST: set[str] = set()
CLOSE_ALLOWLIST: set[str] = set()
MISSING_SPEC_ALLOWLIST: set[str] = set()


def _find_all_source_modules() -> list[Path]:
    """Return every non-spec, non-private, non-test Python module under src/gilt/."""
    modules = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        stem = path.stem
        if stem.startswith("_") or stem.endswith("_spec"):
            continue
        if path == SQLITE_CONNECTION_MODULE:
            continue
        modules.append(path)
    return modules


def _find_storage_modules() -> list[Path]:
    """Return every non-spec, non-private module directly under storage/."""
    modules = []
    for path in sorted(STORAGE_DIR.glob("*.py")):
        stem = path.stem
        if stem.startswith("_") or stem.endswith("_spec"):
            continue
        modules.append(path)
    return modules


def _scan(path: Path, pattern: str) -> list[str]:
    """Return lines containing the given pattern."""
    content = path.read_text(encoding="utf-8")
    hits = []
    for line in content.splitlines():
        stripped = line.strip()
        if pattern in stripped:
            hits.append(stripped)
    return hits


class DescribeStorageModuleLayout:
    def it_should_route_all_connections_through_the_shared_helper(self):
        """No module outside sqlite_connection.py may call sqlite3.connect(."""
        violations: list[str] = []
        for path in _find_all_source_modules():
            if path.stem in CONNECT_ALLOWLIST:
                continue
            hits = _scan(path, "sqlite3.connect(")
            for hit in hits:
                violations.append(f"{path.relative_to(SRC_ROOT)}: {hit}")
        assert violations == [], (
            "Connection lifecycle must go through gilt.storage.sqlite_connection.connect:\n"
            + "\n".join(violations)
        )

    def it_should_not_close_connections_inline(self):
        """No module outside sqlite_connection.py may call conn.close() inline."""
        violations: list[str] = []
        for path in _find_all_source_modules():
            if path.stem in CLOSE_ALLOWLIST:
                continue
            hits = _scan(path, "conn.close()")
            for hit in hits:
                violations.append(f"{path.relative_to(SRC_ROOT)}: {hit}")
        assert violations == [], (
            "Connection close must be handled by gilt.storage.sqlite_connection.connect:\n"
            + "\n".join(violations)
        )

    def it_should_have_a_companion_spec_for_every_storage_module(self):
        """Every non-private module under storage/ must have a sibling *_spec.py."""
        violations: list[str] = []
        for path in _find_storage_modules():
            if path.stem in MISSING_SPEC_ALLOWLIST:
                continue
            spec_path = path.with_name(f"{path.stem}_spec.py")
            if not spec_path.exists():
                violations.append(path.name)
        assert violations == [], "Storage modules missing a companion spec:\n" + "\n".join(
            violations
        )
