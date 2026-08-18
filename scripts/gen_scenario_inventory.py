"""场景二示例数据：库存异常分析库（scenario_inventory）。

演示故事线「库存异常排查」——确定性生成（seed=2026）：
- 维度：仓库(3) / SKU(100) / 日期(100天 2026-03-23~06-30)。
- 事实：fact_inventory_daily 库存日快照（含周转天数）；sales_daily 销售；purchase_order 采购单。
- 异常注入：SKU0001 在 WH1 自 2026-06-15 起因采购延迟(eta 滞后)出现低库存→负库存，
  周转天数飙升，stock_anomaly_log 记录「缺货/负库存」事件。
  → Agent 可归因到「采购到货延迟」而非「销售暴增」。

运行：python -m scripts.gen_scenario_inventory
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import (
    Date,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Column,
    create_engine,
    insert,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME

from app.core.config import settings

DB_NAME = "scenario_inventory"
SEED = 2026
N_SKU = 100
N_DAYS = 100
START = date(2026, 3, 23)

WAREHOUSES = [("WH1", "华东仓", "上海"), ("WH2", "华北仓", "北京"), ("WH3", "华南仓", "广州")]

md = MetaData()

dim_warehouse = Table("dim_warehouse", md,
    Column("wh_id", String(16), primary_key=True),
    Column("wh_name", String(32)),
    Column("region", String(32)),
)
dim_sku = Table("dim_sku", md,
    Column("sku_id", String(32), primary_key=True),
    Column("sku_name", String(64)),
    Column("category", String(32)),
)
dim_date = Table("dim_date", md,
    Column("d", Date, primary_key=True),
    Column("month", String(8)),
)
fact_inventory_daily = Table("fact_inventory_daily", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sku_id", String(32)),
    Column("wh_id", String(16)),
    Column("d", Date),
    Column("stock_qty", Integer),
    Column("inbound", Integer),
    Column("outbound", Integer),
    Column("turnover_days", Float),
    Column("created_at", DATETIME),
)
stock_anomaly_log = Table("stock_anomaly_log", md,
    Column("sku_id", String(32)),
    Column("wh_id", String(16)),
    Column("d", Date),
    Column("anomaly_type", String(32)),
    Column("detail", Text),
)
purchase_order = Table("purchase_order", md,
    Column("po_id", String(32), primary_key=True),
    Column("sku_id", String(32)),
    Column("wh_id", String(16)),
    Column("order_date", Date),
    Column("qty", Integer),
    Column("eta", Date),
)
sales_daily = Table("sales_daily", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sku_id", String(32)),
    Column("wh_id", String(16)),
    Column("d", Date),
    Column("sales_qty", Integer),
)


def _root_engine():
    return create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}?charset=utf8mb4"
    )


def build():
    rng = random.Random(SEED)
    root = _root_engine()
    with root.connect() as c:
        c.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4"))
    engine = create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    md.drop_all(engine)
    md.create_all(engine)

    skus = [f"SKU{i:04d}" for i in range(1, N_SKU + 1)]
    anomaly_sku, anomaly_wh, anomaly_start = "SKU0001", "WH1", date(2026, 6, 15)

    with engine.begin() as conn:
        conn.execute(dim_warehouse.insert(), [{"wh_id": w, "wh_name": n, "region": r} for w, n, r in WAREHOUSES])
        conn.execute(dim_sku.insert(), [{"sku_id": s, "sku_name": f"货品{i:04d}", "category": f"C{i % 5 + 1}"} for i, s in enumerate(skus)])
        conn.execute(dim_date.insert(), [{"d": START + timedelta(days=i), "month": f"{(START + timedelta(days=i)).strftime('%Y-%m')}"} for i in range(N_DAYS)])

        inv_rows, sales_rows, anomaly_rows, po_rows = [], [], [], []
        for di, d in enumerate((START + timedelta(days=i) for i in range(N_DAYS))):
            for sku in skus:
                for wh_id, _, _ in WAREHOUSES:
                    base_stock = rng.randint(200, 800)
                    daily_sales = rng.randint(5, 40)
                    inbound = rng.randint(0, 60)
                    # 异常 SKU 在 WH1 自 anomaly_start 起采购延迟→库存枯竭
                    if sku == anomaly_sku and wh_id == anomaly_wh and d >= anomaly_start:
                        inbound = 0
                        base_stock = max(-30, base_stock - (d - anomaly_start).days * 25)
                    stock = base_stock + inbound - daily_sales
                    turnover = round(stock / max(daily_sales, 1), 1)
                    inv_rows.append({"sku_id": sku, "wh_id": wh_id, "d": d, "stock_qty": stock,
                                     "inbound": inbound, "outbound": daily_sales, "turnover_days": turnover})
                    sales_rows.append({"sku_id": sku, "wh_id": wh_id, "d": d, "sales_qty": daily_sales})
                    if sku == anomaly_sku and wh_id == anomaly_wh and d >= anomaly_start and stock < 50:
                        atype = "negative_stock" if stock < 0 else "low_stock"
                        anomaly_rows.append({"sku_id": sku, "wh_id": wh_id, "d": d, "anomaly_type": atype,
                                             "detail": f"库存={stock}，采购到货延迟导致断货"})
        step = 5000
        for i in range(0, len(inv_rows), step):
            conn.execute(fact_inventory_daily.insert(), inv_rows[i:i + step])
        for i in range(0, len(sales_rows), step):
            conn.execute(sales_daily.insert(), sales_rows[i:i + step])
        # 采购单：异常 SKU 的采购单 eta 滞后（晚于 6/15 很久）
        conn.execute(purchase_order.insert(), [
            {"po_id": "PO0001", "sku_id": anomaly_sku, "wh_id": anomaly_wh,
             "order_date": date(2026, 6, 10), "qty": 500, "eta": date(2026, 7, 5)},
            {"po_id": "PO0002", "sku_id": "SKU0002", "wh_id": "WH2",
             "order_date": date(2026, 5, 20), "qty": 300, "eta": date(2026, 5, 28)},
        ])
        if anomaly_rows:
            conn.execute(stock_anomaly_log.insert(), anomaly_rows)

    print(f"[scenario_inventory] 建表+数据完成：fact_inventory_daily={len(inv_rows)} 行；{anomaly_sku}@{anomaly_wh} 自 {anomaly_start} 缺货异常已注入（{len(anomaly_rows)} 条）。")


if __name__ == "__main__":
    build()
