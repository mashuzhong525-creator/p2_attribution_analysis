# 经营归因分析系统 详细设计（SDD v1.1）

> 面向 AI 编码实现的模块级可执行规格（Detailed Design Spec）
> 依据：PRD v1.1 + 数据模型设计 v1.0 + 概要设计 v1.0 + 详细设计评审会（2026-08-18，grill-me，4 项新增决策）
> 阅读对象：编码 Agent / 开发人员。本文档所有契约字段级定死，可直接据此写代码；未定死处已标注"实现自定"。
> 关联文件：`docs/design/概要设计.md`（架构与流程）、`docs/design/数据模型设计.md`（字段级基线）、`docs/prompts/`（提示词）、`docs/process/需求评审过程稿.md`（决策脉络）。

---

## 0. 文档信息

| 项 | 内容 |
|---|---|
| 版本 | v1.1 |
| 日期 | 2026-08-18 |
| 状态 | 评审稿（编码基线；前端章已深化至独立 Spec） |
| 覆盖范围 | 全局契约 / DDL / backend 模块签名 / auth-service / REST 契约 / WS 协议 / Agent 引擎 / 前端契约 / 关键流程伪代码 / 部署 / 测试 |

**修订记录**：
- v1.1（2026-08-18）：前端章（§9）深化为独立模块 Spec `详细设计-SDD-前端.md`。同步修正：§9.3 管理后台「四 Tab」→「六 Tab」、§9.4 WS 断线参数与概设 §5.4 对齐、§9.5 路由补 `/403` 与 ForbiddenView。前端全部契约以独立 Spec 为准（spec 优先约定）。

**约定**：本文档中「§n.m」引用本文档章节；「概设 §n」引用概要设计；「PRD §n」引用 PRD。代码块为 Python 3.12 / TypeScript 5 签名级伪代码，可直接落地。

---

## 1. 评审结论与收敛决策

### 1.1 评审范围与结论

对 PRD v1.1、数据模型设计 v1.0、概要设计 v1.0 三份初稿交叉比对，发现 **17 处问题**（P0×4 / P1×7 / P2×6）。整体结论：三份初稿内部自洽、可追溯，无大范围返工；问题集中在文档衔接处——概要设计声称的能力在字段定义或接口契约中缺载体。

### 1.2 问题处置表（17 处 → 方案 → 落地章节）

| # | 级别 | 问题 | 处置方案 | 落地 |
|---|---|---|---|---|
| 1 | P0 | conversations 缺 data_source_id（ER 图声称"会话可绑定数据源"但字段没有） | **conversations 加 `data_source_id`**，新建会话必选数据源（默认内置示例库） | §2.2/§3/§6 |
| 2 | P0 | POST /api/chat/send 无 attachment_ids，附件链路断裂 | **send 入参加 `attachment_ids`（可空）**，显式声明本轮分析使用的附件 | §6.2/§8.2 |
| 3 | P0 | 服务重启后 queued 任务悬挂（PRD 只处理 running） | 启动时 `UPDATE analysis_tasks SET task_status='failed', error_message='服务重启中断' WHERE task_status IN ('queued','running')` | §10.7 |
| 4 | P0 | result_generate 工具与 result 域 service 生成职责重叠（双写风险） | **收敛：Markdown 生成唯一入口 = result 域 service**（幂等、确定性）；`result_generate` 工具降级为"写中间文件"能力，不再生成最终结果文件；Agent 循环内不调用它，仅保留注册（flag 可关） | §8.3/§4.8 |
| 5 | P1 | ws seq 靠 Redis INCR，重启/key 过期回卷丢消息 | Redis 开 AOF（`appendonly yes`）+ 数据卷持久化；**启动对齐基线**：Redis 中 key 不存在时，从 `messages` 表 `MAX(seq_no)` 初始化；消息落库后抬升基线（§7.1.2） | §7.1/§11 |
| 6 | P1 | ping/pong 占业务 seq 污染去重 | **心跳走独立控制通道：信封不带 seq**，客户端不参与去重（收到 ping 仅回 pong） | §7.1.1 |
| 7 | P1 | 双示例 schema（scenario_goods/inventory）路由规则未定义 | **会话绑定数据源**（决策 1）+ `db_query` 强制 `schema.table` 全限定 + 白名单按数据源声明 | §7.2/§8.3 |
| 8 | P1 | system_configs 无完整配置清单，seed 无法落地 | 本文档 §2.4 给出 **31 项完整 seed 清单**（key/类型/默认值/分组） | §2.4 |
| 9 | P1 | 错误响应体未统一 | 统一错误响应 `{code, message, detail?}` + HTTP 状态映射（§2.1）；所有 REST/WS 错误走此结构 | §2.1 |
| 10 | P1 | refresh token 轮换与完整时序未定义 | 定死：refresh 使用即轮换（旧 token 立即 revoked，签发新 refresh）；时序见 §5.3/§10.1 | §5.3 |
| 11 | P1 | 认证中心用户管理无入口 | 本期仅初始化脚本建号（决策 3）；auth-service 不提供用户管理端点 | §5 |
| 12 | P2 | 前端乐观渲染策略未定义 | 定死：**发送后本地乐观渲染用户气泡 + pending 占位**；`message_start` 到达后以服务端回显为准（替换占位）；失败回滚 | §9.2/§10.1 |
| 13 | P2 | queued 排队位置无可见性 | 任务状态含 `queue_position`（队列中排第几，0=执行中）；`task_status` 事件 payload 带该字段 | §7.2 |
| 14 | P2 | 附件解析未完成时 Agent 行为未定义 | 上下文装配时：parsed → 注入 parse_result_json；parsing/pending → 注入"附件解析中"提示，工具不可用；failed → 注入失败说明 | §8.2 |
| 15 | P2 | 上下文装配算法缺失 | §8.2 给出完整算法（全量最近 N 条 + 更早摘要 + token 预算截断） | §8.2 |
| 16 | P2 | nginx 反代路径规则未列 | §11.2 给出完整 location 清单（/api /ws /auth → backend；/authorize /userinfo /.well-known → auth） | §11.2 |
| 17 | P2 | 外部数据源 PG 方言范围未定 | **本期仅 MySQL**（决策 4）；data_sources.db_type 仅存 'mysql'，预留枚举值 | §2.3/§8.3 |

### 1.3 详细设计评审新增决策（2026-08-18，grill-me 第 11 轮）

| # | 决策项 | 决策 | 影响 |
|---|---|---|---|
| D1 | 会话-数据源绑定 | `conversations.data_source_id`（逻辑外键，可空→默认内置示例库）；新建会话必选数据源 | DB 加列、create 接口加字段、前端加选择器 |
| D2 | 附件与消息关联 | `POST /api/chat/send` 增加 `attachment_ids`（可空，为空则本轮不注入附件） | send 契约、Agent 上下文 |
| D3 | 认证用户管理 | 本期仅初始化脚本建号（admin/analyst），无管理端点 | auth-service 范围缩小 |
| D4 | 外部数据源范围 | 本期仅 MySQL；`db_type` 枚举保留 'postgres' 占位 | db_query 单方言 |

---

## 2. 全局契约

### 2.1 通用错误响应结构

所有 REST 错误响应（HTTP 4xx/5xx）统一：

