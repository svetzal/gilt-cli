# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
