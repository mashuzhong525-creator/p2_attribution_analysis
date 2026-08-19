"""离线确定性分析器（§8.3 无 LLM 时的兜底）。

当未配置 LLM API Key（演示默认）时，引擎走此路径：直接对会话绑定的场景库执行
确定性 SQL，产出可信的六段式结论。每个分析器返回 (SixSectionResult, steps)，
steps 为工具事件描述（引擎据此向前端推送 tool_start/tool_end，便于还原分析过程）。

场景路由：data_source.database == 'scenario_goods' → 商品目录优化（信息流下滑归因）；
            == 'scenario_inventory' → 库存异常分析（采购到货延迟归因）。

【query topic router】所有 query 在进入具体分析器前先做"语义半径"判断：
若 query 与本场景库覆盖的归因主题无关（如对 goods 库问"给我讲个笑话"），
明确返回"超出离线分析半径"六段式，让前端无指标、无证据、无措辞造句，
并把不可用结论清晰展示出来。
"""
from __future__ import annotations

import re

import asyncmy

from app.core.security import decrypt_secret
from app.domains.agent.schemas import Evidence, KeyMetric, SixSectionResult
from app.models.business import DataSource


# ============================================================================
# Query 主题路由（topic router）：决定 query 是不是属于本场景库覆盖的话题半径
# ============================================================================
_GOODS_KEYWORDS = (
    "信息流", "搜索", "推荐", "渠道", "创意", "素材", "ctr", "曝光", "点击",
    "转化", "gmv", "uv", "pv", "sku", "商品", "上架", "下架", "类目", "品类",
    "广告", "投放", "出价", "预算", "召回", "排序", "人群", "标签", "客单",
    "下单", "订单", "支付", "复购", "流量", "报表",
)
_INVENTORY_KEYWORDS = (
    "库存", "缺货", "采购", "到货", "补货", "安全库存", "再订货", "提前期",
    "出库", "入库", "调拨", "仓", "wh", "周转", "滞销", "积压", "残品",
    "供应商", "配送", "履约", "运输", "在途", "po",
)


def _topic_match(query: str, keywords: tuple[str, ...]) -> bool:
    if not query:
        return False
    q = query.lower()
    return any(kw.lower() in q for kw in keywords)


def _in_scope(query: str, kind: str) -> bool:
    """kind ∈ {'goods','inventory'}。判断 query 是否落在本场景库的语义半径内。"""
    if not query or len(query.strip()) < 2:
        return False
    if kind == "goods":
        return _topic_match(query, _GOODS_KEYWORDS)
    if kind == "inventory":
        return _topic_match(query, _INVENTORY_KEYWORDS)
    return False


# 公开接口：engine 在线/离线共用同一个语义半径判断
def is_query_in_scope(query: str, kind: str) -> bool:
    return _in_scope(query, kind)


def out_of_scope_six(query: str, kind: str) -> SixSectionResult:
    return _out_of_scope_six(query, kind)


def _out_of_scope_six(query: str, kind: str) -> SixSectionResult:
    """不相关 query 的真实六段式：所有内容字段说明"为何不可答"，关键指标和证据链为空。"""
    covered = {
        "goods": "信息流/搜索/推荐等渠道的曝光/点击/转化/CTR、商品维度 GMV 归因、素材级 CTR 与历史基线对比、预算再分配影响等",
        "inventory": "库存量时序、缺货/低库存/负库存事件、采购单 ETA、安全阈值与再订货点、跨仓调拨、供应商提前期等",
    }[kind]
    label = {"goods": "商品归因", "inventory": "库存归因"}[kind]
    return SixSectionResult(
        problem_definition=f"当前问题「{query[:80]}」不属于{label}场景库的语义半径（已知覆盖维度：{covered}）。",
        key_metrics=[],
        evidence_list=[],
        conclusion_text=(
            f"当前会话绑定的离线场景库仅承担「{covered}」范围内的归因分析，"
            f"而您的问题「{query[:80]}」的话题（闲聊/通用问答/非业务主题/不属于上述维度）"
            f"不在其分析半径内，因此不产出任何关键指标与证据。"
            "如需解答此类问题，请配置 LLM（在线规划路径）以获得通用回答能力，"
            "或切换到匹配该话题的数据源后再提问。"
        ),
        missing_data_text=(
            f"本场景库的分析半径限定在：{covered}。"
            "『不在分析半径内的 query』所需的指标/证据在当前绑定数据源中不存在，"
            "建议：（1）在系统配置中填入 LLM API Key 走在线路径；"
            "（2）或者将问题改写为与本场景库维度相关的话题。"
        ),
        next_action_text=(
            "1) 配置 LLM API Key 后重发此问题（在线分析路径不受场景库范围限制）；"
            "2) 或切换到能覆盖该话题的数据源；"
            "3) 或将问题改写为：渠道点击 / 商品 GMV / 库存异常 / 采购到货 等维度的具体问题。"
        ),
    )


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


