#!/bin/bash
# ============================================================
# 经营归因分析系统 · 云服务器一键部署脚本（GitHub 拉取版）
# ============================================================
# 用法（在云服务器上以 root 执行）：
#   bash server_deploy.sh [服务器IP] [LLM_API_KEY]
#
# 示例：
#   bash server_deploy.sh                                        # 默认 IP 106.55.27.9
#   bash server_deploy.sh 106.55.27.9
#   bash server_deploy.sh 106.55.27.9 sk-xxxx你的DeepSeek_key
#
# 前置：一台干净的云服务器（Ubuntu 20.04+/22.04 或 CentOS 7/8）
#       已能用 SSH 登录，有 root 权限
# 说明：幂等可重跑，重跑时跳过已存在的配置
# ============================================================
set -e

# ==================== 可配置参数 ====================
SERVER_IP="${1:-106.55.27.9}"
LLM_API_KEY="${2:-}"                                    # 可空，部署后在管理后台配置
REPO_URL="https://github.com/mashuzhong525-creator/p2_attribution_analysis.git"
APP_DIR="/opt/bia"
DATA_DIR="/data/bia"
# 生产编排用双文件叠加（base + prod 数据盘覆盖）
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
err()  { echo -e "${RED}[ERR]${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
step() { echo ""; echo "=========================================="; echo "  $1"; echo "=========================================="; }

# ==================== [0/10] Root 检查 ====================
if [ "$(id -u)" != "0" ]; then
    err "请以 root 用户执行：sudo bash server_deploy.sh"
fi

# ==================== [1/10] 安装 Docker + Git ====================
step "[1/10] 检查 / 安装 Docker + Git"

# 确保 git 可用（git clone 需要）
if ! command -v git >/dev/null 2>&1; then
    echo "安装 git..."
    if command -v apt-get >/dev/null 2>&1; then
        apt-get update -y && apt-get install -y git
    elif command -v yum >/dev/null 2>&1; then
        yum install -y git
    fi
    ok "git 安装完成"
else
    ok "git 已安装"
fi

if command -v docker >/dev/null 2>&1; then
    ok "Docker 已安装：$(docker --version)"
else
    echo "Docker 未安装，开始自动安装..."
    if command -v apt-get >/dev/null 2>&1; then
        # Ubuntu / Debian
        apt-get update -y
        apt-get install -y ca-certificates curl gnupg lsb-release
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    elif command -v yum >/dev/null 2>&1; then
        # CentOS / RHEL
        yum install -y yum-utils
        yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    else
        err "不支持的系统，请手动安装 Docker：https://docs.docker.com/engine/install/"
    fi
    systemctl enable docker
    systemctl start docker
    ok "Docker 安装完成"
fi

# 检查 compose 插件
if docker compose version >/dev/null 2>&1; then
    ok "Docker Compose 插件就绪"
else
    err "Docker Compose 插件未安装，请手动安装：apt-get install docker-compose-plugin"
fi

# ==================== [2/10] 拉取代码 ====================
step "[2/10] 从 GitHub 拉取代码"

if [ -d "$APP_DIR/.git" ]; then
    echo "目录已存在，执行 git pull 更新..."
    cd "$APP_DIR"
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || warn "git pull 失败，使用现有代码继续"
else
    echo "克隆仓库到 $APP_DIR ..."
    # 注意：必须指定 -b main，仓库默认分支(master)是旧版代码，缺少 docker-compose/Dockerfile/frontend
    git clone -b main "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi
ok "代码就绪：$(pwd)"

# ==================== [3/10] 生成生产密钥 ====================
step "[3/10] 生成生产密钥（数据库密码 / 加密密钥 / OIDC 密钥）"

# 生成强随机密码（仅在 .env 不存在时生成，避免重跑覆盖）
if [ ! -f .env ]; then
    DB_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    MYSQL_ROOT_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24 | tr -d '/+=' | head -c 32)
    OIDC_CLIENT_SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32 | tr -d '/+=' | head -c 40)
    APP_ENCRYPTION_KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null || openssl rand -base64 32 | tr '/+' '_-' | head -c 44)

    cat > .env <<EOF
# ===== 经营归因分析系统 · 生产环境配置 =====
# 由 server_deploy.sh 自动生成于 $(date '+%Y-%m-%d %H:%M:%S')
# 此文件包含敏感密钥，切勿提交 git（已在 .gitignore 排除）

# ---- 数据库 ----
DB_HOST=mysql
DB_PORT=3306
DB_USER=bia
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=bia
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}

