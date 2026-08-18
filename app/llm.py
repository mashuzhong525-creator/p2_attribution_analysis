"""LLM 调用：DeepSeek（OpenAI 兼容）+ 离线演示降级。"""

import json

import httpx

from .config import settings


def chat_completion(prompt: str) -> str:
    if not settings.deepseek_api_key:
        raise RuntimeError("未配置 DeepSeek API Key")
    resp = httpx.post(
        f"{settings.deepseek_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
        json={
            "model": settings.deepseek_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "stream": False,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _offline_attribution(question: str) -> str:
    return json.dumps(
        {
            "problem_definition": question,
            "key_metrics": [{"metric_name": "查询行数", "metric_value": "示例", "metric_unit": "行", "metric_period": "近3个月"}],
            "evidence_list": [{"source_type": "database", "source_name": "sales", "evidence_text": "离线演示数据", "related_metric": "销量", "confidence": 0.8}],
            "conclusion_text": "（离线演示模式）已基于查询结果生成初步归因，请配置 DeepSeek API 后获得完整分析。",
            "missing_data_text": "缺少历史同期与成本数据。",
            "next_action_text": ["补充历史同期数据做环比", "按仓库/SKU 维度拆分定位异常"],
        },
        ensure_ascii=False,
    )


def default_llm_call(prompt: str) -> str:
    if settings.deepseek_api_key:
        try:
            return chat_completion(prompt)
        except Exception as e:  # noqa: BLE001
            return f"（模型调用失败：{e}）"
    # 离线演示：按提示词类型返回确定性的示例结果
    if "【SQL】" in prompt:
        if "转化率" in prompt:
            return (
                "```sql\n"
                "SELECT "
                "(SELECT COUNT(DISTINCT user_id) FROM visits WHERE event_time LIKE '2026-07%') AS visit_users, "
                "(SELECT COUNT(DISTINCT user_id) FROM orders WHERE order_time LIKE '2026-07%') AS order_users\n"
                "```"
            )
        if "库存" in prompt or "周转" in prompt:
            return (
                "```sql\n"
                "SELECT i.period, SUM(i.stock_qty) AS stock_qty, SUM(s.sales_qty) AS sales_qty "
                "FROM inventory i LEFT JOIN sales s ON substr(s.date,1,7)=i.period "
                "GROUP BY i.period ORDER BY i.period\n"
                "```"
            )
        return (
            "```sql\n"
            "SELECT sku_id, SUM(sales_qty) AS sales_qty, SUM(amount) AS amount "
            "FROM sales GROUP BY sku_id ORDER BY sales_qty DESC LIMIT 10\n"
            "```"
        )
    if "【JSON】" in prompt:
        return _offline_attribution(prompt.split("【业务问题】")[-1].split("【查询结果】")[0].strip())
    return "（离线演示模式）"
