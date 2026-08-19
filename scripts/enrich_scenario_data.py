"""场景数据补齐：把两个示例库扩到"足以支撑深度归因"的维度。

为什么需要这个脚本
------------------
原 `gen_scenario_goods.py` / `gen_scenario_inventory.py` 只覆盖了"宽表 + 几个日志表"的最小可用集
—— 跑通六段式产出 OK，但要回答「为什么下降」的**颗粒度问题**就会卡：
  - scenario_goods 缺素材维度、缺 SKU 历史 CTR 基线、缺渠道预算出价 → 「换素材贡献度 / 预算影响」无法量化
  - scenario_inventory 缺 SKU×仓 安全库存阈值、缺在途多采购单 → 「全面断货风险」无法评估

结果就是前端右侧"缺失数据"那一栏只能给硬编码的占位文案、Agent 在归因时也凑不出新证据。

脚本规则
--------
1. 只增不改：现有表一律不触碰，仅 `CREATE DATABASE IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS`。
2. 幂等：每次执行前清空本次新增表，行数与种子保持一致（同一 seed=2026）。
3. 与 `gen_scenario_*` 风格统一：确定性生成、打印关键指标。
4. 不依赖 alembic、不依赖 ORM 模型注册（脚本内即建即用）。

补的表（scenario_goods）
  dim_creative                 素材维度（creative_id, channel_id, theme, ab_group, change_date）
  fact_creative_daily          素材级日表现（exposure / clicks / ctr）
  dim_sku_ctr_baseline         SKU 历史 CTR 基线（avg / median / p10 / p90，前 60 天）
  dim_channel_budget_daily     渠道预算日表（budget / cost / bid）

补的表（scenario_inventory）
  dim_sku_safety               SKU × 仓 安全阈值（safety_stock / reorder_point / lead_time_days）
  purchase_order                补两条在途单（PO0003 / PO0004，其余原始单据不动）
  dim_warehouse_transfer        跨仓调拨记录（from_wh / to_wh / qty / transfer_date）
  fact_supplier_leadtime_daily  供应商日度提前期与准时率（用于"供应链波动"维度）

运行
----
    python -m scripts.enrich_scenario_data
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
    Column,
    create_engine,
    text,
)

from app.core.config import settings

# 与原 gen 脚本完全一致的种子，保证 6/3 换素材、6/10 下架等业务事实不漂移
SEED = 2026
START_GOODS = date(2026, 3, 23)       # scenario_goods 起点
START_INV = date(2026, 3, 23)         # scenario_inventory 起点
N_DAYS_GOODS = 100
N_DAYS_INV = 100
OFFLINE_DATE = date(2026, 6, 10)
CREATIVE_CHANGE_DATE = date(2026, 6, 3)
CH_INFO = "CH_INFO"

CHANNELS = [
    ("CH_INFO", "信息流", "paid"),
    ("CH_SEARCH", "搜索", "paid"),
    ("CH_RECO", "推荐", "organic"),
    ("CH_PRIV", "私域", "organic"),
    ("CH_VIDEO", "短视频", "paid"),
    ("CH_OUT", "外投", "paid"),
]


# ---------------------------------------------------------------------------
# scenario_goods 的补全
# ---------------------------------------------------------------------------
def _engine(db_name: str):
    return create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}?charset=utf8mb4"
    )


def _root_engine():
    return create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}?charset=utf8mb4"
    )


md_g = MetaData()

dim_creative = Table("dim_creative", md_g,
    Column("creative_id", String(32), primary_key=True),
    Column("channel_id", String(16)),
    Column("theme", String(32)),
    Column("ab_group", String(16)),
    Column("change_date", Date),
    Column("note", String(128)),
)
fact_creative_daily = Table("fact_creative_daily", md_g,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("creative_id", String(32)),
    Column("d", Date),
    Column("exposure", Integer),
    Column("clicks", Integer),
    Column("ctr", Float),
)
dim_sku_ctr_baseline = Table("dim_sku_ctr_baseline", md_g,
    Column("sku_id", String(32), primary_key=True),
    Column("window_start", Date),
    Column("window_end", Date),
    Column("avg_ctr", Float),
    Column("median_ctr", Float),
    Column("p10_ctr", Float),
    Column("p90_ctr", Float),
    Column("sample_days", Integer),
)
dim_channel_budget_daily = Table("dim_channel_budget_daily", md_g,
    Column("channel_id", String(16), primary_key=True),
    Column("d", Date, primary_key=True),
    Column("budget", Float),
    Column("cost", Float),
    Column("bid", Float),
    Column("note", String(128)),
)


def enrich_goods(rng: random.Random) -> dict:
    """建表 + 灌数。返回本次写入的统计信息，供上层日志输出。"""
    root = _root_engine()
    with root.connect() as c:
        c.execute(text("CREATE DATABASE IF NOT EXISTS scenario_goods CHARACTER SET utf8mb4"))
    engine = _engine("scenario_goods")
    md_g.create_all(engine, checkfirst=True)

    # 1) 素材维度：CH_INFO 主素材 6/3 切换 + 一组长期 A/B 素材
    creatives = [
        {"creative_id": "CR_INFO_OLD", "channel_id": CH_INFO, "theme": "春季主推",
         "ab_group": "control", "change_date": date(2026, 3, 23),
         "note": "5 月及之前的主推素材"},
        {"creative_id": "CR_INFO_NEW", "channel_id": CH_INFO, "theme": "夏季版",
         "ab_group": "treatment", "change_date": CREATIVE_CHANGE_DATE,
         "note": "6/3 切换的夏季版素材，对应截图里的换素材事件"},
        {"creative_id": "CR_INFO_AB", "channel_id": CH_INFO, "theme": "夏季AB",
         "ab_group": "A", "change_date": CREATIVE_CHANGE_DATE,
         "note": "同主题小流量 AB 素材，用于单独跟踪 CTR 差异"},
        # 其他 5 个渠道各 1 张长期素材（用于证明维度不只信息流存在）
        *[{"creative_id": f"CR_{cid}_MAIN", "channel_id": cid, "theme": "长期主推",
           "ab_group": "control", "change_date": date(2026, 3, 23),
           "note": f"{cid} 长期素材"} for cid, _, _ in CHANNELS if cid != CH_INFO],
    ]

    # 2) SKU × 历史 CTR 基线（5/1 - 5/30，即 6/3 换素材前的稳定窗口）
    #    头部 SKU（SKU0001~SKU0005）CTR 显著高于其他，给"下架主力 SKU 对 CTR/曝光的双重打击"留依据
    baseline_rows = []
    for i in range(1, 201):
        sku = f"SKU{i:04d}"
        # 头部 SKU 基线 CTR 较高，离散度更大（爆款特征）
        if i <= 5:
            avg = round(rng.uniform(0.045, 0.075), 4)
            p10 = round(avg * rng.uniform(0.7, 0.85), 4)
            p90 = round(avg * rng.uniform(1.2, 1.4), 4)
        elif i <= 20:
            avg = round(rng.uniform(0.035, 0.055), 4)
            p10 = round(avg * rng.uniform(0.75, 0.85), 4)
            p90 = round(avg * rng.uniform(1.15, 1.3), 4)
        else:
            avg = round(rng.uniform(0.018, 0.032), 4)
            p10 = round(avg * rng.uniform(0.8, 0.9), 4)
            p90 = round(avg * rng.uniform(1.1, 1.2), 4)
        baseline_rows.append({
            "sku_id": sku,
            "window_start": date(2026, 5, 1),
            "window_end": date(2026, 5, 30),
            "avg_ctr": avg,
            "median_ctr": round(avg * rng.uniform(0.95, 1.05), 4),
            "p10_ctr": p10,
            "p90_ctr": p90,
            "sample_days": 30,
        })

    # 3) 渠道预算日表：5 月 30 天稳定、6/1 起信息流预算/出价"再分配"——是的，
    #    信息流预算从 1.5 万/日被压到 8000，与素材切换同期叠加，是常识里另一个潜在根因。
    budget_rows = []
    for di in range(N_DAYS_GOODS):
        d = START_GOODS + timedelta(days=di)
        for cid, _, _ in CHANNELS:
            # 6 月份 5/31 凌晨作 "渠道预算再分配"：CH_INFO 预算砍 47%、CPC 出价降 30%，
            # 信息流以外的渠道预算小幅上调，解释 "其他渠道相对平稳 / 信息流双杀"
            if cid == CH_INFO:
                base_budget = 15000.0 if d < date(2026, 6, 1) else 8000.0
                base_bid = 1.20 if d < date(2026, 6, 1) else 0.84
                # 实际花费一般 ≈ 预算的 92%~99%
                burn = round(base_budget * rng.uniform(0.92, 0.99), 2)
            else:
                base_budget = rng.uniform(8000, 12000)
                base_bid = round(rng.uniform(0.6, 1.5), 2)
                burn = round(base_budget * rng.uniform(0.85, 0.99), 2)
            note = "6/1 预算再分配：信息流预算/出价同步下调" if (
                cid == CH_INFO and d == date(2026, 6, 1)
            ) else ""
            budget_rows.append({
                "channel_id": cid,
                "d": d,
                "budget": round(base_budget, 2),
                "cost": burn,
                "bid": base_bid,
                "note": note,
            })

    # 4) 素材级日表现：旧素材 3/23~6/2；新素材 6/3 起；AB 素材也 6/3 起
    creative_daily = []
    for di in range(N_DAYS_GOODS):
        d = START_GOODS + timedelta(days=di)
        # 旧素材
        if d < CREATIVE_CHANGE_DATE:
            exp = int(rng.gauss(25000, 4000))
            exp = max(8000, exp)
            ctr = rng.uniform(0.035, 0.052)
        else:
            exp = 0
            ctr = 0.0
        if exp:
            clk = int(exp * ctr)
            creative_daily.append({
                "creative_id": "CR_INFO_OLD", "d": d,
                "exposure": exp, "clicks": clk,
                "ctr": round(clk / exp, 6) if exp else 0.0,
            })

        # 新主推素材：CTR 明显下滑（夏季版素材点击意愿不及春季）
        if d >= CREATIVE_CHANGE_DATE:
            new_exp = int(rng.gauss(18000, 3500))
            new_exp = max(5000, new_exp)
            new_ctr = rng.uniform(0.020, 0.030)   # 换素材后 CTR 跌至 2.0~3.0%（基线 3.5~5.2%）
            new_clk = int(new_exp * new_ctr)
            creative_daily.append({
                "creative_id": "CR_INFO_NEW", "d": d,
                "exposure": new_exp, "clicks": new_clk,
                "ctr": round(new_clk / new_exp, 6) if new_exp else 0.0,
            })
            # AB 素材（小流量），CTR 维持基线水平 → 证明问题在主素材，不在人群/出价
            ab_exp = int(rng.gauss(4000, 800))
            ab_exp = max(800, ab_exp)
            ab_ctr = rng.uniform(0.038, 0.050)
            ab_clk = int(ab_exp * ab_ctr)
            creative_daily.append({
                "creative_id": "CR_INFO_AB", "d": d,
                "exposure": ab_exp, "clicks": ab_clk,
                "ctr": round(ab_clk / ab_exp, 6) if ab_exp else 0.0,
            })

        # 其他渠道：长期主推素材一次/天
        for cid, _, _ in CHANNELS:
            if cid == CH_INFO:
                continue
            crc_exp = int(rng.gauss(9000, 1500))
            crc_exp = max(1500, crc_exp)
            crc_ctr = rng.uniform(0.025, 0.045)
            crc_clk = int(crc_exp * crc_ctr)
            creative_daily.append({
                "creative_id": f"CR_{cid}_MAIN", "d": d,
                "exposure": crc_exp, "clicks": crc_clk,
                "ctr": round(crc_clk / crc_exp, 6) if crc_exp else 0.0,
            })

    # 写库
    with engine.begin() as conn:
        # 清空本次新增的表，幂等
        for t in (dim_creative, fact_creative_daily, dim_sku_ctr_baseline, dim_channel_budget_daily):
            conn.execute(t.delete())

        conn.execute(dim_creative.insert(), creatives)
        # 分批插入 fact_creative_daily
        step = 5000
        for i in range(0, len(creative_daily), step):
            conn.execute(fact_creative_daily.insert(), creative_daily[i:i + step])
        conn.execute(dim_sku_ctr_baseline.insert(), baseline_rows)
        conn.execute(dim_channel_budget_daily.insert(), budget_rows)

    return {
        "dim_creative": len(creatives),
        "fact_creative_daily": len(creative_daily),
        "dim_sku_ctr_baseline": len(baseline_rows),
        "dim_channel_budget_daily": len(budget_rows),
    }


# ---------------------------------------------------------------------------
# scenario_inventory 的补全
# ---------------------------------------------------------------------------
md_i = MetaData()
dim_sku_safety = Table("dim_sku_safety", md_i,
    Column("sku_id", String(32), primary_key=True),
    Column("wh_id", String(16), primary_key=True),
    Column("safety_stock", Integer),
    Column("reorder_point", Integer),
    Column("lead_time_days", Integer),
    Column("avg_daily_sales", Float),
    Column("note", String(128)),
)
dim_warehouse_transfer = Table("dim_warehouse_transfer", md_i,
    Column("transfer_id", String(32), primary_key=True),
    Column("sku_id", String(32)),
    Column("from_wh", String(16)),
    Column("to_wh", String(16)),
    Column("qty", Integer),
    Column("transfer_date", Date),
    Column("status", String(16)),
    Column("reason", String(128)),
)
fact_supplier_leadtime_daily = Table("fact_supplier_leadtime_daily", md_i,
    Column("supplier_id", String(16), primary_key=True),
    Column("d", Date, primary_key=True),
    Column("lead_time_days", Float),
    Column("on_time_rate", Float),
    Column("lead_7d_avg", Float),
    Column("lead_30d_avg", Float),
    Column("note", String(128)),
)


def enrich_inventory(rng: random.Random) -> dict:
    root = _root_engine()
    with root.connect() as c:
        c.execute(text("CREATE DATABASE IF NOT EXISTS scenario_inventory CHARACTER SET utf8mb4"))
    engine = _engine("scenario_inventory")
    md_i.create_all(engine, checkfirst=True)

    # 1) SKU × 仓 安全阈值 + 提前期（3 仓 × 100 SKU = 300 行）
    WAREHOUSES = ["WH1", "WH2", "WH3"]
    safety_rows = []
    for i in range(1, 101):
        sku = f"SKU{i:04d}"
        # 不同仓销售速率 / 提前期不同
        for j, wh in enumerate(WAREHOUSES):
            base_sales = rng.uniform(10, 60)
            # 头部 SKU 销售更快、安全阈值更高、采购提前期更长（断货成本高 → 留更多 buffer）
            if i <= 5:
                base_sales *= 3
                lead = rng.randint(10, 20)
                safety_mult = rng.uniform(1.6, 2.0)
            elif i <= 20:
                lead = rng.randint(7, 12)
                safety_mult = rng.uniform(1.2, 1.5)
            else:
                lead = rng.randint(3, 8)
                safety_mult = rng.uniform(1.0, 1.3)
            sales = round(base_sales, 1)
            reorder = int(lead * sales * safety_mult)
            safety = int(reorder * rng.uniform(1.2, 1.5))
            note = "头部 SKU 留 buffer" if i <= 5 else (
                "标准 SKU" if i <= 20 else "长尾 SKU 阈值较低"
            )
            safety_rows.append({
                "sku_id": sku,
                "wh_id": wh,
                "safety_stock": safety,
                "reorder_point": reorder,
                "lead_time_days": lead,
                "avg_daily_sales": sales,
                "note": note,
            })

    # 2) 在途采购单：PO0001 已存在；补 PO0003 / PO0004 两条——让 "全面断货风险" 评估有数据
    #    PO0003：SKU0001@WH1 紧急补货单，ETA 比 PO0001 早，用以对比"分批补货"是否成立
    #    PO0004：SKU0002@WH2 常规单（差异化 SKU，让"全面断货"的推断不至于被一句 SKU0001 概括）
    extra_pos = [
        {"po_id": "PO0003", "sku_id": "SKU0001", "wh_id": "WH1",
         "order_date": date(2026, 6, 12), "qty": 200, "eta": date(2026, 6, 28)},
        {"po_id": "PO0004", "sku_id": "SKU0002", "wh_id": "WH2",
         "order_date": date(2026, 5, 25), "qty": 250, "eta": date(2026, 6, 5)},
    ]

    # 3) 跨仓调拨：WH3 向 WH1 紧急调拨 SKU0001（作为"调拨可缓解断货"的关键证据）
    transfer_rows = [
        {"transfer_id": "TR0001", "sku_id": "SKU0001", "from_wh": "WH3",
         "to_wh": "WH1", "qty": 80, "transfer_date": date(2026, 6, 18),
         "status": "completed", "reason": "WH1 库存告急，从 WH3 紧急调拨"},
        {"transfer_id": "TR0002", "sku_id": "SKU0001", "from_wh": "WH2",
         "to_wh": "WH1", "qty": 60, "transfer_date": date(2026, 6, 22),
         "status": "in_transit", "reason": "WH2 有 60 件余量，紧急调拨追加"},
        {"transfer_id": "TR0003", "sku_id": "SKU0003", "from_wh": "WH2",
         "to_wh": "WH3", "qty": 40, "transfer_date": date(2026, 6, 5),
         "status": "completed", "reason": "正常区域间调度，非紧急"},
    ]

    # 4) 供应商提前期波动：6/1 起 SUP1（PO0001 来源）lead time 突增 5~9 天，是核心问题
    #    SUP2/SUP3 同期保持稳定，用于在证据链里做"是 SUP1 单点恶化，不是供应链整体"的对照
    supplier_daily: dict[str, list[dict]] = {"SUP1": [], "SUP2": [], "SUP3": []}
    supplier_rows: list[dict] = []
    for di in range(N_DAYS_INV):
        d = START_INV + timedelta(days=di)
        # SUP1：5 月稳定 5~7 天，6/1 起拉到 10~16 天（节后产能不足）
        if d < date(2026, 6, 1):
            lead1 = round(rng.uniform(5.0, 7.0), 1)
            ontime1 = round(rng.uniform(0.94, 0.99), 4)
        else:
            lead1 = round(rng.uniform(10.0, 16.0), 1)
            ontime1 = round(rng.uniform(0.55, 0.78), 4)
        # SUP2 / SUP3：稳定，用同一 rng 分支以保持确定性
        lead2 = round(rng.uniform(6.5, 8.5), 1)
        ontime2 = round(rng.uniform(0.92, 0.98), 4)
        lead3 = round(rng.uniform(7.0, 9.0), 1)
        ontime3 = round(rng.uniform(0.90, 0.97), 4)
        for sid, l, ot in [("SUP1", lead1, ontime1), ("SUP2", lead2, ontime2), ("SUP3", lead3, ontime3)]:
            supplier_daily[sid].append({"d": d, "lead_time_days": l})
            h = supplier_daily[sid]
            lead_7d = round(sum(x["lead_time_days"] for x in h[-7:]) / max(len(h[-7:]), 1), 2)
            lead_30d = round(sum(x["lead_time_days"] for x in h[-30:]) / max(len(h[-30:]), 1), 2)
            note = "节后产能下降 / 物流拥堵" if (sid == "SUP1" and d >= date(2026, 6, 1)) else ""
            supplier_rows.append({
                "supplier_id": sid, "d": d,
                "lead_time_days": l, "on_time_rate": ot,
                "lead_7d_avg": lead_7d, "lead_30d_avg": lead_30d,
                "note": note,
            })

    with engine.begin() as conn:
        conn.execute(dim_sku_safety.delete())
        conn.execute(dim_warehouse_transfer.delete())
        conn.execute(fact_supplier_leadtime_daily.delete())
        # 仅在 PO 不存在时插入，幂等
        existing_po_ids = {
            row[0] for row in conn.execute(text("SELECT po_id FROM purchase_order")).fetchall()
        }
        conn.execute(dim_sku_safety.insert(), safety_rows)
        conn.execute(dim_warehouse_transfer.insert(), transfer_rows)
        # 分批插入供应商提前期（300 行）
        step_s = 5000
        for i in range(0, len(supplier_rows), step_s):
            conn.execute(fact_supplier_leadtime_daily.insert(), supplier_rows[i:i + step_s])
        for po in extra_pos:
            if po["po_id"] not in existing_po_ids:
                conn.execute(
                    text("INSERT INTO purchase_order "
                         "(po_id, sku_id, wh_id, order_date, qty, eta) "
                         "VALUES (:po_id, :sku_id, :wh_id, :order_date, :qty, :eta)"),
                    po,
                )

    return {
        "dim_sku_safety": len(safety_rows),
        "purchase_order_added": len(extra_pos),
        "dim_warehouse_transfer": len(transfer_rows),
        "fact_supplier_leadtime_daily": len(supplier_rows),
    }


# ---------------------------------------------------------------------------
# 一键执行
# ---------------------------------------------------------------------------
def build_all() -> None:
    rng = random.Random(SEED)
    print("[enrich] 正在补 scenario_goods……")
    g = enrich_goods(rng)
    print(f"[enrich]   scenario_goods: {g}")
    print("[enrich] 正在补 scenario_inventory……")
    i = enrich_inventory(rng)
    print(f"[enrich]   scenario_inventory: {i}")
    print("[enrich] 全部完成。两库新维度已就绪，引擎与分析器会自动受益。")


if __name__ == "__main__":
    build_all()
