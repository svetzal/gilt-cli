"""
Static guard: orchestration modules must not embed Rich rendering, interactive prompts,
console output, or hand-rolled dry-run/mutation flow.

For every command/<name>.py that has a sibling <name>_view.py, the orchestration module must
not contain:
  - Table(          direct Rich table construction
  - from rich.table table import
  - Prompt.ask      interactive prompt
  - from rich.prompt prompt import
  - rich.progress   progress bar import
  - Progress(       progress bar construction
  - console.print   direct console output (belongs in the view module)

Additional conventions enforced here:
  - Every orchestration module with more than 3 console.print calls must have a view sibling.
  - Every module with a `write: bool` parameter must route persistence through
    mutations.run_confirmed_mutation / run_persisted_mutation, and must never inline the
    dry-run wording ("Use --write", "use --write", "DRY RUN MODE") — that wording lives
    solely in gilt.cli.console.print_dry_run_message.

The allowlists below name the modules that do not yet satisfy a convention. They are
scaffolding: entries are removed as each module is brought into compliance. An empty
allowlist is the goal.
"""

from __future__ import annotations

from pathlib import Path

COMMAND_DIR = Path(__file__).parent
VIOLATIONS = [
    "Table(",
    "from rich.table",
    "Prompt.ask",
    "from rich.prompt",
    "rich.progress",
    "Progress(",
    "console.print",
]

# Modules that have a view sibling but still emit console.print from orchestration.
# Remove an entry once its console.print calls have moved into the view module.
ORCHESTRATION_PRINT_ALLOWLIST: set[str] = set()

# Modules with more than 3 console.print calls that do not yet have a view sibling.
# Remove an entry once its <name>_view.py is created and the prints move there.
MISSING_VIEW_ALLOWLIST: set[str] = {
    "note",
    "skill_init",
    "init",
    "report",
    "reingest",
    "ingest",
    "category",
    "migrate_to_events",
}

# Modules with a `write: bool` parameter that do not yet route through a mutation helper.
# Remove an entry once persistence is routed through run_confirmed_mutation /
# run_persisted_mutation and the inline dry-run wording is removed.
MUTATION_FLOW_ALLOWLIST: set[str] = {
    "ingest_receipts",
    "report",
    "reingest",
    "ingest",
    "category",
    "migrate_to_events",
}

DRY_RUN_WORDING = ["Use --write", "use --write", "DRY RUN MODE"]
MUTATION_HELPERS = ["run_confirmed_mutation", "run_persisted_mutation"]

_SKIP_STEMS = {"conftest"}


def _is_orchestration_module(path: Path) -> bool:
    stem = path.stem
    if stem.startswith("_"):
        return False
    if stem.endswith("_view") or stem.endswith("_review") or stem.endswith("_spec"):
        return False
    return stem not in _SKIP_STEMS


def _find_orchestration_modules() -> list[tuple[str, Path]]:
    """Return all command orchestration modules (non-view/review/spec/private)."""
    modules = []
    for path in sorted(COMMAND_DIR.glob("*.py")):
        if _is_orchestration_module(path):
            modules.append((path.stem, path))
    return modules


def _find_split_orchestration_modules():
    """Find all orchestration modules that have a companion _view.py."""
    modules = []
    for view_path in sorted(COMMAND_DIR.glob("*_view.py")):
        stem = view_path.stem.replace("_view", "")
        orch_path = COMMAND_DIR / f"{stem}.py"
        if orch_path.exists():
            modules.append((stem, orch_path))
    return modules


class DescribeModuleLayoutConvention:
    def it_should_not_have_rich_rendering_in_orchestration_modules(self):
        split_modules = _find_split_orchestration_modules()
        assert split_modules, "No split orchestration modules found — check the test setup"

        failures = []
        for name, path in split_modules:
            source = path.read_text(encoding="utf-8")
            for violation in VIOLATIONS:
                if violation == "console.print" and name in ORCHESTRATION_PRINT_ALLOWLIST:
                    continue
                if violation in source:
                    failures.append(f"{name}.py contains '{violation}'")

        assert not failures, (
            "Orchestration modules must not embed Rich rendering or console output:\n"
            + "\n".join(f"  {f}" for f in failures)
        )


class DescribeViewSiblingConvention:
    def it_should_have_a_view_sibling_for_print_heavy_orchestration_modules(self):
        """Any orchestration module with more than 3 console.print calls needs a view sibling."""
        failures = []
        for name, path in _find_orchestration_modules():
            source = path.read_text(encoding="utf-8")
            if source.count("console.print") <= 3:
                continue
            if name in MISSING_VIEW_ALLOWLIST:
                continue
            if not (COMMAND_DIR / f"{name}_view.py").exists():
                failures.append(f"{name}.py has >3 console.print calls but no {name}_view.py")

        assert not failures, (
            "Print-heavy orchestration modules must have a view sibling:\n"
            + "\n".join(f"  {f}" for f in failures)
        )


class DescribeMutationFlowConvention:
    def it_should_route_write_commands_through_mutation_helpers(self):
        """Modules with `write: bool` must route through a mutation helper."""
        failures = []
        for name, path in _find_orchestration_modules():
            source = path.read_text(encoding="utf-8")
            if "write: bool" not in source:
                continue
            if name in MUTATION_FLOW_ALLOWLIST:
                continue
            if not any(helper in source for helper in MUTATION_HELPERS):
                failures.append(
                    f"{name}.py has `write: bool` but does not call a mutation helper"
                )

        assert not failures, (
            "Write commands must route through mutations.run_confirmed_mutation / "
            "run_persisted_mutation:\n" + "\n".join(f"  {f}" for f in failures)
        )

    def it_should_not_inline_dry_run_wording_in_write_commands(self):
        """Modules with `write: bool` must not inline dry-run wording."""
        failures = []
        for name, path in _find_orchestration_modules():
            source = path.read_text(encoding="utf-8")
            if "write: bool" not in source:
                continue
            if name in MUTATION_FLOW_ALLOWLIST:
                continue
            for wording in DRY_RUN_WORDING:
                if wording in source:
                    failures.append(f"{name}.py inlines dry-run wording '{wording}'")

        assert not failures, (
            "Dry-run wording lives only in print_dry_run_message:\n"
            + "\n".join(f"  {f}" for f in failures)
        )


def _find_view_and_review_modules():
    """Return all *_view.py and *_review.py modules in the command directory."""
    modules = []
    for path in sorted(COMMAND_DIR.glob("*_view.py")):
        modules.append(path.stem)
    for path in sorted(COMMAND_DIR.glob("*_review.py")):
        modules.append(path.stem)
    return modules


class DescribeSpecCoverage:
    def it_should_have_a_spec_file_for_every_view_and_review_module(self):
        """Every *_view.py and *_review.py must have a companion *_spec.py."""
        modules = _find_view_and_review_modules()
        assert modules, "No view/review modules found — check the test setup"

        missing_specs = []
        for module_stem in modules:
            spec_path = COMMAND_DIR / f"{module_stem}_spec.py"
            if not spec_path.exists():
                missing_specs.append(f"{module_stem}_spec.py")

        assert not missing_specs, (
            "Missing spec files for view/review modules:\n"
            + "\n".join(f"  {s}" for s in missing_specs)
        )
