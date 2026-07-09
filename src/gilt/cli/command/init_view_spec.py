"""Specs for init_view.py — Rich rendering for the init command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.init_view as view_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    view_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
    return buf.getvalue()


class DescribePrintInitHeader:
    def it_should_show_the_workspace_root(self):
        from gilt.cli.command.init_view import print_init_header

        output = _capture(lambda: print_init_header(Path("/tmp/workspace")))
        assert "Initializing workspace" in output
        assert "/tmp/workspace" in output


class DescribeDisplayCreated:
    def it_should_list_created_dirs_and_files(self):
        from gilt.cli.command.init_view import display_created

        output = _capture(lambda: display_created(["data/accounts/"], ["config/accounts.yml"]))
        assert "Created" in output
        assert "data/accounts/" in output
        assert "config/accounts.yml" in output

    def it_should_render_nothing_when_empty(self):
        from gilt.cli.command.init_view import display_created

        output = _capture(lambda: display_created([], []))
        assert output.strip() == ""


class DescribeDisplaySkipped:
    def it_should_list_skipped_paths(self):
        from gilt.cli.command.init_view import display_skipped

        output = _capture(lambda: display_skipped(["ingest/"]))
        assert "Already exists" in output
        assert "ingest/" in output

    def it_should_render_nothing_when_empty(self):
        from gilt.cli.command.init_view import display_skipped

        output = _capture(lambda: display_skipped([]))
        assert output.strip() == ""


class DescribePrintAlreadyInitialized:
    def it_should_mention_already_initialized(self):
        from gilt.cli.command.init_view import print_already_initialized

        output = _capture(print_already_initialized)
        assert "already fully initialized" in output


class DescribePrintNextSteps:
    def it_should_show_the_root_and_next_steps(self):
        from gilt.cli.command.init_view import print_next_steps

        output = _capture(lambda: print_next_steps(Path("/tmp/workspace")))
        assert "Workspace ready at" in output
        assert "/tmp/workspace" in output
        assert "Next steps" in output
        assert "gilt ingest --write" in output
