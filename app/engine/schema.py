"""演示场景的表结构与指标口径（注入 Text2SQL 提示词）。"""

SCHEMA_TEXT = """inventory(sku_id, warehouse_id, stock_qty, period)
inbound(sku_id, warehouse_id, in_qty, in_date)
outbound(sku_id, warehouse_id, out_qty, out_date)
sales(sku_id, date, sales_qty, amount)
customers(user_id, register_date, region, channel)
visits(user_id, page, event_time)
add_to_cart(user_id, sku_id, event_time)
orders(order_id, user_id, sku_id, order_time, amount)"""

METRICS_TEXT = """- 库存周转率（期间）= 期间销量总和 ÷ 平均库存量；平均库存量取 inventory 表中该期间的 stock_qty
- 库存周转天数 = 期间天数 ÷ 库存周转率
- 下单转化率（期间）= 下单独立用户数 ÷ 访问独立用户数（按 user_id 去重）
- 加购转化率 = 加购独立用户数 ÷ 访问独立用户数
- 异常判定：库存周转率环比下降超过 20%，或转化率环比下降超过 15%"""
