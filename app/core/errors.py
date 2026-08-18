"""统一业务错误与 HTTP 异常处理器（§2.1）。

所有 REST 错误响应结构：{ code, message, detail }。
错误码工厂集中管理，便于全局映射 HTTP 状态。
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.db import get_db  # noqa: F401  (kept importable for deps)


class BizError(Exception):
    """业务异常：业务错误码 + 人类可读信息 + HTTP 状态 + 可选 detail。"""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        detail: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.http_status = http_status
        self.detail = detail
        super().__init__(message)


# ---- 错误码工厂（§2.1 表）----
def auth_required(detail: str | None = None) -> BizError:
    return BizError("AUTH_REQUIRED", "未登录", 401, detail)

def auth_expired(detail: str | None = None) -> BizError:
    return BizError("AUTH_EXPIRED", "登录态过期", 401, detail)

def forbidden(detail: str | None = None) -> BizError:
    return BizError("FORBIDDEN", "无权限访问", 403, detail)

def password_change_required(detail: str | None = None) -> BizError:
    return BizError("PASSWORD_CHANGE_REQUIRED", "首次登录需先修改密码", 403, detail)

def not_found(resource: str = "资源") -> BizError:
    return BizError("NOT_FOUND", f"{resource}不存在", 404)

def validation_error(message: str, detail: dict | None = None) -> BizError:
    return BizError("VALIDATION_ERROR", message, 422, detail)

def task_busy(task_id: str) -> BizError:
    return BizError("TASK_BUSY", "会话已有运行中任务", 409, {"task_id": task_id})

def task_not_cancellable(task_id: str) -> BizError:
    return BizError("TASK_NOT_CANCELLABLE", "终态任务不可取消", 409, {"task_id": task_id})

def task_queue_full() -> BizError:
    return BizError("TASK_QUEUE_FULL", "任务队列已满", 429)

def rate_limited(message: str = "接口限流") -> BizError:
    return BizError("RATE_LIMITED", message, 429)

def file_type_not_allowed() -> BizError:
    return BizError("FILE_TYPE_NOT_ALLOWED", "附件类型不允许", 400)

def file_too_large(max_mb: int) -> BizError:
    return BizError("FILE_TOO_LARGE", f"附件超过 {max_mb}MB 上限", 400)

def file_parse_failed(reason: str) -> BizError:
    return BizError("FILE_PARSE_FAILED", f"附件解析失败：{reason}", 400)

def data_source_unavailable(message: str = "数据源不可用") -> BizError:
    return BizError("DATA_SOURCE_UNAVAILABLE", message, 400)

def config_reload_failed(message: str = "配置重载失败") -> BizError:
    return BizError("CONFIG_RELOAD_FAILED", message, 500)

def internal_error(message: str = "服务器内部错误") -> BizError:
    return BizError("INTERNAL_ERROR", message, 500)


async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "detail": exc.detail},
    )