```json
{ "code": "TASK_BUSY", "message": "会话已有运行中任务", "detail": { "task_id": "01J2Y..." } }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| code | string | 业务错误码（PRD 8.5 全表 + 本文档补充） |
| message | string | 人类可读信息（中文） |
| detail | object? | 附加上下文（可选） |

错误码与 HTTP 状态映射（补充 PRD 8.5）：

| 码 | HTTP | 场景 |
|---|---|---|
| AUTH_REQUIRED | 401 | 未登录 |
| AUTH_EXPIRED | 401 | 登录态过期（前端跳刷新/登录） |
| FORBIDDEN | 403 | 非 admin 访问管理接口 / 非本人资源 |
| NOT_FOUND | 404 | 资源不存在 |
| VALIDATION_ERROR | 422 | 参数校验失败（FastAPI 默认） |
| TASK_BUSY | 409 | 会话已有运行中任务 |
| TASK_NOT_CANCELLABLE | 409 | 终态任务不可取消 |
| TASK_QUEUE_FULL | 429 | 任务队列满 |
| RATE_LIMITED | 429 | 接口限流 |
| FILE_TYPE_NOT_ALLOWED | 400 | 附件类型不允许 |
| FILE_TOO_LARGE | 400 | 附件超限 |
| FILE_PARSE_FAILED | 400 | 附件解析失败 |
| DATA_SOURCE_UNAVAILABLE | 400 | 数据源不可用/测试连接失败 |
| CONFIG_RELOAD_FAILED | 500 | 配置重载失败 |
| INTERNAL_ERROR | 500 | 兜底 |

### 2.2 REST 成功响应约定

- 成功响应直接返回数据体（非包裹结构），字段见 §6 各接口。
- 列表接口统一分页：`GET ...?page=1&page_size=20`，响应 `{ "items": [...], "total": 123, "page": 1, "page_size": 20 }`（`page_size` 上限 100）。
- 时间序列化：一律 ISO 8601 UTC（`2026-08-18T07:00:00Z`）；前端 `utils/format.ts` 转本地展示。

### 2.3 ID / 枚举 / 常量约定

| 项 | 约定 |
|---|---|
| 主键 | UUIDv7，VARCHAR(32) 无横线，应用层 `uuid7()` 生成（Python 用 `uuid` 库 `uuid7` 实现或第三方 `uuid7` 包） |
| 时间 | DATETIME（UTC），应用层 `datetime.now(timezone.utc)` 写入 |
| data_source_id 空值 | 默认回退内置示例库（`data_sources` 中 `name='business'` 预置行），不允许悬空 |
| 数据源类型 | `db_type` 本期仅 `'mysql'`；枚举预留 `'postgres'` |
| 消息 seq_no | `messages.seq_no`：会话内从 1 递增，`MAX(seq_no)+1` 取号（应用层，配 UK 防并发冲突，冲突重试） |

### 2.4 system_configs 完整配置清单（seed_configs.py 直接使用）

| config_key | config_type | 默认值 | config_group | 说明 |
|---|---|---|---|---|
| llm_base_url | string | `https://api.deepseek.com/v1` | llm | OpenAI 兼容 base_url |
| llm_api_key | string | ``（空） | llm | API Key（管理后台填写） |
| llm_model | string | `deepseek-chat` | llm | 模型名 |
| llm_price_prompt_per_1k | float | `0.001` | llm | 输入单价（元/1K tokens） |
| llm_price_completion_per_1k | float | `0.002` | llm | 输出单价（元/1K tokens） |
| llm_timeout_seconds | int | `120` | llm | 单次 LLM 调用超时 |
| llm_max_retries | int | `2` | llm | 调用重试次数 |
| task_max_steps | int | `8` | task | 单轮工具步数上限 |
| task_timeout_minutes | int | `10` | task | 单轮总时长上限 |
| task_max_running | int | `3` | task | 同时运行任务上限（信号量） |
| task_queue_maxsize | int | `10` | task | 排队上限（队列满返回 TASK_QUEUE_FULL） |
| context_max_messages | int | `20` | task | 上下文全量加载的最近消息条数 |
| context_summary_max_tokens | int | `1500` | task | 摘要 token 上限 |
| sql_max_rows | int | `500` | security | db_query 结果行数上限 |
| sql_timeout_seconds | int | `30` | security | db_query 超时 |
| cmd_timeout_seconds | int | `60` | security | command_exec 超时 |
| cmd_output_max_bytes | int | `65536` | security | 命令输出截断字节 |
| attachment_max_size_mb | int | `20` | security | 附件大小上限 |
| ws_token_ttl_seconds | int | `300` | security | WS 一次性令牌有效期 |
| ws_max_connections_per_user | int | `5` | security | 单用户 WS 连接上限 |
| soft_delete_days | int | `90` | retention | 软删数据保留期 |
| task_log_retention_days | int | `90` | retention | 任务日志保留期 |
| llm_calls_retention_days | int | `180` | retention | LLM 调用记录保留期 |
| heartbeat_interval_seconds | int | `30` | general | WS 心跳间隔 |
| flag_attachment | bool | `true` | feature_flag | 附件上传开关 |
| flag_export | bool | `true` | feature_flag | 结果导出开关 |
| flag_tool_db_query | bool | `true` | feature_flag | db_query 工具 |
| flag_tool_file_read | bool | `true` | feature_flag | file_read 工具 |
| flag_tool_file_write | bool | `true` | feature_flag | file_write 工具 |
| flag_tool_text_search | bool | `true` | feature_flag | text_search 工具 |
| flag_tool_command_exec | bool | `true` | feature_flag | command_exec 工具 |
| flag_scenario_data | bool | `true` | feature_flag | 示例数据注入开关 |

> 实现说明：`ConfigCache` 启动时全量加载，`POST /api/admin/reload` 后全量刷新；值按 `config_type` 反序列化（bool/int/float/string/json），非法值记 WARN 并回退默认。

### 2.5 环境变量清单

**backend：**

| 变量 | 必填 | 说明 |
|---|---|---|
| DATABASE_URL | Y | `mysql+asyncmy://user:pass@mysql:3306/business?charset=utf8mb4` |
| REDIS_URL | Y | `redis://redis:6379/0` |
| AUTH_SERVICE_URL | Y | `http://auth:8001` |
| AUTH_CLIENT_ID | Y | 预置 client_id（如 `biz-console`） |
| AUTH_CLIENT_SECRET | Y | 预置 client_secret |
| AUTH_REDIRECT_URI | Y | `https://<host>/auth/callback` |
| ENCRYPTION_KEY | Y | AES-256-GCM 密钥（base64，32 字节），用于 data_sources.password_encrypted |
| COOKIE_DOMAIN | N | 默认空（localhost 开发） |
| COOKIE_SECURE | N | 默认 true（生产 https） |
| DATA_ROOT | Y | 数据卷根目录（uploads/exports/workspace 的父目录） |

**auth-service：**

| 变量 | 必填 | 说明 |
|---|---|---|
| DATABASE_URL | Y | `mysql+asyncmy://user:pass@mysql:3306/auth?charset=utf8mb4`（独立 schema `auth`） |
| RSA_PRIVATE_KEY | N | 持久化私钥（PEM 字符串）；缺省启动时生成（重启后 backend 拉新公钥） |
| ACCESS_TOKEN_TTL | N | 默认 900（15 分钟） |
| REFRESH_TOKEN_TTL | N | 默认 604800（7 天） |
| AUTH_CODE_TTL | N | 默认 300（5 分钟） |

---

## 3. 数据库 DDL（MySQL 8，Alembic 0001_initial 直接使用）

> 变更点（相对数据模型设计 v1.0）：① `conversations` 加 `data_source_id`（逻辑外键 + 索引，可空）；② `data_sources` 加 `description`（场景说明，Agent 提示词注入用）。

