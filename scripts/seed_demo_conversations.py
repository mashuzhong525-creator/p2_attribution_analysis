"""演示数据种子：两组完整分析示例会话（幂等，满足《项目实战要求》2.1.12/2.1.13）。

- 会话一「商品目录优化 · 6月信息流点击下滑归因」：绑定 scenario_goods
- 会话二「库存异常分析 · SKU0001 华东仓断货归因」：绑定 scenario_inventory

每组演示会话完整落库一条链路：
  conversations → messages(user/assistant/result) → analysis_tasks → analysis_results(六段式)
                → context_summaries → task_logs → llm_calls
六段式结论复用 `app.domains.agent.analyzers` 的确定性分析逻辑（对场景库实时查询），
保证与运行时无 LLM 演示路径产出的结果完全一致，前端历史回放/结果区展示均为真实链路。

运行（项目根目录）：
  python -m scripts.seed_demo_conversations            # 幂等：按 title 重建两组演示会话
  python -m scripts.seed_demo_conversations --reset    # 先清理全部运行期数据再重建

--reset 物理清理范围（保留 seed 基线与审计）：
  messages / attachments / analysis_tasks / analysis_results / context_summaries /
  websocket_tokens / task_logs / llm_calls / conversations（按依赖序）
  以及过期 auth_auth_codes / auth_refresh_tokens；audit_logs 永久保留并追加清理留痕。
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.uuid import uuid7_str
from app.db.base import Base
import app.models.business  # noqa: F401
import app.models.auth  # noqa: F401

from app.domains.agent.analyzers import analyze_goods, analyze_inventory
from app.models.business import (
    AnalysisResult,
    AnalysisTask,
    AuditLog,
    ContextSummary,
    Conversation,
    DataSource,
    LLMCall,
    Message,
    TaskLog,
    User,
    WebSocketToken,
)
from app.models.auth import AuthAuthCode, AuthRefreshToken

ENGINE = create_engine(settings.SYNC_DB_URL, poolclass=NullPool)
Session = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=ENGINE)

DEMO_TITLES = [
    "商品目录优化 · 6月信息流点击下滑归因",
    "库存异常分析 · SKU0001 华东仓断货归因",
]

# 运行期数据表（--reset 时按此顺序物理清空；保留 users/configs/data_sources/audit）
RUNTIME_TABLES = [
    "messages", "attachments", "analysis_tasks", "analysis_results",
    "context_summaries", "websocket_tokens", "task_logs", "llm_calls",
    "conversations",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- 清理 ----------------
def reset_runtime_data(s) -> None:
    """物理清空运行期数据（调试遗留），保留 seed 基线与审计。"""
    for tbl in RUNTIME_TABLES:
        s.execute(text(f"DELETE FROM {tbl}"))
    # 过期认证票据（设计：auth_auth_codes 5 分钟 / refresh 7 天，见数据模型设计 §5）
    now = _utcnow()
    s.execute(delete(AuthAuthCode).where(AuthAuthCode.expires_at < now))
    s.execute(delete(AuthRefreshToken).where(
        (AuthRefreshToken.expires_at < now) | (AuthRefreshToken.revoked_at.is_not(None))
    ))
    s.add(AuditLog(id=uuid7_str(), user_id="seed", action_type="reset",
                   target_type="system", target_id="runtime-data",
                   after_value={"note": "seed_demo_conversations --reset 清理运行期演示数据"},
                   created_at=now))
    s.commit()
    print("[demo] --reset 完成：已清空 9 张运行期数据表 + 过期认证票据，审计保留。")


# ---------------- 演示会话 ----------------
def _ds_by_database(s, database: str) -> DataSource | None:
    return s.execute(
        select(DataSource).where(DataSource.database == database, DataSource.is_enabled.is_(True))
    ).scalar_one_or_none()


def _drop_demo_conv(s, title: str, owner_id: str) -> None:
    """按 title + owner 幂等删除旧演示会话（不跨用户删，避免 owner 循环相互覆盖）。"""
    conv = s.execute(
        select(Conversation).where(Conversation.title == title, Conversation.user_id == owner_id)
    ).scalar_one_or_none()
    if conv is None:
        return
    cid = conv.id
    task_ids = [r[0] for r in s.execute(
        select(AnalysisTask.id).where(AnalysisTask.conversation_id == cid)
    )]
    if task_ids:
        s.execute(delete(LLMCall).where(LLMCall.task_id.in_(task_ids)))
        s.execute(delete(TaskLog).where(TaskLog.task_id.in_(task_ids)))
        s.execute(delete(AnalysisResult).where(AnalysisResult.task_id.in_(task_ids)))
    s.execute(delete(Message).where(Message.conversation_id == cid))
    s.execute(delete(ContextSummary).where(ContextSummary.conversation_id == cid))
    s.execute(delete(WebSocketToken).where(WebSocketToken.conversation_id == cid))
    s.execute(delete(AnalysisTask).where(AnalysisTask.conversation_id == cid))
    s.execute(delete(Conversation).where(Conversation.id == cid))
    s.commit()


def _mk_messages(s, conv: Conversation, user_q: str, plan_text: str,
                 interim_text: str, six, task: AnalysisTask, t0: datetime) -> None:
    """写消息序列：user/text → assistant/text(思路) → assistant/text(中间结论) → assistant/result。"""
    rows = [
        Message(id=uuid7_str(), conversation_id=conv.id, role="user", message_type="text",
                content=user_q, seq_no=1, created_at=t0 + timedelta(seconds=3)),
        Message(id=uuid7_str(), conversation_id=conv.id, role="assistant", message_type="text",
                content=plan_text, seq_no=2, created_at=t0 + timedelta(seconds=20)),
        Message(id=uuid7_str(), conversation_id=conv.id, role="assistant", message_type="text",
                content=interim_text, seq_no=3, created_at=t0 + timedelta(seconds=300)),
        Message(id=uuid7_str(), conversation_id=conv.id, role="assistant", message_type="result",
                content=six.conclusion_text, task_id=task.id, seq_no=4,
                created_at=t0 + timedelta(seconds=360)),
    ]
    s.add_all(rows)
    s.add(ContextSummary(id=uuid7_str(), conversation_id=conv.id, start_seq_no=1, end_seq_no=4,
                         summary_text=(
                             f"用户围绕「{six.problem_definition}」展开归因分析；"
                             f"已确认 {six.conclusion_text[:80]}…"
                         ), created_at=t0 + timedelta(seconds=365)))


def _mk_logs_and_llm(s, task: AnalysisTask, conv: Conversation, user: User,
                     steps: list[dict], t0: datetime) -> None:
    """任务日志（system/tool/llm）+ LLM 调用记录，与引擎运行时形态一致。"""
    logs = [
        TaskLog(id=uuid7_str(), task_id=task.id, log_level="INFO", log_type="system",
                log_content="任务已创建并进入队列（queued）", created_at=t0),
        TaskLog(id=uuid7_str(), task_id=task.id, log_level="INFO", log_type="system",
                log_content="任务开始执行（queued→running）", created_at=t0 + timedelta(seconds=5)),
    ]
    for i, st in enumerate(steps, start=1):
        logs.append(TaskLog(id=uuid7_str(), task_id=task.id, log_level="INFO", log_type="tool",
                            log_content=f"工具 {i}: {st.get('name')} → {st.get('summary')}",
                            created_at=t0 + timedelta(seconds=5 + i * 40)))
    logs.append(TaskLog(id=uuid7_str(), task_id=task.id, log_level="INFO", log_type="llm",
                        log_content="调用 deepseek-chat 汇总六段式结论",
                        created_at=t0 + timedelta(seconds=5 + (len(steps) + 1) * 40)))
    logs.append(TaskLog(id=uuid7_str(), task_id=task.id, log_level="INFO", log_type="system",
                        log_content="任务完成（running→success）",
                        created_at=t0 + timedelta(seconds=360)))
    s.add_all(logs)

    calls = [
        LLMCall(id=uuid7_str(), task_id=task.id, conversation_id=conv.id, user_id=user.id,
                model="deepseek-chat", prompt_tokens=1820, completion_tokens=260,
                total_tokens=2080, cost=round(1820 * 0.001 / 1000 + 260 * 0.002 / 1000, 4),
                latency_ms=2430, status="success",
                created_at=t0 + timedelta(seconds=200)),
        LLMCall(id=uuid7_str(), task_id=task.id, conversation_id=conv.id, user_id=user.id,
                model="deepseek-chat", prompt_tokens=2140, completion_tokens=480,
                total_tokens=2620, cost=round(2140 * 0.001 / 1000 + 480 * 0.002 / 1000, 4),
                latency_ms=3860, status="success",
                created_at=t0 + timedelta(seconds=340)),
    ]
    s.add_all(calls)


def build_demo_conv(s, title: str, user_q: str, plan_text: str, interim_text: str,
                    ds: DataSource, user: User, t0: datetime, six, steps: list[dict]) -> str:
    """重建单个演示会话（六段式+消息+任务+日志），返回 conversation_id。"""
    _drop_demo_conv(s, title, user.id)
    conv = Conversation(id=uuid7_str(), user_id=user.id, data_source_id=ds.id, title=title,
                        status="active", last_message_at=t0 + timedelta(seconds=365),
                        created_at=t0, updated_at=t0)
    s.add(conv)
    s.flush()

    task = AnalysisTask(id=uuid7_str(), conversation_id=conv.id, user_id=user.id,
                        input_text=user_q, task_status="success", current_step=len(steps),
                        started_at=t0 + timedelta(seconds=5),
                        finished_at=t0 + timedelta(seconds=360),
                        error_message=None, created_at=t0)
    s.add(task)
    s.flush()

    result = AnalysisResult(
        id=uuid7_str(), task_id=task.id, conversation_id=conv.id,
        problem_definition=six.problem_definition,
        key_metrics_json=[m.model_dump() for m in six.key_metrics],
        evidence_list_json=[e.model_dump() for e in six.evidence_list],
        conclusion_text=six.conclusion_text,
        missing_data_text=six.missing_data_text,
        next_action_text=six.next_action_text,
        result_markdown=_to_markdown(six),
        result_file_path=None,
        created_at=t0 + timedelta(seconds=360),
    )
    s.add(result)

    _mk_messages(s, conv, user_q, plan_text, interim_text, six, task, t0)
    _mk_logs_and_llm(s, task, conv, user, steps, t0)
    s.commit()
    return conv.id


def _to_markdown(six) -> str:
    """与 engine._to_markdown 保持一致的 Markdown 副本（供导出/结果展示）。"""
    lines = ["# 经营归因分析", "", f"## 问题定义\n{six.problem_definition}", "", "## 关键指标"]
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


# ---------------- 两组演示会话定义 ----------------
GOODS_USER_Q = "为什么 6 月信息流渠道的点击量明显下滑？帮我定位一下原因并给出优化建议。"
GOODS_PLAN = (
    "收到，我先从渠道日度事实表入手，对比信息流渠道 5 月与 6 月的点击表现，"
    "并核查素材更换、SKU 上下架与促销日历，逐项定位下滑根因。"
)
GOODS_INTERIM = (
    "初步结论：信息流 6 月点击较 5 月明显回落。已发现两个可疑因素——"
    "信息流主素材 6/3 更换为夏季版（CTR 预期下降），以及 5 个头部 SKU 于 6/10 下架"
    "（削减可投放曝光基数）。继续量化各因素影响并完成归因结论。"
)

INV_USER_Q = "华东仓 SKU0001 最近出现缺货和负库存，是什么原因导致的？如何解决？"
INV_PLAN = (
    "收到，我先核查库存日快照、异常事件日志与采购单在途情况，"
    "对比销售与补货两条线索，判断缺货是需求激增还是供应链补货问题。"
)
INV_INTERIM = (
    "初步结论：SKU0001 在华东仓的日销保持平稳，排除销售暴增因素；"
    "自 6/15 起因采购到货延迟，库存被持续消耗至低库存/负库存。"
    "继续核对采购单 ETA 与异常事件明细，完成归因结论。"
)


def seed_demo(s) -> None:
    # 演示会话同时挂给 admin 与 analyst：默认账号 admin 登录即可看到演示，演示验收双向覆盖
    owners = s.execute(
        select(User).where(User.username.in_(["admin", "analyst"])).order_by(User.username)
    ).scalars().all()
    if not owners:
        print("[demo] 未找到 admin/analyst 用户，跳过演示会话生成（请先运行 python -m scripts.seed）")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        ds_goods = _ds_by_database(s, "scenario_goods")
        ds_inv = _ds_by_database(s, "scenario_inventory")
        if ds_goods is None or ds_inv is None:
            print("[demo] 未找到场景数据源（scenario_goods / scenario_inventory），跳过演示会话生成")
            return
        # 本地脚本适配：data_sources.host 存的是容器内主机名(mysql)，本地直连需换回 settings
        ds_goods.host = settings.DB_HOST
        ds_inv.host = settings.DB_HOST
        # 必须传入演示问题 query：分析器按 query 做场景语义判定（_in_scope），
        # 缺省空串会走 out_of_scope 分支导致六段式 key_metrics/evidence_list 为空数组
        six_goods, steps_goods = loop.run_until_complete(analyze_goods(ds_goods, query=GOODS_USER_Q))
        six_inv, steps_inv = loop.run_until_complete(analyze_inventory(ds_inv, query=INV_USER_Q))
    finally:
        loop.close()

    # 时间线：会话一 2026-08-17（UTC），会话二 2026-08-18（UTC），保持最近演示感
    t_a = datetime(2026, 8, 17, 2, 10, 0)
    t_b = datetime(2026, 8, 18, 1, 30, 0)

    built: list[str] = []
    for owner in owners:
        cid_a = build_demo_conv(s, DEMO_TITLES[0], GOODS_USER_Q, GOODS_PLAN, GOODS_INTERIM,
                                ds_goods, owner, t_a, six_goods, steps_goods)
        cid_b = build_demo_conv(s, DEMO_TITLES[1], INV_USER_Q, INV_PLAN, INV_INTERIM,
                                ds_inv, owner, t_b, six_inv, steps_inv)
        built.append(f"{owner.username}: A={cid_a} B={cid_b}")
    print(f"[demo] 演示会话完成（{len(owners)} 个用户 × 2 场景）：")
    for line in built:
        print(f"     - {line}")


def main() -> None:
    Base.metadata.create_all(ENGINE)  # 兜底建表（正常由 alembic 先行）
    with Session() as s:
        if "--reset" in sys.argv:
            reset_runtime_data(s)
        seed_demo(s)
    print("[demo] 完成：两组完整分析示例已就绪，可在前端会话列表直接打开回放。")


if __name__ == "__main__":
    main()
