"""管理接口：配置热更新与日志。"""

from fastapi import APIRouter, Depends, Query

from ..admin import get_config, list_task_logs, reload_config
from ..auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/config")
def config(_: dict = Depends(require_admin)):
    return get_config()


@router.post("/reload")
def reload(_: dict = Depends(require_admin)):
    return reload_config()


@router.get("/logs")
def logs(
    task_id: int | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    _: dict = Depends(require_admin),
):
    return list_task_logs(task_id=task_id, limit=limit)
