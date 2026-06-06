# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-07

### Added
- **Low-stock alert** — set a quantity threshold and see every part at or below it,
  with a downloadable shortlist (`partstash.core.low_stock`).
- **BOM shortfall check** — upload a KiCad / CSV BOM and compare it against the
  inventory store; reports per-part demand, stock, shortfall and status, summed
  across duplicate part-number rows and case-insensitive on the MPN
  (`partstash.core.check_bom_against_store`). Exports a shortfall CSV.
- Tests for both new functions (suite now at 61 tests).

## [0.1.0] - 2026-06-07

First public release.

### Added
- Streamlit dashboard for importing Taobao / JLCPCB purchase orders.
- Automatic column mapping for name / model / quantity / category / price / vendor.
- Electronic vs mechanical classification with editable keyword rules and an
  alphanumeric part-number heuristic.
- Persistent CSV inventory store with upsert-on-import and in-place editing.
- Alias-aware pre-purchase search.
- Top-20 stock chart, domain breakdown chart, and live totals.
- Excel export of the adjusted summary plus raw detail.
- PyInstaller packaging for a standalone Windows executable.

### Changed
- Refactored the original single-file `app.py` into an import-safe `partstash`
  package (`core`, `classify`, `store`) with a dedicated `pytest` suite, leaving
  `app.py` as a thin UI layer.
