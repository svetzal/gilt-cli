"""Install gilt skill files for Claude Code integration."""

from __future__ import annotations

import re
from importlib.metadata import version
from pathlib import Path

from .util import console, print_error

_SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "gilt"

_VERSION_FRONTMATTER_RE = re.compile(r"^(---\n.*?)(---\n)", re.DOTALL)


def _get_package_version() -> str:
    return version("gilt-cli")


def _parse_frontmatter_version(text: str) -> str | None:
    """Extract gilt-version from YAML frontmatter, or None if absent."""
    match = _VERSION_FRONTMATTER_RE.match(text)
    if not match:
        return None
    frontmatter = match.group(1)
    for line in frontmatter.splitlines():
        if line.startswith("gilt-version:"):
            return line.split(":", 1)[1].strip()
    return None


def _stamp_version(text: str, pkg_version: str) -> str:
    """Insert gilt-version into YAML frontmatter."""
    match = _VERSION_FRONTMATTER_RE.match(text)
    if not match:
        return text
    frontmatter = match.group(1)
    closing = match.group(2)
    rest = text[match.end() :]
    return f"{frontmatter}gilt-version: {pkg_version}\n{closing}{rest}"


def _version_tuple(v: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple of ints."""
    parts = []
    for part in v.split("."):
        # Strip non-numeric suffixes (e.g. "1a2" -> 1)
        digits = re.match(r"\d+", part)
        parts.append(int(digits.group()) if digits else 0)
    return tuple(parts)


def _install_file(
    source: Path,
    dest: Path,
    pkg_version: str,
    force: bool,
    stamp: bool,
) -> str:
    """Install a single file. Returns status string."""
    if not source.exists():
        return "missing"

    source_text = source.read_text(encoding="utf-8")

    new_text = _stamp_version(source_text, pkg_version) if stamp else source_text

    if dest.exists():
        existing_text = dest.read_text(encoding="utf-8")

        # Version guard: only applies to stamped files (SKILL.md)
        if stamp and not force:
            installed_version = _parse_frontmatter_version(existing_text)
            if installed_version is not None and _version_tuple(installed_version) > _version_tuple(
                pkg_version
            ):
                return "skipped"

        # Check if content is identical
        if existing_text == new_text:
            return "up-to-date"

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(new_text, encoding="utf-8")
        return "updated"

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(new_text, encoding="utf-8")
    return "created"


def run(
    *,
    global_install: bool = False,
    force: bool = False,
) -> int:
    """Install gilt skill files for Claude Code.

    Args:
        global_install: Install to ~/.claude/skills/gilt/ instead of ./.claude/skills/gilt/
        force: Bypass version guard

    Returns:
        Exit code (0 = success, 1 = error)
    """
    pkg_version = _get_package_version()

    if not _SKILL_SOURCE_DIR.exists():
        print_error("Skill source directory not found.")
        console.print(f"  Expected: {_SKILL_SOURCE_DIR}")
        return 1

    if global_install:
        target_dir = Path.home() / ".claude" / "skills" / "gilt"
    else:
        target_dir = Path.cwd() / ".claude" / "skills" / "gilt"

    console.print(f"[bold cyan]Installing gilt skill[/] v{pkg_version}")
    console.print(f"  Target: {target_dir}\n")

    # Files to install: (relative_path, stamp_version)
    files = [
        (Path("SKILL.md"), True),
        (Path("references") / "command-reference.md", False),
    ]

    results: dict[str, list[str]] = {
        "created": [],
        "updated": [],
        "up-to-date": [],
        "skipped": [],
    }

    for rel_path, stamp in files:
        source = _SKILL_SOURCE_DIR / rel_path
        dest = target_dir / rel_path
        status = _install_file(source, dest, pkg_version, force, stamp)
        if status in results:
            results[status].append(str(rel_path))

    _report_results(results)
    return 0


def _report_results(results: dict[str, list[str]]) -> None:
    _report_group(results["created"], "[green]Created:[/]", "")
    _report_group(results["updated"], "[green]Updated:[/]", "")
    _report_group(results["up-to-date"], "[dim]Up-to-date:[/dim]", "[dim]", suffix="[/dim]")
    if results["skipped"]:
        console.print("[yellow]Skipped (installed version is newer):[/yellow]")
        for f in results["skipped"]:
            console.print(f"  [yellow]{f}[/yellow]")
        console.print("[dim]  Use --force to overwrite.[/dim]")


def _report_group(files: list[str], header: str, prefix: str, suffix: str = "") -> None:
    if files:
        console.print(header)
        for f in files:
            console.print(f"  {prefix}{f}{suffix}")
