"""Tests for the pure data transforms in :mod:`partstash.core`."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from partstash.core import (
    STORE_COLUMNS,
    build_inventory_from_purchases,
    check_bom_against_store,
    clean_text,
    ensure_store_schema,
    extract_item_table,
    infer_column,
    low_stock,
    normalize_col,
    parse_keywords,
    parse_number,
)


class TestParseNumber:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (12, 12.0),
            (3.5, 3.5),
            ("100", 100.0),
            ("￥12.50", 12.50),
            ("3,000 pcs", 3000.0),
            ("-7", -7.0),
            ("数量：42 个", 42.0),
            ("", 0.0),
            ("no number here", 0.0),
            (None, 0.0),
            (np.nan, 0.0),
        ],
    )
    def test_parses_messy_cells(self, value, expected):
        assert parse_number(value) == expected


class TestTextHelpers:
    def test_normalize_col_strips_and_lowers(self):
        assert normalize_col("  Order  ID ") == "orderid"

    def test_clean_text_handles_nan(self):
        assert clean_text(np.nan) == ""
        assert clean_text("  hi ") == "hi"

    def test_parse_keywords_splits_dedupes_sorts(self):
        # De-duplicated and sorted by Unicode code point: 容(5BB9) < 感(611F) < 阻(963B).
        assert parse_keywords("电阻, 电容，电阻\n电感") == ["电容", "电感", "电阻"]

    def test_parse_keywords_empty(self):
        assert parse_keywords("") == []


class TestInferColumn:
    def test_prefers_product_name_over_id(self):
        cols = ["商品编号", "商品名称", "订购数量", "单价"]
        assert infer_column(cols, "name") == "商品名称"

    def test_quantity_not_confused_with_price(self):
        cols = ["商品名称", "订购数量", "金额"]
        assert infer_column(cols, "qty") == "订购数量"

    def test_price_prefers_unit_price(self):
        cols = ["商品名称", "数量", "单价", "总金额"]
        assert infer_column(cols, "price") == "单价"

    def test_returns_none_when_no_match(self):
        assert infer_column(["foo", "bar"], "vendor") is None

    def test_empty_columns(self):
        assert infer_column([], "name") is None


class TestExtractItemTable:
    def test_extracts_table_below_metadata(self):
        raw = pd.DataFrame(
            [
                ["订单信息", "", ""],
                ["商品编号", "商品名称", "订购数量"],
                ["1", "10k 电阻", "100"],
                ["2", "100nF 电容", "50"],
            ]
        )
        out = extract_item_table(raw)
        assert list(out.columns) == ["商品编号", "商品名称", "订购数量"]
        assert len(out) == 2
        assert out.iloc[0]["商品名称"] == "10k 电阻"

    def test_returns_empty_when_no_header(self):
        raw = pd.DataFrame([["random", "data"], ["1", "2"]])
        assert extract_item_table(raw).empty


class TestEnsureStoreSchema:
    def test_adds_missing_columns_and_computes_value(self):
        df = pd.DataFrame({"元器件键": ["a"], "库存数量": ["10"], "单件估价": ["2.5"]})
        out = ensure_store_schema(df)
        assert list(out.columns) == STORE_COLUMNS
        assert out.iloc[0]["估算金额"] == pytest.approx(25.0)

    def test_drops_rows_without_key(self):
        df = pd.DataFrame({"元器件键": ["a", ""], "库存数量": [1, 2]})
        out = ensure_store_schema(df)
        assert len(out) == 1

    def test_empty_domain_becomes_undetermined(self):
        df = pd.DataFrame({"元器件键": ["a"], "领域": [""]})
        assert ensure_store_schema(df).iloc[0]["领域"] == "未确定"

    def test_negative_quantity_floored(self):
        df = pd.DataFrame({"元器件键": ["a"], "库存数量": [-5]})
        assert ensure_store_schema(df).iloc[0]["库存数量"] == 0


class TestBuildInventoryFromPurchases:
    def _raw(self):
        return pd.DataFrame(
            {
                "名称": ["10k 电阻", "10k 电阻", "钢制轴承 608"],
                "型号": ["0603WAF1002T5E", "0603WAF1002T5E", "608ZZ"],
                "数量": [100, 50, 10],
                "单价": [0.01, 0.01, 2.0],
                "_source_file": ["lcsc.xlsx", "lcsc.xlsx", "taobao.xls"],
            }
        )

    def _mapping(self):
        return {"name": "名称", "model": "型号", "qty": "数量", "price": "单价"}

    def test_aggregates_same_part(self):
        out = build_inventory_from_purchases(
            self._raw(), self._mapping(), ["电阻"], ["轴承"]
        )
        resistor = out[out["名称"] == "10k 电阻"].iloc[0]
        assert resistor["库存数量"] == 150
        # 150 units, total cost 1.5 -> unit price 0.01
        assert resistor["单件估价"] == pytest.approx(0.01)
        assert resistor["领域"] == "电子"

    def test_classifies_mechanical(self):
        out = build_inventory_from_purchases(
            self._raw(), self._mapping(), ["电阻"], ["轴承"]
        )
        bearing = out[out["名称"].str.contains("轴承")].iloc[0]
        assert bearing["领域"] == "机械"

    def test_force_file_overrides_to_electronic(self):
        out = build_inventory_from_purchases(
            self._raw(), self._mapping(), ["电阻"], ["轴承"], force_files=["taobao.xls"]
        )
        bearing = out[out["名称"].str.contains("轴承")].iloc[0]
        assert bearing["领域"] == "电子"
        assert bearing["识别来源"] == "强制入库"


def _store(rows):
    """Build a minimal store frame from (型号, 名称, 库存数量) tuples."""
    return pd.DataFrame(
        [{"型号": m, "名称": n, "库存数量": q} for m, n, q in rows]
    )


class TestLowStock:
    def test_filters_at_or_below_threshold(self):
        store = _store([("A", "a", 3), ("B", "b", 10), ("C", "c", 5)])
        low = low_stock(store, 5)
        assert list(low["型号"]) == ["A", "C"]  # sorted scarcest first

    def test_empty_store(self):
        assert low_stock(pd.DataFrame(columns=["库存数量"]), 5).empty


class TestCheckBomAgainstStore:
    def _store(self):
        return _store(
            [
                ("0603WAF1002T5E", "10k 电阻", 400),
                ("1N4148WS", "开关二极管", 100),
                ("0603WAF1002T5E", "10k 电阻(另一批)", 50),  # same mpn, second row
            ]
        )

    def test_sufficient_part(self):
        bom = pd.DataFrame({"MPN": ["1N4148WS"], "Qty": [20]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        row = out[out["型号"] == "1N4148WS"].iloc[0]
        assert row["库存数量"] == 100
        assert row["缺口"] == 0
        assert row["状态"] == "充足"

    def test_shortfall_computed(self):
        bom = pd.DataFrame({"MPN": ["1N4148WS"], "Qty": [150]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        row = out.iloc[0]
        assert row["缺口"] == 50
        assert row["状态"] == "缺料"

    def test_stock_summed_across_duplicate_mpn_rows(self):
        bom = pd.DataFrame({"MPN": ["0603WAF1002T5E"], "Qty": [100]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        assert out.iloc[0]["库存数量"] == 450  # 400 + 50

    def test_case_insensitive_match(self):
        bom = pd.DataFrame({"MPN": ["1n4148ws"], "Qty": [10]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        assert out.iloc[0]["库存数量"] == 100

    def test_part_missing_from_store(self):
        bom = pd.DataFrame({"MPN": ["STM32F103C8T6"], "Qty": [5]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        row = out.iloc[0]
        assert row["库存数量"] == 0
        assert row["缺口"] == 5
        assert row["匹配名称"] == "（库存中无此型号）"

    def test_demand_aggregated_per_mpn(self):
        bom = pd.DataFrame({"MPN": ["1N4148WS", "1N4148WS"], "Qty": [30, 40]})
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        assert len(out) == 1
        assert out.iloc[0]["需求数量"] == 70

    def test_no_qty_column_counts_one_per_row(self):
        bom = pd.DataFrame({"MPN": ["1N4148WS", "1N4148WS", "1N4148WS"]})
        out = check_bom_against_store(self._store(), bom, "MPN", qty_col=None)
        assert out.iloc[0]["需求数量"] == 3

    def test_largest_shortfall_sorted_first(self):
        bom = pd.DataFrame(
            {"MPN": ["1N4148WS", "STM32F103C8T6"], "Qty": [150, 999]}
        )
        out = check_bom_against_store(self._store(), bom, "MPN", "Qty")
        assert out.iloc[0]["型号"] == "STM32F103C8T6"  # shortfall 999 > 50
