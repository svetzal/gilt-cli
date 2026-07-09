from __future__ import annotations

import logging
from datetime import date

from gilt.ingest import load_accounts_config
from gilt.services.transaction_query_service import TransactionQueryService
from gilt.workspace import Workspace

from ..loaders import load_all_transactions
from .ytd_view import display_ytd_table, print_no_transactions

logger = logging.getLogger(__name__)


def run(
    *,
    account: str,
    year: int | None = None,
    workspace: Workspace,
    limit: int | None = None,
    default_currency: str | None = None,
    include_duplicates: bool = False,
    raw: bool = False,
    compare: bool = False,
) -> int:
    """Show year-to-date transactions for a single account as a Rich table."""
    the_year = year or date.today().year

    acct_nature = "asset"
    try:
        accounts = load_accounts_config(workspace.accounts_config)
        for a in accounts:
            aid = getattr(a, "account_id", None)
            if aid == account:
                acct_nature = getattr(a.nature, "value", str(a.nature))
    except OSError:
        logger.debug("Could not determine account nature, defaulting to asset", exc_info=True)

    load_result = load_all_transactions(workspace, include_duplicates=include_duplicates)
    query_service = TransactionQueryService()
    primaries = query_service.find_transactions(
        load_result, account_id=account, year=the_year, limit=limit
    )

    if compare:
        primaries = [t for t in primaries if t.vendor]

    if not primaries:
        print_no_transactions(account, the_year, compare)
        return 0

    display_ytd_table(primaries, account, the_year, acct_nature, compare, raw, query_service)
    return 0
