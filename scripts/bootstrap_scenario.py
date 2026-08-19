"""一键补齐 + 校验两个场景示例库（scenario_goods / scenario_inventory）。

为什么需要这个脚本
------------------
运行环境（docker-compose 首次建卷）已经执行过
`seed → gen_scenario_goods → gen_scenario_inventory → enrich_scenario_data`，
正常情况下表和数据都齐全。但出现以下情况时，前端"六段式"会缺关键指标 / 缺证据链、
Agent 追问回答不上来、'缺失数据'日志频繁出现：

  1. 某个示例库被清空/重建（drop database / 手动误删），只剩部分表；
  2. enrich 脚本未执行（缺少素材维度 / 安全阈值 / 在途多单 / 跨仓调拨 / 供应商提前期等深度表）；
  3. 表在但关键行缺失，分析器 try/except 捕获异常后把指标/证据吞掉，只往 gaps 里写一句。

本脚本是幂等的"补齐 + 自愈"入口：先跑基线种子，再重建/补齐两个场景库全部
分析器所引用的表与数据，最后逐表校验关键行数——任何表缺失或行数过少都会直接报错，
并给出明确的补齐建议，保证离线确定性归因能真正产出关键指标与证据链。

运行
----
    python -m scripts.bootstrap_scenario          # 补齐 + 校验
    python -m scripts.bootstrap_scenario --force  # 即便校验通过也强制重建全量数据
依赖：业务库 / 场景库处于同一 MySQL（同 settings.DB_HOST），bia 用户有对应库权限。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings


# 分析器真实引用的表 → 期望的最小关键行数（低于则视为"缺表/缺数据"，需补齐）
# 表名与 apps/domains/agent/analyzers.py 中 SQL 严格对齐。
REQUIRED_INVENTORY = {
    "dim_warehouse": 1,          # 3 仓维度
    "dim_sku": 1,                # 100 SKU 维度
    "dim_date": 1,               # 日期维度
    "fact_inventory_daily": 1,   # 库存日快照（30k）
    "sales_daily": 1,            # 销售日表（30k）—— 判断"销售是否暴增"必需
    "stock_anomaly_log": 1,      # 异常事件（缺货/低库存/负库存）
    "purchase_order": 1,         # 采购单（含到货 ETA）
    "dim_sku_safety": 1,         # SKU×仓 安全阈值 + 再订货点（enrich 补齐）
    "dim_warehouse_transfer": 1, # 跨仓调拨（enrich 补齐）
    "fact_supplier_leadtime_daily": 1,  # 供应商提前期波动（enrich 补齐）
}
REQUIRED_GOODS = {
    "dim_sku": 1,
    "dim_channel": 1,
    "dim_date": 1,
    "fact_sku_daily": 1,          # SKU 日度明细（12 万行）
    "fact_channel_daily": 1,      # 渠道日度事实
    "creative_change_log": 1,     # 素材更换日志
    "sku_offline_log": 1,         # SKU 下架记录
    "fact_creative_daily": 1,     # 素材级日表现（enrich 补齐）
    "dim_creative": 1,            # 素材维度（enrich 补齐）
    "dim_sku_ctr_baseline": 1,    # SKU 历史 CTR 基线（enrich 补齐）
    "dim_channel_budget_daily": 1,# 渠道预算日表（enrich 补齐）
}


def _root_engine():
    """不指定库名的连接，用于 CROSS 数据库的建库/校验。"""
    return create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}?charset=utf8mb4",
        poolclass=NullPool,
    )


def _db_engine(db_name: str):
    return create_engine(
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}?charset=utf8mb4",
        poolclass=NullPool,
    )


def _ensure_dbs() -> None:
    """确保两个场景库存在（幂等）。"""
    root = _root_engine()
    with root.connect() as c:
        for db in ("scenario_goods", "scenario_inventory"):
            c.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4"))
    print("[bootstrap] 场景库就绪：scenario_goods / scenario_inventory")


def run_baseline_seed() -> None:
    """基线种子（幂等）：configs / 认证用户 / 业务用户 / 数据源。"""
    from scripts.seed import seed_all
    seed_all()


def rebuild_scenario_data() -> None:
    """重建 / 补齐两个场景库（先重建底表，再补深度归因维度的表）。"""
    import scripts.gen_scenario_goods        # noqa: F401  (side-effect: build())
    import scripts.gen_scenario_inventory    # noqa: F401
    import scripts.enrich_scenario_data as enrich

    print("[bootstrap] 重建 scenario_goods 底表 + 数据……")
    scripts.gen_scenario_goods.build()
    print("[bootstrap] 重建 scenario_inventory 底表 + 数据……")
    scripts.gen_scenario_inventory.build()
    print("[bootstrap] 补深维度表（素材/CTR基线/预算 / 安全阈值/在途/调拨/供应商提前期）……")
    enrich.build_all()


def verify_tables(db_name: str, required: dict[str, int], label: str) -> list[str]:
    """校验某库的所有必需表存在且行数≥期望。返回缺失/异常描述列表。"""
    problems: list[str] = []
    engine = _db_engine(db_name)
    with engine.connect() as c:
        existing = {r[0] for r in c.execute(text("SHOW TABLES")).fetchall()}
        for table, min_rows in required.items():
            if table not in existing:
                problems.append(f"  [缺表] {db_name}.{table}")
                continue
            cnt = c.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
            status = "OK" if cnt >= min_rows else "数据不足"
            if status == "OK":
                print(f"  [OK]   {db_name}.{table}: {cnt} 行")
            else:
                problems.append(f"  [数据不足] {db_name}.{table}: 仅 {cnt} 行（期望 ≥ {min_rows}）")
    print(f"[bootstrap] {label} 校验完成")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="补齐并校验场景示例库")
    parser.add_argument("--force", action="store_true",
                        help="即便表都已补齐也强制重新生成全量数据")
    args = parser.parse_args(argv)

    print("=" * 64)
    print(f"[bootstrap] 场景库补齐/自愈 @ {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 64)

    # 1) 基线种子（configs/users/data_sources 幂等补全）
    run_baseline_seed()

    # 2) 缺表探测：只有存在缺表/缺数据或 --force 时才重建，避免无谓耗时
    _ensure_dbs()
    need_rebuild = args.force
    for db, required, label in (("scenario_goods", REQUIRED_GOODS, "商品库"),
                                ("scenario_inventory", REQUIRED_INVENTORY, "库存库")):
        engine = _db_engine(db)
        with engine.connect() as c:
            existing = {r[0] for r in c.execute(text("SHOW TABLES")).fetchall()}
            for table, min_rows in required.items():
                if table not in existing:
                    print(f"[bootstrap] 发现缺表：{db}.{table}")
                    need_rebuild = True
                    break
                cnt = c.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
                if cnt < min_rows:
                    print(f"[bootstrap] 发现数据不足：{db}.{table} 仅 {cnt} 行（期望 {min_rows}）")
                    need_rebuild = True
                    break

    if not need_rebuild:
        print("[bootstrap] 两个场景库表结构/数据已齐全，跳过重建（如需强制重建请加 --force）。")
    else:
        rebuild_scenario_data()

    # 3) 逐表校验（权威结论）
    print("\n[bootstrap] 表级校验：")
    problems: list[str] = []
    problems += verify_tables("scenario_goods", REQUIRED_GOODS, "商品库")
    problems += verify_tables("scenario_inventory", REQUIRED_INVENTORY, "库存库")

    if problems:
        print("\n[bootstrap] 失败：存在缺表/数据不足：")
        for p in problems:
            print(p)
        print("[bootstrap] 请确认 MySQL 可用、bia 用户有库权限后再重试；或加 --force 强制重建。")
        return 1

    print("\n[bootstrap] 全部通过：两库关键表与行数均满足离线确定性归因所需，"
          "关键指标与证据链可正常产出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
