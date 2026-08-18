"""Agent 提示词装配（§4.7 prompts.py / §8.2）。

build_system_prompt：角色 + 场景说明 + schema 描述 + 附件摘要 + 工具清单 + 六段式模板 + 硬性约束。
build_six_section_json_schema：六段式 JSON Schema（约束最终输出）。
"""
from __future__ import annotations

from app.domains.agent.schemas import SixSectionResult


SIX_SECTION_TEMPLATE = """
你是一名资深经营分析专家。请基于证据，按以下六段式结构化输出最终结论（JSON）：
1. problem_definition（问题定义）：用一句话重述用户要分析的经营问题。
2. key_metrics（关键指标）：列表，每项 {metric_name, metric_value, metric_unit, metric_period}。
3. evidence_list（证据链）：列表，每项 {source_type, source_name, evidence_text, related_metric, confidence(0~1)}。
4. conclusion_text（归因结论）：综合判断与根因。
5. missing_data_text（数据缺口）：尚缺哪些数据才能更确定（无则空串）。
6. next_action_text（下一步建议）：可执行的经营动作。
"""


def build_system_prompt(
    role_definition: str,
    scenario_description: str | None,
    schema_description: str | None,
    attachment_summaries: list[str],
    tool_list: list[str],
    flag_scenario: bool,
) -> str:
    parts = [role_definition]
    if flag_scenario and scenario_description:
        parts.append(f"【场景背景】\n{scenario_description}")
    if schema_description:
        parts.append(f"【可用数据表结构】\n{schema_description}")
    if attachment_summaries:
        parts.append("【已上传附件摘要】\n" + "\n".join(attachment_summaries))
    parts.append("【可用工具】\n" + ("、".join(tool_list) if tool_list else "（无）"))
    parts.append(SIX_SECTION_TEMPLATE)
    parts.append(
        "【硬性约束】所有结论必须基于工具返回的真实数据；禁止编造指标。"
        "最终必须调用一次 result 形式的六段式 JSON 输出。"
    )
    return "\n\n".join(parts)


def build_six_section_json_schema() -> dict:
    """供 function calling / 结构化解析的 JSON Schema。"""
    return {
        "type": "object",
        "properties": {
            "problem_definition": {"type": "string"},
            "key_metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric_name": {"type": "string"},
                        "metric_value": {"type": "string"},
                        "metric_unit": {"type": "string"},
                        "metric_period": {"type": "string"},
                    },
                    "required": ["metric_name", "metric_value"],
                },
            },
            "evidence_list": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_type": {"type": "string"},
                        "source_name": {"type": "string"},
                        "evidence_text": {"type": "string"},
                        "related_metric": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["source_type", "source_name", "evidence_text"],
                },
            },
            "conclusion_text": {"type": "string"},
            "missing_data_text": {"type": "string"},
            "next_action_text": {"type": "string"},
        },
        "required": ["problem_definition", "conclusion_text"],
    }


# 避免循环 import 时未定义
from app.domains.agent.schemas import SixSectionResult  # noqa: E402
