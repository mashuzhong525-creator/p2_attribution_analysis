"""为库存场景库补一张「销售预测」表 sales_forecast，纳入断货归因。

为什么需要这张表
----------------
`analyze_inventory` 目前能落到「采购到货延迟、安全阈值被击穿、跨仓调拨不足」，但缺一块
「到货前到底还差多少货」的量化证据——也就是**预测需求缺口**。没有预测销量，结论只能说
"单靠调拨不足以对冲断货"，却算不出一笔明确的需求缺口数字。

本脚本新增 `sales_forecast`（SKU × 仓 × 目标日 的预测销量），其口径与存量表自洽：
- 每 (SKU, 仓) 的日预测基准 = `dim_sku_safety.avg_daily_sales`（安全表里已有，保证一致）
- 预测窗口 = 2026-06-16 ~ 2026-07-05（断货起点 6/15 → PO0001 到货 7/5），
  使分析器能算出「PO0001 到货前，SKU0001@WH1 累计预测需求缺口」。
- 确定性生成（seed=2026），SKU0001 无抖动，保证缺口数字稳定可复现。

接入归因
--------
`app/domains/agent/analyzers.py::analyze_inventory` 增加一段查询：
  对 SKU0001@WH1 在 [6/16, 7/5] 的 forecast_qty 求和 → 得到预测需求总量，
  并结合在途 PO0001(500) / PO0003(200) + 已调入调拨(140) 算出缺口，
  作为新的 key_metric + evidence。这样这张表真正参与归因，而非摆设。

运行
----
    python -m scripts.gen_scenario_forecast        # 建表 + 灌数据（幂等）
依赖：scenario_inventory 已由 gen_scenario_inventory + enrich_scenario_data 生成。
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import (
    Column, Date, DateTime, Integer, MetaData, String, Table, text,
)
from sqlalchemy.dialects.mysql import TINYINT

from app.core.config import settings

DB_NAME = "scenario_inventory"
SEED = 2026
FORECAST_START = date(2026, 6, 16)   # 断货起点(6/15)次日
FORECAST_END = date(2026, 7, 5)      # PO0001 预计到货日（含）
WAREHOUSES = ["WH1", "WH2", "WH3"]
ANOMALY_SKU = "SKU0001"              # 需要精确缺口数字的 SKU（对齐分析器）

md = MetaData()

sales_forecast = Table(
    "sales_forecast", md,
    Column("sku_id", String(32), primary_key=True),
    Column("wh_id", String(16), primary_key=True),
    Column("d", Date, primary_key=True),
    Column("forecast_qty", Integer, nullable=False, comment="预测销量"),
    Column("dow", Integer, nullable=False, comment="周几 0=周一"),
    Column("is_actual", Integer, nullable=False, default=0, comment="0=预测 1=已发生"),
    Column("source_note", String(64), nullable=False, default="dim_sku_safety.avg_daily_sales 口径"),
    Column("created_at", DateTime, nullable=False),
)


def _engine(db_name: str):
    from sqlalchemy import create_engine as _ce
    return _ce(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}?charset=utf8mb4"
    )


def build() -> dict:
    """建表 + 确定性灌数。返回写入统计。"""
    rng = random.Random(SEED)
    engine = _engine(DB_NAME)
    md.create_all(engine, checkfirst=True)

    # 从安全表取每 (SKU,仓) 的日均销作为预测基准 → 与存量口径自洽
    with engine.connect() as c:
        base = {(r[0], r[1]): r[2] for r in c.execute(
            text("SELECT sku_id, wh_id, avg_daily_sales FROM dim_sku_safety")
        ).fetchall()}

    rows = []
    # 枚举所有 (sku, wh)，但 SKU 集合以 dim_sku 为准
    with engine.connect() as c:
        skus = [r[0] for r in c.execute(text("SELECT sku_id FROM dim_sku ORDER BY sku_id")).fetchall()]

    d0 = FORECAST_START
    n_days = (FORECAST_END - FORECAST_START).days + 1
    for sku in skus:
        for wh in WAREHOUSES:
            baseline = base.get((sku, wh), 0.0)
            if baseline <= 0:
                baseline = 40.0
            for k in range(n_days):
                d = d0 + timedelta(days=k)
                dow = d.weekday()
                # 确定性微抖动；SKU0001@WH1 稳定在 70，保证缺口数字可复现
                if sku == ANOMALY_SKU and wh == "WH1":
                    qty = 70
                else:
                    jitter = rng.uniform(-0.12, 0.12)
                    qty = max(0, round(baseline * (1 + jitter)))
                rows.append({
                    "sku_id": sku, "wh_id": wh, "d": d,
                    "forecast_qty": qty, "dow": dow, "is_actual": 0,
                    "source_note": "dim_sku_safety.avg_daily_sales 口径",
                    "created_at": date(2026, 7, 1),
                })

    # 幂等：先清空再插入
    with engine.begin() as conn:
        conn.execute(sales_forecast.delete())
        conn.execute(sales_forecast.insert(), rows)

    # 打印关键指标
    with engine.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM sales_forecast")).scalar()
        sku1 = c.execute(text("SELECT sku_id, wh_id, SUM(forecast_qty) FROM sales_forecast WHERE sku_id='SKU0001' GROUP BY wh_id")).fetchall()
    print(f"[forecast] 建表+灌数完成：sales_forecast {total} 行（{len(skus)} SKU × 3 仓 × {n_days} 天）")
    for r in sku1:
        print(f"[forecast]   SKU0001@{r[1]} 预测窗口累计 = {r[2]}")

    # 缺口示例（SKU0001@WH1）：PO0001(7/5) 前需求 vs 供给
    with engine.connect() as c:
        need = c.execute(text("SELECT SUM(forecast_qty) FROM sales_forecast WHERE sku_id='SKU0001' AND wh_id='WH1'")).scalar()
    in_transit = 500   # PO0001
    done_qty = 80      # 已调入调拨
    gap = need - in_transit - done_qty
    print(f"[forecast]   SKU0001@WH1 到 7/5 预测需求 {need} − PO0001({in_transit}) − 已调拨({done_qty}) = 缺口 {gap}")
    return {"rows": total, "window_days": n_days, "sku1_need": need, "gap": gap}


if __name__ == "__main__":
    build()
