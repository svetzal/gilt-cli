"""
Static guard: CLI flag identity is declared exactly once, in `_options.py`.

Enforces the "Option vocabulary" convention (see AGENTS.md, CLI Command Module
Layout): flag long name, short flag, type, and constraints live in a single
factory function in `gilt.cli.registration._options`. Registration modules pass
only per-command help text to those factories, forward parsed options to `run()`
via `command_kwargs(ctx, ...)` rather than restating every kwarg, and a command's
request dataclass (when it has one) is the sole parameter vocabulary for its
`run()`.

Three rules, each with its own empty-by-design allowlist:

1. No registration module (other than `_options.py`) contains a literal
   `typer.Option(` call for a flag long-name string that `_options.py` already
   declares as a factory. Such a flag must go through the shared factory instead
   of restating its identity inline.

2. No `dispatch(` call site in a registration module passes more than two
   explicit keyword arguments besides `workspace`. Anything more must route
   through `command_kwargs(ctx, ...)` — hand-rolling keyword-by-keyword
   forwarding is exactly the duplication this module layout eliminates.

3. Every flag long-name string (`"--something"`) appears at most once across
   `registration/*.py`, excluding `_options.py` and `*_spec.py` files. A second
   literal occurrence means a flag's identity is being restated instead of
   shared via a factory or left legitimately single-use.

The allowlists below are scaffolding: entries are removed as modules are
brought into compliance. Each is empty by design and must trend to empty.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REGISTRATION_DIR = Path(__file__).parent
OPTIONS_MODULE = REGISTRATION_DIR / "_options.py"

# Registration modules that still contain a raw typer.Option( for a flag already
# declared as a factory in _options.py. Remove an entry once the module is
# migrated to call the shared factory instead.
RAW_OPTION_ALLOWLIST: set[str] = set()

# Registration modules with a dispatch( call site passing more than two explicit
# keyword arguments besides `workspace`. Remove an entry once the call site is
# routed through command_kwargs(ctx, ...).
EXPLICIT_KWARGS_ALLOWLIST: set[str] = set()

# Flag long-name strings that legitimately appear more than once across
# registration/*.py (excluding _options.py and *_spec.py). Remove an entry once
# the duplicate literal is replaced by a shared factory reference.
DUPLICATE_FLAG_ALLOWLIST: set[str] = set()

_FLAG_STRING_RE = re.compile(r'"(--[a-zA-Z][a-zA-Z0-9-]*)"')


def _registration_modules(*, exclude_options: bool = True) -> list[Path]:
    """Non-spec .py modules in registration/, optionally excluding _options.py."""
    modules = []
    for path in sorted(REGISTRATION_DIR.glob("*.py")):
        if path.stem.endswith("_spec"):
            continue
        if exclude_options and path == OPTIONS_MODULE:
            continue
        modules.append(path)
    return modules


def _factory_flag_names() -> set[str]:
    """Flag long-name strings declared as typer.Option(...) args inside _options.py factories."""
    source = OPTIONS_MODULE.read_text(encoding="utf-8")
    return set(_FLAG_STRING_RE.findall(source))


def _dispatch_call_explicit_kwarg_counts(path: Path) -> list[tuple[int, int]]:
    """Return (lineno, explicit_kwarg_count) for every dispatch(...) call in *path*.

    Counts only literal `key=value` keyword arguments (excluding `workspace`);
    a `**command_kwargs(...)` unpack (keyword.arg is None) does not count.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    results = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "dispatch"
        ):
            explicit = [kw for kw in node.keywords if kw.arg is not None and kw.arg != "workspace"]
            results.append((node.lineno, len(explicit)))
    return results


class DescribeRawOptionConvention:
    def it_should_not_hand_roll_typer_option_for_a_flag_declared_in_options_py(self):
        factory_flags = _factory_flag_names()
        failures = []
        for path in _registration_modules():
            if path.stem in RAW_OPTION_ALLOWLIST:
                continue
            source = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(source.splitlines(), start=1):
                if "typer.Option(" not in line:
                    continue
                for flag in _FLAG_STRING_RE.findall(line):
                    if flag in factory_flags:
                        failures.append(f"{path.name}:{lineno} restates factory flag {flag!r}")

        assert not failures, (
            "Flags already declared in _options.py must be forwarded via the shared "
            "factory, not restated inline:\n" + "\n".join(f"  {f}" for f in failures)
        )


class DescribeExplicitKwargsConvention:
    def it_should_not_hand_roll_more_than_two_explicit_dispatch_kwargs(self):
        failures = []
        for path in _registration_modules(exclude_options=False):
            if path == OPTIONS_MODULE:
                continue
            if path.stem in EXPLICIT_KWARGS_ALLOWLIST:
                continue
            for lineno, count in _dispatch_call_explicit_kwarg_counts(path):
                if count > 2:
                    failures.append(
                        f"{path.name}:{lineno} dispatch() call has {count} explicit "
                        "keyword arguments besides workspace"
                    )

        assert not failures, (
            "dispatch() call sites with more than two explicit keyword arguments "
            "(besides workspace) must route through command_kwargs(ctx, ...):\n"
            + "\n".join(f"  {f}" for f in failures)
        )


class DescribeFlagUniquenessConvention:
    def it_should_declare_every_flag_long_name_at_most_once(self):
        counts: dict[str, list[str]] = {}
        for path in _registration_modules():
            source = path.read_text(encoding="utf-8")
            for flag in _FLAG_STRING_RE.findall(source):
                counts.setdefault(flag, []).append(path.name)

        failures = []
        for flag, locations in sorted(counts.items()):
            if flag in DUPLICATE_FLAG_ALLOWLIST:
                continue
            if len(locations) > 1:
                failures.append(f"{flag!r} declared in: {', '.join(locations)}")

        assert not failures, (
            "Each flag long-name must be declared literally at most once across "
            "registration/*.py (share via a factory instead):\n"
            + "\n".join(f"  {f}" for f in failures)
        )