```sql
-- ============ 业务库（schema: business） ============

CREATE TABLE users (
  id                VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  external_user_id  VARCHAR(64)  NOT NULL COMMENT '认证中心 sub',
  username          VARCHAR(64)  NOT NULL,
  display_name      VARCHAR(64)  NOT NULL,
  role              VARCHAR(16)  NOT NULL DEFAULT 'analyst' COMMENT 'analyst/admin',
  status            VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
  last_login_at     DATETIME     NULL,
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_external (external_user_id),
  UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户';

CREATE TABLE conversations (
  id               VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  user_id          VARCHAR(32) NOT NULL,
  data_source_id   VARCHAR(32) NULL COMMENT '逻辑外键 data_sources.id；空=默认内置示例库',
  title            VARCHAR(128) NOT NULL DEFAULT '新会话',
  status           VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT 'active/archived/deleted',
  last_message_at  DATETIME    NULL,
  deleted_at       DATETIME    NULL,
  created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_conv_user_last (user_id, last_message_at),
  KEY idx_conv_ds (data_source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='会话';

CREATE TABLE messages (
  id              VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  conversation_id VARCHAR(32) NOT NULL,
  role            VARCHAR(16) NOT NULL COMMENT 'user/assistant/tool',
  message_type    VARCHAR(16) NOT NULL DEFAULT 'text' COMMENT 'text/tool/result',
  content         LONGTEXT    NOT NULL,
  tool_name       VARCHAR(64) NULL,
  tool_status     VARCHAR(16) NULL COMMENT 'running/success/failed',
  seq_no          INT         NOT NULL,
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at      DATETIME    NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_msg_seq (conversation_id, seq_no),
  KEY idx_msg_conv_created (conversation_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='消息';

CREATE TABLE attachments (
  id               VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  conversation_id  VARCHAR(32)  NOT NULL,
  message_id       VARCHAR(32)  NULL,
  file_name        VARCHAR(255) NOT NULL,
  file_path        VARCHAR(512) NOT NULL,
  file_type        VARCHAR(32)  NOT NULL COMMENT 'csv/xlsx/txt',
  file_size        BIGINT       NOT NULL DEFAULT 0,
  parse_status     VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/parsing/parsed/failed',
  parse_result_json JSON        NULL COMMENT '表头/行列数/摘要/sheet 清单',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at       DATETIME     NULL,
  PRIMARY KEY (id),
  KEY idx_att_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='附件';

CREATE TABLE analysis_tasks (
  id              VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  conversation_id VARCHAR(32)  NOT NULL,
  user_id         VARCHAR(32)  NOT NULL,
  input_text      TEXT         NOT NULL,
  task_status     VARCHAR(16)  NOT NULL DEFAULT 'queued' COMMENT 'queued/running/success/failed/cancelled',
  current_step    INT          NOT NULL DEFAULT 0,
  started_at      DATETIME     NULL,
  finished_at     DATETIME     NULL,
  error_message   TEXT         NULL,
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_task_conv_status (conversation_id, task_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='分析任务';

CREATE TABLE analysis_results (
  id                  VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  task_id             VARCHAR(32)  NOT NULL,
  conversation_id     VARCHAR(32)  NOT NULL,
  problem_definition  TEXT         NOT NULL,
  key_metrics_json    JSON         NOT NULL,
  evidence_list_json  JSON         NOT NULL,
  conclusion_text     TEXT         NOT NULL,
  missing_data_text   TEXT         NOT NULL DEFAULT '',
  next_action_text    TEXT         NOT NULL DEFAULT '',
  result_markdown     LONGTEXT     NOT NULL,
  result_file_path    VARCHAR(512) NULL,
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_result_task (task_id),
  KEY idx_result_conv (conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='六段式分析结果';

CREATE TABLE context_summaries (
  id              VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  conversation_id VARCHAR(32) NOT NULL,
  start_seq_no    INT         NOT NULL,
  end_seq_no      INT         NOT NULL,
  summary_text    TEXT        NOT NULL,
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_summary_conv_end (conversation_id, end_seq_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='上下文摘要';

CREATE TABLE websocket_tokens (
  id              VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  user_id         VARCHAR(32) NOT NULL,
  conversation_id VARCHAR(32) NOT NULL,
  token           VARCHAR(64) NOT NULL,
  expires_at      DATETIME    NOT NULL,
  consumed_at     DATETIME    NULL,
  created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ws_token (token),
  KEY idx_ws_user_conv (user_id, conversation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='WS 一次性令牌';

CREATE TABLE system_configs (
  id           VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  config_key   VARCHAR(64)  NOT NULL,
  config_value TEXT         NOT NULL,
  config_type  VARCHAR(16)  NOT NULL DEFAULT 'string' COMMENT 'bool/int/float/string/json',
  config_group VARCHAR(32)  NOT NULL DEFAULT 'general',
  description  VARCHAR(255) NULL,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统配置';

CREATE TABLE task_logs (
  id          VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  task_id     VARCHAR(32) NOT NULL,
  log_level   VARCHAR(8)  NOT NULL DEFAULT 'INFO' COMMENT 'DEBUG/INFO/WARN/ERROR',
  log_type    VARCHAR(32) NOT NULL DEFAULT 'system' COMMENT 'system/tool/llm/error',
  log_content TEXT        NOT NULL,
  created_at  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_log_task_created (task_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='任务日志';

CREATE TABLE data_sources (
  id                 VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  name               VARCHAR(64)  NOT NULL,
  db_type            VARCHAR(16)  NOT NULL DEFAULT 'mysql' COMMENT '本期仅 mysql；预留 postgres',
  host               VARCHAR(128) NOT NULL,
  port               INT          NOT NULL DEFAULT 3306,
  database           VARCHAR(64)  NOT NULL,
  username           VARCHAR(64)  NOT NULL,
  password_encrypted VARCHAR(512) NOT NULL COMMENT 'AES-256-GCM，密钥 ENCRYPTION_KEY',
  is_readonly        TINYINT(1)   NOT NULL DEFAULT 1,
  is_enabled         TINYINT(1)   NOT NULL DEFAULT 1,
  description        VARCHAR(512) NULL COMMENT '场景说明（Agent 提示词注入）',
  created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ds_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='数据源';

CREATE TABLE audit_logs (
  id           VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  user_id      VARCHAR(32)  NOT NULL,
  action_type  VARCHAR(32)  NOT NULL COMMENT 'create/update/delete/reload/test',
  target_type  VARCHAR(32)  NOT NULL COMMENT 'config/data_source/feature_flag',
  target_id    VARCHAR(64)  NULL,
  before_value JSON         NULL,
  after_value  JSON         NULL,
  ip           VARCHAR(64)  NULL,
  user_agent   VARCHAR(255) NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_user_created (user_id, created_at),
  KEY idx_audit_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='管理审计（永久保留）';

CREATE TABLE llm_calls (
  id                VARCHAR(32)   NOT NULL COMMENT 'UUIDv7',
  task_id           VARCHAR(32)   NOT NULL,
  conversation_id   VARCHAR(32)   NOT NULL,
  user_id           VARCHAR(32)   NOT NULL,
  model             VARCHAR(64)   NOT NULL,
  prompt_tokens     INT           NOT NULL DEFAULT 0,
  completion_tokens INT           NOT NULL DEFAULT 0,
  total_tokens      INT           NOT NULL DEFAULT 0,
  cost              DECIMAL(10,4) NOT NULL DEFAULT 0 COMMENT '元',
  latency_ms        INT           NOT NULL DEFAULT 0,
  status            VARCHAR(16)   NOT NULL DEFAULT 'success' COMMENT 'success/failed',
  error_message     TEXT          NULL,
  created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_llm_task (task_id),
  KEY idx_llm_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='LLM 调用记录';

-- ============ 认证中心库（schema: auth） ============

CREATE TABLE auth_users (
  id            VARCHAR(32) NOT NULL COMMENT 'UUIDv7',
  username      VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL COMMENT 'bcrypt/argon2',
  display_name  VARCHAR(64) NOT NULL,
  role          VARCHAR(16) NOT NULL DEFAULT 'analyst',
  status        VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_auth_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='认证中心用户';

CREATE TABLE auth_clients (
  id                VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  client_id         VARCHAR(64)  NOT NULL,
  client_secret_hash VARCHAR(255) NOT NULL,
  redirect_uris     JSON         NOT NULL,
  scopes            JSON         NOT NULL,
  status            VARCHAR(16)  NOT NULL DEFAULT 'active',
  created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_auth_client_id (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='OAuth 客户端';

CREATE TABLE auth_auth_codes (
  id           VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  code         VARCHAR(64)  NOT NULL,
  client_id    VARCHAR(64)  NOT NULL,
  user_id      VARCHAR(32)  NOT NULL,
  redirect_uri VARCHAR(512) NOT NULL,
  scope        JSON         NULL,
  expires_at   DATETIME     NOT NULL,
  consumed_at  DATETIME     NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_auth_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='授权码（5 分钟）';

CREATE TABLE auth_refresh_tokens (
  id           VARCHAR(32)  NOT NULL COMMENT 'UUIDv7',
  token_hash   VARCHAR(128) NOT NULL,
  client_id    VARCHAR(64)  NOT NULL,
  user_id      VARCHAR(32)  NOT NULL,
  expires_at   DATETIME     NOT NULL,
  revoked_at   DATETIME     NULL,
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_refresh_hash (token_hash),
  KEY idx_refresh_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='刷新令牌（7 天，使用即轮换）';
```

> 索引核对：每表 ≤4 索引；JSON 列不建索引（检索走 text_search）；全部逻辑外键列已建索引（data_source_id 见 idx_conv_ds）。

---

## 4. backend 模块设计（领域垂直切片）

### 4.1 模块总览与依赖方向

```
core ←── 所有 domains ──→ ws（ws 依赖 task/result 域的推送回调）
domains 之间禁止互相 import service；跨域协作经 core.events 事件总线或直接调用对方 dao（仅限读）。
依赖方向：router → service → dao → models；agent → tools → core.security/core.config。
```

### 4.2 core 模块

#### core/config.py

```python
class ConfigCache:
    """system_configs 热更新缓存（单例）。启动全量加载，reload 后全量刷新。"""
    _instance: "ConfigCache | None" = None
    _values: dict[str, Any]          # config_key -> 按 config_type 反序列化后的值
    async def load(self) -> None: ...                    # 全量拉取 + 反序列化
    def get(self, key: str, default: Any = None) -> Any: ...
    def get_int(self, key: str, default: int) -> int: ...
    def get_bool(self, key: str, default: bool) -> bool: ...
    async def reload(self) -> dict: ...                  # 返回 {updated_keys: [...]}，失败抛 ConfigReloadError

class Settings(BaseModel):        # 环境变量（pydantic-settings，prefix 无）
    database_url: str
    redis_url: str
    auth_service_url: str
    auth_client_id: str
    auth_client_secret: str
    auth_redirect_uri: str
    encryption_key: str
    cookie_domain: str = ""
    cookie_secure: bool = True
    data_root: str
```

#### core/db.py

```python
engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=5, pool_recycle=3600)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncIterator[AsyncSession]:   # FastAPI 依赖：yield session，异常回滚，finally close
    ...
```

#### core/redis.py

```python
redis_client = redis.asyncio.from_url(settings.redis_url, decode_responses=True)

async def incr_ws_seq(conversation_id: str) -> int:          # INCR ws:seq:{conv_id}
async def set_ws_seq_if_greater(conversation_id: str, seq: int) -> None:
    """消息落库后抬升基线：当前值 < seq 则 SET（§7.1.2）"""
async def acquire_lock(name: str, ttl: int = 1800) -> bool:  # SETNX 分布式锁
async def release_lock(name: str) -> None: ...
```

#### core/security.py

```python
class JwtVerifier:
    """JWKS 公钥缓存 + RS256 本地验签。启动拉取；验签失败自动重拉一次。"""
    async def start(self) -> None: ...                      # 启动拉取公钥
    async def verify(self, token: str) -> JwtClaims: ...    # 验签/过期/aud；失败抛 AuthError
    async def refresh_keys(self) -> None: ...

class JwtClaims(BaseModel):
    sub: str
    username: str
    role: str
    exp: int
    aud: str

def encrypt_secret(plain: str, key: bytes) -> str: ...   # AES-256-GCM，输出 base64(iv+ciphertext+tag)
def decrypt_secret(enc: str, key: bytes) -> str: ...
```

#### core/errors.py

```python
class BizError(Exception):
    code: str; http_status: int; detail: dict | None
    def __init__(self, code: str, message: str, http_status: int = 400, detail: dict | None = None): ...

TASK_BUSY = lambda task_id: BizError("TASK_BUSY", "会话已有运行中任务", 409, {"task_id": task_id})
# ...（其余错误码工厂函数同 §2.1 表）

async def biz_error_handler(request, exc: BizError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content={"code": exc.code, "message": exc.message, "detail": exc.detail})
```

#### core/logging.py

```python
def get_logger(module: str) -> Logger:          # 结构化：{ts, level, module, task_id?, msg, extra}
async def log_task(task_id: str, level: str, log_type: str, content: str) -> None:
    """写入 task_logs 表（WARN/ERROR 同步落库，INFO 批量/直接落库均可，实现自定）"""
```

#### core/deps.py

```python
async def get_current_user(request: Request, db=Depends(get_db)) -> User:
    """Cookie(access_token) 或 Authorization: Bearer → JwtVerifier.verify → users upsert 查询/缓存 → 返回"""
async def require_admin(user: User = Depends(get_current_user)) -> User:  # role != 'admin' → FORBIDDEN
```

