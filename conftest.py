"""Ensure the repository root is importable when running the test suite directly.

A flat-layout project means ``import partstash`` only works if the repo root is on
``sys.path``. pytest prepends the directory containing the top-level ``conftest.py``,
so this file's mere existence makes the import work without an editable install.
"""
