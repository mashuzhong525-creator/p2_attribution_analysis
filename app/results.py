"""六部分结果落库、Markdown 渲染与导出。"""

import json

from .utils import now_iso


def result_markdown(result: dict) -> str:
    metrics = result.get("key_metrics") or []
    evidence = result.get("evidence_list") or []
    actions = result.get("next_action_text") or []
    lines = [
        "# 归因分析报告",
        "",
        f"## 问题定义\n{result.get('problem_definition', '')}",
        "",
        "## 关键指标",
    ]
    for m in metrics:
        lines.append(f"- {m.get('metric_name')}：{m.get('metric_value')}{m.get('metric_unit')}（{m.get('metric_period')}）")
    lines += ["", "## 证据列表"]
    for e in evidence:
        lines.append(f"- [{e.get('source_type')}] {e.get('source_name')}：{e.get('evidence_text')}（置信度 {e.get('confidence')}）")
    lines += ["", f"## 归因结论\n{result.get('conclusion_text', '')}", ""]
    lines += [f"## 待补充数据\n{result.get('missing_data_text', '')}", "", "## 下一步建议"]
    for a in actions:
        lines.append(f"- {a}")
    return "\n".join(lines)


def save_result(conn, task_id: int, conversation_id: int, result: dict) -> int:
    cur = conn.execute(
        """INSERT INTO analysis_results
           (task_id,conversation_id,problem_definition,key_metrics_json,evidence_list_json,
            conclusion_text,missing_data_text,next_action_text,result_markdown,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            task_id,
            conversation_id,
            result.get("problem_definition", ""),
            json.dumps(result.get("key_metrics") or [], ensure_ascii=False),
            json.dumps(result.get("evidence_list") or [], ensure_ascii=False),
            result.get("conclusion_text", ""),
            result.get("missing_data_text", ""),
            json.dumps(result.get("next_action_text") or [], ensure_ascii=False),
            result_markdown(result),
            now_iso(),
        ),
    )
    return cur.lastrowid


def get_result(conn, task_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM analysis_results WHERE task_id=?", (task_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["key_metrics"] = json.loads(result.pop("key_metrics_json") or "[]")
    result["evidence_list"] = json.loads(result.pop("evidence_list_json") or "[]")
    result["next_action_text"] = json.loads(result.pop("next_action_text") or "[]")
    return result