### 4.3 domains/auth（OIDC 客户端接入）

```python
# router.py
GET  /auth/login        → 拼装 authorize URL（state=随机+存 Cookie）→ 302 auth-service
GET  /auth/callback     → 收 code/state → POST {auth}/token 换令牌 → users upsert → 种 Cookie → 302 /chat
POST /auth/logout       → 清 Cookie → 204
POST /auth/refresh      → 读 refresh Cookie → {auth}/token(grant_type=refresh_token) 轮换 → 重种 Cookie
GET  /api/auth/me       → 当前用户（get_current_user）→ {id, username, display_name, role}

# service.py
class AuthService:
    async def build_authorize_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str, state: str, request: Request) -> AuthSession:
        """POST /token(code) → 验 JWT（JWKS）→ GET /userinfo → users upsert → 返回令牌对"""
    async def refresh(self, refresh_token: str) -> AuthSession: ...   # 轮换：旧 refresh 吊销，发新 refresh
    async def upsert_user(self, userinfo: dict) -> User: ...          # external_user_id 匹配；更新 last_login_at

# jwks.py
class JwksClient:
    """从 {auth_service_url}/.well-known/jwks.json 拉取，缓存 kid→key；verify 失败触发 refresh_keys"""
```

### 4.4 domains/chat

```python
# router.py
POST /api/chat/create   → {title?, data_source_id?} → {conversation_id, title, status, data_source_id}
POST /api/chat/update   → {conversation_id, title} → 同上
POST /api/chat/delete   → {conversation_ids: []} → {status, message, deleted_ids}
GET  /api/chat/ls       → 分页，按 last_message_at 倒序 → {items, total, page, page_size}
GET  /api/chat/ls/{conversation_id} → 历史消息（含 tool/result 类型，按 seq_no 升序）

# service.py
class ConversationService:
    async def create(self, user_id, title=None, data_source_id=None) -> Conversation:
        # data_source_id 为空 → 默认内置示例库（data_sources.name='business'）；校验归属/存在
    async def list(self, user_id, page, page_size) -> Page[Conversation]
    async def rename(self, user_id, conv_id, title) -> Conversation
    async def soft_delete(self, user_id, conv_ids: list[str]) -> list[str]:
        # status=deleted + deleted_at；目录物理清理交给定时任务（§10.6），此处只删 DB 记录状态
    async def get_history(self, user_id, conv_id) -> list[Message]
```

### 4.5 domains/attachment

```python
# router.py
POST /api/attachment/upload   → multipart(file, conversation_id) → {attachment_id, file_name, parse_status}
POST /api/attachment/delete   → {attachment_id} → {status, message}
GET  /api/attachment/get      → ?attachment_id= → 元信息
GET  /api/attachment/download/{attachment_id} → FileResponse（鉴权+路径校验）

# service.py
class AttachmentService:
    async def upload(self, user_id, conv_id, upload_file) -> Attachment:
        # 校验：扩展名白名单(csv/xlsx/txt) + MIME 双重 + ≤20MB + 目录归属 uploads/{uid}/{cid}/
        # 落库 parse_status='pending' → 提交解析任务（信号量限并发 1）
    async def parse(self, attachment: Attachment) -> None:
        # 状态 parsing → parser.parse() → parse_result_json 落库 → parsed / failed
        # 完成推送 WS attachment_parsed；失败置 failed + task_logs
    async def delete(self, user_id, att_id) -> None:     # 删记录 + 物理文件 + 关联消息解除
    async def get_by_ids(self, user_id, att_ids: list[str]) -> list[Attachment]  # 校验归属

# parser.py
class CsvParser:  def parse(path: Path) -> ParseResult: ...   # 表头/前 20 行预览/行列数/摘要统计
class XlsxParser: def parse(path: Path) -> ParseResult: ...   # sheet 清单 + 每 sheet 表头/行列数
class TxtParser:  def parse(path: Path) -> ParseResult: ...   # 行数/前 20 行/摘要（前 2000 字）

class ParseResult(BaseModel):
    file_type: str
    sheet_name: str = ""
    headers: list[str]
    row_count: int
    col_count: int
    preview_rows: list[list[str]]      # 前 20 行
    summary: str                        # 文本摘要（供 text_search 检索）
```

### 4.6 domains/task

```python
# router.py
POST /api/chat/send        → {conversation_id, content, attachment_ids?: []}
                             → {message_id, task_id, queue_position}
POST /api/tasks/{id}/cancel → {task_status, message}
GET  /api/tasks/{id}        → 状态详情
POST /api/chat/ws-token     → {conversation_id} → {websocket_token, expires_in}

# service.py
class TaskService:
    async def send(self, user_id, conv_id, content, attachment_ids) -> SendResult:
        # 1. 互斥：会话无 queued/running 任务（TASK_BUSY）
        # 2. message 落库（role=user, seq_no=MAX+1）
        # 3. attachment 关联：attachments.message_id 更新（若传了 attachment_ids）
        # 4. analysis_task 落库（queued）
        # 5. ws seq 基线抬升到 message.seq_no（set_ws_seq_if_greater）
        # 6. queue.put(task_id) → 返回 {message_id, task_id, queue_position}
    async def cancel(self, user_id, task_id) -> str:
        # 终态 → TASK_NOT_CANCELLABLE；queued → 状态直接置 cancelled；
        # running → task 协程 cancel（LLM 流 aclose / 子进程 terminate）→ 状态置 cancelled
    async def get(self, user_id, task_id) -> TaskDetail    # 含 queue_position

# queue.py
class TaskQueue:
    _queue: asyncio.Queue[str]
    _sem: asyncio.Semaphore          # task_max_running（默认 3）
    _workers: list[asyncio.Task]
    async def start(self, engine: AgentEngine) -> None:    # 3 个 worker 协程
    async def put(self, task_id: str) -> int:              # 满抛 TASK_QUEUE_FULL；返回 queue_position
    async def _worker(self) -> None:
        # task_id = await queue.get()
        # 若任务已是 cancelled（排队中被取消）→ 跳过
        # async with sem: await engine.run(task_id)
        # 终态后推送 done

# state_machine.py
VALID_TRANSITIONS = {
  "queued": {"running", "failed", "cancelled"},
  "running": {"success", "failed", "cancelled"},
  # success/failed/cancelled 为终态，不可逆
}
def transition(current: str, next: str) -> None:   # 非法抛 BizError
```

### 4.7 domains/agent

#### engine.py

```python
class AgentEngine:
    async def run(self, task_id: str) -> None:
        """§8.1 引擎循环：装配上下文 → 规划/工具循环 → 六段式 → 落库 → 摘要压缩"""
    async def _plan(self, ctx: AgentContext, messages: list[dict]) -> PlanResult:
        # 非流式调用（tools=registry.schema()）；返回 tool_calls 或 最终六段式 JSON
    async def _execute_tools(self, tool_calls) -> list[ToolResult]:
        # 逐个：推送 tool_start → registry.run() → 推送 tool_finish → 结果回传
    async def _finalize(self, task_id, six_section: SixSectionResult) -> ResultPersist:
        # 调 result.service.persist()（Markdown 唯一生成入口，§1.2-4）
```

#### llm.py

```python
class LlmClient:
    """OpenAI 兼容客户端。base_url/api_key/model 每次调用从 ConfigCache 读取（热更新生效）。"""
    async def chat_plan(self, system: str, messages: list[dict], tools: list[dict]) -> ChatResponse:
        # stream=False + tools；超时 llm_timeout_seconds；重试 llm_max_retries
    async def chat_stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        # stream=True，yield 文本增量；调用方负责 WS 转发
    async def chat_summarize(self, system: str, messages: list[dict]) -> str:  # 非流式，独立记账
    # 每次调用结束（含异常）→ 写 llm_calls 一行（model/tokens/latency/cost/status）

class LlmCost:
    @staticmethod
    def calc(prompt_tokens: int, completion_tokens: int, price_in: float, price_out: float) -> Decimal
```

#### summarizer.py

```python
async def summarize_turn(task_id: str, conv_id: str, start_seq: int, end_seq: int, content: str) -> None:
    """调用 chat_summarize（提示词见 docs/prompts/context-summary-prompt.md）→ context_summaries 落库"""
```

#### prompts.py

```python
def build_system_prompt(ctx: AgentContext) -> str:
    """装配：角色定义 + 场景说明（data_source.description）+ schema 描述（白名单表）
       + 附件摘要（parse_result_json）+ 工具清单 + 六段式模板 + 硬性约束（引用 docs/prompts/agent-system-prompt.md）"""
def build_six_section_json_schema() -> dict: ...   # 六段式 JSON Schema（供 tools/result 输出约束）
```

#### tools/registry.py

```python
class Tool(BaseModel):
    name: str
    description: str
    parameters: dict                          # JSON Schema（引用 docs/prompts/tool-descriptions.md）
    flag_key: str | None                      # 对应 feature_flag，开关关闭则该工具不注册
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult: ...

class ToolContext(BaseModel):
    user_id: str
    conversation_id: str
    data_source_id: str
    workspace_dir: Path
    db: AsyncSession

class ToolResult(BaseModel):
    success: bool
    summary: str                              # 结果摘要（进 tool_finish 事件 + 回传 LLM）
    data: Any = None                          # 结构化数据（行/文本/片段）
    error: str | None = None

class ToolRegistry:
    _tools: dict[str, Tool]
    def register(self, tool: Tool) -> None: ...
    def schema(self, enabled_flags: set[str]) -> list[dict]: ...   # 过滤关闭的工具
    async def run(self, name: str, ctx: ToolContext, **kwargs) -> ToolResult:
        # 统一：flag 检查 → 参数校验 → task_logs 记录 → execute → 结果摘要截断
```

