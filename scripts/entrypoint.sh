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
  echo "[entrypoint] 补全场景示例数据的归因维度（素材 / 预算 / 安全阈值 / 在途多单）"
  python -m scripts.enrich_scenario_data
  echo "[entrypoint] 生成演示会话（两组完整分析示例，可历史回放）"
  python -m scripts.seed_demo_conversations
fi

# JWT 签名私钥：docker-compose 挂载 secrets/oidc_rsa_private.pem（生产），
# 未挂载时留空，应用启动会生成临时密钥并告警（仅限开发）。
if [ -z "${OIDC_RSA_PRIVATE_KEY}" ] && [ -f /run/secrets/oidc_rsa_private.pem ]; then
  export OIDC_RSA_PRIVATE_KEY="$(cat /run/secrets/oidc_rsa_private.pem)"
  echo "[entrypoint] 已加载 OIDC RSA 私钥（来自挂载文件）"
fi

echo "[entrypoint] 启动 uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
