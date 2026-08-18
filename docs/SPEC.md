# SPEC 模块级规格文档：经营归因分析系统

## 1. 模块总览

| 模块 | 文件 | 职责 | 对外接口 |
|------|------|------|----------|
| 应用入口 | `app/main.py` | FastAPI应用工厂、路由注册、静态资源挂载 | GET / |
| 配置管理 | `app/config.py` | 环境变量与.env配置加载 | settings单例 |
| 数据库层 | `app/database.py` | SQLite连接管理、建表、事务 | get_connection/init_db/db |
| 数据模型 | `app/models.py` | Pydantic请求模型 | - |
| 认证模块 | `app/auth.py` | 登录、令牌管理、权限依赖 | login/require_user/require_admin |
| 会话模块 | `app/chat.py` | 会话与消息CRUD、级联删除 | create/list/update/delete等 |
| 任务模块 | `app/tasks.py` | 任务状态机、日志、并发控制 | create_task/transition/mark_failed |
| 结果模块 | `app/results.py` | 结果落库、Markdown渲染 | save_result/get_result |
| 令牌模块 | `app/tokens.py` | WebSocket一次性令牌 | issue_ws_token/consume_ws_token |
| 长连接模块 | `app/ws.py` | WebSocket连接、鉴权、消息泵 | /api/chat/ws/chat |
| LLM模块 | `app/llm.py` | DeepSeek调用、离线降级 | chat_completion |
| 管理模块 | `app/admin.py` | 配置缓存、热更新、日志查询 | load_config/reload_config |

## 2. 引擎模块规格

| 模块 | 文件 | 职责 |
|------|------|------|
| Schema注册 | `app/engine/schema.py` | 业务表结构文本、指标口径定义 |
| 分析管线 | `app/engine/pipeline.py` | 编排完整分析流程、事件推送 |
| SQL生成 | `app/engine/sql_gen.py` | Text2SQL提示词构建与SQL提取 |
| SQL守卫 | `app/engine/sql_guard.py` | SELECT白名单校验、危险词拦截 |
| SQL执行 | `app/engine/executor.py` | 只读执行、行数限制、失败重试 |
| 归因生成 | `app/engine/attribution.py` | 六维结构生成、解析、降级 |
| 指标计算 | `app/engine/metrics.py` | 库存周转率、转化率等纯函数 |

## 3. 模块详细规格

### 3.1 app/main.py — 应用入口

**职责**：创建FastAPI应用实例，注册所有路由和静态资源，管理应用生命周期。

**接口**：
- `create_app() -> FastAPI`：应用工厂函数
  - 创建FastAPI实例（title、lifespan）
  - lifespan内调用 `database.init_db()`
  - 依次include路由：auth_routes、chat_routes、attachment_routes、task_routes、admin_routes、ws
  - 挂载 `/static` 静态目录
  - 定义 `GET /` 返回index.html
  - 定义 `GET /health` 返回健康状态

**全局实例**：`app = create_app()`

---

### 3.2 app/config.py — 配置管理

**职责**：集中管理所有配置项，支持.env文件覆盖。

**配置项**：

| 配置 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| app_name | str | "经营归因分析系统" | 应用名 |
| host | str | "0.0.0.0" | 监听地址 |
| port | int | 8001 | 监听端口 |
| db_path | str | "data/db.sqlite3" | 数据库路径 |
| upload_dir | str | "data/uploads" | 附件目录 |
| export_dir | str | "data/exports" | 导出目录 |
| deepseek_api_key | str | "" | LLM密钥 |
| deepseek_base_url | str | "https://api.deepseek.com" | LLM地址 |
| deepseek_model | str | "deepseek-chat" | 模型名 |
| ws_token_ttl | int | 300 | WS令牌TTL秒 |
| max_result_rows | int | 200 | SQL结果行上限 |

---

### 3.3 app/database.py — 数据库层

**职责**：SQLite连接管理、DDL执行、事务上下文。

**接口**：
- `get_connection() -> sqlite3.Connection`：创建ROW_FACTORY连接
- `init_db()`：执行全部CREATE TABLE IF NOT EXISTS（11业务表+9业务数据表）+ 索引
- `db()`：上下文管理器，自动commit/rollback/close

**约束**：
- 业务表定义与DATA.md完全一致
- 外键约束启用：`PRAGMA foreign_keys = ON`
- WAL模式提升并发读写

---

### 3.4 app/auth.py — 认证模块

**职责**：Demo级用户名密码认证，内存令牌管理，FastAPI权限依赖。

**接口**：
- `login(username, password) -> dict | None`：校验凭证，签发令牌
  - 查询users表
  - Demo阶段明文比对（标注）
  - 生成UUID令牌，存入 `_TOKENS[token] = {user_id, expires_at}`
  - 返回 `{access_token, token_type, user}`
- `get_current_user(token) -> dict | None`：令牌换用户
- `require_user(authorization) -> dict`：FastAPI依赖，无效令牌抛401
- `require_admin(authorization) -> dict`：FastAPI依赖，非admin抛403

