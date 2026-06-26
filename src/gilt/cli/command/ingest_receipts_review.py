"""Interactive review loop for the ingest-receipts command."""

from __future__ import annotations

from rich.prompt import Prompt

from gilt.services.receipt_ingestion_service import MatchResult

from ..console import console


def resolve_ambiguous_interactively(ambiguous: list[MatchResult]) -> list[MatchResult]:
    """Prompt the user to disambiguate ambiguous matches. Returns resolved items."""
    resolved: list[MatchResult] = []

    for r in ambiguous:
        receipt = r.receipt
        tax_str = f" + ${receipt.tax_amount:.2f} {receipt.tax_type}" if receipt.tax_amount else ""
        subtotal = receipt.amount
        total = subtotal + receipt.tax_amount if receipt.tax_amount else subtotal

        console.print("\n[bold]Ambiguous receipt:[/bold]")
        console.print(f"  Vendor: {receipt.vendor}")
        if receipt.service:
            console.print(f"  Service: {receipt.service}")
        console.print(f"  Amount: ${subtotal:.2f}{tax_str} = ${total:.2f}")
        console.print(f"  Date: {receipt.receipt_date}")
        if receipt.invoice_number:
            console.print(f"  Invoice: {receipt.invoice_number}")
        console.print()

        for i, candidate in enumerate(r.candidates, 1):
            txid = candidate["transaction_id"][:8]
            txn_date = candidate.get("transaction_date", "")
            txn_amount = candidate.get("amount", "")
            desc = candidate.get("canonical_description", "")
            acct = candidate.get("account_id", "")
            console.print(f"  {i}) {txid}  {txn_date}  ${txn_amount}  {desc}  [{acct}]")

        console.print()
        valid_choices = [str(i) for i in range(1, len(r.candidates) + 1)] + ["s", "S"]
        choice = Prompt.ask(
            f"Select [1-{len(r.candidates)}/s to skip]",
            choices=valid_choices,
            show_choices=False,
        )

        if choice.lower() == "s":
            continue

        selected = r.candidates[int(choice) - 1]
        resolved.append(
            MatchResult(
                receipt=receipt,
                status="matched",
                transaction_id=selected["transaction_id"],
                candidate_count=r.candidate_count,
                current_description=selected.get("canonical_description", ""),
                candidates=r.candidates,
                match_confidence="user-selected",
            )
        )

    return resolved
