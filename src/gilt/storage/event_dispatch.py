"""Shared event dispatch helper for projection reducers."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from gilt.model.events import Event


def apply_event_handlers(
    conn: sqlite3.Connection,
    events: list[Event],
    handlers: dict[type[Event], Callable[[sqlite3.Connection, Event], None]],
) -> int:
    """Dispatch events to registered handlers.

    Args:
        conn: Open database connection
        events: Events to apply
        handlers: Mapping from event type to handler function

    Returns:
        Number of events processed (including events with no registered handler)
    """
    processed = 0
    for event in events:
        handler = handlers.get(type(event))
        if handler is not None:
            handler(conn, event)
        processed += 1
    return processed


__all__ = ["apply_event_handlers"]
