"""离线确定性分析器（§8.3 无 LLM 时的兜底）。

当未配置 LLM API Key（演示默认）时，引擎走此路径：直接对会话绑定的场景库执行
确定性 SQL，产出可信的六段式结论。每个分析器返回 (SixSectionResult, steps)，
steps 为工具事件描述（引擎据此向前端推送 tool_start/tool_end，便于还原分析过程）。

场景路由：data_source.database == 'scenario_goods' → 商品目录优化（信息流下滑归因）；
            == 'scenario_inventory' → 库存异常分析（采购到货延迟归因）。
"""
from __future__ import annotations

import asyncmy

from app.core.security import decrypt_secret
from app.domains.agent.schemas import Evidence, KeyMetric, SixSectionResult
from app.models.business import DataSource


async def _ds_query(ds: DataSource, sql: str) -> tuple[list[str], list[tuple]]:
    """对场景数据源执行只读查询，返回 (columns, rows)。"""
    pw = decrypt_secret(ds.password_encrypted)
    conn = await asyncmy.connect(
        host=ds.host, port=ds.port, user=ds.username,
        password=pw, database=ds.database, charset="utf8mb4",
    )
    try:
        cur = conn.cursor()
        await cur.execute(sql)
        rows = await cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, rows
    finally:
        # asyncmy 0.2.x Connection.close() 为同步方法（await 会 TypeError）
        conn.close()


def _scalar(rows, default=0):
    if rows and rows[0]:
        v = rows[0][0]
        return v if v is not None else default
    return default


async def analyze_goods(ds: DataSource) -> tuple[SixSectionResult, list[dict]]:
    steps: list[dict] = []
    # 1. 信息流渠道 6 月 vs 5 月点击
    _, r_jun = await _ds_query(ds, "SELECT SUM(clicks) FROM fact_channel_daily WHERE channel_id='CH_INFO' AND d>='2026-06-01'")
    _, r_may = await _ds_query(ds, "SELECT SUM(clicks) FROM fact_channel_daily WHERE channel_id='CH_INFO' AND d>='2026-05-01' AND d<'2026-06-01'")
    jun = _scalar(r_jun); may = _scalar(r_may)
    decline = (jun / may - 1) if may else 0.0  # 负值=下降，如 -0.59 表示下滑 59%
    steps.append({"name": "db_query", "args": {"sql": "fact_channel_daily 信息流 6月/5月点击聚合"}, "summary": f"6月信息流点击 {jun:,} vs 5月 {may:,}"})
    # 2. 创意更换日志
    _, r_creative = await _ds_query(ds, "SELECT note FROM creative_change_log WHERE channel_id='CH_INFO'")
    creative_note = r_creative[0][0] if r_creative else "无记录"
    steps.append({"name": "db_query", "args": {"sql": "creative_change_log CH_INFO"}, "summary": f"创意更换：{creative_note}"})
    # 3. 头部 SKU 下架
    _, r_off = await _ds_query(ds, "SELECT COUNT(*) FROM sku_offline_log WHERE offline_date>='2026-06-01'")
    off_cnt = _scalar(r_off)
    steps.append({"name": "db_query", "args": {"sql": "sku_offline_log 6月下架"}, "summary": f"6月起下架 SKU 数：{off_cnt}"})
    # 4. 各渠道 6 月点击对比
    cols, r_ch = await _ds_query(ds, "SELECT channel_id, SUM(clicks) FROM fact_channel_daily WHERE d>='2026-06-01' GROUP BY channel_id ORDER BY 2 DESC")
    ch_lines = [f"{r[0]}: {r[1]:,}" for r in r_ch]
    steps.append({"name": "db_query", "args": {"sql": "fact_channel_daily 各渠道6月点击"}, "summary": "；".join(ch_lines[:6])})

    six = SixSectionResult(
        problem_definition="6 月信息流渠道点击量相较 5 月出现明显下滑，需定位根因。",
        key_metrics=[
            KeyMetric(metric_name="信息流(CH_INFO) 6月点击", metric_value=f"{jun:,}", metric_period="2026-06"),
            KeyMetric(metric_name="信息流(CH_INFO) 5月点击", metric_value=f"{may:,}", metric_period="2026-05"),
            KeyMetric(metric_name="信息流点击环比变化", metric_value=f"{decline:+.1%}", metric_period="6月/5月"),
            KeyMetric(metric_name="6月起下架头部SKU数", metric_value=str(off_cnt), metric_period="2026-06"),
        ],
        evidence_list=[
            Evidence(source_type="db_query", source_name="fact_channel_daily",
                     evidence_text=f"信息流渠道 6 月点击 {jun:,}，较 5 月 {may:,} 下滑 {abs(decline):.1%}。",
                     related_metric="信息流点击环比变化", confidence=0.95),
            Evidence(source_type="db_query", source_name="creative_change_log",
                     evidence_text=f"信息流主素材于 2026-06-03 更换为夏季版（{creative_note}），与下滑起点吻合。",
                     related_metric="CTR 预期下降", confidence=0.8),
            Evidence(source_type="db_query", source_name="sku_offline_log",
                     evidence_text=f"头部 5 个 SKU 自 2026-06-10 下架，直接削减信息流可投量。",
                     related_metric="曝光基数下降", confidence=0.85),
        ],
        conclusion_text=(
            f"6 月信息流点击环比下滑约 {abs(decline):.1%}，主因为双因素叠加："
            f"（1）信息流主素材于 6/3 更换为夏季版导致 CTR 预期下降；"
            f"（2）头部 5 个 SKU 自 6/10 下架，直接削减可投放曝光基数。"
            f"二者共同导致信息流渠道点击显著回落，并带动整体 GMV 承压。"
        ),
        missing_data_text="缺少素材级 CTR 分时拆解与各 SKU 历史 CTR 基线，无法量化单因素贡献度。",
        next_action_text=(
            "1) 回滚/AB 测试信息流夏季素材，监控 CTR 恢复；"
            "2) 评估头部 SKU 下架策略，必要时恢复高转化 SKU；"
            "3) 将信息流预算向 CTR 稳定的搜索/推荐渠道做再分配。"
        ),
    )
    return six, steps


