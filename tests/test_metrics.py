"""指标口径：库存周转率、转化率。"""

from app.engine.metrics import conversion_rate, inventory_turnover, turnover_days


def test_inventory_turnover_quantity_basis():
    assert inventory_turnover(sales_qty=300, avg_stock=100) == 3.0
    assert turnover_days(turnover=3.0, period_days=90) == 30.0


def test_inventory_turnover_zero_stock_returns_zero():
    assert inventory_turnover(sales_qty=300, avg_stock=0) == 0.0


def test_conversion_rate_unique_users():
    assert conversion_rate(order_users=50, visit_users=200) == 0.25
    assert conversion_rate(order_users=0, visit_users=100) == 0.0