# ---- Redis ----
REDIS_HOST=redis
REDIS_PORT=6379

# ---- OIDC 认证 ----
OIDC_CLIENT_ID=bia-web
OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}
OIDC_REDIRECT_URI=http://${SERVER_IP}:8080/auth/callback

# ---- 加密密钥（数据源密码 AES）----
APP_ENCRYPTION_KEY=${APP_ENCRYPTION_KEY}

# ---- 功能开关 ----
FLAG_SCENARIO_DATA=true
FLAG_COMMAND_EXEC=false
FLAG_ATTACHMENT=true
FLAG_EXTERNAL_DS=false
FLAG_RESULT_GENERATE=false
FLAG_WS_HEARTBEAT=true

# ---- 资源限制 ----
TASK_CONCURRENCY_LIMIT=3
WS_MAX_CONNECTIONS=10

# ---- LLM ----
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=${LLM_API_KEY}

# ---- 环境与跨域 ----
APP_ENV=prod
CORS_ORIGINS=["http://${SERVER_IP}:8080"]
EOF
    ok ".env 已生成（含自动生成的强密码）"
    echo "  DB_PASSWORD        = ${DB_PASSWORD:0:8}..."
    echo "  MYSQL_ROOT_PASSWD  = ${MYSQL_ROOT_PASSWORD:0:8}..."
    echo "  OIDC_CLIENT_SECRET = ${OIDC_CLIENT_SECRET:0:8}..."
    echo "  APP_ENCRYPTION_KEY = ${APP_ENCRYPTION_KEY:0:8}..."
else
    warn ".env 已存在，跳过生成（如需重新生成请先删除 .env）"
    # 确保关键配置项指向正确的服务器 IP
    if grep -q "localhost" .env 2>/dev/null; then
        warn "检测到 .env 中有 localhost，更新为服务器 IP..."
        cp .env .env.bak.$(date +%s)
        sed -i "s|OIDC_REDIRECT_URI=.*|OIDC_REDIRECT_URI=http://${SERVER_IP}:8080/auth/callback|" .env
        sed -i 's|APP_ENV=.*|APP_ENV=prod|' .env
        sed -i "s|CORS_ORIGINS=.*|CORS_ORIGINS=[\"http://${SERVER_IP}:8080\"]|" .env
        ok ".env 已更新（原文件备份为 .env.bak.*）"
    fi
fi

# ==================== [4/10] 生成 JWT RSA 私钥 ====================
step "[4/10] 生成 JWT 签名 RSA 私钥"

if [ -f secrets/oidc_rsa_private.pem ]; then
    ok "RSA 私钥已存在，跳过"
else
    mkdir -p secrets
    openssl genrsa -out secrets/oidc_rsa_private.pem 2048
    chmod 600 secrets/oidc_rsa_private.pem
    ok "RSA 私钥已生成（2048 bit）"
fi

# ==================== [5/10] 创建数据盘目录 ====================
step "[5/10] 创建数据持久化目录"

mkdir -p ${DATA_DIR}/mysql ${DATA_DIR}/redis ${DATA_DIR}/appdata

# MySQL 官方镜像内 uid=999
chown -R 999:999 ${DATA_DIR}/mysql 2>/dev/null || true
chown -R 999:999 ${DATA_DIR}/redis 2>/dev/null || true
# backend 容器内默认 uid=1000
chown -R 1000:1000 ${DATA_DIR}/appdata 2>/dev/null || true

ok "数据目录就绪：${DATA_DIR}/{mysql,redis,appdata}"

# ==================== [6/10] 启动 MySQL + Redis ====================
step "[6/10] 启动 MySQL + Redis（使用生产编排）"

$COMPOSE up -d mysql redis
ok "MySQL + Redis 启动中"

echo "等待 MySQL 就绪（最多 120 秒）..."
ROOT_PWD=$(grep '^MYSQL_ROOT_PASSWORD=' .env | cut -d= -f2)
for i in $(seq 1 60); do
    if $COMPOSE exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -p"${ROOT_PWD}" >/dev/null 2>&1; then
        ok "MySQL 就绪（耗时 ${i}x2s）"
        break
    fi
    [ "$i" = "60" ] && err "MySQL 未就绪，请检查：$COMPOSE logs mysql"
    sleep 2
done

# ==================== [7/10] 导入数据库快照 ====================
step "[7/10] 导入数据库快照（bia + 场景库）"

