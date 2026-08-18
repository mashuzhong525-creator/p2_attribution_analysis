# 经营归因分析系统

对话式 BI + Agent 归因 + 六段式结构化输出的经营归因分析平台。用户用自然语言提问（如"为什么 6 月信息流渠道点击量下滑？"），系统自动查询数据源、执行归因分析，并输出结构化六段式结论（问题定义 / 关键指标 / 证据链 / 归因结论 / 数据缺口 / 下一步建议）。

## 技术栈与架构

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Pinia + Vue Router（纯手写 CSS，无 UI 库） |
| 后端 | FastAPI + SQLAlchemy 2.0（asyncmy 异步）+ Pydantic v2 |
| 数据 | MySQL 8.0（业务库 + 场景示例库）、Redis 7（WS seq / 锁） |
| 认证 | 自建 OIDC 认证中心（授权码模式，RS256 + JWKS），合并进 backend |
| 归因引擎 | 自主规划 + 工具调用（db_query / file_read / file_write / text_search / command_exec）；未配置 LLM 时走离线确定性分析（演示开箱即用） |
| 部署 | Docker Compose 单机（独立命名空间 `bia`），目标资源 2C2G |

```
浏览器 ── 8080 ── frontend (nginx 静态托管 + 反代)
                      │  /api、/api/ws
                  backend (FastAPI :8000)
                      │
              ┌───────┴───────┐
           mysql:3306      redis:6379
        (bia + scenario_*)   (WS seq/锁)
```

## 快速启动

前置：Docker Desktop（或任意 Docker 引擎）。

```bash
# 1. 进入项目根目录
cd <项目目录>

# 2. 构建并启动全部服务（首次构建较慢）
docker compose up -d --build

# 3. 等待 backend 完成初始化（迁移 + 种子 + 场景数据），约 1~2 分钟
docker compose ps          # 四服务均应为 running/healthy

# 4. 浏览器访问
#    前端： http://localhost:8080
#    后端API：http://localhost:8000/docs   （Swagger）
```

**默认账号**：`admin / admin123`（管理员）、`analyst / analyst123`（分析师）。**首次登录必须修改密码**，修改成功后才能使用系统；生产部署请把初始口令替换为强口令。

backend 容器启动时自动执行：`alembic upgrade head`（建 17 表）→ 种子（配置/认证用户/客户端/业务用户/数据源）→ 生成两个场景示例库数据（约 15 万行），**无需手工初始化**。

## 演示场景

| 场景 | 数据源 | 推荐提问 |
|---|---|---|
| 商品目录优化 | 商品目录优化示例库 | 为什么 6 月信息流渠道点击量下滑？ |
| 库存异常分析 | 库存异常分析示例库 | 华东仓 SKU0001 缺货原因是什么？ |

提示：新建会话时可选数据源；不选则默认绑定第一个启用数据源。

## 验证与测试

端到端冒烟测试覆盖：健康检查 → 登录 → 首次登录强制改密（业务拦截 / 错误原密码 / 正式改密 / 标记清除）→ 选数据源 → 建会话 → 提问 → 任务终态 → 六段式结果 → 会话历史 → WS token（自动清理测试会话，并在结束后恢复初始口令）：

```bash
python scripts/smoke_test.py
# 可选环境变量：BIA_BASE / BIA_USER / BIA_PASS / BIA_QUESTION / BIA_QUESTION2
```

WebSocket 实时链路依赖 `websockets` 库（已写入 `requirements.txt`）；缺失时 uvicorn 会把升级请求当作普通 HTTP 返回 404，前端自动降级为轮询，仍可完成分析。

## 目录结构

```
├── app/                  # 后端（FastAPI）
│   ├── core/             # 配置 / 安全(JWT·AES·bcrypt) / DB / Redis / 错误 / 日志
│   ├── models/           # ORM：13 张业务表 + 4 张认证表
│   ├── schemas/          # 请求/响应契约
│   └── domains/          # 业务域：auth / chat / task / agent / config / datasource / attachment
├── frontend/             # 前端（Vue3），Dockerfile + nginx.conf
├── alembic/              # 数据库迁移（0001_initial 建 17 表）
├── scripts/              # 种子 / 场景数据生成 / mysql-init / entrypoint
├── docs/                 # 设计文档（PRD / 数据模型 / 概要 / SDD / 原型 / 过程稿）
├── docker-compose.yml    # 编排（name: bia）
└── Dockerfile            # backend 镜像
```

## 常用命令

```bash
docker compose ps                      # 查看服务状态
docker compose logs -f backend         # 跟踪 backend 日志
docker compose up -d --build backend   # 修改后端后重建
docker compose down                    # 停止（保留数据卷）
docker compose down -v                 # 停止并清空数据（重建初始化）
docker compose config                  # 校验编排配置
```

## 配置（环境变量）

默认值可直接跑通开发/演示；**生产部署必须显式设置**以下项：

| 变量 | 默认 | 生产必填 | 说明 |
|---|---|---|---|
| `OIDC_RSA_PRIVATE_KEY` | 空（启动生成临时密钥） | ✅ | RSA PEM 私钥，不设则重启后所有登录态失效 |
| `APP_ENCRYPTION_KEY` | 空（退化用 client secret 派生） | ✅ | 数据源密码 AES 加密密钥（Fernet 32 字节 base64） |
| `OIDC_CLIENT_SECRET` | `change-me-client-secret` | ✅ | 认证客户端密钥 |
| `DB_PASSWORD` | `bia_password` | ✅ | MySQL 业务账号密码（与 MYSQL_PASSWORD 一致） |
| `MYSQL_ROOT_PASSWORD` | `root_password` | ✅ | MySQL root 密码 |
| `APP_ENV` | `prod` | — | `prod` 时 Cookie 仅 HTTPS |
| `CORS_ORIGINS` | 本机前端地址 | 按需 | 前端域名白名单 |

完整清单见 `docs/部署运维文档.md`。

> 隐私与安全：`.env` 已被 `.gitignore` 排除，仓库只提交 `.env.example`；默认账号与密码仅用于本地演示，部署前请替换为强口令并显式设置 `OIDC_RSA_PRIVATE_KEY` 与 `APP_ENCRYPTION_KEY`。

## 文档索引

- `docs/经营归因分析系统-需求规格说明书PRD.md` — PRD v1.1（2C2G 收敛）
- `docs/design/数据模型设计.md`、`docs/design/概要设计.md`、`docs/design/详细设计-SDD.md`、`docs/design/详细设计-SDD-前端.md`
- `docs/部署运维文档.md` — 部署、环境变量、故障排查
- `docs/prototype/低保真原型-wireframe.html` — 可交互原型
