"""分析流水线：建任务 → 生成 SQL → 执行 → 归因 → 落库。"""

import json

from ..chat import add_message
from ..llm import default_llm_call
from ..results import save_result
from ..tasks import create_task, log_task, mark_failed, transition
from .attribution import generate_attribution
from .executor import execute_with_retry
from .schema import METRICS_TEXT, SCHEMA_TEXT
from .sql_gen import generate_sql


def run_analysis(question: str, conversation_id: int, user_id: int, emit=None) -> dict:
    def evt(payload: dict) -> None:
        if emit:
            emit(payload)

    from ..database import db

    with db() as conn:
        try:
            task_id = create_task(conn, conversation_id, user_id, question)
            add_message(conn, conversation_id, "user", "text", question)
        except ValueError as e:
            evt({"event": "error", "error_message": str(e)})
            return {"task_id": None, "error": str(e)}

        evt({"event": "message_start", "task_id": task_id, "conversation_id": conversation_id})
        evt({"event": "task_status", "task_status": "queued", "task_id": task_id})
        transition(conn, task_id, "running")
        evt({"event": "task_status", "task_status": "running", "task_id": task_id})

        try:
            evt({"event": "tool_start", "tool_name": "sql_generate"})
            log_task(conn, task_id, "INFO", "tool", "生成 SQL")

            def fix_sql(error: str, bad_sql: str) -> str:
                prompt = f"{question}\n（上次 SQL 执行失败：{error}，请修正后重新输出）"
                return generate_sql(prompt, SCHEMA_TEXT, METRICS_TEXT, default_llm_call)

            sql = generate_sql(question, SCHEMA_TEXT, METRICS_TEXT, default_llm_call)
            evt({"event": "tool_finish", "tool_name": "sql_generate", "tool_result_summary": sql[:200]})

            evt({"event": "tool_start", "tool_name": "sql_execute"})
            result = execute_with_retry(sql, fix_fn=fix_sql)
            evt({"event": "tool_finish", "tool_name": "sql_execute", "tool_result_summary": f"{len(result['rows'])} 行"})

            result_text = json.dumps(result["rows"][:20], ensure_ascii=False, default=str)
            evt({"event": "message_delta", "delta": "正在生成归因结论……"})
            attribution = generate_attribution(question, result_text, result["rows"], result["columns"], default_llm_call)
            save_result(conn, task_id, conversation_id, attribution)

            transition(conn, task_id, "success")
            evt({"event": "result_ready", "task_id": task_id})
            evt({"event": "task_status", "task_status": "success", "task_id": task_id})
            evt({"event": "done", "task_id": task_id})
            return {"task_id": task_id, "result": attribution, "sql": sql}
        except Exception as e:  # noqa: BLE001
            mark_failed(conn, task_id, str(e))
            evt({"event": "error", "task_id": task_id, "error_message": str(e)})
            evt({"event": "done", "task_id": task_id})
            return {"task_id": task_id, "error": str(e)}
