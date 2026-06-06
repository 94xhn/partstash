"""CSV persistence for the long-lived inventory store.

The store is a single UTF-8 (BOM) CSV with the columns defined in
:data:`partstash.core.STORE_COLUMNS`. ``upsert_store`` merges a new batch into the
existing store, keyed on ``元器件键`` (the part key), keeping the latest row.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

from partstash.core import STORE_COLUMNS, ensure_store_schema


def default_store_path() -> Path:
    """Resolve where the inventory CSV lives, in priority order:

    1. ``$COMPONENTS_STORE_PATH`` if set (used by the packaged launcher).
    2. Next to the executable when running as a frozen PyInstaller bundle.
    3. ``inventory_store.csv`` beside this package otherwise.
    """
    env = os.getenv("COMPONENTS_STORE_PATH")
    if env:
        return Path(env).expanduser()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().with_name("inventory_store.csv")
    # partstash/store.py -> repo root -> inventory_store.csv
    return Path(__file__).resolve().parent.parent / "inventory_store.csv"


def load_store(path: str | os.PathLike[str] | None = None) -> pd.DataFrame:
    """Load the inventory store, returning an empty (schema-correct) frame if absent."""
    p = Path(path) if path is not None else default_store_path()
    if not p.exists():
        return pd.DataFrame(columns=STORE_COLUMNS)
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(p, encoding="utf-8")
    return ensure_store_schema(df)


def save_store(df: pd.DataFrame, path: str | os.PathLike[str] | None = None) -> Path:
    """Normalise, sort by stock and write the store as UTF-8-BOM CSV. Returns the path."""
    p = Path(path) if path is not None else default_store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    out = ensure_store_schema(df).sort_values("库存数量", ascending=False)
    out.to_csv(p, index=False, encoding="utf-8-sig")
    return p


def upsert_store(existing: pd.DataFrame, incoming: pd.DataFrame) -> pd.DataFrame:
    """Merge ``incoming`` into ``existing``, keyed on 元器件键, keeping the latest row."""
    if existing is None or existing.empty:
        return ensure_store_schema(incoming)
    if incoming is None or incoming.empty:
        return ensure_store_schema(existing)
    merged = pd.concat(
        [ensure_store_schema(existing), ensure_store_schema(incoming)],
        ignore_index=True,
    )
    merged = merged.drop_duplicates(subset=["元器件键"], keep="last")
    return ensure_store_schema(merged)