#### tools/db_query.py

```python
class DbQueryTool(Tool):
    async def execute(self, ctx, sql: str) -> ToolResult:
        # ① 连接：会话绑定 data_source（解密密码，只读账号）；内置示例库走预置 data_sources
        # ② SQL 校验链：去注释 → 正则白名单（^SELECT，禁 ; 多语句 / INTO OUTFILE / LOAD_FILE / UPDATE / DELETE）
        # ③ schema 全限定：sql 中的表必须写成 schema.table 且 ∈ 该数据源白名单
        # ④ LIMIT 500（无 LIMIT 时强制追加）
        # ⑤ asyncio.wait_for 30s；结果 → ToolResult.data（列名+行数组）
```

#### tools/file_read.py / file_write.py

```python
class FileReadTool(Tool):
    async def execute(self, ctx, path: str) -> ToolResult:
        # realpath 规范化，前缀 ∈ workspace/{uid}/{cid}/ 或 uploads/{uid}/{cid}/；拒绝越界；≤1MB 读取
class FileWriteTool(Tool):
    async def execute(self, ctx, path: str, content: str) -> ToolResult:
        # 同上路径约束；仅 workspace 内；覆盖前校验大小 ≤5MB
```

#### tools/text_search.py

```python
class TextSearchTool(Tool):
    async def execute(self, ctx, keyword: str, limit: int = 10) -> ToolResult:
        # 检索范围 = 本会话已解析附件 parse_result_json（summary/preview_rows）+ workspace 文本文件
        # 关键词匹配（不分大小写包含匹配）；返回片段 + 来源（attachment_id/文件名）；limit ≤ 20
```

#### tools/command_exec.py

```python
class CommandExecTool(Tool):
    async def execute(self, ctx, command: str, args: list[str]) -> ToolResult:
        # 白名单命令：python3（仅数据分析）；黑名单关键词对 argv 逐项检查
        # asyncio.create_subprocess_exec(cwd=workspace/{uid}/{cid}/, shell=False, timeout=cmd_timeout)
        # 超时 terminate → 3s 后 kill；stdout+stderr 合并截断 cmd_output_max_bytes
```

#### tools/result_generate.py（职责收敛后，§1.2-4）

```python
class ResultGenerateTool(Tool):
    """仅保留为"写中间分析文件"能力（如生成 CSV 中间结果）；不再生成最终结果文件。
       默认 flag_tool_result_generate=false 不注册；演示如需可开。实现同 FileWriteTool（workspace 内）。"""
```

### 4.8 domains/result

```python
# router.py
GET  /api/results/{task_id}        → 六段式完整结果（含 result_markdown）
POST /api/results/{task_id}/export → {result_id, result_file_path}
GET  /api/results/download/{result_id} → FileResponse

# service.py
class ResultService:
    async def persist(self, task_id: str, conv_id: str, six: SixSectionResult) -> ResultPersist:
        """Markdown 生成唯一入口：六段式 → result_markdown → exports/{uid}/{cid}/result_{task_id}.md
           写文件 + analysis_results 落库（result_file_path）→ 推送 result_ready（payload 带完整结果）"""
    async def export(self, user_id, task_id) -> ResultExport:   # 已生成则直接返回，未生成重新生成
    async def download(self, user_id, result_id) -> Path
    async def get(self, user_id, task_id) -> AnalysisResult
```

### 4.9 domains/admin

```python
# router.py（全部 require_admin）
GET    /api/admin/configs        → 按 config_group 分组列表
PUT    /api/admin/configs        → {items: [{config_key, config_value}]} → 批量更新 + 审计
POST   /api/admin/reload         → {status, message, updated_keys}
GET    /api/admin/data-sources   → 列表（password 脱敏返回）
POST   /api/admin/data-sources   → 新增（密码加密落库）+ 审计
PUT    /api/admin/data-sources/{id} → 更新 + 审计
DELETE /api/admin/data-sources/{id} → 删除 + 审计（引用中则拒绝，409）
POST   /api/admin/data-sources/{id}/test → 测试连接（解密后尝试建连）→ {ok, message, latency_ms}
PUT    /api/admin/feature-flags  → {items: [{config_key, config_value}]} → 同 configs 更新
GET    /api/admin/logs           → 过滤（level/log_type/task_id）+ 分页

# service.py
class AdminService:
    async def update_configs(self, admin: User, items: list[ConfigUpdate], audit_ctx: AuditCtx) -> None
        # 写 system_configs + audit_logs(before/after) + 提示 ConfigCache 下次 reload 生效
    async def test_data_source(self, ds: DataSource) -> TestResult   # 建连 + SELECT 1
```

### 4.10 ws

```python
# connection.py
class ConnectionManager:
    _conns: dict[str, set[WebSocket]]        # conversation_id -> 连接集合（同一会话多标签页广播）
    async def connect(self, ws: WebSocket, conversation_id: str) -> None
    async def disconnect(self, ws: WebSocket, conversation_id: str) -> None
    def count_for_user(self, user_id: str) -> int

# dispatcher.py
class EventDispatcher:
    async def push(self, conversation_id: str, type: str, payload: dict, task_id: str | None = None) -> None:
        # seq = redis.incr_ws_seq(conversation_id)（ping 类型除外）
        # envelope = {v:1, type, conversation_id, task_id, seq, ts, payload}
        # 广播到该会话全部连接；发送失败（连接断开）静默忽略，交由 REST 恢复兜底
    async def push_raw(self, conversation_id: str, envelope: dict) -> None   # 心跳等控制消息（不带 seq）

# handlers.py
async def handle_inbound(ws: WebSocket, msg: dict, current_user: User) -> None:
    # type=cancel_task → TaskService.cancel；type=pong → 更新该连接 last_pong
```

### 4.11 models

```python
# base.py
class UUIDv7PK:        id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uuid7)
class TimestampMixin:  created_at / updated_at（DATETIME，server_default=func.now()）
class SoftDeleteMixin: deleted_at: Mapped[datetime | None]

# business.py / auth_tables.py
# 17 张表 ORM 类，字段对齐 §3 DDL；DAO 层查询默认过滤 deleted_at IS NULL（软删表）
```

---

## 5. auth-service 详细设计

### 5.1 端点契约

| 端点 | 方法 | 说明 | 关键逻辑 |
|---|---|---|---|
| `/authorize` | GET | 授权端点 | 校验 client_id/redirect_uri/scope → 未登录则渲染登录页（账号密码+记住我）→ 登录成功后签发一次性授权码（5 分钟）→ 302 `redirect_uri?code=` |
| `/token` | POST | 令牌端点 | grant_type=authorization_code：校验 code（未消费/未过期/redirect_uri 一致）→ 消费 code → 签发 access(JWT 15min)+refresh(7d)；grant_type=refresh_token：校验 hash/未吊销/未过期 → **轮换**（旧 refresh 置 revoked_at，签发新 refresh） |
| `/userinfo` | GET | 用户信息 | Bearer access → 返回 `{sub, username, display_name, role}` |
| `/.well-known/jwks.json` | GET | 公钥 | RS256 公钥（kid 标识） |
| `/.well-known/openid-configuration` | GET | 发现文档 | issuer/token_endpoint/userinfo_endpoint/jwks_uri |

### 5.2 JWT claims 与校验

```json
{ "iss": "http://auth:8001", "sub": "<auth_users.id>", "aud": "biz-console",
  "username": "admin", "role": "admin", "iat": 1755500000, "exp": 1755500900 }
```

- 算法 RS256；private key 存 auth-service（启动生成或注入）；public key 经 jwks 暴露。
- backend 验签规则：签名（kid 匹配公钥）→ `exp` → `aud == AUTH_CLIENT_ID` → 取 `sub` 查/缓存 users。

### 5.3 令牌生命周期与轮换

```
登录 → access(15min, Cookie) + refresh(7d, Cookie)
access 过期 → 前端 401 AUTH_EXPIRED → POST /auth/refresh（带 refresh Cookie）
  → backend 调 {auth}/token(grant_type=refresh_token)
  → auth 验 hash → 旧 refresh 置 revoked_at（轮换）→ 签发 新 access + 新 refresh
  → backend 重种双 Cookie → 前端重放原请求
记住我=off：refresh TTL 24h；记住我=on：7d（登录页表单参数，auth-service 签发时读取）
```

---

## 6. REST 接口契约全集（字段级）

> 通用：成功直接返回数据体；错误走 §2.1；时间 ISO 8601 UTC；分页见 §2.2。

### 6.1 认证接口

| # | 方法/路径 | 请求 | 响应 | 错误码 |
|---|---|---|---|---|
| A1 | GET /auth/login | — | 302 → auth/authorize | — |
| A2 | GET /auth/callback | query: code, state | 302 → /chat | AUTH_REQUIRED |
| A3 | POST /auth/logout | — | 204 | — |
| A4 | POST /auth/refresh | Cookie: refresh_token | 204（重种 Cookie） | AUTH_EXPIRED |
| A5 | GET /api/auth/me | — | `{id, username, display_name, role}` | AUTH_REQUIRED |

### 6.2 业务接口

