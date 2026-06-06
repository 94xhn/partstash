"""Pure data transforms: parsing, column inference, purchase-table extraction and
the canonical inventory schema. Nothing here touches Streamlit, disk, or global
state, so every function is straightforward to unit-test.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime

import pandas as pd

# Canonical column order of the persisted inventory store. Kept in Chinese to stay
# byte-compatible with the CSV files the original tool already produced.
STORE_COLUMNS = [
    "元器件键",
    "名称",
    "型号",
    "分类",
    "领域",
    "库存数量",
    "单件估价",
    "估算金额",
    "识别来源",
    "更新时间",
]

# Numeric columns that must always be coerced to numbers, not text.
_NUMERIC_STORE_COLUMNS = ("库存数量", "单件估价", "估算金额")

# Hints used as a weak fallback when scoring candidate columns during auto-mapping.
COLUMN_HINTS: dict[str, list[str]] = {
    "name": ["元器件", "物料", "商品", "名称", "品名", "标题"],
    "model": ["型号", "规格", "参数", "料号", "mpn", "封装"],
    "qty": ["数量", "件数", "购买数", "采购数量", "qty", "pcs", "个数"],
    "category": ["分类", "类目", "类别", "品类"],
    "price": ["单价", "成交价", "含税单价", "金额", "总价", "price", "rmb"],
    "vendor": ["店铺", "卖家", "供应商", "商家", "渠道"],
}


def now_text() -> str:
    """Current local time as ``YYYY-MM-DD HH:MM:SS``."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_col(col: str) -> str:
    """Lower-case a column name and strip all whitespace, for fuzzy comparison."""
    return re.sub(r"\s+", "", str(col)).lower()


def normalize_search_text(text: str) -> str:
    """Lower-case and strip whitespace from arbitrary text for substring search."""
    return re.sub(r"\s+", "", str(text)).lower()


def clean_text(val: object) -> str:
    """Return a stripped string, mapping NaN/None to an empty string."""
    if pd.isna(val):
        return ""
    return str(val).strip()


def parse_number(val: object) -> float:
    """Best-effort extraction of a single number from a messy cell.

    Handles ``"￥12.50"``, ``"3,000 pcs"`` and similar. Returns ``0.0`` when no
    number can be found. Never raises.
    """
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    text = str(val)
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return 0.0
    try:
        return float(match.group(0))
    except ValueError:
        return 0.0


def parse_keywords(text: str) -> list[str]:
    """Split a free-form keyword blob (comma / newline / space separated) into a
    sorted, de-duplicated, lower-cased list."""
    parts = re.split(r"[,，;；\n\r\t ]+", text or "")
    out = {p.strip().lower() for p in parts if p.strip()}
    return sorted(out)


def infer_column(columns: Iterable[str], target: str) -> str | None:
    """Guess which column holds ``target`` (one of the :data:`COLUMN_HINTS` keys).

    Returns the best-scoring column name, or ``None`` when nothing scores positively.
    The scoring rules encode hard-won knowledge about Taobao / JLCPCB export headers
    (e.g. an ``订单编号`` column must never be mistaken for the part name).
    """
    cols = list(columns)
    if not cols:
        return None

    def score(col: str) -> int:
        norm = normalize_col(col)
        s = 0
        if target == "name":
            if "商品名称" in col:
                s += 12
            if "名称" in col or "品名" in col:
                s += 10
            if "物料" in col:
                s += 8
            if "商品" in col:
                s += 4
            if ("编号" in col) or ("序号" in col) or ("订单" in col):
                s -= 12
        elif target == "qty":
            if ("订购数量" in col) or ("购买数量" in col):
                s += 12
            if "数量" in col or "qty" in norm:
                s += 9
            if ("金额" in col) or ("单价" in col) or ("价格" in col):
                s -= 10
        elif target == "model":
            if ("厂家型号" in col) or ("规格型号" in col):
                s += 12
            if "型号" in col or "规格" in col or "mpn" in norm:
                s += 8
        elif target == "price":
            if "单价" in col:
                s += 12
            if ("金额" in col) or ("价格" in col) or ("总价" in col):
                s += 8
            if "数量" in col:
                s -= 8
        elif target == "vendor":
            if ("供应商" in col) or ("卖家" in col) or ("店铺" in col):
                s += 10
        elif target == "category":
            if ("分类" in col) or ("类目" in col) or ("品类" in col):
                s += 10

        for hint in COLUMN_HINTS[target]:
            if normalize_col(hint) in norm:
                s += 1
        return s

    best_score, best_col = max(((score(c), c) for c in cols), key=lambda x: x[0])
    return best_col if best_score > 0 else None


