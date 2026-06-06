"""Tests for :mod:`partstash.store` (CSV persistence and upsert)."""

from __future__ import annotations

import pandas as pd

from partstash.core import STORE_COLUMNS
from partstash.store import default_store_path, load_store, save_store, upsert_store


def _row(key, qty, price=1.0, name="part", domain="电子"):
    return {
        "元器件键": key,
        "名称": name,
        "型号": "M",
        "分类": "未分类",
        "领域": domain,
        "库存数量": qty,
        "单件估价": price,
        "估算金额": qty * price,
        "识别来源": "规则识别",
        "更新时间": "2026-01-01 00:00:00",
    }


class TestRoundTrip:
    def test_save_then_load_is_stable(self, tmp_path):
        path = tmp_path / "store.csv"
        df = pd.DataFrame([_row("a | 1", 10), _row("b | 2", 5)])
        save_store(df, path)
        loaded = load_store(path)
        assert set(loaded["元器件键"]) == {"a | 1", "b | 2"}
        assert list(loaded.columns) == STORE_COLUMNS

    def test_load_missing_returns_empty_schema(self, tmp_path):
        loaded = load_store(tmp_path / "nope.csv")
        assert loaded.empty
        assert list(loaded.columns) == STORE_COLUMNS

    def test_save_sorts_by_quantity_desc(self, tmp_path):
        path = tmp_path / "store.csv"
        save_store(pd.DataFrame([_row("low", 1), _row("high", 99)]), path)
        loaded = load_store(path)
        assert loaded.iloc[0]["元器件键"] == "high"


class TestUpsert:
    def test_new_keys_are_appended(self):
        existing = pd.DataFrame([_row("a", 10)])
        incoming = pd.DataFrame([_row("b", 5)])
        merged = upsert_store(existing, incoming)
        assert set(merged["元器件键"]) == {"a", "b"}

    def test_existing_key_is_replaced_by_incoming(self):
        existing = pd.DataFrame([_row("a", 10)])
        incoming = pd.DataFrame([_row("a", 999)])
        merged = upsert_store(existing, incoming)
        assert len(merged) == 1
        assert merged.iloc[0]["库存数量"] == 999

    def test_upsert_into_empty(self):
        merged = upsert_store(pd.DataFrame(), pd.DataFrame([_row("a", 1)]))
        assert len(merged) == 1


class TestDefaultStorePath:
    def test_env_override(self, monkeypatch, tmp_path):
        target = tmp_path / "custom.csv"
        monkeypatch.setenv("COMPONENTS_STORE_PATH", str(target))
        assert default_store_path() == target