**约束**：
- 令牌有效期7200秒
- 过期令牌自动清理

---

### 3.5 app/chat.py — 会话模块

**职责**：会话与消息的完整生命周期管理。

**接口**：
- `create_conversation(user_id, title) -> dict`
- `list_conversations(user_id) -> list[dict]`：仅返回非deleted，按last_message_at倒序
- `get_conversation(user_id, conversation_id) -> dict | None`
- `update_conversation(user_id, conversation_id, title) -> dict | None`
- `delete_conversation(user_id, conversation_ids) -> int`：事务内级联删除8张表记录+物理目录
- `add_message(conversation_id, role, content, message_type, tool_name, tool_status) -> dict`：seq_no会话内自增
- `list_messages(conversation_id) -> list[dict]`：按seq_no升序
- `add_attachment(conversation_id, file_name, file_path, file_type, file_size) -> dict`
- `list_attachments(conversation_id) -> list[dict]`
- `get_attachment(user_id, attachment_id) -> dict | None`

**级联删除规则**（单事务）：attachments(含物理文件) → task_logs → analysis_results → analysis_tasks → context_summaries → websocket_tokens → messages → conversations → uploads/exports/workspace目录

---

### 3.6 app/tasks.py — 任务模块

**职责**：分析任务状态机与运行日志。

**常量**：
- `ALLOWED_TRANSITIONS = {queued: [running], running: [success, failed, cancelled]}`

**接口**：
- `log_task(task_id, level, log_type, content)`：写task_logs
- `create_task(conversation_id, user_id, input_text) -> dict`：
  - 校验该会话无queued/running任务（冲突抛异常）
  - 插入任务记录，状态queued
- `transition(task_id, from_status, to_status, current_step) -> dict`：
  - 校验状态转换合法性，非法抛异常
  - 更新状态、时间戳（started_at/finished_at）
- `mark_failed(task_id, error_message)`：running→failed + 错误信息
- `list_tasks(conversation_id=None, status=None) -> list[dict]`

---

### 3.7 app/results.py — 结果模块

**职责**：六维结构化结果的持久化与Markdown渲染。

**接口**：
- `result_markdown(result: dict) -> str`：渲染六段式Markdown报告
- `save_result(task_id, conversation_id, data: dict) -> dict`：
  - list字段序列化为JSON字符串入库
  - 生成result_markdown一并保存
- `get_result(task_id) -> dict | None`：反序列化JSON字段

---

### 3.8 app/tokens.py — 令牌模块

**职责**：WebSocket一次性令牌签发与消费。

**接口**：
- `issue_ws_token(user_id, conversation_id) -> dict`：
  - 生成UUID令牌
  - expires_at = now + TTL
  - 入库websocket_tokens
  - 返回 `{websocket_token, expires_in}`
- `consume_ws_token(token, user_id, conversation_id) -> bool`：
  - 查询令牌
  - 校验：存在 / 未消费 / 未过期 / 用户匹配 / 会话匹配
  - 通过则写consumed_at，返回True

---

### 3.9 app/ws.py — 长连接模块

**职责**：WebSocket端点，鉴权后循环接收问题并分发分析任务。

**行为规格**：
1. 连接参数校验（token + conversation_id）
2. `consume_ws_token` 鉴权，失败关闭连接（code=4001）
3. 创建事件队列 `asyncio.Queue`
4. 循环接收客户端JSON消息：
   - type == "question"：`asyncio.to_thread(pipeline.run_analysis, ...)` 后台执行
   - 其他类型：忽略
5. 发送协程持续从队列取事件推送给客户端
6. 连接关闭时清理

---

### 3.10 app/llm.py — LLM模块

**职责**：封装DeepSeek调用，提供离线降级。

**接口**：
- `chat_completion(messages, temperature=0.2) -> str`：
  - 无API Key → 直接走 `default_llm_call` 离线模式
  - 有Key → httpx POST /chat/completions
  - 网络异常 → 降级离线模式
- `default_llm_call(messages) -> str`：离线确定性应答
  - Prompt含"转化率/库存/周转"关键词 → 返回预设SQL
  - 归因类Prompt → 返回模板化六维JSON

---

### 3.11 app/engine/pipeline.py — 分析管线

**职责**：编排单轮分析全流程，通过回调推送事件。

**接口**：
- `run_analysis(conversation_id, user_id, question, emit) -> None`：
  1. `create_task` → emit(message_start)
  2. `transition(queued→running)` → emit(task_status)
  3. `add_message(user, question)`
  4. 步骤"生成SQL"：emit(tool_start) → `sql_gen.generate_sql` → emit(tool_finish) + emit(message_delta)
  5. 步骤"执行查询"：emit(tool_start) → `executor.execute_with_retry` → emit(tool_finish) + emit(message_delta)
  6. 步骤"生成归因"：emit(tool_start) → `attribution.generate_attribution` → emit(tool_finish) + emit(message_delta)
  7. `save_result` + `add_message(assistant)` → emit(result_ready)
  8. `transition(running→success)` → emit(done)
  9. 异常：`mark_failed` → emit(error)

