"""Specs for skill_init_view.py — Rich rendering for the skill-init command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.skill_init_view as view_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    view_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
    return buf.getvalue()


class DescribePrintSourceNotFound:
    def it_should_show_the_expected_path(self):
        from gilt.cli.command.skill_init_view import print_source_not_found

        output = _capture(lambda: print_source_not_found(Path("/tmp/skills/gilt")))
        assert "Expected:" in output
        assert "/tmp/skills/gilt" in output


class DescribePrintInstallHeader:
    def it_should_show_the_version_and_target(self):
        from gilt.cli.command.skill_init_view import print_install_header

        output = _capture(lambda: print_install_header("0.4.1", Path("/tmp/.claude/skills/gilt")))
        assert "Installing gilt skill" in output
        assert "0.4.1" in output
        assert "/tmp/.claude/skills/gilt" in output


class DescribeDisplayResults:
    def it_should_report_created_files(self):
        from gilt.cli.command.skill_init_view import display_results

        entries = [{"path": "SKILL.md", "action": "created"}]
        output = _capture(lambda: display_results(entries))
        assert "Created:" in output
        assert "SKILL.md" in output

    def it_should_report_updated_files(self):
        from gilt.cli.command.skill_init_view import display_results

        entries = [{"path": "SKILL.md", "action": "updated"}]
        output = _capture(lambda: display_results(entries))
        assert "Updated:" in output
        assert "SKILL.md" in output

    def it_should_report_up_to_date_files(self):
        from gilt.cli.command.skill_init_view import display_results

        entries = [{"path": "SKILL.md", "action": "up-to-date"}]
        output = _capture(lambda: display_results(entries))
        assert "Up-to-date:" in output
        assert "SKILL.md" in output

    def it_should_report_skipped_files_with_force_hint(self):
        from gilt.cli.command.skill_init_view import display_results

        entries = [{"path": "SKILL.md", "action": "skipped"}]
        output = _capture(lambda: display_results(entries))
        assert "Skipped" in output
        assert "--force" in output
        assert "SKILL.md" in output

    def it_should_report_missing_source_files(self):
        from gilt.cli.command.skill_init_view import display_results

        entries = [{"path": "references/command-reference.md", "action": "missing"}]
        output = _capture(lambda: display_results(entries))
        assert "Missing source files:" in output
        assert "references/command-reference.md" in output
