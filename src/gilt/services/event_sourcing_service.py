"""
Event sourcing service - centralized initialization and setup for event store and projections.

This service extracts all event-sourcing infrastructure setup logic from CLI commands,
providing a single place to initialize event stores, check for their existence,
and set up projections. This follows the DRY principle and ensures consistent
error messages and setup behavior across all commands.

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

Dependencies are injected. Functions return data structures or raise exceptions
that the caller can handle appropriately (e.g., display with Rich in CLI).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from gilt.workspace import Workspace

from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


@dataclass
class EventStoreStatus:
    """Status of event store existence check."""

    exists: bool
    path: Path
    csv_files_count: Optional[int] = None  # Number of CSV files found if event store missing


@dataclass
class ProjectionStatus:
    """Status of projection database."""

    exists: bool
    path: Path
    current_sequence: int = 0
    latest_event_sequence: int = 0
    is_outdated: bool = False
    events_to_process: int = 0


class EventSourcingService:
    """
    Service for event sourcing infrastructure setup.

    This is the functional core - pure business logic with no I/O dependencies
    beyond reading filesystem and database status.

    Responsibilities:
    - Check event store and projection existence
    - Initialize event store and projection builder
    - Determine if projections need rebuilding
    - Provide consistent error information

    Does NOT:
    - Display anything to console
    - Prompt users for input
    - Format output for display
    - Exit the process
    """

    def __init__(
        self,
        event_store_path: Optional[Path] = None,
        projections_path: Optional[Path] = None,
        workspace: Optional["Workspace"] = None,
    ):
        """
        Initialize the service.

        Args:
            event_store_path: Path to event store database (explicit override)
            projections_path: Path to projections database (explicit override)
            workspace: Workspace to derive paths from (used when explicit paths not given)
        """
        if workspace is not None:
            self.event_store_path = event_store_path or workspace.event_store_path
            self.projections_path = projections_path or workspace.projections_path
        else:
            # Fallback to relative paths for backward compat
            self.event_store_path = event_store_path or Path("data/events.db")
            self.projections_path = projections_path or Path("data/projections.db")

    def check_event_store_status(self, data_dir: Optional[Path] = None) -> EventStoreStatus:
        """
        Check if event store exists and gather diagnostic info.

        Args:
            data_dir: Optional data directory to check for CSV files (for migration hints)

        Returns:
            EventStoreStatus with existence info and diagnostics
        """
        exists = self.event_store_path.exists()

        csv_count = None
        if not exists and data_dir and data_dir.exists():
            # Check for CSV files to provide helpful migration message
            csv_files = list(data_dir.glob("*.csv"))
            csv_count = len(csv_files)

        return EventStoreStatus(
            exists=exists, path=self.event_store_path, csv_files_count=csv_count
        )

    def check_projection_status(self, event_store: EventStore) -> ProjectionStatus:
        """
        Check if projections exist and whether they're up to date.

        Args:
            event_store: Event store to check against

        Returns:
            ProjectionStatus with state information
        """
        exists = self.projections_path.exists()

        if not exists:
            return ProjectionStatus(exists=False, path=self.projections_path)

        # Check if up to date
        projection_builder = ProjectionBuilder(self.projections_path)
        current_seq = projection_builder.get_current_sequence()
        latest_seq = event_store.get_latest_sequence_number()

        is_outdated = current_seq < latest_seq
        events_to_process = latest_seq - current_seq if is_outdated else 0

        return ProjectionStatus(
            exists=True,
            path=self.projections_path,
            current_sequence=current_seq,
            latest_event_sequence=latest_seq,
            is_outdated=is_outdated,
            events_to_process=events_to_process,
        )

    def get_event_store(self) -> EventStore:
        """
        Get initialized event store.

        Note: This will CREATE the database file if it doesn't exist.
        Caller should check existence first using check_event_store_status().

        Returns:
            EventStore instance
        """
        return EventStore(str(self.event_store_path))

    def get_projection_builder(self) -> ProjectionBuilder:
        """
        Get initialized projection builder.

        Note: This will CREATE the database file if it doesn't exist.
        Caller should check existence first using check_projection_status().

        Returns:
            ProjectionBuilder instance
        """
        return ProjectionBuilder(self.projections_path)

    def ensure_projections_up_to_date(
        self, event_store: EventStore, projection_builder: Optional[ProjectionBuilder] = None
    ) -> int:
        """
        Ensure projections are up to date, rebuilding if necessary.

        Args:
            event_store: Event store to read events from
            projection_builder: Optional existing projection builder (will create if None)

        Returns:
            Number of events processed (0 if already up to date)
        """
        if projection_builder is None:
            projection_builder = self.get_projection_builder()

        status = self.check_projection_status(event_store)

        if not status.exists:
            # Rebuild from scratch
            return projection_builder.rebuild_from_scratch(event_store)
        elif status.is_outdated:
            # Incremental rebuild
            return projection_builder.rebuild_incremental(event_store)
        else:
            # Already up to date
            return 0


__all__ = [
    "EventSourcingService",
    "EventStoreStatus",
    "ProjectionStatus",
]
