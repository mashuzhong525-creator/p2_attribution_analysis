"""六部分结果契约（C-ATTRIBUTION）。"""

import pytest

from app.engine.attribution import build_fallback_result, validate_result


def test_validate_result_accepts_six_fields():
    data = {
        "problem_definition": "为什么库存下降",
        "key_metrics": [{"metric_name": "库存周转率", "metric_value": "3.0", "metric_unit": "次", "metric_period": "2026-07"}],
        "evidence_list": [{"source_type": "database", "source_name": "sales", "evidence_text": "销量 300", "related_metric": "库存周转率", "confidence": 0.9}],
        "conclusion_text": "结论",
        "missing_data_text": "无",
        "next_action_text": ["动作1", "动作2"],
    }
    validate_result(data)


def test_validate_result_rejects_missing_field():
    with pytest.raises(ValueError):
        validate_result({"problem_definition": "缺字段", "key_metrics": []})


def test_build_fallback_result_from_rows():
    result = build_fallback_result(
        question="为什么库存下降",
        rows=[{"sku_id": "A1", "sales_qty": 100}],
        columns=["sku_id", "sales_qty"],
    )
    assert result["problem_definition"] == "为什么库存下降"
    assert result["key_metrics"]
    assert len(result["next_action_text"]) >= 2
