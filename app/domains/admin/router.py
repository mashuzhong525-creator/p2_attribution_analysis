"""管理监控 API（上线增强 Tab：运行日志 / LLM 成本 / 审计日志）。

- GET /api/admin/logs         运行日志（task_logs，级别/类型/关键词过滤 + 分页）
- GET /api/admin/llm-costs    LLM 调用成本（llm_calls，今日/本月 KPI + 明细分页）
- GET /api/admin/audit-logs   审计日志（audit_logs，分页）
均需 admin 角色（require_admin）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_admin
from app.models.business import AuditLog, LLMCall, TaskLog, User

router = APIRouter(tags=["admin-monitor"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/api/admin/logs")
async def list_logs(
    level: str | None = Query(default=None, description="log_level 过滤：DEBUG/INFO/WARN/ERROR"),
    log_type: str | None = Query(default=None, description="log_type 过滤：任务/工具/LLM/系统"),
    keyword: str | None = Query(default=None, description="内容关键词模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TaskLog)
    if level:
        stmt = stmt.where(TaskLog.log_level == level.upper())
    if log_type:
        stmt = stmt.where(TaskLog.log_type == log_type)
    if keyword:
        stmt = stmt.where(TaskLog.log_content.like(f"%{keyword}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(TaskLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "log_level": r.log_level,
                "log_type": r.log_type,
                "log_content": r.log_content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/api/admin/llm-costs")
async def list_llm_costs(
    date: str | None = Query(default=None, description="按日期过滤 YYYY-MM-DD，缺省不过滤"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    today_start = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    async def _agg(stmt) -> dict:
        row = (await db.execute(stmt)).one()
        return {
            "cost": float(row[0] or 0),
            "calls": int(row[1] or 0),
            "tokens": int(row[2] or 0),
        }

    today = await _agg(
        select(func.coalesce(func.sum(LLMCall.cost), 0), func.count(LLMCall.id), func.coalesce(func.sum(LLMCall.total_tokens), 0))
        .where(LLMCall.created_at >= today_start)
    )
    month = await _agg(
        select(func.coalesce(func.sum(LLMCall.cost), 0), func.count(LLMCall.id), func.coalesce(func.sum(LLMCall.total_tokens), 0))
        .where(LLMCall.created_at >= month_start)
    )

    stmt = select(LLMCall)
    if date:
        d0 = datetime.strptime(date, "%Y-%m-%d")
        d1 = d0 + timedelta(days=1)
        stmt = stmt.where(LLMCall.created_at >= d0, LLMCall.created_at < d1)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(LLMCall.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "kpi": {
            "today_cost": round(today["cost"], 4),
            "today_calls": today["calls"],
            "today_tokens": today["tokens"],
            "month_cost": round(month["cost"], 4),
            "month_calls": month["calls"],
            "month_tokens": month["tokens"],
        },
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "model": r.model,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost": float(r.cost),
                "latency_ms": r.latency_ms,
                "status": r.status,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/api/admin/audit-logs")
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action_type": r.action_type,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "before_value": r.before_value,
                "after_value": r.after_value,
                "ip": r.ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }
