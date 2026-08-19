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
from app.domains.agent.analyzers import analyze, is_query_in_scope, out_of_scope_six
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


# 无效指标占位：数据源不可用时 LLM 常编造这类值，须识别并降级
_INVALID_METRIC_HINTS = ("无法获取", "获取失败", "连接失败", "不可用", "无数据", "未获取", "暂无", "N/A", "n/a", "null", "None")


def _metrics_all_invalid(six: SixSectionResult) -> bool:
    """关键指标非空但全部为无效占位 → 判定 LLM 在瞎编。空指标（无指标）不算。"""
    if not six.key_metrics:
        return False
    for m in six.key_metrics:
        v = (m.metric_value or "").strip()
        if v and not any(h in v for h in _INVALID_METRIC_HINTS):
            return False
    return True


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
        task_id=task.id,
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


async def _load_attachment_lines(db, conv_id: str) -> list[str]:
    """读取会话已解析附件的摘要+预览行，供 system prompt 注入。"""
    from app.models.business import Attachment as _Att
    atts = (await db.execute(
        select(_Att).where(
            _Att.conversation_id == conv_id,
            _Att.deleted_at.is_(None),
            _Att.parse_status == "parsed",
        ).order_by(_Att.created_at.desc())
    )).scalars().all()
    lines: list[str] = []
    for a in atts:
        pr = a.parse_result_json or {}
        summary = (pr.get("summary") or "")[:300]
        preview = (pr.get("preview_rows") or [])[:5]
        size_kb = max(1, a.file_size // 1024)
        lines.append(
            f"### {a.file_name}（{a.file_type}, {size_kb}KB）\n"
            f"- 摘要: {summary}\n"
            f"- 预览前 5 行: {preview}\n"
            f"- 全文路径: {a.file_path}\n"
            f"- 可调用 text_search(按关键词) 或 file_read(path) 访问全文"
        )
    return lines


async def _build_system_prompt(db, conv, ds, trigger_query):
    """Build system prompt with business context, schema description, attachments and explicit analysis instructions."""
    # 1) 加载附件摘要（核心修复点：让 LLM 看得到用户上传的文件）
    att_lines = await _load_attachment_lines(db, conv.id)
    attachment_block = ""
    if att_lines:
        attachment_block = (
            "【已上传附件（必读，请基于附件内容做分析；如附件与问题强相关，请优先调用 "
            "text_search/file_read 工具读取真实数据，不要凭印象作答）】\n"
            + "\n".join(att_lines)
        )

    # 2) 既有：schema_info
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
        f"{attachment_block}\n\n"
        f"{schema_info}"
        "## 分析方法（务必按此执行，不要无目的探索）\n"
        "1) **若存在附件且附件与问题强相关：第 1 步用 file_read 读取附件全文，第 2 步就输出六段式 JSON 结论**（不要再做无谓的 db_query 探索）。\n"
        "2) 若需要数据库事实（如附件不覆盖），先 1 步 db_query 拿到关键数据，第 2 步就输出 JSON。\n"
        "3) 严禁连续 2 步以上重复调用同一工具（说明你没在思考），超过 3 步工具调用还没出 JSON 是严重的错误。\n\n"
        "## 输出格式（不可省略）\n"
        "你必须仅输出标准六段式 JSON（不要任何解释文字、markdown标记、换行之外的任何内容）：\n"
        f"{{\"problem_definition\": \"...\", \"key_metrics\": [{{\"metric_name\":\"...\",\"metric_value\":\"...\",\"metric_unit\":\"...\",\"metric_period\":\"...\"}}], "
        f"\"evidence_list\": [{{\"source_type\":\"attachment|db_query|file_read\",\"source_name\":\"...\",\"evidence_text\":\"...\",\"related_metric\":\"...\",\"confidence\":0.xx}}], "
        f"\"conclusion_text\": \"...\", \"missing_data_text\": \"...\", \"next_action_text\": \"...\"}}\n\n"
        "每个 evidence 必须来自真实查询/附件内容。置信度 0~1。禁止编造指标。"
    )


def _tool_table(res) -> dict | None:
    """提取工具结果的表格数据（columns+rows）供前端渲染，防超量最多 8 列 20 行。"""
    if not getattr(res, "success", False):
        return None
    data = getattr(res, "data", None)
    if not (isinstance(data, dict) and data.get("rows")):
        return None
    return {
        "columns": (data.get("columns") or [])[:8],
        "rows": data["rows"][:20],
        "total": len(data["rows"]),
    }


