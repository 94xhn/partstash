"""PartStash — Streamlit dashboard.

This module is the presentation layer only: file upload, widgets, tables and charts.
All data logic lives in the import-safe :mod:`partstash` package so it can be tested
without spinning up Streamlit.

Run with::

    streamlit run app.py
"""

from __future__ import annotations

import sys
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from partstash.classify import (
    DEFAULT_ELECTRONIC_KEYWORDS,
    DEFAULT_MECHANICAL_KEYWORDS,
    search_inventory,
)
from partstash.core import (
    build_inventory_from_purchases,
    check_bom_against_store,
    ensure_store_schema,
    extract_item_table,
    infer_column,
    low_stock,
    now_text,
    parse_keywords,
    parse_number,
)
from partstash.store import default_store_path, load_store, save_store, upsert_store

st.set_page_config(page_title="PartStash 元器件库存看板", page_icon="📦", layout="wide")

STORE_PATH = default_store_path()


@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read a purchase-order workbook into a flat frame, tagged with its source."""
    filename_lower = filename.lower()
    engine = (
        "xlrd"
        if filename_lower.endswith(".xls") and not filename_lower.endswith(".xlsx")
        else None
    )
    try:
        excel = pd.ExcelFile(BytesIO(file_bytes), engine=engine)
    except ImportError as exc:
        if engine == "xlrd":
            py = sys.executable.replace("\\", "/")
            raise RuntimeError(
                "当前运行环境缺少 xlrd，无法读取 .xls。"
                f"请先执行：`\"{py}\" -m pip install xlrd>=2.0.1`，然后重启程序。"
            ) from exc
        raise

    frames: list[pd.DataFrame] = []
    for sheet in excel.sheet_names:
        raw = excel.parse(sheet_name=sheet, header=None)
        df = extract_item_table(raw)
        if df.empty:
            df = excel.parse(sheet_name=sheet)
        if df is None or df.empty:
            continue
        df = df.copy()
        df["_source_file"] = filename
        df["_source_sheet"] = sheet
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def make_download_xlsx(adjusted: pd.DataFrame, detail: pd.DataFrame) -> bytes:
    """Pack the adjusted summary and the raw detail into a two-sheet workbook."""
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        adjusted.to_excel(writer, sheet_name="调整后汇总", index=False)
        detail.to_excel(writer, sheet_name="原始明细", index=False)
    return bio.getvalue()


def read_bom_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read a BOM upload (CSV or Excel) into a flat frame with a clean header row."""
    name = filename.lower()
    if name.endswith(".csv"):
        for enc in ("utf-8-sig", "gbk", "utf-8"):
            try:
                return pd.read_csv(BytesIO(file_bytes), encoding=enc)
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        return pd.read_csv(BytesIO(file_bytes), encoding="utf-8", engine="python")
    engine = "xlrd" if name.endswith(".xls") and not name.endswith(".xlsx") else None
    return pd.read_excel(BytesIO(file_bytes), engine=engine)


# --------------------------------------------------------------------------- #
# Persisted store section
# --------------------------------------------------------------------------- #
st.title("PartStash · 元器件库存可视化看板")
st.caption(f"支持淘宝/嘉立创采购记录 xls/xlsx。库存库持久化文件：{STORE_PATH}")

stored_df = load_store(STORE_PATH)
st.subheader("库存库（持久化）")
if stored_df.empty:
    st.info("当前库存库为空。导入采购单后点击“写入库存库”，下次打开不会丢失。")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("库存库总数量", f"{stored_df['库存数量'].sum():,.0f}")
    c2.metric("库存库种类", f"{stored_df['元器件键'].nunique():,}")
    c3.metric("库存库估算金额", f"¥ {stored_df['估算金额'].sum():,.2f}")

    st.markdown("### 采购前查询")
    q = st.text_input("输入要找的元器件（名称/型号/关键词）", value="", key="store_query").strip()
    if q:
        hit = search_inventory(stored_df, q)
        if hit.empty:
            st.error("未找到匹配元器件：建议采购。")
        else:
            st.success(f"已找到 {len(hit)} 条匹配：可先从现有库存中查找。")
            st.dataframe(
                hit[["元器件键", "名称", "型号", "器件类型", "分类", "领域", "库存数量", "更新时间"]],
                use_container_width=True,
                hide_index=True,
            )

