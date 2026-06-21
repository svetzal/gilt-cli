from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from gilt.gui.services.import_service import ImportFileMapping, ImportResult, ImportService


def compute_file_progress_window(i: int, total: int) -> tuple[int, int]:
    """Return (start_pct, end_pct) for file i of total, for progress bar allocation."""
    return int((i / total) * 100), int(((i + 1) / total) * 100)


class ImportWorker(QThread):
    """Worker thread for import operations."""

    progress = Signal(int)  # 0-100
    finished = Signal(object)  # ImportResult
    error = Signal(str)

    def __init__(
        self,
        service: ImportService,
        mappings: list[ImportFileMapping],
        write: bool,
        exclude_ids: list[str] | None = None,
        categorization_map: dict[str, str] | None = None,
    ):
        super().__init__()
        self.service = service
        self.mappings = mappings
        self.write = write
        self.exclude_ids = exclude_ids
        self.categorization_map = categorization_map

    def run(self):
        try:
            total_imported = 0
            total_duplicates = 0
            all_messages = []

            for i, mapping in enumerate(self.mappings):
                if not mapping.selected_account_id:
                    continue

                file_progress_start, file_progress_end = compute_file_progress_window(
                    i, len(self.mappings)
                )

                def progress_callback(pct, _start=file_progress_start, _end=file_progress_end):
                    overall = _start + int((pct / 100) * (_end - _start))
                    self.progress.emit(overall)

                result = self.service.import_file(
                    mapping.file_info.path,
                    mapping.selected_account_id,
                    write=self.write,
                    progress_callback=progress_callback,
                    exclude_ids=self.exclude_ids,
                    categorization_map=self.categorization_map,
                )

                total_imported += result.imported_count
                total_duplicates += result.duplicate_count
                all_messages.extend(result.messages)

                if not result.success:
                    self.finished.emit(
                        ImportResult(
                            success=False,
                            imported_count=total_imported,
                            duplicate_count=total_duplicates,
                            error_count=1,
                            messages=all_messages,
                        )
                    )
                    return

            self.progress.emit(100)
            self.finished.emit(
                ImportResult(
                    success=True,
                    imported_count=total_imported,
                    duplicate_count=total_duplicates,
                    error_count=0,
                    messages=all_messages,
                )
            )

        except (OSError, ValueError, UnicodeDecodeError) as e:
            self.error.emit(str(e))