def _tool_content(res) -> str:
    """把工具结果渲染为供 LLM 阅读的文本：优先注入真实数据，否则用 summary/error。

    渲染优先级：
      1) data 是 dict 且有 rows → 表格（columns + 最多 50 行）
      2) data 是 str（file_read / text_search 等）→ 直接返回内容（必要时截断）
      3) data 是 list → JSON dump
      4) 否则用 summary / error
    """
    if not res.success:
        return f"执行失败：{res.error}"
    data = getattr(res, "data", None)
    if isinstance(data, dict) and data.get("rows"):
        cols = data.get("columns") or []
        rows = data["rows"][:50]
        header = " | ".join(str(c) for c in cols)
        lines = [f"表头: {header}"]
        for r in rows:
            lines.append(" | ".join("" if v is None else str(v) for v in r))
        if len(data["rows"]) > 50:
            lines.append(f"…（共 {len(data['rows'])} 行，已省略）")
        return "\n".join(lines)
    if isinstance(data, str) and data:
        # file_read / 文本类工具：把内容原样交给 LLM，截断到 8000 字防超上下文
        snippet = data[:8000]
        if len(data) > 8000:
            snippet += f"\n…（共 {len(data)} 字符，已截断）"
        return snippet
    if isinstance(data, list):
        import json as _json
        return _json.dumps(data, ensure_ascii=False, default=str)[:8000]
    return res.summary or "（无返回）"


async def _emit_tool_messages(ctx_messages, tc, res) -> None:
    ctx_messages.append({
        "role": "tool", "tool_call_id": tc.get("id"),
        "name": tc.get("function", {}).get("name"),
        "content": _tool_content(res),
    })