store_edit_cols = [
    "元器件键", "名称", "型号", "分类", "领域",
    "库存数量", "单件估价", "估算金额", "识别来源", "更新时间",
]
store_editor = st.data_editor(
    stored_df[store_edit_cols].copy(),
    key="store_editor",
    use_container_width=True,
    hide_index=True,
    column_config={
        "库存数量": st.column_config.NumberColumn("库存数量", min_value=0.0, step=1.0, format="%.0f"),
        "单件估价": st.column_config.NumberColumn("单件估价", min_value=0.0, format="%.4f"),
        "领域": st.column_config.SelectboxColumn("领域", options=["电子", "机械", "未确定"]),
    },
    disabled=["元器件键", "名称", "型号", "分类", "估算金额", "识别来源", "更新时间"],
)

left_btn, right_btn = st.columns(2)
if left_btn.button("保存库存库修改", type="primary"):
    to_save = store_editor.copy()
    to_save["库存数量"] = to_save["库存数量"].map(parse_number).clip(lower=0)
    to_save["单件估价"] = to_save["单件估价"].map(parse_number).clip(lower=0)
    to_save["估算金额"] = to_save["库存数量"] * to_save["单件估价"]
    to_save["更新时间"] = now_text()
    save_store(to_save, STORE_PATH)
    st.success("库存库已保存到本地磁盘。")

if right_btn.button("导出库存库.xlsx"):
    out = ensure_store_schema(store_editor)
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        out.to_excel(writer, sheet_name="库存库", index=False)
    st.download_button(
        label="点击下载库存库文件",
        data=bio.getvalue(),
        file_name="inventory_store.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_store_xlsx",
    )

# --------------------------------------------------------------------------- #
# Low-stock alert
# --------------------------------------------------------------------------- #
if not stored_df.empty:
    st.divider()
    st.subheader("📉 库存低位预警")
    threshold = st.number_input(
        "库存数量阈值（≤ 该值视为偏低）",
        min_value=0.0, value=10.0, step=1.0, key="low_stock_threshold",
    )
    low = low_stock(stored_df, threshold)
    if low.empty:
        st.success(f"没有库存 ≤ {threshold:.0f} 的元器件。")
    else:
        st.warning(f"有 {len(low)} 种元器件库存 ≤ {threshold:.0f}，建议补货。")
        st.dataframe(
            low[["元器件键", "名称", "型号", "分类", "领域", "库存数量", "更新时间"]],
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            "下载低库存清单.csv",
            data=low.to_csv(index=False).encode("utf-8-sig"),
            file_name="low_stock.csv", mime="text/csv", key="dl_low_stock",
        )

# --------------------------------------------------------------------------- #
# BOM shortfall check
# --------------------------------------------------------------------------- #
st.divider()
st.subheader("🧾 BOM 缺口检查")
st.caption("上传 KiCad / CSV 的 BOM，对比库存库，看哪些料不够、还差几个。")
bom_file = st.file_uploader(
    "上传 BOM 文件（.csv / .xls / .xlsx）", type=["csv", "xls", "xlsx"], key="bom_upload"
)
if bom_file is not None:
    try:
        bom_df = read_bom_file(bom_file.read(), bom_file.name)
    except Exception as exc:  # noqa: BLE001 - surface any parse error to the user
        st.error(f"读取 BOM 失败：{exc}")
        bom_df = pd.DataFrame()

    if bom_df.empty:
        st.error("BOM 没有读到数据。")
    else:
        bom_cols = list(bom_df.columns)
        guess_mpn = infer_column(bom_cols, "model")
        guess_qty = infer_column(bom_cols, "qty")
        cc1, cc2 = st.columns(2)
        mpn_col = cc1.selectbox(
            "型号 / MPN 列", options=bom_cols,
            index=bom_cols.index(guess_mpn) if guess_mpn in bom_cols else 0,
            key="bom_mpn_col",
        )
        qty_options = ["（每行按 1 件）"] + bom_cols
        qty_default = bom_cols.index(guess_qty) + 1 if guess_qty in bom_cols else 0
        qty_pick = cc2.selectbox("数量列", options=qty_options, index=qty_default, key="bom_qty_col")
        qty_col = None if qty_pick == "（每行按 1 件）" else qty_pick

        result = check_bom_against_store(stored_df, bom_df, mpn_col, qty_col)
        short = result[result["状态"] == "缺料"]

        m1, m2, m3 = st.columns(3)
        m1.metric("BOM 物料种类", f"{len(result):,}")
        m2.metric("缺料种类", f"{len(short):,}")
        m3.metric("总缺口数量", f"{short['缺口'].sum():,.0f}")
        if short.empty:
            st.success("库存可满足整张 BOM。")
        else:
            st.warning(f"有 {len(short)} 种料不足，下单前请补齐。")
        st.dataframe(result, use_container_width=True, hide_index=True)
        st.download_button(
            "下载缺口清单.csv",
            data=short.to_csv(index=False).encode("utf-8-sig"),
            file_name="bom_shortfall.csv", mime="text/csv", key="dl_bom_short",
        )

