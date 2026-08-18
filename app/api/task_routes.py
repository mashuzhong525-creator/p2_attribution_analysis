"""任务与结果接口。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ..auth import require_user
from ..database import db
from ..results import get_result, result_markdown
from ..tasks import list_tasks

router = APIRouter(prefix="/api", tags=["task"])


@router.get("/tasks/{task_id}")
def task_detail(task_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        tasks = list_tasks(conn, task_id=task_id)
        if not tasks:
            raise HTTPException(status_code=404, detail="任务不存在")
        return tasks[0]


@router.get("/results/{task_id}")
def result_detail(task_id: int, user: dict = Depends(require_user)):
    with db() as conn:
        result = get_result(conn, task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="结果不存在")
        return result


@router.get("/results/{task_id}/export")
def result_export(task_id: int, fmt: str = "md", user: dict = Depends(require_user)):
    with db() as conn:
        result = get_result(conn, task_id)
        if result is None:
            raise HTTPException(status_code=404, detail="结果不存在")
        if fmt == "json":
            import json

            content = json.dumps(result, ensure_ascii=False, indent=2)
            suffix = ".json"
        else:
            content = result_markdown(result)
            suffix = ".md"
    path = __import__("pathlib").Path(__import__("tempfile").gettempdir()) / f"result_{task_id}{suffix}"
    path.write_text(content, encoding="utf-8")
    return FileResponse(path, filename=f"result_{task_id}{suffix}")
