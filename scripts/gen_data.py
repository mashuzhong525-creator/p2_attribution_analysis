"""演示数据生成 + 管理员与配置（python scripts/gen_data.py）。"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.admin import set_config  # noqa: E402
from app.database import db, init_db  # noqa: E402
from app.utils import now_iso  # noqa: E402

SKUS = [f"SKU{i:03d}" for i in range(1, 21)]
WHS = ["华东仓", "华南仓", "华北仓"]
REGIONS = ["华东", "华南", "华北", "西南"]
CHANNELS = ["APP", "小程序", "官网"]
MONTHS = ["2026-05", "2026-06", "2026-07"]
USERS = [f"U{i:04d}" for i in range(1, 61)]


def seed_base() -> None:
    init_db()
    now = now_iso()
    with db() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
            conn.execute(
                "INSERT INTO users(external_user_id,username,password,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                ("u-admin", "admin", "admin123", "系统管理员", "admin", "active", now, now),
            )
        set_config(conn, "max_result_rows", "100", "engine")
        set_config(conn, "llm_model", "deepseek-chat", "llm")
        set_config(conn, "anomaly_threshold_turnover", "20", "metric")
        set_config(conn, "anomaly_threshold_conversion", "15", "metric")


def gen() -> None:
    random.seed(42)
    seed_base()
    with db() as conn:
        for t in ("inventory", "inbound", "outbound", "sales", "customers", "visits", "add_to_cart", "orders"):
            conn.execute(f"DELETE FROM {t}")

        # 库存月度快照：7 月华东仓库存积压（stock 偏高）
        for m in MONTHS:
            for sku in SKUS:
                for wh in WHS:
                    stock = random.randint(80, 300)
                    if m == "2026-07" and wh == "华东仓":
                        stock = int(stock * 1.6)
                    conn.execute(
                        "INSERT INTO inventory(sku_id,warehouse_id,stock_qty,period) VALUES(?,?,?,?)",
                        (sku, wh, stock, m),
                    )

        # 出入库与销量：7 月华东仓进多出少，销量整体下滑
        for m in MONTHS:
            for day in range(1, 29):
                d = f"{m}-{day:02d}"
                for sku in SKUS:
                    wh = random.choice(WHS)
                    in_qty, out_qty = random.randint(5, 30), random.randint(5, 28)
                    if m == "2026-07" and wh == "华东仓":
                        in_qty, out_qty = random.randint(40, 80), random.randint(5, 15)
                    conn.execute("INSERT INTO inbound(sku_id,warehouse_id,in_qty,in_date) VALUES(?,?,?,?)", (sku, wh, in_qty, d))
                    conn.execute("INSERT INTO outbound(sku_id,warehouse_id,out_qty,out_date) VALUES(?,?,?,?)", (sku, wh, out_qty, d))
                    sales_qty = random.randint(5, 25)
                    if m == "2026-07":
                        sales_qty = int(sales_qty * 0.6)
                    conn.execute("INSERT INTO sales(sku_id,date,sales_qty,amount) VALUES(?,?,?,?)", (sku, d, sales_qty, sales_qty * random.randint(80, 200)))

        # 用户与行为：7 月下单量下降（转化率下滑）
        for uid in USERS:
            conn.execute(
                "INSERT INTO customers(user_id,register_date,region,channel) VALUES(?,?,?,?)",
                (uid, f"2026-0{random.randint(1, 4)}-{random.randint(1, 28):02d}", random.choice(REGIONS), random.choice(CHANNELS)),
            )
        for m in MONTHS:
            for day in range(1, 29):
                d = f"{m}-{day:02d}"
                for _ in range(30):
                    conn.execute("INSERT INTO visits(user_id,page,event_time) VALUES(?,?,?)", (random.choice(USERS), "/home", f"{d} 10:00:00"))
                for _ in range(12):
                    conn.execute("INSERT INTO add_to_cart(user_id,sku_id,event_time) VALUES(?,?,?)", (random.choice(USERS), random.choice(SKUS), f"{d} 10:30:00"))
                orders_n = 8 if m != "2026-07" else 4
                for i in range(orders_n):
                    conn.execute(
                        "INSERT INTO orders(order_id,user_id,sku_id,order_time,amount) VALUES(?,?,?,?,?)",
                        (f"O{d}-{i}", random.choice(USERS), random.choice(SKUS), f"{d} 11:00:00", random.randint(50, 500)),
                    )
    print("demo data OK: 3 个月，双场景（库存/客户行为），含 7 月异常注入")


if __name__ == "__main__":
    gen()
