"""Install gilt skill files for Claude Code integration."""

from __future__ import annotations

import json
import re
from importlib.metadata import version
from pathlib import Path

from ..console import print_error
from ._errors import CommandAbort
from .skill_init_view import display_results, print_install_header, print_source_not_found

_SKILL_SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "gilt"

_VERSION_FRONTMATTER_RE = re.compile(r"^(---\n.*?)(---\n)", re.DOTALL)

_SUCCESS_ACTIONS = frozenset({"created", "updated", "up-to-date"})


def _get_package_version() -> str:
    return version("gilt-cli")


def _build_frontmatter_version(text: str) -> str | None:
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
    """Install a single file. Returns status: created | updated | up-to-date | skipped | missing."""
    if not source.exists():
        return "missing"

    source_text = source.read_text(encoding="utf-8")

    new_text = _stamp_version(source_text, pkg_version) if stamp else source_text

    if dest.exists():
        existing_text = dest.read_text(encoding="utf-8")

        # Version guard: only applies to stamped files (SKILL.md)
        if stamp and not force:
            installed_version = _build_frontmatter_version(existing_text)
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


def _build_message(file_entries: list[dict[str, str]]) -> str:
    """Build a human-readable summary from file entries, omitting zero-count actions."""
    counts: dict[str, int] = {}
    for entry in file_entries:
        action = entry["action"]
        counts[action] = counts.get(action, 0) + 1

    parts = []
    for action in ("created", "updated", "up-to-date", "skipped", "missing"):
        if counts.get(action, 0) > 0:
            parts.append(f"{counts[action]} {action}")

    return "Skill files installed: " + (", ".join(parts) if parts else "nothing to do")


def run(
    *,
    global_install: bool = False,
    force: bool = False,
    json_output: bool = False,
) -> int:
    """Install gilt skill files for Claude Code.

    Args:
        global_install: Install to ~/.claude/skills/gilt/ instead of ./.claude/skills/gilt/
        force: Bypass version guard (overrides the refusal to overwrite a newer installed version)
        json_output: Emit machine-readable JSON to stdout instead of Rich console output

    Returns:
        Exit code (0 = all files succeeded, 1 = any file skipped/missing or source error)
    """
    pkg_version = _get_package_version()

    if not _SKILL_SOURCE_DIR.exists():
        if json_output:
            payload = {
                "success": False,
                "message": f"Skill source directory not found: {_SKILL_SOURCE_DIR}",
                "version": pkg_version,
                "files": [],
            }
            print(json.dumps(payload))
        else:
            print_error("Skill source directory not found.")
            print_source_not_found(_SKILL_SOURCE_DIR)
        raise CommandAbort(1)

    if global_install:
        target_dir = Path.home() / ".claude" / "skills" / "gilt"
    else:
        target_dir = Path.cwd() / ".claude" / "skills" / "gilt"

    # Files to install: (relative_path, stamp_version)
    files = [
        (Path("SKILL.md"), True),
        (Path("references") / "command-reference.md", False),
    ]

    file_entries: list[dict[str, str]] = []

    for rel_path, stamp in files:
        source = _SKILL_SOURCE_DIR / rel_path
        dest = target_dir / rel_path
        action = _install_file(source, dest, pkg_version, force, stamp)
        file_entries.append({"path": str(rel_path), "action": action})

    success = all(entry["action"] in _SUCCESS_ACTIONS for entry in file_entries)
    message = _build_message(file_entries)

    if json_output:
        payload = {
            "success": success,
            "message": message,
            "version": pkg_version,
            "files": file_entries,
        }
        print(json.dumps(payload))
    else:
        print_install_header(pkg_version, target_dir)
        display_results(file_entries)

    if not success:
        raise CommandAbort(1)
    return 0
