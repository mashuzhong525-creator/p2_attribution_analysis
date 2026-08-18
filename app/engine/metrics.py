"""指标口径计算。"""


def inventory_turnover(sales_qty: float, avg_stock: float) -> float:
    return round(sales_qty / avg_stock, 2) if avg_stock else 0.0


def turnover_days(turnover: float, period_days: int) -> float:
    return round(period_days / turnover, 1) if turnover else 0.0


def conversion_rate(order_users: int, visit_users: int) -> float:
    return round(order_users / visit_users, 4) if visit_users else 0.0
