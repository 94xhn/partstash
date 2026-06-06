# PartStash 📦

> Turn the messy `.xls` / `.xlsx` purchase orders you get from Taobao and JLCPCB
> (嘉立创) into a clean, searchable electronic-component inventory — so before you
> buy *another* reel of 10 kΩ resistors, you can check whether you already have 400
> of them in a drawer.

PartStash is a small, local-first [Streamlit](https://streamlit.io) dashboard. It
imports your order history, auto-detects the columns, classifies each line as an
**electronic** or **mechanical** part, persists everything to a single CSV, and
gives you charts, search, and a "do I already own this?" lookup.

[简体中文说明见下方](#中文说明) ·  Licensed under [MIT](LICENSE).

---

## Why

If you build hardware as a hobby or for coursework, your parts come from a dozen
Taobao shops and the occasional JLCPCB order. Each gives you a differently-shaped
spreadsheet. After a year you have no idea what you own. PartStash answers three
questions fast:

- **What do I have, and how much?** — totals, per-domain breakdown, top-20 chart.
- **Do I already own this part?** — alias-aware search (`电阻` also matches
  `0603WAF...`) before you place an order.
- **What's it worth?** — estimated value from per-unit prices.

## Features

- 📥 **Imports Taobao / JLCPCB exports** (`.xls` and `.xlsx`), multiple files at once.
- 🧭 **Auto column mapping** — guesses name / model / quantity / category / price /
  vendor columns, with manual override in the sidebar.
- 🏷️ **Electronic vs mechanical classification** by editable keyword rules, plus a
  part-number heuristic (e.g. `SN74LS138DR` reads as electronic).
- 💾 **Persistent CSV store** — merge new orders into your long-term inventory
  (upsert keyed on the part), edit quantities in-place, survives restarts.
- 🔎 **Pre-purchase search** with type-alias expansion.
- 📊 **Charts** — top-20 by stock, domain breakdown, live totals.
- 📤 **Excel export** of the adjusted summary plus the raw detail.
- 🧱 **Zero cloud** — everything runs and stays on your machine.

## Install & run

Requires Python 3.9+.

```bash
git clone https://github.com/94xhn/partstash.git
cd partstash
pip install -r requirements.txt
streamlit run app.py
```

On Windows you can also double-click `run_dashboard.bat`.

The dashboard opens in your browser. Your inventory is stored in
`inventory_store.csv` next to the project (override with the `COMPONENTS_STORE_PATH`
environment variable). A small `examples/sample_inventory.csv` is included so you can
see the format.

## How classification works

The domain of each part is decided by a transparent, fully-overridable rule:

```
electronic score = (# electronic keywords hit) + part_number_score(name, model, category)
mechanical score = (# mechanical keywords hit)
```

The higher positive score wins; a tie (or two zeros) yields **未确定 / undetermined**,
which is filtered out by default. `part_number_score` rewards alphanumeric tokens
that mix letters and digits (the shape of real MPNs). Edit the keyword lists live in
the sidebar, or force specific files in wholesale via "强制全量入库".

## Project layout

```
partstash/            # import-safe package — no Streamlit, fully unit-tested
├── core.py           #   parsing, column inference, table extraction, schema, aggregation
├── classify.py       #   electronic/mechanical classification + search
└── store.py          #   CSV load / save / upsert
app.py                # Streamlit UI — thin presentation layer over the package
tests/                # pytest suite for the package
packaging/            # PyInstaller launcher + spec (build a standalone .exe)
examples/             # sample inventory CSV
```

The data logic is deliberately separated from the UI so it can be tested without
launching Streamlit. Run the suite with:

```bash
pip install -r requirements-dev.txt
pytest
```

## Build a standalone executable (Windows)

```bash
pip install pyinstaller
pyinstaller packaging/ComponentsInventoryApp.spec
```

The bundled `.exe` lands in `dist/`. It keeps its inventory CSV alongside the
executable.

## Roadmap

- Low-stock thresholds and alerts.
- BOM check: upload a KiCad / CSV BOM and see what you're short.
- LCSC / JLCPCB part-number enrichment.
- Storage-location (bin/drawer) tracking.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 中文说明

**PartStash** 是一个本地运行的元器件库存可视化看板。把你从淘宝、嘉立创下载的采购单
（`.xls` / `.xlsx`）导入进来，它会自动识别列、判定每一项是「电子 / 机械」、持久化到一个
CSV 文件，并提供图表、搜索和「我是不是已经有这个料了？」的采购前查询。

### 功能

- 📥 导入淘宝 / 嘉立创采购单（`.xls` `.xlsx`），支持多文件合并
- 🧭 自动识别列名（名称 / 型号 / 数量 / 分类 / 单价 / 供应商），可在侧边栏手动映射
- 🏷️ 关键词规则 + 型号串启发式判定「电子 / 机械 / 未确定」，规则可在页面里实时修改
- 💾 持久化 CSV 库存库，新采购单按「元器件键」增量合并（upsert），可页内改数量
- 🔎 采购前查询（带类型别名扩展，搜「电阻」也能命中 `0603WAF...`）
- 📊 Top20 库存柱状图、领域占比饼图、实时统计
- 📤 一键导出 Excel（调整后汇总 + 原始明细）
- 🧱 纯本地，无需联网

### 安装与运行（Python 3.9+）

```bash
git clone https://github.com/94xhn/partstash.git
cd partstash
pip install -r requirements.txt
streamlit run app.py
```

Windows 也可直接双击 `run_dashboard.bat`。库存默认存到项目目录下的
`inventory_store.csv`（可用环境变量 `COMPONENTS_STORE_PATH` 覆盖）。

### 运行测试

```bash
pip install -r requirements-dev.txt
pytest
```

欢迎贡献，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。本项目以 [MIT](LICENSE) 协议开源。
