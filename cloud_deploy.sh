#!/bin/bash
# ============================================================
# 经营归因分析系统 · 云服务器一键部署脚本
# 用法：解包 bia_upload.tar.gz 后，在包目录内执行：
#   bash cloud_deploy.sh
# 前置：已安装 docker + docker compose 插件（v2）
# 说明：幂等可重跑；重跑时会跳过已存在的导入/容器
# ============================================================
set -e
cd "$(dirname "$0")"

PUBLIC_ADDR="${1:-106.55.27.9}"   # 可传参覆盖：bash cloud_deploy.sh <域名或IP>

echo "=========================================="
echo "[1/6] 检查环境依赖"
echo "=========================================="
command -v docker >/dev/null 2>&1 || { echo "❌ 未安装 docker，请先安装"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "❌ 未安装 docker compose 插件，请先安装"; exit 1; }

echo "=========================================="
echo "[2/6] 配置 .env（生产模式 + 公网地址 ${PUBLIC_ADDR}）"
echo "=========================================="
[ -f .env ] || { echo "❌ 缺少 .env"; exit 1; }
cp .env .env.cloud.bak 2>/dev/null || true
sed -i "s|^APP_ENV=.*|APP_ENV=prod|" .env
sed -i "s|^OIDC_ISSUER=.*|OIDC_ISSUER=http://${PUBLIC_ADDR}:8080|" .env
sed -i "s|^OIDC_REDIRECT_URI=.*|OIDC_REDIRECT_URI=http://${PUBLIC_ADDR}:8080/auth/callback|" .env
sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"http://${PUBLIC_ADDR}:8080\"]|" .env
echo "✓ .env 已更新（原文件备份为 .env.cloud.bak）"

echo "=========================================="
echo "[3/6] 启动 MySQL + Redis（首次会初始化）"
echo "=========================================="
docker compose up -d mysql redis
echo "等待 MySQL 就绪（最多 120s）..."
for i in $(seq 1 60); do
  if docker compose exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -p"$(grep '^MYSQL_ROOT_PASSWORD=' .env | cut -d= -f2)" >/dev/null 2>&1; then
    echo "✓ MySQL 就绪（${i}x2s）"; break
  fi
  [ "$i" = "60" ] && { echo "❌ MySQL 未就绪，请检查日志：docker compose logs mysql"; exit 1; }
  sleep 2
done

echo "=========================================="
echo "[4/6] 导入数据库快照（bia + 场景库）"
echo "=========================================="
if [ -f bia_migrate.sql ]; then
  docker compose exec -T mysql sh -c 'exec mysql -uroot -p"'"$(grep '^MYSQL_ROOT_PASSWORD=' .env | cut -d= -f2)"'"' < bia_migrate.sql
  echo "✓ 数据导入完成"
else
  echo "⚠️ 未找到 bia_migrate.sql，跳过导入（业务库将为空）"
fi

echo "=========================================="
echo "[5/6] 构建并启动全部服务"
echo "=========================================="
docker compose up -d --build
sleep 3
docker compose ps

echo "=========================================="
echo "[6/6] 启动验证"
echo "=========================================="
sleep 2
code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/" || true)
echo "前端 8080 HTTP: ${code:-未响应}"
echo "----- 完成后请到云控制台放行 8080 端口（安全组/防火墙） -----"
echo "访问地址: http://${PUBLIC_ADDR}:8080"
echo "账号: admin / admin123  或  analyst / analyst123（建议登录后尽快改密）"
