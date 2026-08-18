"""Text2SQL 引擎：SQL 提取、生成、执行自愈。"""

from app.engine.sql_gen import extract_sql, generate_sql
from app.engine.executor import execute_with_retry


def test_extract_sql_from_code_block():
    text = '```sql\nSELECT sku_id FROM sales\n```\n说明文字'
    assert extract_sql(text) == "SELECT sku_id FROM sales"


def test_extract_sql_plain_text():
    assert extract_sql("SELECT 1") == "SELECT 1"


def test_generate_sql_injects_schema_and_metric():
    def fake_llm(prompt):
        assert "sales" in prompt and "库存周转率" in prompt
        return "```sql\nSELECT sku_id, SUM(sales_qty) AS sales_qty FROM sales GROUP BY sku_id\n```"

    sql = generate_sql(
        question="哪个 SKU 销量最高？",
        schema_text="sales(sku_id, sales_qty, date)",
        metrics_text="库存周转率 = 期间销量 ÷ 平均库存量",
        llm_call=fake_llm,
    )
    assert sql.startswith("SELECT")


def test_execute_with_retry_heals_once(db, monkeypatch):
    calls = {"n": 0}

    def fake_exec(sql):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("syntax error")
        return {"rows": [{"x": 1}], "columns": ["x"]}

    result = execute_with_retry("SELECT 1", exec_fn=fake_exec, fix_fn=lambda err, sql: "SELECT 2")
    assert result["rows"] == [{"x": 1}]
    assert calls["n"] == 2