| # | 方法/路径 | 请求 | 响应 | 错误码 |
|---|---|---|---|---|
| B1 | POST /api/chat/create | `{title?, data_source_id?}` | `{conversation_id, title, status, data_source_id}` | VALIDATION_ERROR |
| B2 | POST /api/chat/update | `{conversation_id, title}` | `{conversation_id, title, status}` | NOT_FOUND |
| B3 | POST /api/chat/delete | `{conversation_ids: []}` | `{status, message, deleted_ids}` | NOT_FOUND |
| B4 | GET /api/chat/ls | query: page, page_size | `{items: [{conversation_id, title, status, last_message_at}], total, page, page_size}` | — |
| B5 | GET /api/chat/ls/{conversation_id} | — | `{conversation_id, data_source_id, items: [{message_id, role, message_type, content, tool_name, tool_status, seq_no, attachments: [], created_at}]}` | NOT_FOUND |
| B6 | **POST /api/chat/send** | `{conversation_id, content, attachment_ids?: []}` | `{message_id, task_id, queue_position}` | TASK_BUSY / TASK_QUEUE_FULL / NOT_FOUND |
| B7 | POST /api/attachment/upload | multipart: file, conversation_id | `{attachment_id, file_name, file_type, file_size, parse_status}` | FILE_TYPE_NOT_ALLOWED / FILE_TOO_LARGE / NOT_FOUND |
| B8 | POST /api/attachment/delete | `{attachment_id}` | `{status, message}` | NOT_FOUND |
| B9 | GET /api/attachment/get | query: attachment_id | `{attachment_id, file_name, file_type, file_size, parse_status, parse_result_json, created_at}` | NOT_FOUND |
| B10 | GET /api/attachment/download/{attachment_id} | — | 文件流（Content-Disposition: attachment） | NOT_FOUND |
| B11 | POST /api/chat/ws-token | `{conversation_id}` | `{websocket_token, expires_in}` | NOT_FOUND / RATE_LIMITED |
| B12 | WS /api/chat/ws/chat | query: websocket_token, conversation_id | 见 §7 | AUTH_REQUIRED |
| B13 | POST /api/tasks/{task_id}/cancel | — | `{task_status, message}` | TASK_NOT_CANCELLABLE / NOT_FOUND |
| B14 | GET /api/tasks/{task_id} | — | `{task_id, task_status, current_step, queue_position, started_at, finished_at, error_message}` | NOT_FOUND |
| B15 | GET /api/results/{task_id} | — | `{result_id, problem_definition, key_metrics, evidence_list, conclusion_text, missing_data_text, next_action_text, result_markdown, created_at}` | NOT_FOUND |
| B16 | POST /api/results/{task_id}/export | — | `{result_id, result_file_path}` | NOT_FOUND |
| B17 | GET /api/results/download/{result_id} | — | 文件流 | NOT_FOUND |

> B6 为概要设计补充接口，本次评审再增 `attachment_ids`（决策 D2）。

### 6.3 管理接口（全部 require_admin）

| # | 方法/路径 | 请求 | 响应 | 错误码 |
|---|---|---|---|---|
| C1 | GET /api/admin/configs | — | `{groups: [{group, items: [{config_key, config_value, config_type, description}]}]}` | FORBIDDEN |
| C2 | PUT /api/admin/configs | `{items: [{config_key, config_value}]}` | `{status, message, updated_count}` | VALIDATION_ERROR |
| C3 | POST /api/admin/reload | — | `{status, message, updated_keys}` | CONFIG_RELOAD_FAILED |
| C4 | GET /api/admin/data-sources | — | `{items: [{id, name, db_type, host, port, database, username, is_readonly, is_enabled, description}]}`（password 脱敏） | FORBIDDEN |
| C5 | POST /api/admin/data-sources | `{name, db_type, host, port, database, username, password, is_readonly?, is_enabled?, description?}` | `{id, name, status}` | VALIDATION_ERROR / DATA_SOURCE_UNAVAILABLE |
| C6 | PUT /api/admin/data-sources/{id} | 同 C5（password 可空=不修改） | `{id, status}` | NOT_FOUND |
| C7 | DELETE /api/admin/data-sources/{id} | — | `{status, message}` | NOT_FOUND / 409（引用中） |
| C8 | POST /api/admin/data-sources/{id}/test | — | `{ok, message, latency_ms}` | DATA_SOURCE_UNAVAILABLE |
| C9 | PUT /api/admin/feature-flags | `{items: [{config_key, config_value}]}` | `{status, message, updated_count}` | VALIDATION_ERROR |
| C10 | GET /api/admin/logs | query: level?, log_type?, task_id?, page, page_size | `{items: [{log_id, task_id, log_level, log_type, log_content, created_at}], total, page, page_size}` | FORBIDDEN |

---

## 7. WS 协议详细设计

### 7.1 统一信封

```json
{
  "v": 1, "type": "tool_start",
  "conversation_id": "01J2X...", "task_id": "01J2Y...",
  "seq": 42, "ts": "2026-08-18T07:00:00Z",
  "payload": { "tool_name": "db_query", "params_preview": "SELECT ..." }
}
```

#### 7.1.1 seq 与心跳规则

- **业务事件**（§7.2 出站 9 类）带 `seq`：Redis `INCR ws:seq:{conversation_id}` 分配，从 1 起。
- **控制消息**（`ping`）**不带 seq**：客户端收到仅回 `pong`，不更新去重游标。
- 客户端去重：维护 `maxSeq`；`seq <= maxSeq` 丢弃；`seq == maxSeq+1` 渲染并推进；`seq > maxSeq+1` 缓存 2s 后按序补渲染（乱序保护）。

#### 7.1.2 seq 基线对齐（防重启回卷，处置 P1-5）

```
规则：消息落库后必须抬升基线。
发送消息（B6）步骤 5：set_ws_seq_if_greater(conv_id, message.seq_no)   # Redis 值 < seq_no 则 SET
启动时：若 ws:seq:{conv_id} 不存在 → SET 到 messages 表 MAX(seq_no)（惰性，首次 INCR 前检查）
Redis 持久化：compose 中 redis 开 appendonly yes + 挂数据卷（§11.1）
```

### 7.2 消息类型与 payload（字段级）

**出站：**

| type | payload 必含 | 说明 |
|---|---|---|
| message_start | `{task_id, queue_position}` | 任务开始执行（worker 取出时） |
| message_delta | `{task_id, delta_text}` | 结论流式增量（20~50 字/块） |
| tool_start | `{task_id, tool_name, params_preview}` | 工具开始（params_preview 截断 200 字） |
| tool_finish | `{task_id, tool_name, tool_result_summary, success}` | 工具完成（summary 截断 500 字） |
| task_status | `{task_id, task_status, current_step, queue_position}` | 状态变化（含排队中） |
| result_ready | `{task_id, result_id, result: <完整六段式>}` | **payload 带完整结果**，前端直接渲染（降级 REST） |
| error | `{task_id, error_message}` | 分析失败 |
| done | `{task_id, finished_at}` | 终态收尾（success/failed/cancelled 均发） |
| attachment_parsed | `{attachment_id, parse_status}` | 附件解析完成/失败 |

**入站：**

| type | payload | 说明 |
|---|---|---|
| cancel_task | `{task_id}` | 取消（WS 与 HTTP B13 双通道） |
| pong | `{}` | 心跳响应 |

**终态消息顺序（定死，前端按此渲染）：**
```
success: result_ready → task_status(success) → done
failed:  error → task_status(failed) → done
cancelled: task_status(cancelled) → done
```

### 7.3 时序要点（完整图见概设 §5.2/§5.3，此处仅列增量约定）

- 心跳：服务端每 `heartbeat_interval_seconds`(30s) 发 `ping`；客户端 2 次未 pong 判断线清理；客户端 60s 未收到任何消息判定连接异常 → 主动重连。
- 重连：指数退避 1s→30s 封顶；重连前重新调 B11 换令牌；成功后并行拉 B5+B14+B15 恢复 UI（REST 恢复 + WS 增量，概设决策 7）。
- WS 连接鉴权：校验 token 未消费/未过期/会话归属当前用户 → 标记 consumed；同一用户连接数超 `ws_max_connections_per_user` → 拒绝（RATE_LIMITED）。

---

## 8. Agent 引擎详细设计

### 8.1 循环状态机

```
run(task_id):
  ctx = 装配上下文(§8.2)
  推送 task_status(running, step=0)
  loop step in 1..task_max_steps:
    规划(非流式, tools) → PlanResult
      ├─ tool_calls → 逐个执行(§8.3) → tool 消息回传 → continue
      └─ 最终六段式 JSON → break
  超时(> task_timeout_minutes) → 中断循环，基于已有证据组装部分结果
  六段式校验(§8.5) → 失败重试 1 次 → 仍失败组装降级结果
  result.service.persist()（Markdown 唯一入口，§1.2-4）
  summarizer.summarize_turn() → context_summaries 落库
  推送 result_ready → task_status(success) → done
异常/取消：捕获 → task_status(failed/cancelled) + error → done
```

### 8.2 上下文装配算法（处置 P2-15）

