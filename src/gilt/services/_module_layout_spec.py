"""
Static guard: service modules must not import UI libraries or emit console output.

Services are the functional core — they must remain free of presentation concerns
so that both CLI and GUI shells can compose them without carrying UI dependencies.

Rules enforced:
  - No module under services/ or gui/services/ may import rich, typer, or PySide6.
  - No module under services/ or gui/services/ may call console.print, Table(, or Prompt.ask.

The allowlists below are empty by default and must stay empty. An empty allowlist
is the invariant, not the goal — all service modules comply at the time this guard
was introduced. Add entries only as temporary scaffolding for active migrations,
and remove them as soon as the module is brought into compliance.

Module length alone is NOT a violation. category_management_service.py,
duplicate_review_service.py, and similar large pure-logic modules must not be
split for size — only for genuine separation of concerns.
"""

from __future__ import annotations

from pathlib import Path

SERVICES_DIR = Path(__file__).parent
GUI_SERVICES_DIR = Path(__file__).parent.parent / "gui" / "services"

UI_IMPORT_PATTERNS = [
    "from rich",
    "import rich",
    "from typer",
    "import typer",
    "from PySide6",
    "import PySide6",
]

CONSOLE_PATTERNS = [
    "console.print",
    "Table(",
    "Prompt.ask",
]

# Empty by design — all service modules comply. Add entries only for active migrations.
UI_IMPORT_ALLOWLIST: set[str] = set()
CONSOLE_OUTPUT_ALLOWLIST: set[str] = set()


def _find_service_modules() -> list[tuple[str, Path]]:
    """Return all non-spec, non-private Python modules under services/ and gui/services/."""
    modules = []
    for search_dir in (SERVICES_DIR, GUI_SERVICES_DIR):
        if not search_dir.is_dir():
            continue
        for path in sorted(search_dir.glob("*.py")):
            stem = path.stem
            if stem.startswith("_") or stem.endswith("_spec"):
                continue
            modules.append((stem, path))
    return modules


def _scan(path: Path, patterns: list[str]) -> list[str]:
    """Return lines that contain any of the given patterns."""
    content = path.read_text(encoding="utf-8")
    hits = []
    for line in content.splitlines():
        stripped = line.strip()
        if any(p in stripped for p in patterns):
            hits.append(stripped)
    return hits


class DescribeServicesModuleLayout:
    def it_should_not_import_ui_libraries(self):
        """No service module may import rich, typer, or PySide6."""
        violations: list[str] = []
        for stem, path in _find_service_modules():
            if stem in UI_IMPORT_ALLOWLIST:
                continue
            hits = _scan(path, UI_IMPORT_PATTERNS)
            for hit in hits:
                violations.append(f"{path.name}: {hit}")
        assert violations == [], "Service modules must not import UI libraries.\n" + "\n".join(
            violations
        )

    def it_should_not_emit_console_output(self):
        """No service module may call console.print, Table(, or Prompt.ask."""
        violations: list[str] = []
        for stem, path in _find_service_modules():
            if stem in CONSOLE_OUTPUT_ALLOWLIST:
                continue
            hits = _scan(path, CONSOLE_PATTERNS)
            for hit in hits:
                violations.append(f"{path.name}: {hit}")
        assert violations == [], "Service modules must not emit console output.\n" + "\n".join(
            violations
        )
