"""SQL 只读安全校验。"""

import pytest

from app.engine.sql_guard import validate_select


def test_allows_simple_select():
    validate_select("SELECT sku_id, SUM(sales_qty) FROM sales WHERE date >= '2026-07-01' GROUP BY sku_id")


def test_allows_select_with_semicolon_tail():
    validate_select("SELECT * FROM sales;")


def test_rejects_delete():
    with pytest.raises(ValueError):
        validate_select("DELETE FROM sales WHERE sku_id=1")


def test_rejects_update_and_insert():
    with pytest.raises(ValueError):
        validate_select("UPDATE sales SET amount=0")
    with pytest.raises(ValueError):
        validate_select("INSERT INTO sales(sku_id) VALUES(1)")


def test_rejects_multiple_statements():
    with pytest.raises(ValueError):
        validate_select("SELECT * FROM sales; DELETE FROM sales")


def test_rejects_comment_hidden_write():
    with pytest.raises(ValueError):
        validate_select("SELECT * FROM sales -- ; DELETE FROM sales")