**约束**：每步骤写task_logs；emit异常不中断主流程。

---

### 3.12 app/engine/sql_gen.py — SQL生成

**接口**：
- `build_prompt(question) -> list[dict]`：system（规则+Schema+指标口径）+ user（问题）
- `extract_sql(text) -> str | None`：正则提取 ```sql 代码块或裸SELECT
- `generate_sql(question, fix_context=None) -> str`：LLM生成 → 提取 → `sql_guard.validate_select` → 失败抛异常

---

### 3.13 app/engine/sql_guard.py — SQL守卫

**接口**：
- `validate_select(sql) -> tuple[bool, str]`：
  - 剥离 `--` 与 `/* */` 注释
  - 必须以SELECT/WITH开头
  - 黑名单词检测（18词，词边界匹配）
  - 分号计数≤1（单语句）
  - 返回(是否合法, 原因)

---

### 3.14 app/engine/executor.py — SQL执行

**接口**：
- `execute_sql(sql) -> dict`：
  - `sqlite3.connect("file:...?mode=ro", uri=True)` 只读连接
  - 执行后截断至max_result_rows
  - 返回 `{rows, columns, truncated}`
- `execute_with_retry(sql, fix_fn) -> dict`：失败时fix_fn修正后重试一次

---

### 3.15 app/engine/attribution.py — 归因生成

**数据模型**：
- `Metric(metric_name, metric_value, metric_unit, metric_period)`
- `Evidence(source_type, source_name, evidence_text, related_metric, confidence)`
- `AttributionResult(problem_definition, key_metrics, evidence_list, conclusion_text, missing_data_text, next_action_text)`

**接口**：
- `build_prompt(question, sql, exec_result) -> list[dict]`
- `parse_result(text) -> AttributionResult`：JSON提取 + Pydantic校验
- `build_fallback_result(question, exec_result) -> AttributionResult`：从行列数据确定性构建
- `generate_attribution(question, sql, exec_result) -> dict`：LLM优先，失败降级

---

### 3.16 app/engine/metrics.py — 指标计算

- `inventory_turnover(sales_qty, avg_inventory) -> float`：销量/平均库存
- `turnover_days(turnover, days) -> float`：天数/周转率
- `conversion_rate(conversions, visits) -> float`：转化/访问，除零保护

---

### 3.17 app/admin.py — 管理模块

- `load_config()`：启动时全量加载system_configs到内存缓存
- `reload_config() -> int`：重新加载，返回配置数
- `get_config(key, default)`：读缓存
- `set_config(key, value, group)`：upsert入库并刷新缓存
- `list_task_logs(offset, limit) -> dict`：分页查询task_logs

## 4. API路由模块规格

### 4.1 app/api/auth_routes.py
- `POST /api/auth/login`：LoginRequest → auth.login
- `GET /api/auth/me`：require_user → 用户信息

### 4.2 app/api/chat_routes.py
- `POST /api/chat/create`：require_user → 建会话
- `POST /api/chat/delete`：require_user → 批量删
- `POST /api/chat/update`：require_user → 改标题
- `GET /api/chat/ls`：require_user → 会话列表
- `GET /api/chat/ls/{cid}`：require_user → 消息列表（含每条消息附件）
- `POST /api/chat/ws-token`：require_user → 签发WS令牌

### 4.3 app/api/attachment_routes.py
- `POST /api/attachment/upload`：multipart → 磁盘保存 + 入库
- `POST /api/attachment/delete`：删记录 + 删物理文件
- `GET /api/attachment/get`：FileResponse下载
- `GET /api/attachment/ls`：会话附件列表

### 4.4 app/api/task_routes.py
- `GET /api/tasks/{task_id}`：任务状态详情
- `GET /api/results/{task_id}`：六维结构化结果
- `GET /api/results/{task_id}/export`：md/json导出文件流

### 4.5 app/api/admin_routes.py
- `GET /api/admin/config`：require_admin → 配置列表
- `POST /api/admin/reload`：require_admin → 热更新
- `GET /api/admin/logs`：require_admin → 分页日志

## 5. 脚本与测试规格

### 5.1 scripts/gen_data.py — 数据生成
- 建库建表 → 种子用户(admin/admin123) → 系统配置 → 库存场景数据(5-7月,东仓异常) → 客户行为数据(5-7月,7月转化率下降)
- `random.seed(42)` 确定性

### 5.2 tests/ — 测试套件
| 文件 | 覆盖 |
|------|------|
| test_sql_guard.py | SQL守卫正反用例 |
| test_metrics.py | 指标计算与除零 |
| test_results.py | 结果序列化与Markdown |
| test_tasks.py | 状态机与并发控制 |
| test_ws_token.py | 令牌一次性与过期 |
| test_engine.py | 管线端到端（离线LLM） |
