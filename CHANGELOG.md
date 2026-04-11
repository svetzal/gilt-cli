# Changelog

All notable changes to this project will be documented in this file.

## [0.5.1] - 2026-04-11

### Changed
- Extract file I/O from EventMigrationService, isolating pure business logic from filesystem dependencies
- Extract budget reporting logic to dedicated BudgetReportingService with dataclass models
- Remove category logic duplication in GUI service layer by delegating to CategoryManagementService
- Link CHARTER.md in AGENTS.md for agent clarity on project purpose and constraints

### Tests
- Add ~190 comprehensive tests across transfer linking, GUI services, ledger I/O, budget, duplicate detection, and event sourcing modules

### Dependencies
- Update ruff, openai, anthropic, PySide6, anyio, mkdocs-material, and transitive dependencies to latest patches

## [0.5.0] - 2026-03-17

### Added
- Skill distribution infrastructure (`gilt skill-init` command)
- Rule-inference engine for automatic transaction categorization
- Receipt matching and disambiguation in GUI
- Interactive disambiguation for receipt ingestion
- Progress indicator for background intelligence scan
- `reingest` command, detail panel enhancements, and selection stability
- `amount_sign` import hint to support reversed debit/credit

### Changed
- Switch GUI transaction loading to projections database
- Sync projections DB after categorization so view reflects changes
- Centralize default Ollama model to `DEFAULT_OLLAMA_MODEL` constant
- Improve detail panel layout and preserve sort order across reloads
- Expand ruff lint rules with Bugbear, McCabe, isort, Simplify, and pyupgrade
- Reduce McCabe complexity (C901) across 19 functions and enforce max-complexity 12

### Fixed
- GUI crash bugs: sync projections after mutations and clean up worker threads

### Dependencies
- Numerous dependency updates (mojentic, ruff, openai, anthropic, scipy, typer, rich, and others)

## [0.3.5] and earlier

See git history for previous changes.
