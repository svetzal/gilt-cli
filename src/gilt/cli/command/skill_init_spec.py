"""Specs for the skill-init command."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gilt.cli.command.skill_init import (
    _parse_frontmatter_version,
    _stamp_version,
    _version_tuple,
    run,
)


class DescribeVersionParsing:
    def it_should_extract_version_from_frontmatter(self):
        text = "---\nname: gilt\ngilt-version: 1.2.3\n---\nBody\n"
        assert _parse_frontmatter_version(text) == "1.2.3"

    def it_should_return_none_when_no_version_field(self):
        text = "---\nname: gilt\n---\nBody\n"
        assert _parse_frontmatter_version(text) is None

    def it_should_return_none_when_no_frontmatter(self):
        text = "# Just markdown\n"
        assert _parse_frontmatter_version(text) is None


class DescribeVersionStamping:
    def it_should_insert_version_into_frontmatter(self):
        text = "---\nname: gilt\n---\nBody\n"
        result = _stamp_version(text, "0.4.1")
        assert "gilt-version: 0.4.1" in result
        assert result.startswith("---\n")
        assert "Body\n" in result

    def it_should_preserve_existing_frontmatter_fields(self):
        text = "---\nname: gilt\ndescription: A tool\n---\nContent\n"
        result = _stamp_version(text, "1.0.0")
        assert "name: gilt" in result
        assert "description: A tool" in result
        assert "gilt-version: 1.0.0" in result


class DescribeVersionTuple:
    def it_should_parse_simple_version(self):
        assert _version_tuple("1.2.3") == (1, 2, 3)

    def it_should_compare_versions_correctly(self):
        assert _version_tuple("0.5.0") > _version_tuple("0.4.1")
        assert _version_tuple("0.4.1") < _version_tuple("0.4.2")
        assert _version_tuple("1.0.0") > _version_tuple("0.99.99")


class DescribeSkillInit:
    def it_should_create_skill_files_in_target_directory(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run()

            skill_md = target / ".claude" / "skills" / "gilt" / "SKILL.md"
            cmd_ref = target / ".claude" / "skills" / "gilt" / "references" / "command-reference.md"
            assert rc == 0
            assert skill_md.exists()
            assert cmd_ref.exists()

    def it_should_stamp_version_into_skill_md(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run()

            skill_md = target / ".claude" / "skills" / "gilt" / "SKILL.md"
            content = skill_md.read_text(encoding="utf-8")
            assert _parse_frontmatter_version(content) == "0.4.1"

    def it_should_not_stamp_version_into_command_reference(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run()

            cmd_ref = target / ".claude" / "skills" / "gilt" / "references" / "command-reference.md"
            content = cmd_ref.read_text(encoding="utf-8")
            assert "gilt-version" not in content

    def it_should_install_to_global_directory_with_flag(self):
        with TemporaryDirectory() as tmpdir:
            global_home = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.home", return_value=global_home),
            ):
                rc = run(global_install=True)

            skill_md = global_home / ".claude" / "skills" / "gilt" / "SKILL.md"
            assert rc == 0
            assert skill_md.exists()

    def it_should_refuse_to_overwrite_when_installed_version_is_newer(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            skill_dir = target / ".claude" / "skills" / "gilt"
            skill_dir.mkdir(parents=True)
            # Pre-install a newer version
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\nname: gilt\ngilt-version: 9.9.9\n---\nOld content\n",
                encoding="utf-8",
            )

            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run()

            # Should not overwrite
            content = skill_md.read_text(encoding="utf-8")
            assert _parse_frontmatter_version(content) == "9.9.9"
            assert "Old content" in content
            assert rc == 1  # skipped file → non-zero exit

    def it_should_overwrite_newer_version_with_force(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            skill_dir = target / ".claude" / "skills" / "gilt"
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\nname: gilt\ngilt-version: 9.9.9\n---\nOld content\n",
                encoding="utf-8",
            )

            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run(force=True)

            content = skill_md.read_text(encoding="utf-8")
            assert _parse_frontmatter_version(content) == "0.4.1"
            assert rc == 0

    def it_should_always_install_when_no_version_in_existing_file(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            skill_dir = target / ".claude" / "skills" / "gilt"
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\nname: gilt\n---\nOld content without version\n",
                encoding="utf-8",
            )

            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run()

            content = skill_md.read_text(encoding="utf-8")
            assert _parse_frontmatter_version(content) == "0.4.1"
            assert rc == 0

    def it_should_report_up_to_date_when_content_unchanged(self):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            # First install
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run()

            # Second install — should be up-to-date
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run()

            assert rc == 0

    def it_should_return_1_when_any_file_is_skipped(self):
        """Exit code 1 in Rich mode when the version guard skips a file."""
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            skill_dir = target / ".claude" / "skills" / "gilt"
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\nname: gilt\ngilt-version: 9.9.9\n---\nOld content\n",
                encoding="utf-8",
            )

            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run()

            assert rc == 1


class DescribeJsonOutput:
    def it_should_emit_json_with_expected_top_level_keys(self, capsys):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run(json_output=True)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert "success" in payload
            assert "message" in payload
            assert "version" in payload
            assert "files" in payload
            assert isinstance(payload["files"], list)
            for entry in payload["files"]:
                assert "path" in entry
                assert "action" in entry

    def it_should_report_success_true_on_clean_install(self, capsys):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run(json_output=True)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert rc == 0
            assert payload["success"] is True
            assert payload["version"] == "0.4.1"
            assert all(e["action"] == "created" for e in payload["files"])

    def it_should_report_success_false_when_any_file_skipped(self, capsys):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            skill_dir = target / ".claude" / "skills" / "gilt"
            skill_dir.mkdir(parents=True)
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\nname: gilt\ngilt-version: 9.9.9\n---\nOld content\n",
                encoding="utf-8",
            )

            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run(json_output=True)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert rc == 1
            assert payload["success"] is False
            skill_entry = next(e for e in payload["files"] if e["path"] == "SKILL.md")
            assert skill_entry["action"] == "skipped"

    def it_should_report_up_to_date_as_success(self, capsys):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            # First install — drain capsys so only the second run's JSON is captured
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run(json_output=True)
            capsys.readouterr()  # discard first-install output

            # Second install — should be up-to-date
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                rc = run(json_output=True)

            captured = capsys.readouterr()
            payload = json.loads(captured.out)
            assert rc == 0
            assert payload["success"] is True
            assert all(e["action"] == "up-to-date" for e in payload["files"])

    def it_should_not_emit_rich_markup_in_json_mode(self, capsys):
        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            with (
                patch("gilt.cli.command.skill_init._get_package_version", return_value="0.4.1"),
                patch("gilt.cli.command.skill_init.Path.cwd", return_value=target),
            ):
                run(json_output=True)

            captured = capsys.readouterr()
            # Output must parse as valid JSON — no Rich markup (e.g. [bold cyan]) leaking in
            payload = json.loads(captured.out)
            assert payload is not None
