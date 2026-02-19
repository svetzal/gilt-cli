# gilt × mailctl Integration Plan

## Vision

Bank transaction data has truth but anemic descriptions. Email receipts have rich context — service names, invoice numbers, tax breakdowns, PDF attachments. Combining them gives a complete financial picture.

gilt becomes the single source of truth for personal finance, enriched by mailctl's email intelligence, navigable through the Qt GUI, and reportable via CLI and dashboards.

## Phase 1 — Transaction Enrichment from Email

### New command: `gilt enrich`

Accept enrichment data that augments existing transactions with richer metadata from email receipts.

**Input format:** JSON enrichment records that match to existing transactions:

```json
{
  "match": {
    "date": "2026-02-16",
    "amount": -35.01,
    "account": "RBC_MC",
    "description_contains": "ZOOM"
  },
  "enrichment": {
    "vendor": "Zoom Communications, Inc.",
    "service": "Zoom Workplace Pro + Scheduler",
    "invoice_number": "INV342066242",
    "tax_amount": 4.03,
    "tax_type": "HST",
    "receipt_email_uid": 22568,
    "receipt_pdf": "INV342066242_A01117877_02162026.pdf",
    "type": "business"
  }
}
```

**Matching strategy:**
- Primary: amount + date (±2 days) + account
- Secondary: amount + description pattern + account
- Flag ambiguous matches for manual review

**Storage:** Enrichment data stored as events in the event store, projected into a `transaction_enrichments` table linked by transaction ID.

### New command: `gilt subscriptions`

Detect recurring transactions and produce a subscription report.

**Detection logic:**
- Group transactions by normalized vendor (from enrichment or description pattern)
- Compute cadence from date intervals
- Flag active vs possibly-cancelled (no charge in 2× expected interval)
- Pull enrichment data for rich display

**Output:**
- Human-readable table (default)
- JSON (--json) for dashboard consumption
- Markdown (--format md) for reports

### mailctl export command

Add `mailctl receipts-export` that outputs enrichment-ready JSON:
- Searches for receipt/invoice emails
- Extracts vendor, amount, date, invoice number, tax details
- Outputs JSON matching gilt's enrichment format
- Pipe-friendly: `mailctl receipts-export | gilt enrich --write`

## Phase 2 — Qt GUI Subscription View

Add a subscriptions panel to the Qt GUI:
- Summary cards: business total, personal total, grand total, potential savings
- List view of all detected subscriptions grouped by business/personal
- Drill down from subscription → matched transactions → enrichment details (invoice #, tax, PDF)
- Visual timeline of upcoming renewals and decision deadlines
- Cost trend charts (monthly spend over time per service)
- Flag services for review/cancel with notes

## Phase 3 — Ongoing Automation

### Enrichment pipeline

```
mailctl receipts-export --since last-run \
  | gilt enrich --write
```

- Run via cron or on-demand
- Track last-run timestamp to avoid re-processing
- Deduplicate by invoice number / receipt ID

### Smart categorization

Use enrichment vendor data to improve gilt's auto-categorization:
- Known subscription vendors → auto-assign categories
- Business-flagged vendors → Mojility:Subscriptions
- Enrichment data trains the ML categorizer

## Open Questions

- Should enrichment data live in gilt's event store or as a separate SQLite table?
- How to handle multi-currency normalization (USD charges on CAD card)?
- Should the mailctl → gilt pipeline be a single command or stay as a pipe?
- Qt GUI: new tab or integrated into existing transaction view?
