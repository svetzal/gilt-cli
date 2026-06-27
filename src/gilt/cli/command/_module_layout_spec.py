"""
Static guard: orchestration modules must not embed Rich rendering or interactive prompts.

For every command/<name>.py that has a sibling <name>_view.py, the orchestration module must
not contain:
  - Table(          direct Rich table construction
  - from rich.table table import
  - Prompt.ask      interactive prompt
  - from rich.prompt prompt import
  - rich.progress   progress bar import
  - Progress(       progress bar construction
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
]


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
                if violation in source:
                    failures.append(f"{name}.py contains '{violation}'")

        assert not failures, (
            "Orchestration modules must not embed Rich rendering:\n"
            + "\n".join(f"  {f}" for f in failures)
        )
