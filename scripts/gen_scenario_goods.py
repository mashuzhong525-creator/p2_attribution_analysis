"""场景一示例数据：商品目录优化库（scenario_goods）。

支撑演示故事线「为什么 6 月信息流渠道点击量下滑」——确定性生成（seed=2026）：
- 维度：SKU(200) / 渠道(6) / 类目 / 品牌 / 日期(100天)。
- 事实：fact_sku_daily 约 12 万行（200×6×100），fact_channel_daily 渠道聚合。
- 异常注入：信息流渠道 6 月起点击量骤降约 55%；同期(6/3)素材更换日志；5 个头部 SKU 6/10 下架。
  → Agent 可从数据归因到「素材更换 + 头部 SKU 下架」双因素。

运行：python -m scripts.gen_scenario_goods
依赖：业务库 settings（同主机 MySQL），会自动 CREATE DATABASE IF NOT EXISTS scenario_goods。
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

DB_NAME = "scenario_goods"
SEED = 2026
N_SKU = 200
N_DAYS = 100  # 2026-03-23 ~ 2026-06-30
START = date(2026, 3, 23)

CHANNELS = [
    ("CH_INFO", "信息流", "paid"),
    ("CH_SEARCH", "搜索", "paid"),
    ("CH_RECO", "推荐", "organic"),
    ("CH_PRIV", "私域", "organic"),
    ("CH_VIDEO", "短视频", "paid"),
    ("CH_OUT", "外投", "paid"),
]
CATEGORIES = [("C1", "美妆"), ("C2", "数码"), ("C3", "家居"), ("C4", "食品"), ("C5", "服饰")]
BRANDS = [("B1", "本味"), ("B2", "极光"), ("B3", "云栖"), ("B4", "禾木"), ("B5", "川流")]

md = MetaData()

dim_sku = Table("dim_sku", md,
    Column("sku_id", String(32), primary_key=True),
    Column("sku_name", String(64)),
    Column("category", String(32)),
    Column("brand", String(32)),
    Column("status", String(16)),
    Column("list_price", Float),
)
dim_channel = Table("dim_channel", md,
    Column("channel_id", String(16), primary_key=True),
    Column("channel_name", String(32)),
    Column("channel_type", String(16)),
)
dim_category = Table("dim_category", md,
    Column("category_id", String(16), primary_key=True),
    Column("category_name", String(32)),
)
dim_brand = Table("dim_brand", md,
    Column("brand_id", String(16), primary_key=True),
    Column("brand_name", String(32)),
)
dim_date = Table("dim_date", md,
    Column("d", Date, primary_key=True),
    Column("month", String(8)),
    Column("is_promo", Integer),
)
fact_sku_daily = Table("fact_sku_daily", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("sku_id", String(32)),
    Column("channel_id", String(16)),
    Column("d", Date),
    Column("exposure", Integer),
    Column("clicks", Integer),
    Column("conversions", Integer),
    Column("gmv", Float),
    Column("created_at", DATETIME),
)
fact_channel_daily = Table("fact_channel_daily", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("channel_id", String(16)),
    Column("d", Date),
    Column("exposure", Integer),
    Column("clicks", Integer),
    Column("conversions", Integer),
    Column("gmv", Float),
)
sku_offline_log = Table("sku_offline_log", md,
    Column("sku_id", String(32)),
    Column("offline_date", Date),
    Column("reason", Text),
)
creative_change_log = Table("creative_change_log", md,
    Column("channel_id", String(16)),
    Column("change_date", Date),
    Column("note", Text),
)
promotion_calendar = Table("promotion_calendar", md,
    Column("d", Date, primary_key=True),
    Column("name", String(64)),
    Column("discount", Float),
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
    offline_skus = set(skus[:5])  # 头部 5 个 6/10 下架
    offline_date = date(2026, 6, 10)
    promo_dates = {START + timedelta(days=40): "618 预热", date(2026, 6, 18): "618 大促"}

    with engine.begin() as conn:
        conn.execute(dim_category.insert(), [{"category_id": c, "category_name": n} for c, n in CATEGORIES])
        conn.execute(dim_brand.insert(), [{"brand_id": b, "brand_name": n} for b, n in BRANDS])
        conn.execute(dim_channel.insert(), [{"channel_id": i, "channel_name": n, "channel_type": t} for i, n, t in CHANNELS])
        sku_rows = []
        for i, sku in enumerate(skus):
            cat = CATEGORIES[i % len(CATEGORIES)][0]
            brd = BRANDS[i % len(BRANDS)][0]
            st = "offline" if sku in offline_skus else "on_shelf"
            sku_rows.append({"sku_id": sku, "sku_name": f"商品{i:04d}", "category": cat, "brand": brd, "status": st, "list_price": round(rng.uniform(9.9, 999.0), 2)})
        conn.execute(dim_sku.insert(), sku_rows)
        date_rows = []
        for d in (START + timedelta(days=i) for i in range(N_DAYS)):
            date_rows.append({"d": d, "month": f"{d.year}-{d.month:02d}", "is_promo": 1 if d in promo_dates else 0})
        conn.execute(dim_date.insert(), date_rows)
        conn.execute(creative_change_log.insert(), [
            {"channel_id": "CH_INFO", "change_date": date(2026, 6, 3), "note": "信息流主素材更换为夏季版，CTR 预期下降"},
        ])
        conn.execute(sku_offline_log.insert(), [
            {"sku_id": s, "offline_date": offline_date, "reason": "类目策略调整，头部 SKU 下架"} for s in offline_skus
        ])
        conn.execute(promotion_calendar.insert(), [
            {"d": d, "name": n, "discount": round(rng.uniform(0.1, 0.3), 2)} for d, n in promo_dates.items()
        ])

        # 事实明细
        fact_rows = []
        chan_weight = {"CH_INFO": 1.0, "CH_SEARCH": 0.8, "CH_RECO": 0.6, "CH_PRIV": 0.4, "CH_VIDEO": 0.7, "CH_OUT": 0.5}
        for di, d in enumerate((START + timedelta(days=i) for i in range(N_DAYS))):
            for sku in skus:
                if sku in offline_skus and d >= offline_date:
                    continue  # 下架后无曝光
                for cid, _, _ in CHANNELS:
                    base_exp = int(rng.gauss(800, 200) * chan_weight[cid] * (1 + 0.3 * (d in promo_dates)))
                    base_exp = max(50, base_exp)
                    ctr = rng.uniform(0.02, 0.06)
                    clicks = int(base_exp * ctr)
                    # 异常：信息流 6 月起点击骤降
                    if cid == "CH_INFO" and d >= date(2026, 6, 1):
                        clicks = int(clicks * 0.45)
                        base_exp = int(base_exp * 0.6)
                    conv = int(clicks * rng.uniform(0.05, 0.15))
                    gmv = round(conv * rng.uniform(50, 300), 2)
                    fact_rows.append({"sku_id": sku, "channel_id": cid, "d": d,
                                      "exposure": base_exp, "clicks": clicks, "conversions": conv, "gmv": gmv})
        # 分批插入
        step = 5000
        for i in range(0, len(fact_rows), step):
            conn.execute(fact_sku_daily.insert(), fact_rows[i:i + step])

        # 渠道日聚合
        agg = {}
        for r in fact_rows:
            k = (r["channel_id"], r["d"])
            a = agg.setdefault(k, {"exposure": 0, "clicks": 0, "conversions": 0, "gmv": 0.0})
            a["exposure"] += r["exposure"]; a["clicks"] += r["clicks"]
            a["conversions"] += r["conversions"]; a["gmv"] += r["gmv"]
        conn.execute(fact_channel_daily.insert(), [
            {"channel_id": c, "d": d, **v} for (c, d), v in agg.items()
        ])

    print(f"[scenario_goods] 建表+数据完成：fact_sku_daily={len(fact_rows)} 行；信息流6月点击骤降已注入。")


if __name__ == "__main__":
    build()