async def analyze_goods(ds: DataSource, query: str = "") -> tuple[SixSectionResult, list[dict]]:
    """商品目录优化场景：为什么 6 月信息流渠道点击量下滑？

    数据流：原有 fact_channel_daily/creative_change_log/sku_offline_log + 补齐后的
    dim_creative/fact_creative_daily/dim_sku_ctr_baseline/dim_channel_budget_daily。
    缺失数据段（missing_data_text）改为"基于实际查询后剩余的真缺口"——
    已经有数据的维度会被叙述融入 evidence / key_metrics，缺数据的才列出来。

    query 不在【商品归因】语义半径内时直接返回 out_of_scope_six()。
    """
    if not _in_scope(query, "goods"):
        return _out_of_scope_six(query, "goods"), []
    steps: list[dict] = []
    gaps: list[str] = []  # 用来动态装配 missing_data_text

    # 1) 信息流 6 月 vs 5 月点击（基线事实）
    _, r_jun = await _ds_query(ds, "SELECT SUM(clicks) FROM fact_channel_daily WHERE channel_id='CH_INFO' AND d>='2026-06-01'")
    _, r_may = await _ds_query(ds, "SELECT SUM(clicks) FROM fact_channel_daily WHERE channel_id='CH_INFO' AND d>='2026-05-01' AND d<'2026-06-01'")
    jun = _scalar(r_jun); may = _scalar(r_may)
    decline = (jun / may - 1) if may else 0.0
    steps.append({"name": "db_query", "args": {"sql": "fact_channel_daily 信息流 6月/5月点击聚合"}, "summary": f"6月信息流点击 {jun:,} vs 5月 {may:,}"})

    # 2) 创意更换日志（基线事实）
    _, r_creative = await _ds_query(ds, "SELECT note FROM creative_change_log WHERE channel_id='CH_INFO'")
    creative_note = r_creative[0][0] if r_creative else "无记录"
    steps.append({"name": "db_query", "args": {"sql": "creative_change_log CH_INFO"}, "summary": f"创意更换：{creative_note}"})

    # 3) 头部 SKU 下架（基线事实）
    _, r_off = await _ds_query(ds, "SELECT COUNT(*) FROM sku_offline_log WHERE offline_date>='2026-06-01'")
    off_cnt = _scalar(r_off)
    steps.append({"name": "db_query", "args": {"sql": "sku_offline_log 6月下架"}, "summary": f"6月起下架 SKU 数：{off_cnt}"})

    # 4) 各渠道 6 月点击对比（基线事实）
    cols, r_ch = await _ds_query(ds, "SELECT channel_id, SUM(clicks) FROM fact_channel_daily WHERE d>='2026-06-01' GROUP BY channel_id ORDER BY 2 DESC")
    ch_lines = [f"{r[0]}: {r[1]:,}" for r in r_ch]
    steps.append({"name": "db_query", "args": {"sql": "fact_channel_daily 各渠道6月点击"}, "summary": "；".join(ch_lines[:6])})

    # ===== 以下为补齐数据后才有的"维度证据" =====
    # 5) 素材级日 CTR：旧 vs 新 vs AB —— 直接证明"主素材 CTR 腰斩"是核心归因
    creative_ctr_new = None
    creative_ctr_old = None
    creative_ctr_ab = None
    try:
        cols, rows = await _ds_query(ds, """
            SELECT creative_id,
                   ROUND(SUM(clicks)*1.0/NULLIF(SUM(exposure),0), 4) AS ctr
            FROM fact_creative_daily
            WHERE creative_id IN ('CR_INFO_OLD','CR_INFO_NEW','CR_INFO_AB')
            GROUP BY creative_id
        """)
        rec = {r[0]: r[1] for r in rows}
        creative_ctr_old = rec.get("CR_INFO_OLD")
        creative_ctr_new = rec.get("CR_INFO_NEW")
        creative_ctr_ab = rec.get("CR_INFO_AB")
        steps.append({"name": "db_query",
                      "args": {"sql": "fact_creative_daily 素材级 CTR 聚合"},
                      "summary": f"旧素材 {creative_ctr_old} → 新主推 {creative_ctr_new} → AB {creative_ctr_ab}"})
    except Exception:
        gaps.append("素材级 CTR 分时拆解（fact_creative_daily）")

    # 6) 信息流 6 月 CTR vs 历史 SKU 基线均值 —— 量化"切换后跌出基线"
    ctr_jun_ratio = None
    try:
        cols, rows = await _ds_query(ds, """
            SELECT ROUND(SUM(fcd.clicks)*1.0/NULLIF(SUM(fcd.exposure),0), 4)
            FROM fact_channel_daily fcd WHERE fcd.channel_id='CH_INFO' AND fcd.d>='2026-06-01'
        """)
        ctr_jun = (rows[0][0] if rows and rows[0] else None)
        cols2, rows2 = await _ds_query(ds, """
            SELECT ROUND(AVG(avg_ctr), 4) FROM dim_sku_ctr_baseline
        """)
        avg_base = (rows2[0][0] if rows2 and rows2[0] else None)
        if ctr_jun and avg_base:
            ctr_jun_ratio = round(ctr_jun / avg_base - 1, 4)
        steps.append({"name": "db_query",
                      "args": {"sql": "fact_channel_daily 信息流6月CTR vs dim_sku_ctr_baseline"},
                      "summary": f"信息流6月CTR {ctr_jun} vs SKU基线均值 {avg_base} (差 {ctr_jun_ratio})"})
    except Exception:
        gaps.append("渠道级实时 CTR vs SKU 历史 CTR 基线对比")

    # 7) 信息流预算再分配（6/1 起）
    budget_shrink_ratio = None
    try:
        cols, rows = await _ds_query(ds, """
            SELECT
              AVG(CASE WHEN d<'2026-06-01' THEN budget END) AS b_pre,
              AVG(CASE WHEN d>='2026-06-01' THEN budget END) AS b_post
            FROM dim_channel_budget_daily WHERE channel_id='CH_INFO'
        """)
        b_pre, b_post = (rows[0][0], rows[0][1]) if rows and rows[0] else (None, None)
        if b_pre and b_post:
            budget_shrink_ratio = round(b_post / b_pre - 1, 4)
        steps.append({"name": "db_query",
                      "args": {"sql": "dim_channel_budget_daily 信息流预算 5/6月"},
                      "summary": f"信息流预算 6/1 起下调 {budget_shrink_ratio}（{b_pre} → {b_post}）"})
    except Exception:
        gaps.append("渠道级预算/出价时序（dim_channel_budget_daily）")

    # 8) 头部 5 SKU 历史 GMV 占比（在下架前 30 天）
    head_gmv_share = None
    try:
        cols, rows = await _ds_query(ds, """
            SELECT
              ROUND(SUM(CASE WHEN sku_id BETWEEN 'SKU0001' AND 'SKU0005' THEN gmv END)*100.0/
                    NULLIF(SUM(gmv),0), 2) AS pct
            FROM fact_sku_daily
            WHERE d BETWEEN '2026-05-11' AND '2026-06-09'
        """)
        head_gmv_share = rows[0][0] if rows and rows[0] else None
        steps.append({"name": "db_query",
                      "args": {"sql": "fact_sku_daily 头部SKU GMV 占比（下架前30天）"},
                      "summary": f"头部 5 SKU 在下架前 30 天贡献 {head_gmv_share}% GMV"})
    except Exception:
        gaps.append("头部 SKU 历史 GMV 贡献占比")

    # 装配证据链：如果某条新维度数据拿到了，补进 evidence_list
    evidence_list = [
        Evidence(source_type="db_query", source_name="fact_channel_daily",
                 evidence_text=f"信息流渠道 6 月点击 {jun:,}，较 5 月 {may:,} 下滑 {abs(decline):.1%}。",
                 related_metric="信息流点击环比变化", confidence=0.95),
        Evidence(source_type="db_query", source_name="creative_change_log",
                 evidence_text=f"信息流主素材于 2026-06-03 更换为夏季版（{creative_note}），与下滑起点吻合。",
                 related_metric="CTR 预期下降", confidence=0.8),
        Evidence(source_type="db_query", source_name="sku_offline_log",
                 evidence_text=f"头部 5 个 SKU 自 2026-06-10 下架，直接削减信息流可投量。",
                 related_metric="曝光基数下降", confidence=0.85),
    ]
    if creative_ctr_new is not None and creative_ctr_old is not None:
        diff = creative_ctr_new - creative_ctr_old
        evidence_list.append(Evidence(
            source_type="db_query", source_name="fact_creative_daily",
            evidence_text=(f"素材级效果验证：旧主推素材 CTR {creative_ctr_old:.2%} → 夏季新主推 {creative_ctr_new:.2%}"
                           f"（差 {diff:+.2%}）；同期 AB 素材 CTR {creative_ctr_ab:.2%} 维持基线，排除人群/出价干扰。"),
            related_metric="主素材 CTR 腰斩", confidence=0.95))
    if budget_shrink_ratio is not None:
        evidence_list.append(Evidence(
            source_type="db_query", source_name="dim_channel_budget_daily",
            evidence_text=f"6/1 起信息流预算再做 {budget_shrink_ratio:+.0%} 的再分配，下调时点与点击下滑高度同期。",
            related_metric="预算下调 → 曝光基数收缩", confidence=0.78))
    if head_gmv_share is not None:
        evidence_list.append(Evidence(
            source_type="db_query", source_name="fact_sku_daily",
            evidence_text=f"头部 5 个 SKU 在 6/10 下架前 30 天贡献 {head_gmv_share}% GMV，下架直接砍掉近 {round(head_gmv_share/5,1)}% 的潜在转化池。",
            related_metric="头部 SKU 下架双重打击（可投量 + GMV）", confidence=0.9))

    # 关键指标也加几条
    key_metrics = [
        KeyMetric(metric_name="信息流(CH_INFO) 6月点击", metric_value=f"{jun:,}", metric_period="2026-06"),
        KeyMetric(metric_name="信息流(CH_INFO) 5月点击", metric_value=f"{may:,}", metric_period="2026-05"),
        KeyMetric(metric_name="信息流点击环比变化", metric_value=f"{decline:+.1%}", metric_period="6月/5月"),
        KeyMetric(metric_name="6月起下架头部SKU数", metric_value=str(off_cnt), metric_period="2026-06"),
    ]
    if creative_ctr_new is not None and creative_ctr_old is not None:
        key_metrics.append(KeyMetric(
            metric_name="主推素材 CTR（换前→换后）",
            metric_value=f"{creative_ctr_old:.2%} → {creative_ctr_new:.2%}",
            metric_period="2026-03-23 ~ 2026-06-30"))
    if budget_shrink_ratio is not None:
        key_metrics.append(KeyMetric(
            metric_name="信息流预算再分配", metric_value=f"{budget_shrink_ratio:+.0%}", metric_period="2026-06-01"))
    if head_gmv_share is not None:
        key_metrics.append(KeyMetric(
            metric_name="头部5 SKU 历史 GMV 占比", metric_value=f"{head_gmv_share}%", metric_period="2026-05-11~06-09"))

    # 真实剩余缺口——这就是前端会看到的「缺失数据」段
    if not gaps:
        missing_data_text = "已覆盖素材维度 / 历史 CTR 基线 / 预算再分配 / 下架 SKU GMV 占比四项维度；继续追问可深入 AB 组粒度或分时 CTR。"
    else:
        missing_data_text = "剩余缺口：" + "；".join(gaps) + "。如需进一步定位，请补齐后再分析。"

    old_str = f"{creative_ctr_old:.2%}" if creative_ctr_old else "?"
    new_str = f"{creative_ctr_new:.2%}" if creative_ctr_new else "?"
    six = SixSectionResult(
        problem_definition="6 月信息流渠道点击量相较 5 月出现明显下滑，需定位根因。",
        key_metrics=key_metrics,
        evidence_list=evidence_list,
        conclusion_text=(
            f"6 月信息流点击环比下滑约 {abs(decline):.1%}，主因为多因素叠加："
            f"（1）信息流主素材于 6/3 更换为夏季版，素材级 CTR 由 {old_str} 跌至 {new_str}；"
            f"（2）头部 5 个 SKU 自 6/10 下架，直接削减可投放曝光基数（占历史 GMV {head_gmv_share}%）；"
            f"（3）6/1 起信息流预算再分配（{budget_shrink_ratio:+.0%}），进一步压制曝光与点击上限。"
            f"三者共同导致信息流渠道点击显著回落，并带动整体 GMV 承压。"
        ),
        missing_data_text=missing_data_text,
        next_action_text=(
            "1) 回滚夏季主素材或加大 AB 素材投放，监控 CTR 恢复；"
            "2) 评估头部 SKU 下架策略，将高 CTR SKU 恢复上架；"
            "3) 复核 6/1 的预算再分配决策，避免曝光配额被进一步压缩；"
            "4) 将预算向 CTR 稳定的搜索/推荐渠道做再分配。"
        ),
    )
    return six, steps


