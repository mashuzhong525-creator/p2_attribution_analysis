"""六段式 Pydantic 模型与校验降级（§8.5）。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class KeyMetric(BaseModel):
    metric_name: str
    metric_value: str  # 保留原始精度（LLM 输出转字符串）
    metric_unit: str = ""
    metric_period: str = ""


class Evidence(BaseModel):
    source_type: Literal[
        "db_query", "file_read", "text_search", "command_exec", "attachment", "user_input"
    ]
    source_name: str
    evidence_text: str
    related_metric: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SixSectionResult(BaseModel):
    problem_definition: str
    key_metrics: list[KeyMetric] = []
    evidence_list: list[Evidence] = []
    conclusion_text: str
    missing_data_text: str = ""
    next_action_text: str = ""


def parse_six_section(text: str) -> SixSectionResult:
    """从 LLM 文本解析六段式：优先 JSON，失败抛 ValueError（由引擎降级）。"""
    import json
    import re

    # 提取首个 JSON 块
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("未找到 JSON 结构")
    obj = json.loads(m.group(0))
    return SixSectionResult.model_validate(obj)
