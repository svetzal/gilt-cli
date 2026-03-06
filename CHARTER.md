# Gilt Charter

## Purpose

Gilt exists to give individuals and households **clear sight into where their money goes and deliberate control over where it should go** — without surrendering financial data to third parties.

It is a tool for building and enforcing **fiscal policy at the personal scale**: the ongoing practice of defining spending intentions, measuring reality against those intentions, and adjusting course with full knowledge of the facts.

## Vision

A person using Gilt — whether directly through the GUI or with agentic assistance through the CLI — can at any moment answer:

- **Where did my money go?** — Every transaction is ingested, normalized, categorized, and traceable across accounts.
- **Where is my money going?** — Budgets, spending trends, and category analysis reveal the current trajectory.
- **Where should my money go?** — Fiscal policies (budgets, category structures, allocation targets) encode deliberate intent about spending.
- **Am I on track?** — Budget-vs-actual comparisons, variance reports, and trend analysis close the feedback loop between policy and reality.

Over time, Gilt becomes a **financial memory and policy engine** — the place where a household's fiscal knowledge accumulates, patterns are recognized, and decisions are informed by complete history rather than fragmentary recollection.

## Design Philosophy

### Privacy as Architecture

Financial data is intimate. Gilt treats privacy not as a feature toggle but as an architectural constraint. All processing — ingestion, categorization, duplicate detection, ML inference, reporting — runs locally. There is no network layer to secure because there is no network layer. The user's data stays on the user's machine, period.

### Safety Through Explicitness

Every mutation is dry-run by default. The system shows what it would do, waits for explicit confirmation via `--write`, and only then acts. This makes Gilt safe to explore — you can ask any question, try any categorization, preview any batch operation — without risk of corrupting your data.

### Two Interfaces, One Truth

The CLI serves agentic workflows and power users. The GUI serves visual exploration and interactive review. Both interfaces share the same service layer, the same event store, and the same projections. Neither is subordinate — they are peers that address different modes of financial work.

### Learning From Use

Gilt improves with use. Categorization patterns learned from user decisions feed ML classifiers. Duplicate detection evolves through feedback loops. The event-sourced architecture preserves every decision as training data for future automation, creating a virtuous cycle where manual work today reduces manual work tomorrow.

## Core Capabilities

### 1. Ingestion & Normalization
Import raw bank exports from any institution and normalize them into a unified ledger format. Link inter-account transfers automatically. Compute deterministic transaction IDs for idempotent re-processing.

### 2. Categorization & Policy
Define a category hierarchy that reflects how you think about spending. Apply categories manually, by rule, or through ML-assisted auto-categorization. Diagnose inconsistencies. The category structure *is* fiscal policy — it encodes what kinds of spending you distinguish and care about.

### 3. Budgeting & Variance Analysis
Set budget targets by category (monthly or yearly). Compare actual spending to budgeted amounts. Prorate budgets for partial periods. Generate reports that reveal where reality diverges from intent — the essential feedback loop of fiscal management.

### 4. Duplicate Detection & Data Quality
Identify and resolve duplicate transactions using heuristic matching, local LLM inference, and trained ML classifiers. Maintain data integrity through an immutable event log and deterministic projections.

### 5. Reporting & Insight
Generate structured reports (markdown, docx) for periodic review. Support time-travel queries against historical budget states. Provide the raw material for informed fiscal decisions.

### 6. Event-Sourced Audit Trail
Every categorization, budget change, duplicate resolution, and enrichment is recorded as an immutable event. The complete history of financial decisions is preserved, queryable, and available as training data. Projections can be rebuilt from events at any time.

## Aspirational Directions

These represent where Gilt can evolve, guided by the same principles:

### Fiscal Policy as Code
Move beyond budgets-as-numbers toward budgets-as-rules. Allow users to express fiscal policies declaratively: spending limits, savings targets, allocation percentages, seasonal adjustments. The system enforces and reports against these policies automatically.

### Proactive Agentic Assistance
An agent working with Gilt should be able to: ingest new exports, auto-categorize with high confidence, flag anomalies, generate periodic reports, and surface only the decisions that genuinely require human judgment. The human sets policy; the agent executes it.

### Trend Analysis & Forecasting
Use accumulated history to project future spending patterns. Identify seasonal variations, creeping expenses, and structural changes in cash flow. Help users see not just where they are but where they're heading.

### Household Financial Dashboard
The GUI evolves from a transaction viewer into a financial dashboard — a place where a household can see its complete financial picture at a glance, drill into any category or account, and make informed decisions about allocation and spending.

### Receipt & Document Integration
Connect transactions to supporting documents (receipts, invoices, statements) for complete record-keeping. Support tax preparation by linking categorized transactions to their documentation.

### Multi-Currency & International
Support transactions in multiple currencies with proper conversion tracking, essential for users who operate across financial jurisdictions.

## Guiding Constraints

1. **No cloud, no APIs, no telemetry.** All processing is local. This is not negotiable.
2. **Safe by default.** Mutations require explicit opt-in. Preview before persist.
3. **Data belongs to the user.** Plain files (CSV, YAML, SQLite) in user-controlled directories. No proprietary formats.
4. **Complexity must earn its place.** Every feature must justify itself against the cost of understanding it. Simplicity is a feature.
5. **Real financial data never appears in the codebase.** Tests, examples, and documentation use only synthetic data.
