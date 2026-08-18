"""归因引擎（§4.7 / §8）。队列 worker 入口 run_task。

流程：
  running → message_start
        → [online: 规划/工具循环直至六段式] | [offline: 场景确定性分析]
        → message_delta 流式结论
        → 落库(assistant result 消息 + AnalysisResult + 更新会话)
        → result_ready → task success
取消/超时/异常 → 对应终态 + WS 事件 + task_logs 记账。
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.core.config import settings
from app.core.logging import get_logger, log_task
from app.core.uuid import uuid7_str
from app.domains.agent.analyzers import analyze
from app.domains.agent.llm import LlmClient
from app.domains.agent.prompts import build_system_prompt
from app.domains.agent.schemas import SixSectionResult, parse_six_section
from app.domains.agent.tools.flags import enabled_tool_flags
from app.domains.agent.tools.registry import ToolContext, registry
from app.domains.task.state_machine import TERMINAL
from app.domains.task.ws import push_event
from app.models.business import AnalysisResult, AnalysisTask, Conversation, DataSource, Message

logger = get_logger("agent.engine")

ROLE = "你是一名资深经营分析专家，擅长基于真实数据做归因分析，输出结构化六段式结论。"

WS_TYPES = {"message_start", "message_delta", "message_end", "tool_start", "tool_end",
            "result_ready", "task_status", "error", "cancelled"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _emit(db, task, msg_type: str, payload: dict) -> None:
    try:
        await push_event(task.conversation_id, msg_type, payload, task.id)
    except Exception:  # pragma: no cover - WS/Redis 故障不应中断分析
        logger.warning("WS 推送失败 task=%s type=%s", task.id, msg_type)


async def _alloc_seq(db, conv_id: str) -> int:
    cur = (await db.execute(
        select(func.max(Message.seq_no)).where(Message.conversation_id == conv_id)
    )).scalar()
    return (cur or 0) + 1


async def _build_messages(db, conv: Conversation, limit: int = 20) -> list[dict]:
    rows = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.deleted_at.is_(None))
        .order_by(Message.seq_no.desc())
        .limit(limit)
    )).scalars().all()
    rows = list(reversed(rows))
    out = []
    for m in rows:
        out.append({"role": m.role, "content": m.content or ""})
    return out


def _degrade(text: str) -> SixSectionResult:
    return SixSectionResult(
        problem_definition=(text or "经营归因分析")[:200],
        key_metrics=[],
        evidence_list=[],
        conclusion_text=text[:2000] or "（未能结构化输出）",
        missing_data_text="LLM 未返回合规六段式 JSON，已降级展示原始结论。",
        next_action_text="",
    )


def _to_markdown(six: SixSectionResult) -> str:
    lines = [
        f"# 经营归因分析",
        "",
        f"## 问题定义\n{six.problem_definition}",
        "",
        "## 关键指标",
    ]
    for m in six.key_metrics:
        lines.append(f"- **{m.metric_name}**：{m.metric_value} {m.metric_unit}（{m.metric_period}）")
    lines.append("")
    lines.append("## 证据链")
    for e in six.evidence_list:
        lines.append(f"- [{e.source_name}] {e.evidence_text}（置信度 {e.confidence:.2f}）")
    lines.append("")
    lines.append(f"## 归因结论\n{six.conclusion_text}")
    if six.missing_data_text:
        lines.append(f"\n## 数据缺口\n{six.missing_data_text}")
    if six.next_action_text:
        lines.append(f"\n## 下一步建议\n{six.next_action_text}")
    return "\n".join(lines)


async def _persist(db, task: AnalysisTask, conv: Conversation, six: SixSectionResult) -> AnalysisResult:
    seq = await _alloc_seq(db, conv.id)
    db.add(Message(
        id=uuid7_str(), conversation_id=conv.id, role="assistant",
        message_type="result", content=six.conclusion_text, seq_no=seq,
    ))
    result = AnalysisResult(
        id=uuid7_str(), task_id=task.id, conversation_id=conv.id,
        problem_definition=six.problem_definition,
        key_metrics_json=[m.model_dump() for m in six.key_metrics],
        evidence_list_json=[e.model_dump() for e in six.evidence_list],
        conclusion_text=six.conclusion_text,
        missing_data_text=six.missing_data_text,
        next_action_text=six.next_action_text,
        result_markdown=_to_markdown(six),
    )
    db.add(result)
    conv.last_message_at = _utcnow()
    await db.commit()
    await db.refresh(result)
    return result


async def _stream_text(text: str, task: AnalysisTask) -> None:
    if not text:
        return
    for i in range(0, len(text), 30):
        await _emit(None, task, "message_delta", {"task_id": task.id, "delta_text": text[i:i + 30]})
        await asyncio.sleep(0.02)


def _build_system_prompt(conv, ds, trigger_query):
    """Build system prompt with business context, schema description, and explicit analysis instructions."""
    # Build schema description based on known scenario databases
    schema_info = ""
    if ds:
        db_name = ds.database
        if db_name == "scenario_goods":
            schema_info = (
                "【数据源架构】数据库：scenario_goods\n"
                "- dim_sku(sku_id, sku_name, category, brand, status, list_price) — SKU维度表\n"
                "- dim_channel(channel_id, channel_name, channel_type) — 渠道维度(信息流CH_INFO/搜索CH_SEARCH/推荐CH_RECO等)\n"
                "- fact_channel_daily(channel_id, d, exposure, clicks, conversions, gmv) — 渠道日度事实表\n"
                "- fact_sku_daily(sku_id, channel_id, d, exposure, clicks, conversions, gmv) — SKU日度明细\n"
                "- creative_change_log(channel_id, change_date, note) — 素材更换日志\n"
                "- sku_offline_log(sku_id, offline_date, reason) — SKU下架记录\n"
            )
        elif db_name == "scenario_inventory":
            schema_info = (
                "【数据源架构】数据库：scenario_inventory\n"
                "- fact_inventory_daily(d, sku_id, wh_id, stock_qty) — 每日库存\n"
                "- purchase_order(sku_id, order_date, eta, status) — 采购单\n"
                "- stock_anomaly_log(anomaly_type, sku_id, wh_id, d, qty) — 异常事件\n"
            )

    return (
        f"你是资深经营分析专家。当前用户的问题是：\n【{trigger_query}】\n\n"
        f"{schema_info}"
        "## 分析方法\n"
        "1. 使用 db_query 工具执行 SELECT 查询，直接从上述表中获取真实数据\n"
        "2. 关键SQL示例（根据问题选择）：\n"
        '   - "SELECT channel_id, SUM(clicks) FROM fact_channel_daily WHERE d BETWEEN ... GROUP BY channel_id"\n'
        '   - "SELECT COUNT(*) FROM sku_offline_log WHERE offline_date >= ..."\n'
        '   - "SELECT s.sku_id, SUM(c.clicks) FROM fact_channel_daily c JOIN dim_sku s ON c.channel_id = s.id ..."\n'
        "3. 用查询结果构建六段式结构化JSON结论\n\n"
        "## 输出格式\n"
        "你必须仅输出标准六段式 JSON（不要任何解释文字），直接给出最终答案：\n"
        f"{{\"problem_definition\": \"...\", \"key_metrics\": [{{\"metric_name\":\"...\",\"metric_value\":\"...\",\"metric_unit\":\"...\",\"metric_period\":\"...\"}}], "
        f"\"evidence_list\": [{{\"source_type\":\"db_query\",\"source_name\":\"...\",\"evidence_text\":\"...\",\"related_metric\":\"...\",\"confidence\":0.xx}}], "
        f"\"conclusion_text\": \"...\", \"missing_data_text\": \"...\", \"next_action_text\": \"...\"}}\n\n"
        "每个证据必须来自真实查询结果。置信度范围 0~1。\n"
        "先做2-3步精准查询获取关键数据，然后直接输出JSON。禁止盲目探索！"
    )


async def _run_online(db, task: AnalysisTask, conv: Conversation, tool_ctx: ToolContext, llm: LlmClient):
    ds = await db.get(DataSource, conv.data_source_id) if conv.data_source_id else None
    enabled = enabled_tool_flags()
    tool_list = [t["function"]["name"] for t in registry.schema(enabled)]

    # Extract latest user message as trigger query (not full conversation history)
    rows = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.deleted_at.is_(None))
        .order_by(Message.seq_no.desc())
        .limit(5)
    )).scalars().all()
    rows = list(reversed(rows))
    trigger_query = ""
    for m in rows:
        if m.role == "user" and m.content:
            trigger_query = m.content[:500]
            break
    if not trigger_query:
        trigger_query = task.input_text[:500] if task.input_text else "经营归因分析"

    # Build clean context: only last 3 assistant+tool cycles + trigger question
    ctx_messages = []
    if trigger_query:
        ctx_messages.append({"role": "user", "content": trigger_query})

    system = _build_system_prompt(conv, ds, trigger_query)

    max_steps = settings.AGENT_MAX_STEPS
    last_content = ""
    for step in range(max_steps):
        fresh = await db.get(AnalysisTask, task.id)
        if fresh and fresh.task_status == "cancelled":
            raise asyncio.CancelledError()
        task.current_step = step + 1
        await db.commit()
        await log_task(task.id, "INFO", "plan", f"规划第 {step + 1} 步", db)

        resp = await llm.chat_plan(db, task.id, conv.id, task.user_id, system, ctx_messages,
                                   tools=registry.schema(enabled))
        if isinstance(resp, dict) and resp.get("mock"):
            logger.warning("LLM 返回 mock，降级离线分析")
            return await analyze(task, conv, ds, db)
        tool_calls = resp.get("tool_calls") if isinstance(resp, dict) else None
        content = resp.get("content", "") if isinstance(resp, dict) else ""
        last_content = content
        if tool_calls:
            ctx_messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                await _emit(db, task, "tool_start", {"name": name, "args": args})
                res = await registry.run(name, tool_ctx, **args)
                await _emit(db, task, "tool_end",
                            {"name": name, "success": res.success, "summary": res.summary, "error": res.error})
                ctx_messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                 "name": name, "content": res.summary or res.error or ""})
        else:
            # No tool calls → try to parse as six-section JSON
            six = None
            errors = []
            try:
                six = parse_six_section(content)
            except Exception as e:
                errors.append(f"parse_fail: {e}")

            if six is None:
                # Repair attempt with strict re-instruction
                repair_resp = await llm.chat_plan(
                    db, task.id, conv.id, task.user_id,
                    system + "\n【最后重申】你必须仅输出合法JSON，不要任何解释、markdown标记或换行。",
                    ctx_messages + [{"role": "assistant", "content": content},
                                    {"role": "user", "content": "只输出六段式JSON，不要任何其他文字。"}],
                    tools=None,
                )
                c2 = repair_resp.get("content", "") if isinstance(repair_resp, dict) else ""
                try:
                    six = parse_six_section(c2)
                except Exception as e2:
                    errors.append(f"repair_fail: {e2}")
                    # Final fallback: use content as conclusion directly (no six-section but at least has something)
                    logger.warning("LLM未能产出六段式JSON，降级为原始内容。errors=%s", errors[:3])
                    six = SixSectionResult(
                        problem_definition=(trigger_query or "经营归因分析")[:200],
                        key_metrics=[],
                        evidence_list=[],
                        conclusion_text=(content or c2 or "（LLM未返回结构化结论）")[:5000],
                        missing_data_text="LLM 未返回合规六段式 JSON，已使用原始响应展示。",
                        next_action_text="",
                    )
            return six, []
    return _degrade(last_content), []


async def run_task(task_id: str) -> None:
    """队列 worker 入口（main.lifespan 注入 task_queue.start(run_task)）。"""
    async with db_session() as db:
        task = await db.get(AnalysisTask, task_id)
        if task is None or task.task_status in TERMINAL:
            return
        task.task_status = "running"
        task.started_at = _utcnow()
        task.current_step = 0
        await db.commit()
        try:
            await _emit(db, task, "message_start", {"task_id": task_id})
            llm = LlmClient()
            conv = await db.get(Conversation, task.conversation_id)
            if conv is None:
                raise RuntimeError("会话不存在")
            ds = await db.get(DataSource, conv.data_source_id) if conv.data_source_id else None
            tool_ctx = ToolContext(
                user_id=task.user_id,
                conversation_id=conv.id,
                data_source_id=conv.data_source_id,
                db=db,
                workspace_dir=f"{settings.DATA_ROOT}/workspace/{task.user_id}/{conv.id}",
            )
            # Prefer offline deterministic analyzer for known scenarios (reliable structured output),
            # use online LLM only for truly custom/unstructured questions beyond predefined scenarios.
            use_online = llm.available and ds is None
            if use_online:
                try:
                    six, steps = await _run_online(db, task, conv, tool_ctx, llm)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Online path failed (%s), falling back to offline", e)
                    use_online = False

            if not use_online:
                six, steps = await analyze(task, conv, ds, db)
                for s in steps:
                    await _emit(db, task, "tool_start", {"name": s.get("name"), "args": s.get("args", {})})
                    await _emit(db, task, "tool_end",
                                {"name": s.get("name"), "success": True, "summary": s.get("summary", "")})

            if not six:
                raise RuntimeError("未产出六段式结论")

            await _stream_text(six.conclusion_text, task)
            result = await _persist(db, task, conv, six)
            await _emit(db, task, "result_ready",
                        {"task_id": task_id, "result_id": result.id, "result": six.model_dump()})
            task.task_status = "success"
            task.finished_at = _utcnow()
            await db.commit()
        except asyncio.CancelledError:
            task.task_status = "cancelled"
            task.finished_at = _utcnow()
            await db.commit()
            await _emit(db, task, "cancelled", {"task_id": task_id})
            await log_task(task_id, "WARN", "system", "任务被取消", db)
        except Exception as e:  # noqa: BLE001
            logger.exception("任务 %s 执行失败", task_id)
            task.task_status = "failed"
            task.error_message = str(e)[:500]
            task.finished_at = _utcnow()
            await db.commit()
            await _emit(db, task, "error", {"task_id": task_id, "message": str(e)[:300]})
            await log_task(task_id, "ERROR", "system", f"执行失败: {e}", db)


def db_session():
    from app.core.db import AsyncSessionLocal
    return AsyncSessionLocal()
