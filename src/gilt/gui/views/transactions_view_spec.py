import logging

import pytest

pytest.importorskip("PySide6")

from unittest.mock import MagicMock

from gilt.gui.views.transactions_view import TransactionsView


class DescribeLoadEnrichment:
    def it_should_set_enrichment_service_to_none_and_log_warning_on_error(self, caplog):
        view = MagicMock()
        view.event_store = MagicMock()
        view.event_store.get_events_by_type.side_effect = ValueError("corrupt event store")

        with caplog.at_level(logging.WARNING, logger="gilt.gui.views.transactions_view"):
            TransactionsView._load_enrichment(view)

        assert view.enrichment_service is None
        assert "Enrichment data unavailable" in caplog.text
