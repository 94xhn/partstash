"""Tests for :mod:`partstash.classify`."""

from __future__ import annotations

import pandas as pd

from partstash.classify import (
    infer_domain,
    infer_type_label,
    part_number_score,
    query_expand,
    search_inventory,
)

ELEC = ["电阻", "电容", "芯片", "ic", "stm32"]
MECH = ["轴承", "齿轮", "螺丝", "螺母"]


class TestInferTypeLabel:
    def test_recognises_resistor_by_partnumber(self):
        assert infer_type_label("贴片电阻", "0603WAF1002T5E", "key") == "电阻"

    def test_recognises_diode(self):
        assert infer_type_label("开关二极管", "1N4148", "k") == "二极管"

    def test_unlabelled(self):
        assert infer_type_label("神秘物件", "XYZ", "k") == "未标注"


class TestQueryExpand:
    def test_expands_known_type(self):
        words = query_expand("电阻")
        assert "电阻" in words
        assert "0603waf" in words  # alias pulled in

    def test_unknown_query_is_itself(self):
        assert query_expand("stm32f103") == ["stm32f103"]


class TestPartNumberScore:
    def test_alphanumeric_tokens_score(self):
        assert part_number_score("", "SN74LS138DR", "") >= 1

    def test_three_tokens_get_bonus(self):
        score = part_number_score("AO3400 SI2302 MMBT5401S", "", "")
        assert score >= 5  # 3 tokens + bonus

    def test_plain_words_score_zero(self):
        assert part_number_score("螺丝", "钢", "五金") == 0


class TestInferDomain:
    def test_electronic_by_keyword(self):
        assert infer_domain("贴片电阻", "", "", ELEC, MECH) == "电子"

    def test_mechanical_by_keyword(self):
        assert infer_domain("不锈钢螺丝", "M3", "五金", ELEC, MECH) == "机械"

    def test_electronic_by_partnumber_when_no_keyword(self):
        # No keyword hit, but a strong part-number string -> electronic.
        assert infer_domain("模块", "ESP32-WROOM-32E", "", ELEC, MECH) == "电子"

    def test_undetermined_when_no_signal(self):
        assert infer_domain("不明物体", "", "", ELEC, MECH) == "未确定"


class TestSearchInventory:
    def _df(self):
        return pd.DataFrame(
            {
                "元器件键": ["10k 电阻 | R1", "608 轴承 | B1"],
                "名称": ["10k 贴片电阻", "608 轴承"],
                "型号": ["0603WAF1002T5E", "608ZZ"],
                "分类": ["电阻", "轴承"],
                "领域": ["电子", "机械"],
                "库存数量": [100, 5],
            }
        )

    def test_finds_by_alias_expansion(self):
        hit = search_inventory(self._df(), "电阻")
        assert len(hit) == 1
        assert hit.iloc[0]["名称"] == "10k 贴片电阻"

    def test_empty_query_returns_all(self):
        df = self._df()
        assert len(search_inventory(df, "")) == len(df)

    def test_no_match_returns_empty(self):
        assert search_inventory(self._df(), "继电器").empty
