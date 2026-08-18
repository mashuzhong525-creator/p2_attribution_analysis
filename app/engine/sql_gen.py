"""Text2SQL：schema/指标注入 → LLM 生成 SQL → 只读校验。"""

import re

from .sql_guard import validate_select

SQL_PROMPT_TEMPLATE = """你是数据分析 SQL 助手。根据业务问题，仅使用给定的表结构生成一条只读 SQL（SQLite 方言）。

【规则】
1. 只能 SELECT，禁止 DELETE/UPDATE/INSERT/DROP/ALTER/ATTACH 等任何写操作；
2. 只能使用下方列出的表与字段，禁止猜测不存在的字段；
3. 指标口径必须按下方【指标口径】定义计算；
4. 只输出 SQL 代码块，不要任何解释。

【指标口径】
{metrics_text}

【表结构】
{schema_text}

【业务问题】
{question}

【SQL】"""


def extract_sql(text: str) -> str:
    m = re.search(r"```sql\s*(.*?)```", text or "", re.S | re.I)
    if m:
        return m.group(1).strip()
    return (text or "").strip()


def generate_sql(question: str, schema_text: str, metrics_text: str, llm_call) -> str:
    prompt = SQL_PROMPT_TEMPLATE.format(
        question=question, schema_text=schema_text, metrics_text=metrics_text
    )
    raw = llm_call(prompt)
    sql = extract_sql(raw)
    return validate_select(sql)
