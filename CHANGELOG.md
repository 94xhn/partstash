# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
