#!/bin/sh
# 容器启动：等 MySQL 健康 → 迁移 → 种子 → (示例数据) → 启动 uvicorn
set -e

echo "[entrypoint] 等待 MySQL 就绪…"
python - <<'PY'
import os, time, pymysql, sys
for _ in range(30):
    try:
        pymysql.connect(
            host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]),
            user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], connect_timeout=3,
        )
        break
    except Exception:
        time.sleep(2)
else:
    print("MySQL 未就绪，退出"); sys.exit(1)
print("[entrypoint] MySQL 就绪")
PY

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] 基线种子"
python -m scripts.seed

if [ "${FLAG_SCENARIO_DATA}" = "true" ]; then
  echo "[entrypoint] 生成场景示例数据（商品 / 库存）"
  python -m scripts.gen_scenario_goods
  python -m scripts.gen_scenario_inventory
fi

echo "[entrypoint] 启动 uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