```
输入：task(input_text), conversation_id, attachment_ids
1. 会话 + 数据源：conversations.data_source_id → data_sources
   - 场景说明 = data_source.description；schema 描述 = 白名单表清单（表名+列名，来自该库 information_schema 或预置描述）
   - flag_scenario_data=false → 不注入场景 schema
2. 附件：按 attachment_ids（B6 传入）拉取 attachments
   - parsed → 注入 parse_result_json（headers/preview_rows/summary）
   - parsing/pending → 注入提示「附件解析中，暂不可用于检索」
   - failed → 注入「附件解析失败：<原因>」
3. 历史消息：最近 context_max_messages(20) 条完整消息（role/content/seq_no）
   - 更早的部分：取 context_summaries 中 end_seq_no < 最早完整消息 seq 的最近一条摘要注入
4. 工具清单：registry.schema(启用 flags)（§8.3）
5. 六段式模板 + 角色定义（prompts.py，引用 docs/prompts/agent-system-prompt.md）
6. token 预算：估算 system+messages 总 token；超限从最旧消息开始裁剪，每裁 5 条重估一次，直到预算内
   （估算：字符数 / 3 粗略换算，实现自定）
```

### 8.3 工具契约（入参 JSON Schema + 出参 ToolResult）

> 完整 function calling JSON 见 `docs/prompts/tool-descriptions.md`，此处为入参契约要点。

| 工具 | 入参（JSON Schema 要点） | 出参（ToolResult） | 安全 |
|---|---|---|---|
| db_query | `sql: string`（必填，`schema.table` 全限定） | data: `{columns, rows}`；summary: `N 行结果，含 X 列` | §4.7 tools/db_query.py 校验链 |
| file_read | `path: string`（相对工作区/上传目录） | data: 文本内容（截断） | realpath 前缀校验 |
| file_write | `path: string, content: string` | summary: `已写入 N 字节` | workspace 内、≤5MB |
| text_search | `keyword: string, limit?: int(≤20)` | data: `[{source, snippet}]` | 会话内附件+workspace |
| command_exec | `command: 'python3', args: string[]` | data: stdout（截断） | 白名单+黑名单+超时 |
| result_generate | （默认关闭） | — | 同 file_write |

### 8.4 LLM 调用管理与记账

```
每次调用（plan/stream/summarize）结束写入 llm_calls 一行：
  model / prompt_tokens / completion_tokens / total_tokens
  cost = prompt_tokens/1000*price_in + completion_tokens/1000*price_out（§2.4 单价）
  latency_ms / status(success|failed) / error_message
调用取消（用户取消）→ 流 aclose() → 已产生的 token 记账，status=failed, error='用户取消'
```

### 8.5 六段式 Pydantic 模型与校验降级

```python
class KeyMetric(BaseModel):
    metric_name: str
    metric_value: str                      # 保留原始精度（LLM 输出转字符串）
    metric_unit: str = ""
    metric_period: str = ""

class Evidence(BaseModel):
    source_type: Literal["db_query","file_read","text_search","command_exec","attachment","user_input"]
    source_name: str
    evidence_text: str
    related_metric: str = ""
    confidence: float = Field(ge=0.0, le=1.0)

class SixSectionResult(BaseModel):
    problem_definition: str
    key_metrics: list[KeyMetric] = []
    evidence_list: list[Evidence] = []
    conclusion_text: str
    missing_data_text: str = ""
    next_action_text: str = ""
```

校验流程：`model_validate_json(llm_text)` → 失败 → 把错误信息回灌 LLM 修正 1 次 → 仍失败 → 降级结果：`problem_definition=原问题, conclusion_text=LLM 原始输出（截断）, missing_data_text="结构化输出解析失败"`，写入 task_logs WARN。`result_markdown` 顶部标注 `> 质量提示：本结果由原始文本降级生成`。

---

## 9. 前端详细设计

### 9.1 目录结构（文件级，与概设 §7.1 对齐，增补文件）

```
frontend/src/
├── main.ts / App.vue
├── router/index.ts            # 路由 + 守卫（§9.5）
├── api/
│   ├── http.ts                # axios 实例：withCredentials、401 拦截 → refresh 重放（1 次）
│   ├── auth.ts / chat.ts / attachment.ts / task.ts / result.ts / admin.ts
├── stores/                    # §9.2
├── ws/wsClient.ts             # §9.4
├── views/  LoginView / CallbackView / ChatView / AdminView / NotFoundView
├── components/
│   ├── chat/ ConversationList / ConversationItem / MessageList / MessageBubble /
│   │        ToolCard / AttachmentSidebar / InputBar / DataSourceSelect
│   ├── result/ ResultPanel / EvidenceList / MetricCard / ActionList
│   └── admin/ ConfigTable / DataSourceForm / DataSourceList / LogTable / FeatureSwitches
└── utils/ format.ts（UTC→本地）/ markdown.ts（渲染白名单）
```

### 9.2 Pinia store 接口（TS 签名）

```ts
// chat.ts
interface ChatState { conversations: Conversation[]; current: Conversation | null; }
const chatStore = defineStore('chat', {
  state: (): ChatState => ({ conversations: [], current: null }),
  actions: {
    async loadList(): Promise<void>,
    async create(title?: string, dataSourceId?: string): Promise<Conversation>,
    async rename(id: string, title: string): Promise<void>,
    async remove(ids: string[]): Promise<void>,
    async switchTo(id: string): Promise<void>,   // 拉 B5 历史 → messageStore.loadHistory
  },
})

// message.ts
interface MessageState {
  messages: Message[];            // 按 seq_no 升序
  maxSeq: number;                 // 已处理 WS seq 游标
  pendingDeltas: Map<string, string>;  // taskId -> 流式缓冲
}
actions: {
  loadHistory(convId: string): Promise<void>,
  appendLocal(text: string): Message,          // 乐观渲染（P2-12）
  onMessageStart(taskId: string, queuePosition: number): void,
  applyDelta(taskId: string, delta: string): void,   // requestAnimationFrame 节流
  upsertTool(evt: ToolEvent): void,
  commitResult(taskId: string, result: SixSection): void,
  rollbackLocal(messageId: string): void,
}

// task.ts
interface TaskState { current: TaskStatus | null; cancelling: boolean; }
actions: { setStatus(evt): void; setStep(step): void; cancel(): Promise<void>; }

// result.ts
interface ResultState { current: SixSection | null; exporting: boolean; }
actions: { setResult(r: SixSection): void; load(taskId): Promise<void>; export(taskId): Promise<void>; download(resultId): Promise<void>; }

// ws.ts
interface WsState { connected: boolean; reconnecting: boolean; }
actions: {
  connect(conversationId: string): Promise<void>,
  dispatch(evt: Envelope): void,     // 按 type 分发到各 store（§7.2 消息类型）
  reconnect(): void,                 // 指数退避 + 重新取 token + REST 恢复
}

// admin.ts
interface AdminState { configs: ConfigGroup[]; dataSources: DataSource[]; logs: LogRow[]; flags: FlagItem[]; }
actions: { fetchConfigs(); updateConfigs(items); reload(); fetchDataSources(); createDataSource(d); updateDataSource(id, d); removeDataSource(id); testDataSource(id); fetchLogs(params); updateFlags(items); }
```

### 9.3 核心组件契约

| 组件 | props | emits | 说明 |
|---|---|---|---|
| ConversationList | conversations, currentId | select, create, rename, remove | 新建/列表/悬浮菜单 |
| DataSourceSelect | dataSources, modelValue | update:modelValue | 新建会话时选择数据源（B1） |
| MessageList | messages | — | 按 seq_no 渲染；自动滚动 |
| MessageBubble | message | — | user/assistant 气泡；result 类型渲染六段式摘要 |
| ToolCard | tool: {name, status, summary} | — | running 态动画 / 成功 / 失败徽标 |
| AttachmentSidebar | attachments | upload, remove, download | 解析状态徽标（pending/parsing/parsed/failed） |
| InputBar | disabled, cancelling | send(content, attachmentIds), cancel | Enter 发送；任务运行中显示取消 |
| ResultPanel | result | copy, export, download | 六段式渲染 + 空态引导 |
| ConfigTable / DataSourceForm / LogTable / FeatureSwitches / LlmCostPanel / AuditLogTable | 见 adminStore | 变更事件 | 管理后台六 Tab（详见《详细设计-SDD-前端.md》§9.10） |

### 9.4 wsClient 类（TS 签名）

```ts
class WsClient {
  private ws: WebSocket | null = null;
  private convId = '';
  private retry = 0;
  private maxSeq = 0;
  private cache = new Map<number, Envelope>();     // 乱序缓存
  on(event: WsEventType, cb: (e: Envelope) => void): void;
  async connect(conversationId: string): Promise<void>;  // 调 B11 取 token → new WebSocket(`/ws/api/chat/ws/chat?websocket_token=&conversation_id=`)
  private onMessage(raw: MessageEvent): void;      // 解析信封 → 校验 seq → 去重/乱序 → emit
  cancelTask(taskId: string): void;
  close(): void;
  // 内部：心跳响应 pong；断线检测：60s 无 pong 判定断线（与概设 §5.4 对齐）→ reconnect（退避 1s→30s，重连前重取 token）
}
```

### 9.5 路由与守卫

| 路由 | 组件 | 守卫 |
|---|---|---|
| /login | LoginView | 已登录 → /chat |
| /auth/callback | CallbackView | 处理 code → 302 /chat |
| /chat | ChatView | 需登录 |
| /admin | AdminView | 需登录 + role=admin，否则跳 /403 |
| /403 | ForbiddenView | 独立 403 页（详见《详细设计-SDD-前端.md》§9.7） |
| * | NotFoundView | — |

---

## 10. 关键流程伪代码

### 10.1 发送消息全链路（B6 + WS）