def extract_item_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Locate and slice out the real line-item table from a raw, header-less sheet.

    Order/invoice exports usually bury the item table under a few rows of metadata.
    This finds the header row (one containing a product-name, a quantity and an
    id/serial column), promotes it to column names, and keeps only the numbered
    line-item rows. Returns an empty frame when no plausible header is found.
    """
    header_row = None
    for i in range(len(raw)):
        row_vals = [clean_text(v) for v in raw.iloc[i].tolist()]
        row_nonempty = [v for v in row_vals if v]
        if not row_nonempty:
            continue
        joined = " ".join(row_nonempty)
        has_name = "商品名称" in joined
        has_qty = ("订购数量" in joined) or ("数量" in joined)
        has_id = ("商品编号" in joined) or ("序号" in joined)
        if has_name and has_qty and has_id:
            header_row = i
            break

    if header_row is None:
        return pd.DataFrame()

    header_cells = [clean_text(v) for v in raw.iloc[header_row].tolist()]
    keep_cols = [idx for idx, name in enumerate(header_cells) if name]
    if not keep_cols:
        return pd.DataFrame()

    data = raw.iloc[header_row + 1 :, keep_cols].copy()
    data.columns = [header_cells[idx] for idx in keep_cols]
    data = data.dropna(how="all")
    if data.empty:
        return pd.DataFrame()

    first_col = data.columns[0]
    data[first_col] = data[first_col].map(clean_text)
    data = data[
        data[first_col].ne("")
        & ~data[first_col].str.contains("商品明细|订单|收货|发票|信息", na=False)
    ].copy()

    # When the first column is a serial number, keep only genuine numbered rows.
    serial_mask = data[first_col].str.fullmatch(r"\d+")
    if serial_mask.any():
        data = data[serial_mask].copy()

    return data.reset_index(drop=True)


def ensure_store_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary frame into the canonical :data:`STORE_COLUMNS` shape.

    Missing columns are added, numeric columns are parsed and floored at zero, the
    estimated value is recomputed, and rows without a part key are dropped.
    """
    out = df.copy()
    for col in STORE_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0 if col in _NUMERIC_STORE_COLUMNS else ""

    out["库存数量"] = out["库存数量"].map(parse_number).clip(lower=0)
    out["单件估价"] = out["单件估价"].map(parse_number).clip(lower=0)
    out["估算金额"] = out["库存数量"] * out["单件估价"]
    out["元器件键"] = out["元器件键"].astype(str).str.strip()
    out = out[out["元器件键"].ne("")].copy()
    out["名称"] = out["名称"].astype(str).str.strip()
    out["型号"] = out["型号"].astype(str).str.strip()
    out["分类"] = out["分类"].astype(str).str.strip()
    out["领域"] = out["领域"].astype(str).str.strip().replace("", "未确定")
    out["识别来源"] = out["识别来源"].astype(str).str.strip()
    out["更新时间"] = out["更新时间"].astype(str).str.strip()
    return out[STORE_COLUMNS].copy()


def build_inventory_from_purchases(
    raw_df: pd.DataFrame,
    mapping: Mapping[str, str],
    elec_keywords: list[str],
    mech_keywords: list[str],
    force_files: Iterable[str] = (),
) -> pd.DataFrame:
    """Aggregate raw purchase rows into a per-part inventory frame.

    Args:
        raw_df: Concatenated purchase rows. Must contain a ``_source_file`` column
            (used by the force-include rule); ``_source_sheet`` is optional.
        mapping: Column mapping with keys ``name``, ``model``, ``qty``, ``category``,
            ``price``, ``vendor``. Empty strings mean "column not present".
        elec_keywords / mech_keywords: Lower-cased keyword lists driving the
            electronic / mechanical domain classifier.
        force_files: Source file names whose rows are forced into the inventory as
            electronic parts, bypassing the keyword classifier.

    Returns:
        A frame with one row per ``元器件键`` and the columns
        ``元器件键, 名称, 型号, 分类, 识别来源, 自动领域, 领域, 库存数量, 单件估价``.
    """
    # Local import avoids a circular dependency at module load time.
    from partstash.classify import infer_domain

    name_col = mapping.get("name", "")
    model_col = mapping.get("model", "")
    qty_col = mapping.get("qty", "")
    category_col = mapping.get("category", "")
    price_col = mapping.get("price", "")
    vendor_col = mapping.get("vendor", "")

    work = pd.DataFrame()
    work["名称"] = raw_df[name_col].astype(str).str.strip()
    work["型号"] = raw_df[model_col].astype(str).str.strip() if model_col else ""
    work["数量"] = raw_df[qty_col].map(parse_number)
    work["分类"] = raw_df[category_col].astype(str).str.strip() if category_col else "未分类"
    work["单价"] = raw_df[price_col].map(parse_number) if price_col else 0.0
    work["供应商"] = raw_df[vendor_col].astype(str).str.strip() if vendor_col else ""
    work["来源文件"] = raw_df["_source_file"].astype(str) if "_source_file" in raw_df else ""

    force_file_set = set(force_files)
    work["强制入库"] = work["来源文件"].isin(force_file_set)

    work = work[work["名称"].ne("")].copy()
    work["数量"] = work["数量"].clip(lower=0)
    work["元器件键"] = work["名称"] + " | " + work["型号"].replace("", "(无型号)")
    work["行金额"] = work["数量"] * work["单价"]

    agg = (
        work.groupby(["元器件键", "名称", "型号", "分类"], dropna=False, as_index=False)
        .agg(
            库存数量=("数量", "sum"),
            累计金额=("行金额", "sum"),
            强制入库=("强制入库", "max"),
        )
        .sort_values("库存数量", ascending=False)
    )
    agg["自动领域"] = agg.apply(
        lambda row: "电子"
        if bool(row["强制入库"])
        else infer_domain(
            str(row["名称"]), str(row["型号"]), str(row["分类"]), elec_keywords, mech_keywords
        ),
        axis=1,
    )
    agg["识别来源"] = agg["强制入库"].map(lambda v: "强制入库" if bool(v) else "规则识别")
    agg["领域"] = agg["自动领域"]
    agg["单件估价"] = agg.apply(
        lambda row: float(row["累计金额"]) / float(row["库存数量"])
        if float(row["库存数量"]) > 0
        else 0.0,
        axis=1,
    )
    return agg[
        ["元器件键", "名称", "型号", "分类", "识别来源", "自动领域", "领域", "库存数量", "单件估价"]
    ].copy()
