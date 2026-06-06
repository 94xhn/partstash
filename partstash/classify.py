"""Domain classification (electronic vs mechanical vs unknown) and inventory search.

The classifier is deliberately simple and transparent: keyword hit-counting plus a
heuristic that recognises alphanumeric part-number strings as a strong electronic
signal. Every rule is overridable by the user via the dashboard sidebar.
"""

from __future__ import annotations

import re

import pandas as pd

from partstash.core import normalize_search_text

# Default keyword sets. The dashboard lets the user edit these at runtime.
DEFAULT_ELECTRONIC_KEYWORDS = (
    "电阻,电容,电感,二极管,三极管,MOS,IGBT,运放,芯片,IC,MCU,单片机,"
    "STM32,ESP32,继电器,晶振,连接器,排针,传感器,PCB,FPC,模块,电源,稳压"
)
DEFAULT_MECHANICAL_KEYWORDS = (
    "轴承,齿轮,螺丝,螺母,螺栓,弹簧,联轴器,导轨,滑块,支架,外壳,机箱,电机,"
    "减速机,气缸,皮带,同步轮,铝型材,钣金,密封圈,O型圈"
)

# Coarse part-type labels used to enrich search (so a query for "电阻" also matches
# rows whose name only contains "0603WAF...").
TYPE_ALIASES: dict[str, list[str]] = {
    "二极管": ["二极管", "1n4148", "1n4007", "肖特基", "齐纳", "稳压管", "tvs", "ss14", "led"],
    "电阻": ["电阻", "resistor", "rmf", "mfr", "r0", "r010", "0603waf", "0805w8f"],
    "电容": ["电容", "cap", "uf", "nf", "pf", "瓷片", "钽电容", "铝电解"],
    "电感": ["电感", "inductor", "uh", "mh", "功率电感"],
    "运放": ["运放", "opamp", "tl07", "lm358", "ne5532"],
    "连接器": ["连接器", "排针", "插座", "type-c", "usb", "xhb", "ph2.0", "bnc"],
}


def infer_type_label(name: str, model: str, key: str) -> str:
    """Return the first matching coarse part-type label, or ``"未标注"``."""
    blob = normalize_search_text(f"{name} {model} {key}")
    for label, words in TYPE_ALIASES.items():
        for w in words:
            if normalize_search_text(w) in blob:
                return label
    return "未标注"


def query_expand(query: str) -> list[str]:
    """Expand a query into itself plus any aliases of a type it names.

    Searching ``"电阻"`` expands to all resistor aliases so part-number-only rows
    still match. A query that isn't a known type expands to just itself.
    """
    qn = normalize_search_text(query)
    words = {qn}
    for label, aliases in TYPE_ALIASES.items():
        all_norm = [normalize_search_text(x) for x in [label, *aliases]]
        if qn in all_norm:
            words.update(all_norm)
    return sorted(words)


def part_number_score(name: str, model: str, category: str) -> int:
    """Score how 'part-number-like' the text is.

    Alphanumeric tokens of length >= 6 that mix letters and digits (e.g.
    ``SN74LS138DR``) are a strong signal of an electronic component. Three or more
    such tokens earns a bonus.
    """
    text = f"{name} {model} {category}".upper()
    tokens = re.findall(r"[A-Z0-9][A-Z0-9\-_/\[\]]{5,}", text)
    score = 0
    for token in tokens:
        has_letter = bool(re.search(r"[A-Z]", token))
        has_digit = bool(re.search(r"\d", token))
        if has_letter and has_digit:
            score += 1
    if score >= 3:
        score += 2
    return score


def infer_domain(
    name: str,
    model: str,
    category: str,
    elec_keywords: list[str],
    mech_keywords: list[str],
) -> str:
    """Classify a part as ``"电子"``, ``"机械"`` or ``"未确定"``.

    Electronic score = electronic keyword hits + :func:`part_number_score`.
    Mechanical score = mechanical keyword hits. The higher (and positive) score wins;
    ties or two zeros yield ``"未确定"``.
    """
    source = f"{name} {model} {category}".lower()
    elec_score = sum(1 for kw in elec_keywords if kw in source)
    mech_score = sum(1 for kw in mech_keywords if kw in source)
    elec_score += part_number_score(name, model, category)
    if elec_score > mech_score and elec_score > 0:
        return "电子"
    if mech_score > elec_score and mech_score > 0:
        return "机械"
    return "未确定"


def search_inventory(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Filter an inventory frame by a free-text query, sorted by stock descending.

    Matching is alias-expanded (see :func:`query_expand`) and runs over a normalised
    blob of name + model + key + category + domain + inferred type. An empty query
    returns the frame unchanged.
    """
    if not query.strip() or df.empty:
        return df

    qset = set(query_expand(query))
    idx = df.copy()
    idx["器件类型"] = idx.apply(
        lambda r: infer_type_label(str(r["名称"]), str(r["型号"]), str(r["元器件键"])),
        axis=1,
    )
    idx["检索串"] = idx.apply(
        lambda r: normalize_search_text(
            f"{r['名称']} {r['型号']} {r['元器件键']} {r['分类']} {r['领域']} {r['器件类型']}"
        ),
        axis=1,
    )
    hit = idx[idx["检索串"].apply(lambda s: any(w in s for w in qset))].copy()
    return hit.sort_values("库存数量", ascending=False)