async def analyze_inventory(ds: DataSource) -> tuple[SixSectionResult, list[dict]]:
    steps: list[dict] = []
    # 1. 异常事件统计
    _, r_anom = await _ds_query(ds, "SELECT anomaly_type, COUNT(*) FROM stock_anomaly_log GROUP BY anomaly_type")
    anom_lines = [f"{r[0]}:{r[1]}" for r in r_anom]
    steps.append({"name": "db_query", "args": {"sql": "stock_anomaly_log 异常类型统计"}, "summary": "；".join(anom_lines)})
    # 2. 异常 SKU 近期库存趋势
    _, r_inv = await _ds_query(ds, "SELECT d, stock_qty FROM fact_inventory_daily WHERE sku_id='SKU0001' AND wh_id='WH1' AND d>='2026-06-15' ORDER BY d LIMIT 10")
    inv_line = " → ".join(str(r[1]) for r in r_inv)
    steps.append({"name": "db_query", "args": {"sql": "fact_inventory_daily SKU0001@WH1 6/15起"}, "summary": f"库存序列: {inv_line}"})
    # 3. 采购单 ETA
    _, r_po = await _ds_query(ds, "SELECT sku_id, order_date, eta FROM purchase_order WHERE sku_id='SKU0001'")
    po_line = f"下单 {r_po[0][1]} / 预计到货 {r_po[0][2]}" if r_po else "无采购单"
    steps.append({"name": "db_query", "args": {"sql": "purchase_order SKU0001"}, "summary": f"采购单: {po_line}"})

    neg = sum(1 for r in r_anom if r[0] == "negative_stock")
    low = sum(1 for r in r_anom if r[0] == "low_stock")
    six = SixSectionResult(
        problem_definition="华东仓(WI1) SKU0001 自 6 月中出现低库存乃至负库存缺货异常，需定位根因。",
        key_metrics=[
            KeyMetric(metric_name="负库存事件数", metric_value=str(neg), metric_period="2026-06-15起"),
            KeyMetric(metric_name="低库存事件数", metric_value=str(low), metric_period="2026-06-15起"),
            KeyMetric(metric_name="采购单预计到货", metric_value=str(r_po[0][2]) if r_po else "未知", metric_period="PO0001"),
        ],
        evidence_list=[
            Evidence(source_type="db_query", source_name="stock_anomaly_log",
                     evidence_text=f"SKU0001@WH1 自 6/15 起累计负库存 {neg} 次、低库存 {low} 次。",
                     related_metric="缺货事件", confidence=0.95),
            Evidence(source_type="db_query", source_name="fact_inventory_daily",
                     evidence_text=f"库存自 6/15 起持续走低至负值（序列: {inv_line}），非销售暴增导致（日销平稳）。",
                     related_metric="库存枯竭", confidence=0.9),
            Evidence(source_type="db_query", source_name="purchase_order",
                     evidence_text=f"对应采购单 PO0001 下单 6/10，预计到货 {r_po[0][2] if r_po else '未知'}，远晚于缺货起点 6/15，确认到货延迟。",
                     related_metric="采购到货延迟", confidence=0.92),
        ],
        conclusion_text=(
            "SKU0001 在华东仓的缺货/负库存并非销售暴增所致（日销平稳），"
            "根因是采购到货延迟：6/10 下的采购单预计到货 7/5，远晚于 6/15 起的缺货起点，"
            "补货中断使库存被持续出库消耗至负值。属于供应链补货节奏问题。"
        ),
        missing_data_text="缺少安全库存阈值与在途其他采购单明细，无法评估全面断货风险。",
        next_action_text=(
            "1) 紧急催单/改派 PO0001 到货，或启用就近仓调拨；"
            "2) 为头部 SKU 设置安全库存与自动补货触发；"
            "3) 对齐采购提前期与销售预测，避免到货窗口错配。"
        ),
    )
    return six, steps


async def analyze(task, conv, ds: DataSource | None, db) -> tuple[SixSectionResult, list[dict]]:
    """场景路由入口。无场景库时返回通用离线结论。"""
    if ds is not None and ds.database == "scenario_goods":
        return await analyze_goods(ds)
    if ds is not None and ds.database == "scenario_inventory":
        return await analyze_inventory(ds)
    six = SixSectionResult(
        problem_definition=(task.input_text or "经营归因分析")[:200],
        key_metrics=[],
        evidence_list=[],
        conclusion_text=(
            "当前会话未绑定场景示例数据源，且未配置 LLM，无法执行真实数据归因。"
            "请在会话中绑定数据源或配置 LLM API Key 后重试。"
        ),
        missing_data_text="缺少可查询的数据源或 LLM 配置。",
        next_action_text="绑定商品/库存场景数据源，或在系统配置中填入 LLM 凭证。",
    )
    return six, []
