"""Specs for gilt.storage.event_dispatch — shared event dispatch helper."""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

from gilt.storage.event_dispatch import apply_event_handlers


class _EventA:
    pass


class _EventB:
    pass


class DescribeApplyEventHandlers:
    def it_should_dispatch_each_event_to_its_handler(self):
        conn = MagicMock(spec=sqlite3.Connection)
        handler_a = MagicMock()
        handler_b = MagicMock()

        event_a = _EventA()
        event_b = _EventB()
        handlers = {_EventA: handler_a, _EventB: handler_b}

        apply_event_handlers(conn, [event_a, event_b], handlers)

        handler_a.assert_called_once_with(conn, event_a)
        handler_b.assert_called_once_with(conn, event_b)

    def it_should_skip_events_with_no_registered_handler(self):
        conn = MagicMock(spec=sqlite3.Connection)
        handler_a = MagicMock()

        event_a = _EventA()
        event_unhandled = _EventB()
        handlers = {_EventA: handler_a}

        apply_event_handlers(conn, [event_a, event_unhandled], handlers)

        handler_a.assert_called_once_with(conn, event_a)

    def it_should_return_the_count_of_events_processed(self):
        conn = MagicMock(spec=sqlite3.Connection)
        handler = MagicMock()

        events = [_EventA() for _ in range(3)]
        handlers = {_EventA: handler}

        count = apply_event_handlers(conn, events, handlers)

        assert count == 3

    def it_should_count_unhandled_events_too(self):
        conn = MagicMock(spec=sqlite3.Connection)
        events = [_EventA(), _EventB()]
        handlers = {}

        count = apply_event_handlers(conn, events, handlers)

        assert count == 2