# --------------------------------------------------------------------------- #
# Import purchases section
# --------------------------------------------------------------------------- #
st.divider()
st.subheader("导入采购单并入库")

uploads = st.file_uploader(
    "上传一个或多个 .xls/.xlsx 文件（可选）",
    type=["xls", "xlsx"],
    accept_multiple_files=True,
)

if not uploads:
    st.stop()

uploaded_names = sorted({f.name for f in uploads})
force_include_mode = st.checkbox("启用“所选文件强制全量入库（跳过识别）”", value=False)
force_include_files: list[str] = []
if force_include_mode:
    force_include_files = st.multiselect(
        "选择要强制入库的 .xls/.xlsx 文件",
        options=uploaded_names,
        default=[],
        help="选中的文件会将所有商品直接纳入元器件库，不走电子/机械判断逻辑。",
    )

raw_frames: list[pd.DataFrame] = []
for f in uploads:
    try:
        raw = load_excel(f.read(), f.name)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()
    if not raw.empty:
        raw_frames.append(raw)

if not raw_frames:
    st.error("没有读取到有效数据，请检查文件是否包含表格数据。")
    st.stop()

raw_df = pd.concat(raw_frames, ignore_index=True)
all_cols = list(raw_df.columns)

with st.sidebar:
    st.subheader("字段映射")
    default_name = infer_column(all_cols, "name")
    default_model = infer_column(all_cols, "model")
    default_qty = infer_column(all_cols, "qty")
    default_category = infer_column(all_cols, "category")
    default_price = infer_column(all_cols, "price")
    default_vendor = infer_column(all_cols, "vendor")

    name_col = st.selectbox(
        "名称列", options=all_cols,
        index=all_cols.index(default_name) if default_name in all_cols else 0,
    )
    model_col = st.selectbox(
        "型号列（可选）", options=[""] + all_cols,
        index=([""] + all_cols).index(default_model) if default_model in all_cols else 0,
    )
    qty_col = st.selectbox(
        "数量列", options=all_cols,
        index=all_cols.index(default_qty) if default_qty in all_cols else 0,
    )
    category_col = st.selectbox(
        "分类列（可选）", options=[""] + all_cols,
        index=([""] + all_cols).index(default_category) if default_category in all_cols else 0,
    )
    price_col = st.selectbox(
        "单价/金额列（可选）", options=[""] + all_cols,
        index=([""] + all_cols).index(default_price) if default_price in all_cols else 0,
    )
    vendor_col = st.selectbox(
        "供应商列（可选）", options=[""] + all_cols,
        index=([""] + all_cols).index(default_vendor) if default_vendor in all_cols else 0,
    )

    st.subheader("电子/机械识别规则")
    elec_text = st.text_area("电子关键词（逗号分隔）", value=DEFAULT_ELECTRONIC_KEYWORDS, height=110)
    mech_text = st.text_area("机械关键词（逗号分隔）", value=DEFAULT_MECHANICAL_KEYWORDS, height=110)

    st.subheader("过滤设置")
    exclude_unknown = st.checkbox("剔除非电子/机械（未确定）", value=True)

elec_keywords = parse_keywords(elec_text)
mech_keywords = parse_keywords(mech_text)

mapping = {
    "name": name_col,
    "model": model_col,
    "qty": qty_col,
    "category": category_col,
    "price": price_col,
    "vendor": vendor_col,
}
agg = build_inventory_from_purchases(
    raw_df, mapping, elec_keywords, mech_keywords, force_files=force_include_files
)

