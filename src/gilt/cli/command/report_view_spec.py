"""Specs for report_view.py — Rich rendering for the report command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.report_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


class DescribeReportStatusMessages:
    def it_should_print_pandoc_warning(self):
        from gilt.cli.command.report_view import print_pandoc_warning

        assert "pandoc" in _capture(print_pandoc_warning)

    def it_should_print_no_categories(self):
        from gilt.cli.command.report_view import print_no_categories

        assert "No categories defined" in _capture(print_no_categories)

    def it_should_print_written_markdown_path(self):
        from gilt.cli.command.report_view import print_written_markdown

        assert "report.md" in _capture(lambda: print_written_markdown(Path("report.md")))

    def it_should_print_written_docx_path(self):
        from gilt.cli.command.report_view import print_written_docx

        assert "report.docx" in _capture(lambda: print_written_docx(Path("report.docx")))

    def it_should_print_docx_conversion_failed(self):
        from gilt.cli.command.report_view import print_docx_conversion_failed

        assert "conversion failed" in _capture(print_docx_conversion_failed)


class DescribeDisplayReportPreview:
    def it_should_show_paths_and_truncated_preview(self):
        from gilt.cli.command.report_view import display_report_preview

        content = "x" * 600
        output = _capture(
            lambda: display_report_preview(
                Path("out.md"), Path("out.docx"), True, content
            )
        )
        assert "out.md" in output
        assert "out.docx" in output
        assert "..." in output

    def it_should_omit_docx_path_without_pandoc(self):
        from gilt.cli.command.report_view import display_report_preview

        output = _capture(
            lambda: display_report_preview(Path("out.md"), Path("out.docx"), False, "short")
        )
        assert "out.md" in output
        assert "out.docx" not in output