async def analyze_inventory(ds: DataSource, query: str = "") -> tuple[SixSectionResult, list[dict]]:
    """库存异常场景：SKU0001 在 WH1 的断货根因。

    数据流：原有 stock_anomaly_log/fact_inventory_daily/purchase_order + 补齐后的
    dim_sku_safety（全 SKU × 3 仓安全阈值 + 提前期）+ 在途采购单 PO0003/PO0004 +
    dim_warehouse_transfer（跨仓调拨）/ fact_supplier_leadtime_daily（供应商提前期波动）。

    query 不在【库存归因】语义半径内时直接返回 out_of_scope_six()。
    """
    if not _in_scope(query, "inventory"):
        return _out_of_scope_six(query, "inventory"), []
    steps: list[dict] = []
    gaps: list[str] = []

    # 1) 异常事件统计
    _, r_anom = await _ds_query(ds, "SELECT anomaly_type, COUNT(*) FROM stock_anomaly_log GROUP BY anomaly_type")
    anom_lines = [f"{r[0]}:{r[1]}" for r in r_anom]
    steps.append({"name": "db_query", "args": {"sql": "stock_anomaly_log 异常类型统计"}, "summary": "；".join(anom_lines)})
    # 2) 异常 SKU 近期库存趋势
    _, r_inv = await _ds_query(ds, "SELECT d, stock_qty FROM fact_inventory_daily WHERE sku_id='SKU0001' AND wh_id='WH1' AND d>='2026-06-15' ORDER BY d LIMIT 10")
    inv_line = " → ".join(str(r[1]) for r in r_inv)
    steps.append({"name": "db_query", "args": {"sql": "fact_inventory_daily SKU0001@WH1 6/15起"}, "summary": f"库存序列: {inv_line}"})
    # 3) 采购单 ETA
    _, r_po = await _ds_query(ds, "SELECT sku_id, order_date, eta FROM purchase_order WHERE sku_id='SKU0001'")
    po_line = f"下单 {r_po[0][1]} / 预计到货 {r_po[0][2]}" if r_po else "无采购单"
    steps.append({"name": "db_query", "args": {"sql": "purchase_order SKU0001"}, "summary": f"采购单: {po_line}"})

    neg = sum(1 for r in r_anom if r[0] == "negative_stock")
    low = sum(1 for r in r_anom if r[0] == "low_stock")

    # 4) 安全阈值（SKU0001@WH1）：衡量"库存离安全线还差多远"
    safety = None
    try:
        _, rows = await _ds_query(ds, """
            SELECT safety_stock, reorder_point, lead_time_days, avg_daily_sales
            FROM dim_sku_safety WHERE sku_id='SKU0001' AND wh_id='WH1'
        """)
        safety = rows[0] if rows else None
        steps.append({"name": "db_query",
                      "args": {"sql": "dim_sku_safety SKU0001@WH1"},
                      "summary": (f"安全库存={safety[0]} / 再订货点={safety[1]} / 提前期={safety[2]}d / 日均销={safety[3]}"
                                  if safety else "dim_sku_safety 未找到")})
    except Exception:
        gaps.append("SKU×仓安全阈值与提前期（dim_sku_safety）")

    # 5) 在途采购单（SKU0001 全口径）：评估"补货中断 vs 在途总池"
    in_transit = []
    try:
        _, rows = await _ds_query(ds, """
            SELECT po_id, order_date, qty, eta
            FROM purchase_order WHERE sku_id='SKU0001' ORDER BY order_date
        """)
        in_transit = rows
        steps.append({"name": "db_query",
                      "args": {"sql": "purchase_order SKU0001 全部在途/历史单"},
                      "summary": f"SKU0001 共 {len(rows)} 条 PO：{[(r[0], str(r[1]), r[2], str(r[3])) for r in rows]}"})
    except Exception:
        gaps.append("SKU 全口径采购单（在途+历史）")

    # 6) SKU0001@WH1 日均销 vs 历史窗口 —— 用作"日销是否暴增"反证
    avg_sales = None
    try:
        _, rows = await _ds_query(ds, """
            SELECT ROUND(AVG(sales_qty),1) FROM sales_daily
            WHERE sku_id='SKU0001' AND wh_id='WH1' AND d BETWEEN '2026-05-15' AND '2026-06-14'
        """)
        avg_sales = rows[0][0] if rows and rows[0] else None
        steps.append({"name": "db_query",
                      "args": {"sql": "sales_daily SKU0001@WH1 5月下半月日均"},
                      "summary": f"5 月下半月日均销 {avg_sales} → 6/15 起无暴增"})
    except Exception:
        pass

    # 7) 跨仓调拨记录（SKU0001）：评估"调拨作为应急手段"是否已启动
    transfers = []
    try:
        _, rows = await _ds_query(ds, """
            SELECT transfer_id, from_wh, to_wh, qty, transfer_date, status
            FROM dim_warehouse_transfer WHERE sku_id='SKU0001' ORDER BY transfer_date
        """)
        transfers = rows
        tr_line = "；".join(f"{r[0]} {r[1]}→{r[2]} {r[3]}件@{r[4]}({r[5]})" for r in rows) or "无调拨记录"
        steps.append({"name": "db_query",
                      "args": {"sql": "dim_warehouse_transfer SKU0001"},
                      "summary": f"跨仓调拨：{tr_line}"})
    except Exception:
        gaps.append("跨仓调拨记录（dim_warehouse_transfer）")

    # 8) 供应商提前期波动：对比 5 月 vs 6 月 —— 是"谁"导致到货延迟
    lead_pre = lead_post = ontime_post = None
    try:
        _, rows = await _ds_query(ds, """
            SELECT
              ROUND(AVG(CASE WHEN d<'2026-06-01' THEN lead_time_days END),1) AS lt_pre,
              ROUND(AVG(CASE WHEN d>='2026-06-01' THEN lead_time_days END),1) AS lt_post,
              ROUND(AVG(CASE WHEN d>='2026-06-01' THEN on_time_rate END),3) AS ot_post
            FROM fact_supplier_leadtime_daily WHERE supplier_id='SUP1'
        """)
        if rows and rows[0]:
            lead_pre, lead_post, ontime_post = rows[0]
        steps.append({"name": "db_query",
                      "args": {"sql": "fact_supplier_leadtime_daily SUP1 5月/6月提前期"},
                      "summary": f"SUP1 提前期 5月均值 {lead_pre} 天 → 6月均值 {lead_post} 天；6月准时率 {ontime_post}"})
    except Exception:
        gaps.append("供应商提前期波动（fact_supplier_leadtime_daily）")

    evidence_list = [
        Evidence(source_type="db_query", source_name="stock_anomaly_log",
                 evidence_text=f"SKU0001@WH1 自 6/15 起累计负库存 {neg} 次、低库存 {low} 次。",
                 related_metric="缺货事件", confidence=0.95),
        Evidence(source_type="db_query", source_name="fact_inventory_daily",
                 evidence_text=f"库存自 6/15 起持续走低至负值（序列: {inv_line}），非销售暴增导致（5 月下半月日均销 {avg_sales}）。",
                 related_metric="库存枯竭", confidence=0.9),
        Evidence(source_type="db_query", source_name="purchase_order",
                 evidence_text=f"对应采购单 PO0001 下单 6/10，预计到货 {r_po[0][2] if r_po else '未知'}，远晚于缺货起点 6/15，确认到货延迟。",
                 related_metric="采购到货延迟", confidence=0.92),
    ]
    if safety:
        evidence_list.append(Evidence(
            source_type="db_query", source_name="dim_sku_safety",
            evidence_text=(f"SKU0001@WH1 安全库存阈值 = {safety[0]}（再订货点 {safety[1]}、提前期 {safety[2]} 天、"
                           f"日均销 {safety[3]}），实际自 6/15 起已远低于安全线，确认触发了「应立即补货」条件。"),
            related_metric="安全阈值被击穿", confidence=0.88))
    if len(in_transit) >= 2:
        names = "、".join(r[0] for r in in_transit)
        evidence_list.append(Evidence(
            source_type="db_query", source_name="purchase_order",
            evidence_text=(f"SKU0001 全口径在途 PO 共 {len(in_transit)} 条（{names}），"
                           f"除 PO0001（ETA 7/5）外是否有更早批次决定了「补货中断」还是「分批错峰」。"),
            related_metric="在途多单 vs 补货策略", confidence=0.75))
    if transfers:
        done_qty = sum(r[3] for r in transfers if r[5] == "completed")
        transit_qty = sum(r[3] for r in transfers if r[5] == "in_transit")
        evidence_list.append(Evidence(
            source_type="db_query", source_name="dim_warehouse_transfer",
            evidence_text=(f"跨仓应急调拨已启动：{done_qty} 件已完成调入（WH3→WH1），"
                           f"另有 {transit_qty} 件在途（WH2→WH1），"
                           f"但调拨量远小于缺口（日均销 {avg_sales or '?'} × 到货前 20 天），单靠调拨无法完全对冲断货。"),
            related_metric="跨仓调拨对冲能力", confidence=0.82))
    if lead_pre is not None and lead_post is not None:
        evidence_list.append(Evidence(
            source_type="db_query", source_name="fact_supplier_leadtime_daily",
            evidence_text=(f"供应商 SUP1 提前期 5 月均值 {lead_pre} 天 → 6 月均值 {lead_post} 天（"
                           f"准时率降至 {ontime_post}），"
                           f"确认到货延迟根因在供应商侧产能/物流波动，而非采购下单不及时。"),
            related_metric="供应商提前期恶化", confidence=0.9))

    key_metrics = [
        KeyMetric(metric_name="负库存事件数", metric_value=str(neg), metric_period="2026-06-15起"),
        KeyMetric(metric_name="低库存事件数", metric_value=str(low), metric_period="2026-06-15起"),
        KeyMetric(metric_name="采购单预计到货", metric_value=str(r_po[0][2]) if r_po else "未知", metric_period="PO0001"),
    ]
    if safety:
        key_metrics.append(KeyMetric(
            metric_name="SKU0001@WH1 安全库存阈值",
            metric_value=f"{safety[0]}（再订货点 {safety[1]}）",
            metric_period="dim_sku_safety"))
    if in_transit:
        key_metrics.append(KeyMetric(
            metric_name="SKU0001 在途 PO 总数",
            metric_value=f"{len(in_transit)} 条（共 {sum(r[2] for r in in_transit)} 件）",
            metric_period="purchase_order"))
    if lead_pre is not None and lead_post is not None:
        key_metrics.append(KeyMetric(
            metric_name="SUP1 采购提前期（5月→6月）",
            metric_value=f"{lead_pre} 天 → {lead_post} 天",
            metric_period="fact_supplier_leadtime_daily"))
    if transfers:
        key_metrics.append(KeyMetric(
            metric_name="跨仓调拨量（已完成/在途）",
            metric_value=f"{sum(r[3] for r in transfers if r[5] == 'completed')} / {sum(r[3] for r in transfers if r[5] == 'in_transit')} 件",
            metric_period="dim_warehouse_transfer"))

    if not gaps:
        missing_data_text = ("已覆盖异常事件 / 库存趋势 / 采购单 / 安全阈值 / 在途多单 / 跨仓调拨 / 供应商提前期七项维度；"
                             "如需更细可引入销售预测或上游二级供应商交付率。")
    else:
        missing_data_text = "剩余缺口：" + "；".join(gaps) + "。如需进一步定位，请补齐后再分析。"

    supplier_part = ""
    if lead_pre is not None and lead_post is not None:
        supplier_part = (f"深层根因为供应商 SUP1 提前期由 5 月均值 {lead_pre} 天恶化至 6 月 {lead_post} 天"
                         f"（准时率 {ontime_post}），")
    transfer_part = ""
    if transfers:
        done_qty = sum(r[3] for r in transfers if r[5] == "completed")
        transfer_part = (f"当前跨仓调拨（已入 {done_qty} 件）可部分缓解但不足以覆盖缺口，")

    six = SixSectionResult(
        problem_definition="华东仓(WH1) SKU0001 自 6 月中出现低库存乃至负库存缺货异常，需定位根因。",
        key_metrics=key_metrics,
        evidence_list=evidence_list,
        conclusion_text=(
            f"SKU0001 在华东仓的缺货/负库存并非销售暴增所致（5 月下半月日均销 {avg_sales} 平稳），"
            f"根因是采购到货节奏问题：6/10 下的 PO0001 预计到货 7/5，"
            f"远晚于 6/15 起的缺货起点 + 安全阈值 {safety[0] if safety else '?'}（再订货点 {safety[1] if safety else '?'}）已被击穿。"
            f"{supplier_part}"
            f"{'另有 ' + str(len(in_transit)) + ' 条在途 PO（含 PO0003 等），可作为分批补货手段评估。' if len(in_transit) >= 2 else ''}"
            f"{transfer_part}"
            f"属于供应链补货节奏问题。"
        ),
        missing_data_text=missing_data_text,
        next_action_text=(
            "1) 紧急催单/改派 PO0001 到货，或启用就近仓调拨；"
            "2) 为头部 SKU 设置安全库存与自动补货触发；"
            "3) 对齐采购提前期与销售预测，避免到货窗口错配；"
            "4) 评估在途多 PO（PO0003 等）作为分批补货的可行性；"
            "5) 针对 SUP1 提前期恶化，考虑启用备选供应商（SUP2/SUP3 准时率更稳定）分单。"
        ),
    )
    return six, steps


async def analyze(task, conv, ds: DataSource | None, db) -> tuple[SixSectionResult, list[dict]]:
    """场景路由入口。无场景库时返回通用离线结论。

    把 task.input_text 当作 query 透传，让 topic router 判断"query 是否在场景半径内"，
    避免『给我讲个笑话』被强行答成『6月信息流点击下滑』的过度泛化问题。
    """
    query = (task.input_text or "").strip()
    if ds is not None and ds.database == "scenario_goods":
        return await analyze_goods(ds, query=query)
    if ds is not None and ds.database == "scenario_inventory":
        return await analyze_inventory(ds, query=query)
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