st.subheader("库存调整")
st.caption("可直接修改 `库存数量` 和 `领域`，用于记录当前手头实际库存。")
edited = st.data_editor(
    agg.copy(),
    key="inventory_editor",
    use_container_width=True,
    hide_index=True,
    column_config={
        "库存数量": st.column_config.NumberColumn("库存数量", min_value=0.0, step=1.0, format="%.0f"),
        "单件估价": st.column_config.NumberColumn("单件估价", min_value=0.0, format="%.4f"),
        "领域": st.column_config.SelectboxColumn("领域", options=["电子", "机械", "未确定"]),
    },
    disabled=["元器件键", "名称", "型号", "分类", "识别来源", "自动领域"],
)

adjusted = edited.copy()
adjusted["库存数量"] = adjusted["库存数量"].map(parse_number).clip(lower=0)
adjusted["单件估价"] = adjusted["单件估价"].map(parse_number).clip(lower=0)
adjusted["估算金额"] = adjusted["库存数量"] * adjusted["单件估价"]
adjusted = adjusted.sort_values("库存数量", ascending=False)

unknown_count = int((adjusted["领域"] == "未确定").sum())
if exclude_unknown:
    adjusted_view = adjusted[adjusted["领域"].isin(["电子", "机械"])].copy()
else:
    adjusted_view = adjusted.copy()

if exclude_unknown and unknown_count > 0:
    st.warning(f"已剔除 {unknown_count} 条“未确定”商品（非电子/机械）。")
if force_include_mode and force_include_files:
    st.info(f"已启用强制入库文件：{', '.join(force_include_files)}")

if st.button("将当前结果写入库存库（持久化）", type="primary"):
    incoming = adjusted_view.copy()
    incoming["更新时间"] = now_text()
    incoming = incoming[
        ["元器件键", "名称", "型号", "分类", "领域",
         "库存数量", "单件估价", "估算金额", "识别来源", "更新时间"]
    ]
    new_store = upsert_store(load_store(STORE_PATH), incoming)
    save_store(new_store, STORE_PATH)
    st.success(f"已写入库存库：{len(incoming)} 条。下次打开程序仍会保留。")

# --------------------------------------------------------------------------- #
# Metrics and charts
# --------------------------------------------------------------------------- #
total_qty = float(adjusted_view["库存数量"].sum()) if not adjusted_view.empty else 0.0
total_types = int(adjusted_view["元器件键"].nunique()) if not adjusted_view.empty else 0
total_value = float(adjusted_view["估算金额"].sum()) if not adjusted_view.empty else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("当前库存总数量", f"{total_qty:,.0f}")
c2.metric("元器件种类", f"{total_types:,}")
c3.metric("采购明细行数", f"{len(raw_df):,}")
c4.metric("当前估算总金额", f"¥ {total_value:,.2f}")

left, right = st.columns([1.3, 1])
with left:
    st.subheader("Top 20 元器件（按当前库存）")
    top_n = adjusted_view.head(20).copy()
    fig_bar = px.bar(top_n, x="库存数量", y="元器件键", color="领域", orientation="h")
    fig_bar.update_layout(height=620, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_bar, use_container_width=True)

with right:
    st.subheader("领域占比")
    by_domain = (
        adjusted_view.groupby("领域", as_index=False)["库存数量"]
        .sum()
        .sort_values("库存数量", ascending=False)
    )
    fig_pie = px.pie(by_domain, names="领域", values="库存数量", hole=0.4)
    fig_pie.update_layout(height=620)
    st.plotly_chart(fig_pie, use_container_width=True)

st.subheader("明细筛选")
key = st.text_input("按名称/型号/供应商搜索", value="").strip()
min_qty = st.number_input("最小库存数量", min_value=0.0, value=0.0, step=1.0)
domain_default = ["电子", "机械"] if exclude_unknown else ["电子", "机械", "未确定"]
domain_pick = st.multiselect("按领域筛选", options=["电子", "机械", "未确定"], default=domain_default)

filtered = adjusted_view[adjusted_view["库存数量"] >= min_qty].copy()
if domain_pick:
    filtered = filtered[filtered["领域"].isin(domain_pick)]
if key:
    filtered = filtered[
        filtered["名称"].str.contains(key, case=False, na=False)
        | filtered["型号"].str.contains(key, case=False, na=False)
        | filtered["元器件键"].str.contains(key, case=False, na=False)
    ]

st.dataframe(filtered, use_container_width=True, hide_index=True)

st.download_button(
    label="下载当前结果（调整后汇总+原始明细）.xlsx",
    data=make_download_xlsx(filtered, raw_df),
    file_name="partstash_result.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