# 检查 bia 库是否已有数据（幂等：已有数据则跳过）
TABLE_COUNT=$($COMPOSE exec -T mysql mysql -uroot -p"${ROOT_PWD}" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='bia'" 2>/dev/null || echo "0")

if [ "${TABLE_COUNT}" -gt 0 ] 2>/dev/null; then
    ok "bia 库已有 ${TABLE_COUNT} 张表，跳过导入"
else
    if [ -f bia_migrate.sql ]; then
        echo "导入 bia_migrate.sql（约 1260 行，包含 schema + 种子 + 场景数据）..."
        $COMPOSE exec -T mysql sh -c 'exec mysql -uroot -p"'"${ROOT_PWD}"'"' < bia_migrate.sql
        ok "数据导入完成"
    else
        warn "未找到 bia_migrate.sql，将依赖 entrypoint 的 alembic + seed 初始化"
    fi
fi

# ==================== [8/10] 构建并启动全部服务 ====================
step "[8/10] 构建并启动全部服务（backend + frontend）"

echo "构建镜像（首次约 3~5 分钟，包含 npm install + pip install）..."
$COMPOSE up -d --build
sleep 5

echo ""
echo "--- 服务状态 ---"
$COMPOSE ps

ok "全部服务已启动"

# ==================== [9/10] 配置防火墙 ====================
step "[9/10] 配置防火墙（仅放行 22 + 8080）"

if command -v ufw >/dev/null 2>&1; then
    echo "检测到 ufw，配置规则..."
    ufw allow 22/tcp   >/dev/null 2>&1 || true
    ufw allow 8080/tcp >/dev/null 2>&1 || true
    # 3306/6379/8001 已在 docker-compose 中绑定 127.0.0.1，无需放行
    echo "y" | ufw enable 2>/dev/null || true
    ok "ufw 防火墙已配置：22(SSH) + 8080(Web) 放行"
    warn "请同时到云控制台 -> 安全组 -> 放行 TCP 8080 端口"
elif command -v firewall-cmd >/dev/null 2>&1; then
    echo "检测到 firewalld，配置规则..."
    firewall-cmd --permanent --add-port=22/tcp   2>/dev/null || true
    firewall-cmd --permanent --add-port=8080/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    ok "firewalld 已配置：22(SSH) + 8080(Web) 放行"
    warn "请同时到云控制台 -> 安全组 -> 放行 TCP 8080 端口"
else
    warn "未检测到 ufw / firewalld，请手动配置防火墙放行 22 + 8080 端口"
fi
warn "云控制台 -> 安全组 -> 放行 TCP 8080 端口（必须）"

# ==================== [10/10] 启动验证 ====================
step "[10/10] 启动验证"

echo "等待 backend 初始化完成（迁移 + 种子，约 30~60s）..."
for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/" 2>/dev/null || echo "000")
    if [ "$code" != "000" ] && [ "$code" != "" ]; then
        break
    fi
    sleep 2
done

echo ""
echo "--- 验证结果 ---"
echo "前端 8080 HTTP: ${code:-未响应}"

# 后端 API 健康检查
api_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080/api/health" 2>/dev/null || echo "000")
echo "后端 /api/health: ${api_code:-未响应}"

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "  访问地址:  http://${SERVER_IP}:8080"
echo "  默认账号:  admin / admin123"
echo "             analyst / analyst123"
echo "  ⚠️  首次登录必须修改密码"
echo ""
if [ -z "$LLM_API_KEY" ]; then
    echo "  ⚠️  LLM API Key 未配置"
    echo "     方式1: 登录管理后台 -> 系统配置 -> 填入 DeepSeek API Key"
    echo "     方式2: 编辑 .env 添加 LLM_API_KEY 后重启 backend"
fi
echo ""
echo "  常用运维命令："
echo "    cd ${APP_DIR}"
echo "    ${COMPOSE} ps                    # 查看服务状态"
echo "    ${COMPOSE} logs -f backend       # 跟踪后端日志"
echo "    ${COMPOSE} restart backend       # 重启后端"
echo "    ${COMPOSE} down                  # 停止（保留数据）"
echo "    ${COMPOSE} up -d --build         # 重新构建并启动"
echo ""
echo "  数据备份："
echo "    ${COMPOSE} exec -T mysql mysqldump -uroot -p\"\\\${ROOT_PWD}\" bia > backup.sql"
echo "    重要：同时备份 .env 和 secrets/ 目录（含加密密钥，缺一不可）"
echo ""