```
Frontend: 调 B6 {conversation_id, content, attachment_ids} → 乐观渲染用户气泡 + pending 占位
Backend B6:
  1. 互斥：SELECT 1 FROM analysis_tasks WHERE conversation_id=? AND task_status IN ('queued','running') → 有则 TASK_BUSY
  2. seq_no = MAX(messages.seq_no)+1（UK 冲突重试 3 次）
  3. INSERT message(role=user, seq_no)
  4. IF attachment_ids: UPDATE attachments SET message_id=? WHERE id IN (...) AND conversation_id=?（归属校验）
  5. INSERT analysis_task(queued)
  6. set_ws_seq_if_greater(conv_id, seq_no)          # §7.1.2
  7. pos = queue.put(task_id)                        # 满 → TASK_QUEUE_FULL（任务/消息回滚）
  8. 返回 {message_id, task_id, queue_position: pos}
Worker:
  9. task = queue.get()；若任务已 cancelled → 跳过
 10. async with sem(3): task→running；推送 task_status(running, queue_position=0)
 11. engine.run(task_id)（§8.1；期间推送 message_start/tool_*/message_delta/result_ready...）
 12. 推送 done
```

### 10.2 取消（WS cancel_task 或 B13）

```
校验任务非终态（终态 → TASK_NOT_CANCELLABLE）
queued → UPDATE task_status='cancelled', error_message='用户取消', finished_at=NOW()；推送 task_status(cancelled) → done
running → 持有 task 协程的 Future.cancel()：
  - LLM 流：response.aclose()；llm_calls 记 status=failed, error='用户取消'
  - command_exec 子进程：terminate()（3s 后 kill）
  → UPDATE cancelled → 推送 task_status(cancelled) → done
```

### 10.3 断线重连恢复

```
客户端检测断线/60s 无消息 → reconnect()（退避 1s→30s）
重连成功 → 并行：B5（历史消息）/ B14（任务状态）/ B15（结果若存在）
→ 重建 UI；WS 增量正常接收（seq 去重；缓存乱序 2s 补渲染）
断线期间产生的事件：REST 兜底不丢（B5/B14/B15 幂等）
```

### 10.4 附件解析（异步，限并发 1）

```
上传（B7）→ 落库 pending → 提交解析协程（信号量 1，超限排队）
解析：pending→parsing → parser.parse(path)（xlsx ≤10s 目标）→ parse_result_json 落库 → parsed
失败：failed + task_logs ERROR + WS attachment_parsed(parse_status=failed)
完成：WS attachment_parsed(parse_status=parsed)
并发约束：解析协程与 Agent 任务共用进程事件循环，信号量仅限制解析自身并发
```

### 10.5 配置热更新

```
C2 更新 → audit_logs 写 before/after → 返回（不立即生效）
C3 reload → ConfigCache.load() → 返回 updated_keys；失败 CONFIG_RELOAD_FAILED
生效范围：LLM 配置（新任务生效）/ 任务上限（worker 循环读取）/ 功能开关（registry.schema 过滤）/ 附件限制（B7 校验）
```

### 10.6 数据清理（每日 03:00 UTC）

```
acquire_lock('cleanup', ttl=1800)；失败则跳过
批次1 软删业务数据：conversations(deleted_at<now-90d) → 级联物理删 messages/attachments(+文件)/
     analysis_tasks/analysis_results/context_summaries/websocket_tokens；每批 500，循环至清完
批次2 task_logs / llm_calls 按保留期 DELETE（每批 500）
批次3 websocket_tokens/auth_auth_codes 过期清理；auth_refresh_tokens 过期/吊销>30d
每批失败重试 3 次记 WARN，不阻塞后续；全部完成 release_lock
```

### 10.7 启动恢复（处置 P0-3）

```
backend 启动顺序：
1. alembic upgrade head（失败 → 健康检查不过，不对外）
2. ConfigCache.load()
3. JwtVerifier.start()（拉 JWKS）
4. UPDATE analysis_tasks SET task_status='failed', error_message='服务重启中断', finished_at=NOW()
   WHERE task_status IN ('queued','running')
5. TaskQueue.start(engine)（3 worker + 信号量）
6. 数据清理定时任务注册（每日 03:00 UTC）
7. 开始接受请求（健康检查 /healthz 通过）
```

---

## 11. 部署与初始化

### 11.1 Docker Compose 服务定义要点（对齐 PRD 11.1 预算）

| 服务 | 镜像 | mem_limit | 关键配置 |
|---|---|---|---|
| mysql | mysql:8.0 | 400m | `--innodb-buffer-pool-size=192M --max-connections=50 --innodb-flush-log-at-trx-commit=2`；卷：mysql-data |
| redis | redis:7-alpine | 180m | `--maxmemory 128mb --maxmemory-policy allkeys-lru --appendonly yes`；卷：redis-data |
| auth | 自建 | 180m | 单 worker；健康检查 /healthz |
| backend | 自建 | 600m | 单 worker（`--workers 1`）；健康检查 /healthz |
| frontend | nginx:alpine | 40m | 静态 + 反代（§11.2） |

服务依赖：backend/auth 依赖 mysql/redis healthy；backend 依赖 auth healthy（JWKS 拉取）。

### 11.2 nginx 反代配置要点

```nginx
server {
  listen 443 ssl;  # 证书挂载；开发环境可 http
  location /api/          { proxy_pass http://backend:8000; proxy_set_header Host $host; ... }
  location /ws/           { proxy_pass http://backend:8000; proxy_http_version 1.1;
                            proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }
  location /auth/         { proxy_pass http://backend:8000; }
  location /authorize     { proxy_pass http://auth:8001; }
  location /userinfo      { proxy_pass http://auth:8001; }
  location /.well-known/  { proxy_pass http://auth:8001; }
  location /token         { proxy_pass http://auth:8001; }
  location /              { root /usr/share/nginx/html; try_files $uri $uri/ /index.html; }
}
```

> `/authorize`、`/token`、`/userinfo`、`/.well-known/` 反代到 auth-service（浏览器授权跳转直达 + backend 服务端调用可走内网 `AUTH_SERVICE_URL`，两者皆可）；其余走 backend。

### 11.3 初始化编排（init_all.sh，幂等）

```
1. alembic upgrade head（建 17 张表 + 索引）
2. seed_configs.py（§2.4 清单，幂等 upsert）
3. seed_data_sources.py（预置 2 条：business 内置示例库 + scenario_goods 或按需，description 写场景说明）
4. seed_users.py（auth_users admin/analyst + users 双侧；默认密码首次登录提示修改）
5. gen_scenario_goods.py / gen_scenario_inventory.py（seed=2026，批量 INSERT 每批 500，12 万行 < 60s；已存在跳过）
```

---

## 12. 测试设计

| 层 | 范围 | 关键用例 |
|---|---|---|
| 单元（pytest） | core/工具/状态机 | SQL 校验链（白名单/黑名单/多语句拒绝）；命令沙箱（注入/超时/黑名单）；UUIDv7 单调性；六段式 Pydantic 校验与降级；llm_calls 记账 |
| 集成 | API/WS | B6 互斥（TASK_BUSY）；取消（queued/running 两态）；WS 信封 seq 去重/乱序；断线重连恢复；附件解析状态流转；配置热更新生效 |
| 端到端 | 场景演示 | 场景一/二完整问答链路（按 PRD §10 演示链路）；2C2G 内存监控（< 预算） |

---

## 13. 与 PRD / 概要设计的差异清单

| # | 差异 | 说明 |
|---|---|---|
| 1 | conversations 新增 `data_source_id`（+索引） | 处置 P0-1；数据源路由载体（§3） |
| 2 | data_sources 新增 `description` | 场景说明注入 Agent 提示词（§8.2） |
| 3 | B6 send 新增 `attachment_ids` | 处置 P0-2；附件显式关联（§6.2） |
| 4 | 结果生成职责收敛至 result 域 | 处置 P0-4；result_generate 工具默认关闭（§4.7/§4.8） |
| 5 | 启动恢复覆盖 queued+running | 处置 P0-3；PRD 11.3 只覆盖 running（§10.7） |
| 6 | ws seq 基线对齐 + Redis AOF | 处置 P1-5；防重启回卷（§7.1.2/§11.1） |
| 7 | ping/pong 不带 seq | 处置 P1-6；心跳独立控制通道（§7.1.1） |
| 8 | 统一错误响应结构 + 4 个新错误码 | 处置 P1-9（§2.1） |
| 9 | refresh token 使用即轮换 | 处置 P1-10（§5.3） |
| 10 | 完整 system_configs 清单（31 项） | 处置 P1-8；seed 依据（§2.4） |
| 11 | 外部数据源本期仅 MySQL | 决策 D4（§2.3） |
| 12 | 认证中心无用户管理端点 | 决策 D3（§5） |

---

## 14. 待验证风险

| # | 事项 | 验证时机 |
|---|---|---|
| 1 | asyncmy + SQLAlchemy 2.0 在 Windows 本地开发环境兼容性（备选 aiomysql） | M1 起步 |
| 2 | UUIDv7 实现选择（标准库 3.12 无内置，第三方 `uuid7` 包或自实现） | M1 起步 |
| 3 | Redis AOF 在 2C2G 下的写入放大（appendonly everysec） | M1 联调 |
| 4 | 12 万行示例数据灌入时长与 400MB 配额下索引构建 | M3 |
| 5 | 流式转发 + 3 任务并发内存峰值 < 600MB | M2 压测 |
| 6 | command_exec 沙箱对 python3 脚本的隔离充分性 | M2 安全测试 |
| 7 | 断线窗口内产生消息的 seq 对齐（基线抬升时机） | M3 联调 |

---

*本文档 v1.0 为编码基线。M1 起步时若发现契约需要调整，一律回写本文档（版本递增）后再改代码，保持 spec 与实现同步。*
