"""六部分归因结果契约（C-ATTRIBUTION）与兜底。"""

import json

from pydantic import BaseModel, ValidationError

ATTRIBUTION_PROMPT_TEMPLATE = """你是经营归因分析助手。基于查询结果回答业务问题，只输出严格 JSON，不要多余文字。

【JSON 结构】
{{
  "problem_definition": "业务问题",
  "key_metrics": [{{"metric_name": "指标名", "metric_value": "数值", "metric_unit": "单位", "metric_period": "期间"}}],
  "evidence_list": [{{"source_type": "database", "source_name": "表名", "evidence_text": "证据描述", "related_metric": "关联指标", "confidence": 0.9}}],
  "conclusion_text": "归因结论（基于查询结果，不编造）",
  "missing_data_text": "缺失数据说明",
  "next_action_text": ["建议动作1", "建议动作2"]
}}

【规则】
1. 结论只能基于查询结果中的数字，禁止编造；
2. 数据不足时在 missing_data_text 中说明；
3. next_action_text 至少 2 条。

【业务问题】
{question}

【查询结果】
{result_text}

【JSON】"""


class Metric(BaseModel):
    metric_name: str
    metric_value: str
    metric_unit: str
    metric_period: str


class Evidence(BaseModel):
    source_type: str
    source_name: str
    evidence_text: str
    related_metric: str
    confidence: float


class AttributionResult(BaseModel):
    problem_definition: str
    key_metrics: list[Metric]
    evidence_list: list[Evidence]
    conclusion_text: str
    missing_data_text: str
    next_action_text: list[str]


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("未找到 JSON")
    return json.loads(text[start : end + 1])


def validate_result(data: dict) -> bool:
    try:
        AttributionResult(**data)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    return True


def build_prompt(question: str, result_text: str) -> str:
    return ATTRIBUTION_PROMPT_TEMPLATE.format(question=question, result_text=result_text)


def parse_result(text: str) -> dict:
    data = _extract_json(text)
    validate_result(data)
    return data


def build_fallback_result(question: str, rows: list[dict], columns: list[str]) -> dict:
    metrics = []
    for col in columns:
        if col in ("sales_qty", "amount", "in_qty", "out_qty", "stock_qty", "count"):
            total = sum(float(r.get(col) or 0) for r in rows)
            metrics.append(
                {"metric_name": col, "metric_value": str(total), "metric_unit": "数量", "metric_period": ""}
            )
    evidence = [
        {
            "source_type": "database",
            "source_name": str(r.get(columns[0], "")) if columns else "",
            "evidence_text": str(r)[:200],
            "related_metric": columns[0] if columns else "",
            "confidence": 0.8,
        }
        for r in rows[:5]
    ]
    return {
        "problem_definition": question,
        "key_metrics": metrics[:5],
        "evidence_list": evidence,
        "conclusion_text": f"共查询到 {len(rows)} 行结果，需结合完整数据进一步归因。",
        "missing_data_text": "缺少历史同期对比数据，建议补充基线。",
        "next_action_text": ["补充历史同期数据做环比分析", "按仓库/SKU 维度拆分定位异常"],
    }


def generate_attribution(question: str, result_text: str, rows: list[dict], columns: list[str], llm_call) -> dict:
    prompt = build_prompt(question, result_text)
    try:
        return parse_result(llm_call(prompt))
    except Exception:  # noqa: BLE001
        return build_fallback_result(question, rows, columns)