async def _run_online(db, task: AnalysisTask, conv: Conversation, tool_ctx: ToolContext, llm: LlmClient):
    ds = await db.get(DataSource, conv.data_source_id) if conv.data_source_id else None
    enabled = enabled_tool_flags()
    tool_list = [t["function"]["name"] for t in registry.schema(enabled)]

    # 本轮工具失败计数：数据源不可用等工具错误时，LLM 补丁内容不可信，须降级离线确定性分析
    tool_fail_cnt = 0

    # Extract latest user message as trigger query (not full conversation history)
    rows = (await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.deleted_at.is_(None))
        .order_by(Message.seq_no.desc())
        .limit(5)
    )).scalars().all()
    # rows 为时间倒序（最新在前）：取第一条 user 消息即"最新的用户提问"。
    # 注意不能取窗口内最早的——连续提问时会导致 LLM 答非所问（用旧问题回答新问题）。
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

    system = await _build_system_prompt(db, conv, ds, trigger_query)

    max_steps = settings.AGENT_MAX_STEPS
    last_content = ""
    for step in range(max_steps):
        fresh = await db.get(AnalysisTask, task.id)
        if fresh and fresh.task_status == "cancelled":
            raise asyncio.CancelledError()
        task.current_step = step + 1
        await db.commit()
        await _emit(db, task, "task_status",
                    {"task_id": task.id, "task_status": "running", "current_step": step + 1})
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
                if not res.success:
                    tool_fail_cnt += 1
                await _emit(db, task, "tool_end",
                            {"name": name, "success": res.success, "summary": res.summary, "error": res.error,
                             "table": _tool_table(res)})
                await _emit_tool_messages(ctx_messages, tc, res)
        else:
            # No tool calls → try to parse as six-section JSON
            six = None
            errors = []
            try:
                six = parse_six_section(content)
            except Exception as e:
                errors.append(f"parse_fail: {e}")

            # 关键指标全部为无效占位（无法获取/连接失败等）→ LLM 在瞎编，降级离线确定性分析
            if six is not None and _metrics_all_invalid(six):
                logger.warning("LLM 六段式指标均为无效占位，降级离线确定性分析")
                return await analyze(task, conv, ds, db)

            if six is None:
                # 工具已失败（如数据源不可用）时，LLM 补丁内容不可信，直接降级离线分析，禁止把瞎编内容当结论
                if tool_fail_cnt > 0:
                    logger.warning("工具失败 %d 次，LLM 结论不可信，降级离线确定性分析", tool_fail_cnt)
                    return await analyze(task, conv, ds, db)
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
        await _emit(db, task, "task_status",
                    {"task_id": task_id, "task_status": "running", "current_step": 0})
        try:
            await _emit(db, task, "message_start", {"task_id": task_id})
            llm = LlmClient()
            conv = await db.get(Conversation, task.conversation_id)
            if conv is None:
                raise RuntimeError("会话不存在")
            ds = await db.get(DataSource, conv.data_source_id) if conv.data_source_id else None
            # ==== 语义半径前置闸门（仅离线确定性路径使用）====
            # query 与会话绑定的场景库主题无关时，离线确定性路径拿不到关键指标/证据，
            # 直接产出"不在分析半径"六段式（0 指标、0 证据、明确拒答说明）。
            # 但若已配置 LLM（在线路径可用），不在范围内的通用/闲聊 query 不再硬拒答，
            # 交回在线 Agent 用通用能力 + db_query/附件作答，从而得到真正的指标与证据链。
            if (ds is not None and ds.database in ("scenario_goods", "scenario_inventory")
                    and not llm.available):
                kind = "goods" if ds.database == "scenario_goods" else "inventory"
                q = (task.input_text or "").strip()
                if not is_query_in_scope(q, kind):
                    from app.models.business import Attachment as _Att
                    att_cnt = (await db.execute(
                        select(func.count(_Att.id)).where(
                            _Att.conversation_id == conv.id,
                            _Att.deleted_at.is_(None),
                            _Att.parse_status == "parsed",
                        )
                    )).scalar() or 0
                    if att_cnt == 0:
                        six = out_of_scope_six(q, kind)
                        await log_task(task.id, "INFO", "router",
                                       f"query 不在 {kind} 场景语义半径内，返回 out-of-scope 六段式", db)
                        await _stream_text(six.conclusion_text, task)
                        result = await _persist(db, task, conv, six)
                        await _emit(db, task, "result_ready",
                                    {"task_id": task_id, "result_id": result.id, "result": six.model_dump()})
                        task.task_status = "success"
                        task.finished_at = _utcnow()
                        await db.commit()
                        await _emit(db, task, "task_status",
                                    {"task_id": task_id, "task_status": "success", "current_step": 1})
                        return
                    # 有附件 → 让 LLM 走在线路径读附件作答，不再硬拒答
                    await log_task(task.id, "INFO", "router",
                                   f"query 不在 {kind} 场景半径内，但会话有 {att_cnt} 个附件，转 LLM 在线分析附件", db)
            tool_ctx = ToolContext(
                user_id=task.user_id,
                conversation_id=conv.id,
                data_source_id=conv.data_source_id,
                db=db,
                workspace_dir=f"{settings.DATA_ROOT}/workspace/{task.user_id}/{conv.id}",
            )
            # 上线主路径：配置了 LLM 即走在线工具循环（可回答任意业务问题，数据源由 db_query 工具查询）。
            # LLM 不可用或在线路径异常时，降级离线确定性分析（仅支持预置场景库）。
            use_online = llm.available
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
            await _emit(db, task, "task_status",
                        {"task_id": task_id, "task_status": "success", "current_step": task.current_step})
        except asyncio.CancelledError:
            task.task_status = "cancelled"
            task.finished_at = _utcnow()
            await db.commit()
            await _emit(db, task, "cancelled", {"task_id": task_id})
            await _emit(db, task, "task_status",
                        {"task_id": task_id, "task_status": "cancelled", "current_step": task.current_step})
            await log_task(task_id, "WARN", "system", "任务被取消", db)
        except Exception as e:  # noqa: BLE001
            logger.exception("任务 %s 执行失败", task_id)
            task.task_status = "failed"
            task.error_message = str(e)[:500]
            task.finished_at = _utcnow()
            await db.commit()
            await _emit(db, task, "error", {"task_id": task_id, "message": str(e)[:300]})
            await _emit(db, task, "task_status",
                        {"task_id": task_id, "task_status": "failed", "current_step": task.current_step})
            await log_task(task_id, "ERROR", "system", f"执行失败: {e}", db)


def db_session():
    from app.core.db import AsyncSessionLocal
    return AsyncSessionLocal()
