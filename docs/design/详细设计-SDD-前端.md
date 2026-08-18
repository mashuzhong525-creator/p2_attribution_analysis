# 模块级详细设计（前端）· 经营归因分析系统

> 本文档为《详细设计-SDD.md》的**前端模块裁剪版**（单模块 Spec）。依据：
> - PRD v1.1（`docs/经营归因分析系统-需求规格说明书PRD.md`）
> - 概要设计 v1.0（`docs/design/概要设计.md`，决策 9/10/11）
> - 完整 SDD v1.0（`docs/design/详细设计-SDD.md`，§9 前端章为待深化基线）
> - 评审日期：2026-08-18｜新增决策 4 项（D1–D4）｜处置缺口 13 处（F-P0×2 / F-P1×6 / F-P2×5）
>
> 阅读约定：未在本模块展开的后端 / auth / 部署章标注「本节范围外（见完整 SDD）」。

---

## 0. 文档信息

| 项 | 值 |
|---|---|
| 模块 | 前端（Vue3 SPA） |
| 版本 | v1.0 |
| 日期 | 2026-08-18 |
| 状态 | 评审稿（已通过交叉评审 + 4 项决策收敛） |
| 上游基线 | PRD v1.1 / 概要设计 v1.0 / SDD v1.0 |
| 技术栈 | Vue 3.4 + TypeScript 5.4 + Vite 5 + Pinia 2 + Vue Router 4 + 原生 CSS（D1 决策：零 UI 库） |
| 目标规格 | 2C2G 云服务器；前端为静态资源经 Nginx 托管，无运行时计算压力 |

---

## 1. 评审结论与收敛决策

### 1.1 评审范围与结论

对 SDD §9（前端章）按「可上线级、字段级定死」标准交叉评审，发现 **13 处缺口**（P0×2 / P1×6 / P2×5）。结论：SDD §9 已有目录、store 签名骨架、组件表、wsClient 签名、路由表，但与 PRD 7.x、概要设计前端决策基本对齐但**处于骨架级而非可编码级**。最要命的两条：① 跨 store 协作链路未定死（编码 Agent 会各写各的）；② 403 页组件缺失（违反 PRD 7.5）。

### 1.2 问题分级与处置表

| 编号 | 维度 | 问题 | 严重度 | 处置（本 Spec 章节） |
|---|---|---|---|---|
| F-P0-1 | 跨 store 协作 | wsStore 收到事件后如何驱动 message/task/result/chat 四 store 联动、会话切换如何清理未定死 | P0 | §9.4 功能链路表 + §9.7 会话切换清理 |
| F-P0-2 | 路由守卫 | PRD 7.5 要求「非 admin 跳转 403」，SDD §9.5 仅「否则 403 页」五字，无组件契约 | P0 | §9.7 独立 ForbiddenView（D2） |
| F-P1-1 | WS 客户端 | 心跳/断线参数未与概要对齐定死（SDD 注释「60s 无消息」与概要「30s ping ×2」表述不一） | P1 | §9.6 参数定死：30s ping / 60s 无 pong 判定断线 |
| F-P1-2 | WS 客户端 | seq 去重与重启基线对齐逻辑缺失（wsClient 启动 maxSeq 初值来源未定） | P1 | §9.6 seq 规则 + 首次连接 REST 恢复带回 maxSeq |
| F-P1-3 | 渲染 | 乐观渲染回滚边界未定（失败场景、pending 占位标记、并发 seq 冲突） | P1 | §9.3 appendLocal/rollbackLocal + §10.1 |
| F-P1-4 | 组件 | props 关键字段缺失（MessageBubble/ToolCard/ResultPanel 结构未定死） | P1 | §9.5 组件契约全量补全 |
| F-P1-5 | 错误 | 全局错误提示机制缺失（api 层错误码如何映射展示） | P1 | §9.8 自研 Toast + 错误码映射（D4） |
| F-P1-6 | admin | SDD §9.3 写「管理后台四 Tab」，但 SDD 其他章节已加 llm_calls/audit_logs 表 | P1 | §9.10 定死为六 Tab（与上线决策一致） |
| F-P2-1 | 渲染 | 流式节流合并窗口未定（requestAnimationFrame 节流但未说合并策略） | P2 | §9.3 applyDelta 合并窗口 16ms |
| F-P2-2 | 附件 | 上传进度绑定方式未定（fetch/XHR、进度条） | P2 | §9.5 AttachmentSidebar + §10.6 |
| F-P2-3 | 路由 | 路由切换 WS 时机未定（切 /admin 是否断开） | P2 | §9.7 全局单例保活（D3） |
| F-P2-4 | 安全 | markdown 渲染 XSS 防护方案未定 | P2 | §9.9 白名单 + DOMPurify 可选 |
| F-P2-5 | 表单 | DataSourceForm 字段校验规则未定 | P2 | §9.5 校验规则表 |

### 1.3 拷问决策（4 项，全部采纳推荐）

| 编号 | 问题 | 决策 | 理由 |
|---|---|---|---|
| D1 | UI 组件库选型 | **纯手写原生 CSS**（零 UI 库） | 与现有原型/目录结构/轻量原则一致；2C2G 前端无性能压力；风格完全可控 |
| D2 | 403 页形态 | **独立 ForbiddenView**（路由 `/403`） | PRD 7.5 明确要求；语义正确（权限非不存在）；验收不打折 |
| D3 | WS 生命周期 | **全局单例 + 按会话连接** | App 级 wsClient 单例；进 /chat 连接当前会话，切 /admin 保活，切会话重建；恢复最简单 |
| D4 | 错误提示 | **自研轻量 Toast** | 无依赖；api 层统一拦截映射；与「无第三方依赖」原则一致 |

---

## 2. 全局契约（前端相关子集）

> 完整错误响应结构、system_configs 清单、环境变量见完整 SDD §2。本节仅列前端直接依赖的子集。

### 2.1 后端统一响应结构（前端必须按此解析）

```ts
// 成功：HTTP 2xx，body 为业务数据（各接口响应字段见 §6）
// 失败：HTTP 4xx/5xx，body：
interface ApiError {
  code: string;     // 业务错误码，如 AUTH_EXPIRED / TASK_BUSY / VALIDATION_ERROR
  message: string;  // 可读中文文案（展示用）
  data?: null;
}
```

### 2.2 前端错误码 → 展示文案映射（D4，定死）

| code | HTTP | 文案 | 行为 |
|---|---|---|---|
| `AUTH_EXPIRED` | 401 | 登录态已过期，正在刷新… | 触发刷新重放（§10.5），不弹 Toast |
| `AUTH_INVALID` | 401 | 登录无效，请重新登录 | 跳 /login |
| `FORBIDDEN` | 403 | 无权限访问该页面 | 跳 /403（D2） |
| `TASK_BUSY` | 409 | 该会话已有分析任务进行中 | 提示并禁用发送，展示当前任务 |
| `VALIDATION_ERROR` | 422 | 参数错误：{detail} | 表单内联错误 / Toast |
| `RATE_LIMITED` | 429 | 操作过于频繁，请稍后再试 | Toast |
| `UPLOAD_TOO_LARGE` | 413 | 附件超过 20MB 限制 | Toast |
| `INTERNAL_ERROR` | 500 | 服务异常，请稍后重试 | Toast + 上报 |

### 2.3 前端环境变量（`.env` / `.env.prod`）

```ini
VITE_API_BASE=/api            # REST 基址（经 Nginx 反代，同源）
VITE_WS_BASE=/ws/api/chat/ws/chat   # WS 基址
VITE_AUTH_CALLBACK=/auth/callback   # 回调路由，用于登录后 302 目标
VITE_APP_TITLE=经营归因分析系统
```

### 2.4 影响前端的 system_configs（展示/开关类，其余见完整 SDD）

| config_key | 类型 | 前端用途 |
|---|---|---|
| `flag_scenario_data` | bool | 新建会话时是否展示「示例场景数据源」选项（P0-1 决策：场景 schema 注入开关） |
| `flag_command_exec` | bool | 输入区是否展示「命令执行」高级模式入口 |
| `ui_stream_throttle_ms` | int | 流式渲染合并窗口（默认 16，F-P2-1） |

> 其他 LLM/base_url 等配置仅后端使用，前端不展示。

---

## 3. 数据库 DDL

本节范围外（见完整 SDD §3，前端不直接操作数据库）。

---

## 4. backend 模块设计

本节范围外（见完整 SDD §4）。前端仅依赖其暴露的 REST/WS 契约（§6、§7）。

---

## 5. auth-service

本节范围外（见完整 SDD §5）。前端仅依赖：
- `GET /auth/login` → 302 至认证中心 authorize
- `GET /auth/callback` → 建立登录态（HttpOnly Cookie：access + refresh）
- `POST /auth/logout`
- `GET /api/auth/me` → `{username, display_name, role}`

---

## 6. REST 接口契约全集（前端调用）

> 字段级定死。所有请求带 `withCredentials`；路径相对 `VITE_API_BASE`。

### 6.1 认证与用户

| 方法/路径 | 请求 | 响应（body） | 说明 |
|---|---|---|---|
| `GET /api/auth/me` | — | `{username, display_name, role: 'admin'|'analyst'}` | 守卫调用；401 → 跳 /login |
| `POST /auth/logout` | — | `{status:'ok'}` | 清 Cookie |

### 6.2 会话（chat）

| 方法/路径 | 请求 | 响应 | 说明 |
|---|---|---|---|
| `POST /api/chat/create` | `{title?:string, data_source_id:string}` | `{conversation_id:string, title:string, status:'active', data_source_id:string}` | data_source_id 必填（P0-1 决策） |
| `POST /api/chat/delete` | `{conversation_ids:string[]}` | `{status:'ok', deleted_ids:string[]}` | 软删 |
| `POST /api/chat/update` | `{conversation_id:string, title:string}` | `{conversation_id, title, status}` | 重命名 |
| `GET /api/chat/ls` | — | `{conversations: ConversationListItem[]}` | 列表 |
| `GET /api/chat/ls/{conversation_id}` | — | `{messages: Message[]}` | 历史，按 seq_no 升序 |
| `POST /api/chat/send` | `{conversation_id:string, content:string, attachment_ids?:string[]}` | `{message_id:string, task_id:string|null}` | **B6 发送入口**（P0-2：attachment_ids 显式关联） |

```ts
interface ConversationListItem {
  conversation_id: string;
  title: string;
  status: 'active' | 'archived' | 'deleted';
  data_source_id: string;          // P0-1：会话绑定数据源
  data_source_name?: string;       // 列表展示用，后端 JOIN 返回
  last_message_at: string | null;  // UTC ISO8601
}
interface Message {
  message_id: string;
  role: 'user' | 'assistant' | 'system';
  message_type: 'text' | 'tool' | 'result' | 'error';
  content: string;                 // user/assistant 文本；result 类型时为六段式 markdown
  seq_no: number;                  // 会话内单调递增（与 WS seq 不同源，见 §7.2）
  tool_name?: string;              // message_type=tool 时
  tool_status?: 'start' | 'finish' | 'error';
  attachments?: Attachment[];      // 用户消息携带的附件
  created_at: string;              // UTC
}
interface Attachment {
  attachment_id: string;
  file_name: string;
  file_type: 'csv' | 'xlsx' | 'txt';
  file_size: number;
  parse_status: 'pending' | 'parsing' | 'parsed' | 'failed';
  parse_result?: AttachmentParseResult;  // parsed 时
}
```

### 6.3 附件（attachment）

| 方法/路径 | 请求 | 响应 | 说明 |
|---|---|---|---|
| `POST /api/attachment/upload` | `multipart/form-data: {conversation_id, file}` | `Attachment`（含 attachment_id） | 异步解析，状态经 WS 推送 |
| `POST /api/attachment/delete` | `{attachment_id:string}` | `{status:'ok'}` | |
| `GET /api/attachment/{attachment_id}/download` | — | 文件流（blob） | |

### 6.4 任务与结果（task / result）

| 方法/路径 | 请求 | 响应 | 说明 |
|---|---|---|---|
| `GET /api/tasks/{task_id}` | — | `{task_id, conversation_id, task_status, current_step, started_at, finished_at?, error_message?}` | 重连恢复用 |
| `POST /api/tasks/{task_id}/cancel` | — | `{status:'ok'}` | REST 取消兜底（WS cancel_task 优先） |
| `GET /api/tasks/{task_id}/logs` | — | `{logs: TaskLogItem[]}` | 实时任务区展示 |
| `GET /api/results/{task_id}` | — | `SixSection` | 结果详情 |
| `POST /api/results/{result_id}/export` | — | `{file_url:string}` | 导出文件 |

```ts
type TaskStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled';
interface SixSection {              // 六段式（§7.4 展示）
  problem_definition: string;
  key_metrics: KeyMetric[];
  evidence_list: Evidence[];
  conclusion_text: string;
  missing_data_text: string;
  next_action_text: string;
  result_markdown: string;          // 整段渲染用
  result_file_path?: string;
}
interface KeyMetric { name: string; value: string; delta?: string; unit?: string; }
interface Evidence {
  source_type: 'db' | 'file' | 'text' | 'command';
  source_name: string;
  content: string;
  confidence: number;               // 0~1
}
```

### 6.5 WS 令牌（B11）

| 方法/路径 | 请求 | 响应 | 说明 |
|---|---|---|---|
| `POST /api/chat/ws-token` | `{conversation_id:string}` | `{websocket_token:string}` | 一次性令牌，重连前重新获取（§7.3） |

### 6.6 管理后台（admin，六 Tab，F-P1-6 定死）

| 方法/路径 | 请求 | 响应 | Tab |
|---|---|---|---|
| `GET /api/admin/configs` | — | `{groups: ConfigGroup[]}` | 系统配置 |
| `PUT /api/admin/configs` | `{items: {config_key, config_value}[]}` | `{status:'ok'}` | 系统配置 |
| `POST /api/admin/reload` | — | `{status:'ok'}` | 系统配置（热重载） |
| `GET /api/admin/datasources` | — | `{data_sources: DataSource[]}` | 数据源 |
| `POST /api/admin/datasources` | `DataSourceForm` | `{data_source_id}` | 数据源 |
| `PUT /api/admin/datasources/{id}` | `DataSourceForm` | `{status:'ok'}` | 数据源 |
| `DELETE /api/admin/datasources/{id}` | — | `{status:'ok'}` | 数据源 |
| `POST /api/admin/datasources/{id}/test` | — | `{ok:boolean, message:string}` | 数据源 |
| `GET /api/admin/logs` | `{level?, type?, page, size}` | `{rows: LogRow[], total}` | 运行日志 |
| `GET /api/admin/flags` | — | `{flags: FlagItem[]}` | 功能开关 |
| `PUT /api/admin/flags` | `{items:{flag_key, enabled}[]}` | `{status:'ok'}` | 功能开关 |
| `GET /api/admin/llm-costs` | `{range:'today'|'month'}` | `{total_cost, total_tokens, rows: LlmCallRow[]}` | **LLM 成本（新增 Tab）** |
| `GET /api/admin/audit-logs` | `{page, size}` | `{rows: AuditRow[], total}` | **审计日志（新增 Tab）** |

```ts
interface DataSourceForm {
  name: string; db_type: 'mysql' | 'postgres'; host: string; port: number;
  database: string; username: string; password?: string;
  is_readonly: boolean; is_enabled: boolean;
}
interface FlagItem { flag_key: string; enabled: boolean; description: string; }
```

---

## 7. WS 协议（前端相关）

### 7.1 统一信封（来自概要决策 6）

```ts
interface Envelope {
  v: 1;
  type: WsEventType;
  conversation_id: string;
  task_id?: string;
  seq: number;          // 事件流序号（Redis INCR，与 messages.seq_no 不同源，见 §7.2）
  ts: number;           // 服务端 UTC 毫秒
  payload: unknown;
}
type WsEventType =
  | 'message_start' | 'message_delta' | 'message_end'
  | 'tool_start' | 'tool_finish' | 'tool_error'
  | 'result_ready' | 'task_status' | 'done' | 'error'
  | 'attachment_parse' | 'ping' | 'pong';
```

### 7.2 seq 规则（F-P1-2 定死）

- **WS `seq`**：服务端 Redis INCR 生成，全会话单调递增；用于前端**去重与乱序检测**。
- **`messages.seq_no`**：落库消息序号（用户/助手气泡），用于历史回放排序。
- 两者**不同源但均单调**（概要决策 2 澄清）。前端 `messageStore.maxSeq` 跟踪 WS seq 游标；`messages` 数组按 `seq_no` 排序。
- **重启基线对齐**：wsClient 首次 `connect` 后，先并行拉 `GET /api/chat/ls/{id}`（带 MAX(seq_no)）；`maxSeq` 初值 = REST 返回的最大 WS seq（由后端在历史事件响应中附带 `last_ws_seq` 字段，无则为 0）。断线重连恢复（§10.3）同样以 REST 回填 `maxSeq`。

### 7.3 心跳与断线（F-P1-1 定死，与概要 §5.4 对齐）

- 服务端每 **30s** 发 `ping`；客户端收到即回 `pong`（**pong 不带 seq，走独立控制通道，不污染去重**，完整 SDD P1-6 处置）。
- 客户端维护 `lastPongAt`；若 **60s（=2×30s）内未收到任何 pong** → 判定断线 → 触发重连。
- 重连：指数退避 **1s → 2s → 4s → … → 30s 封顶**；重连前重新调 `POST /api/chat/ws-token` 换取新一次性令牌。
- 连续重连失败 **5 次** → 提示「连接失败，请刷新页面」并停止重试。

### 7.4 事件 → UI 映射（F-P0-1 协作链路基础）

| 事件 | 触发动作 | 目标 store |
|---|---|---|
| `message_start` | 创建占位气泡（assistant）+ 任务进度条 | messageStore + taskStore |
| `message_delta` | 追加流式文本（节流合并） | messageStore.applyDelta |
| `message_end` | 封口该气泡 | messageStore |
| `tool_start` | 新增 ToolCard（running 动画） | messageStore.upsertTool |
| `tool_finish` | ToolCard → success + 摘要 | messageStore.upsertTool |
| `tool_error` | ToolCard → failed 红标 | messageStore.upsertTool |
| `result_ready` | 渲染六段式到结果区 | resultStore.setResult |
| `task_status` | 更新任务状态条（含 cancelled） | taskStore.setStatus |
| `done` | 任务完成、触发历史摘要压缩标记 | taskStore + chatStore |
| `error` | 全局 Toast + 回滚乐观消息 | toast + messageStore.rollbackLocal |
| `attachment_parse` | 更新附件侧栏状态徽标 | 由 chatStore/附件列表订阅 |

---

## 8. Agent 引擎

本节范围外（见完整 SDD §8）。前端仅消费其经 WS 推送的事件（§7.4）。

---

## 9. 前端详细设计（★ 核心）

### 9.1 目录结构（文件级，D1 零 UI 库）

```
frontend/
├── index.html / vite.config.ts / tsconfig.json / .env / .env.prod
├── src/
│   ├── main.ts                      # 挂载 App + router + pinia + 全局 Toast 容器
│   ├── App.vue                      # 全局布局壳 + wsClient 单例挂载（D3）
│   ├── router/index.ts              # 路由表 + 守卫（§9.7）
│   ├── types/index.ts               # 全局 TS 类型（§9.2）
│   ├── api/
│   │   ├── http.ts                  # axios 实例：withCredentials、401 刷新重放（§10.5）
│   │   ├── auth.ts / chat.ts / attachment.ts / task.ts / result.ts / admin.ts
│   ├── stores/                      # §9.3 六个 store
│   │   ├── chat.ts / message.ts / task.ts / result.ts / ws.ts / admin.ts
│   ├── ws/wsClient.ts               # §9.6 自研 WS 客户端
│   ├── views/
│   │   ├── LoginView.vue / CallbackView.vue / ChatView.vue
│   │   ├── AdminView.vue / ForbiddenView.vue / NotFoundView.vue
│   ├── components/
│   │   ├── chat/  ConversationList / ConversationItem / MessageList / MessageBubble
│   │   │        / ToolCard / AttachmentSidebar / InputBar / DataSourceSelect
│   │   ├── result/ ResultPanel / EvidenceList / MetricCard / ActionList
│   │   ├── admin/  ConfigTable / DataSourceForm / DataSourceList / LogTable
│   │   │        / FeatureSwitches / LlmCostPanel / AuditLogTable
│   │   └── common/ Toast.vue / Spinner.vue / Modal.vue / Guard403.vue
│   ├── utils/ format.ts（UTC→本地）/ markdown.ts（白名单渲染，§9.9）/ throttle.ts
│   └── styles/ variables.css（CSS 变量）/ base.css
```

### 9.2 全局类型定义（types/index.ts，定死，供全模块 import）

```ts
// 上述 §6 所有 interface（ConversationListItem/Message/Attachment/SixSection/
// KeyMetric/Evidence/TaskStatus/DataSourceForm/FlagItem/ConfigGroup/LogRow/
// LlmCallRow/AuditRow/Envelope/WsEventType）均在此导出。
// 补充 WS 事件载荷：
interface ToolEvent { task_id: string; name: string; status: 'start'|'finish'|'error'; summary?: string; }
interface TaskStatusEvent { task_id: string; task_status: TaskStatus; current_step?: number; error_message?: string; }
```

### 9.3 Pinia 六个 store（完整 state + actions + 关键逻辑）

#### chatStore
```ts
interface ChatState {
  conversations: ConversationListItem[];
  currentId: string | null;
  current: ConversationListItem | null;
}
actions:
  async loadList(): Promise<void>            // GET /api/chat/ls → conversations
  async create(title?: string, dataSourceId: string): Promise<ConversationListItem>
  async rename(id: string, title: string): Promise<void>
  async remove(ids: string[]): Promise<void>
  async switchTo(id: string): Promise<void>  // 1) chatStore.currentId=id
                                             // 2) messageStore.loadHistory(id)
                                             // 3) resultStore.load(id)（如有）
                                             // 4) wsStore.connect(id)（D3 全局单例）
  clearCurrent(): void                       // 会话切换/退出时清理（F-P0-1）
```

#### messageStore（F-P1-3 乐观渲染定死）
```ts
interface MessageState {
  messages: Message[];                        // 按 seq_no 升序
  maxSeq: number;                             // WS seq 游标（去重/乱序）
  pendingDeltas: Map<string, string>;        // taskId -> 流式缓冲
  pendingIds: Set<string>;                    // 乐观消息本地 id 集合（回滚用）
}
actions:
  loadHistory(convId: string): Promise<void>  // GET 历史 → messages；maxSeq=响应.last_ws_seq
  appendLocal(text: string, attachments?: Attachment[]): string
      // 返回本地 id；插入占位气泡 role=user, message_type='text', seq_no=临时-1
      // 标记 pendingIds.add(localId)
  onMessageStart(taskId: string, queuePos: number): void
      // 插入 assistant 占位气泡（message_type='text', 空 content），绑定 taskId
  applyDelta(taskId: string, delta: string): void
      // 合并窗口 16ms（requestAnimationFrame + 缓冲，F-P2-1）：
      // pendingDeltas[taskId] += delta；rAF  flush 到对应气泡 content
  upsertTool(evt: ToolEvent): void            // 按 taskId 定位气泡，插入/更新 ToolCard
  commitResult(taskId: string, result: SixSection): void
      // 将 assistant 气泡 message_type 置 'result'，content=result_markdown
  rollbackLocal(localId: string): void       // 从 messages 移除占位；pendingIds.delete
  markFailed(localId: string, reason: string): void  // 占位气泡标红 + 错误文案
getters:
  orderedMessages: Message[]                  // 按 seq_no 排序（临时 -1 排末尾）
```

#### taskStore
```ts
interface TaskState { current: TaskStatusEvent | null; cancelling: boolean; queuePos: number; }
actions:
  setStatus(evt: TaskStatusEvent): void       // 更新 current；cancelling=false
  setQueuePosition(pos: number): void
  async cancel(): Promise<void>               // 优先 wsStore.cancelTask(taskId)；失败兜底 POST /api/tasks/{id}/cancel
```

#### resultStore
```ts
interface ResultState { current: SixSection | null; exporting: boolean; }
actions:
  setResult(r: SixSection): void
  async load(convId: string): Promise<void>   // 取最近成功任务结果回填（切换会话用）
  async export(resultId: string): Promise<void>  // POST export → 下载 blob
  download(url: string): void                 // 触发 <a download>
```

#### wsStore（D3 全局单例封装）
```ts
interface WsState { connected: boolean; reconnecting: boolean; }
actions:
  connect(conversationId: string): Promise<void>  // 委托 wsClient.connect；绑定 onEvent 回调
  onEvent(env: Envelope): void                    // 按 §7.4 分发表驱动各 store
  reconnect(): void                               // wsClient.reconnect → 成功后 REST 恢复（§10.3）
  cancelTask(taskId: string): void                // wsClient.cancelTask
  disconnect(): void                              // 登出时调用
```

#### adminStore（F-P1-6 六 Tab 数据）
```ts
interface AdminState {
  configs: ConfigGroup[]; dataSources: DataSource[]; logs: LogRow[];
  flags: FlagItem[]; llmCosts: {total_cost:number; rows:LlmCallRow[]}; auditLogs: AuditRow[];
}
actions:
  fetchConfigs(); updateConfigs(items); reload();
  fetchDataSources(); createDataSource(d); updateDataSource(id,d); removeDataSource(id); testDataSource(id);
  fetchLogs(params); fetchFlags(); updateFlags(items);
  fetchLlmCosts(range); fetchAuditLogs(params);   // 两个新增 Tab 的数据源
```

### 9.4 跨 store 协作链路（F-P0-1 定死，解决「各写各的」）

**单一事件入口**：所有 WS 事件只经 `wsStore.onEvent(env)` 分发，禁止组件直接监听 wsClient。分发表（与 §7.4 一致）：

```
wsStore.onEvent(env):
  switch env.type:
    'message_start'  -> messageStore.onMessageStart(env.task_id, env.payload.queue_position)
                         + taskStore.setQueuePosition(env.payload.queue_position)
    'message_delta'  -> messageStore.applyDelta(env.task_id, env.payload.delta)
    'message_end'    -> messageStore.commitMessage(env.task_id)
    'tool_start'     -> messageStore.upsertTool(env.payload as ToolEvent) + taskStore.setStatus({task_status:'running'})
    'tool_finish'    -> messageStore.upsertTool(env.payload)
    'tool_error'     -> messageStore.upsertTool(env.payload)
    'result_ready'   -> resultStore.setResult(env.payload as SixSection)
    'task_status'    -> taskStore.setStatus(env.payload as TaskStatusEvent)
    'done'           -> taskStore.setStatus({task_status:'success'}) + chatStore.refreshLastMessageAt()
    'error'          -> toast.error(env.payload.message) + messageStore.rollbackLocal(env.payload.local_id?)
    'attachment_parse' -> chatStore.updateAttachmentStatus(env.payload)
    'pong'           -> wsClient.notePong()   // 不进 store，控制通道
    'ping'           -> wsClient.respondPong()
```

**会话切换清理（F-P0-1）**：`chatStore.switchTo(newId)` 执行顺序：
1. `messageStore.$reset()` 清消息与 pendingDeltas/pendingIds
2. `taskStore.$reset()` 清当前任务
3. `resultStore.current = null`
4. `await messageStore.loadHistory(newId)` + `resultStore.load(newId)`
5. `wsStore.connect(newId)`（D3：单例切会话重建连接）

### 9.5 核心组件契约（全量 props/emits，F-P1-4 补全）

| 组件 | props | emits | 关键逻辑 |
|---|---|---|---|
| `ConversationList` | `conversations: ConversationListItem[]`, `currentId: string` | `select(id)`, `create`, `rename(id,title)`, `remove(ids)` | 悬浮菜单；选中态高亮 |
| `ConversationItem` | `item: ConversationListItem` | `select`, `rename`, `remove` | 标题 + 数据源名 + 时间；右键菜单 |
| `DataSourceSelect` | `dataSources: DataSourceListItem[]`, `modelValue: string` | `update:modelValue` | 新建会话弹窗内选择（P0-1；选项受 `flag_scenario_data` 控制是否含示例源） |
| `MessageList` | `messages: Message[]` | — | 按 seq_no 渲染；自动滚底；`message_delta` 期间禁用滚底按钮 |
| `MessageBubble` | `message: Message` | — | user/assistant 气泡；`message_type='tool'` 渲染 ToolCard；`'result'` 渲染 ResultPanel 摘要；时间 UTC→本地 |
| `ToolCard` | `tool: {name, status:'start'|'finish'|'error', summary?}` | — | start：旋转动画 + 名称；finish：✓ + summary；error：✗ 红标 |
| `AttachmentSidebar` | `attachments: Attachment[]` | `upload(files)`, `remove(id)`, `download(id)` | 状态徽标：`pending`(灰)/`parsing`(蓝转圈)/`parsed`(绿)/`failed`(红)；上传进度条（F-P2-2，XHR `onprogress`） |
| `InputBar` | `disabled: boolean`, `cancelling: boolean`, `attachmentIds: string[]` | `send(content, attachmentIds)`, `cancel` | Enter 发送 / Shift+Enter 换行；任务运行中显示取消按钮；附件入口 |
| `ResultPanel` | `result: SixSection` | `copy`, `export(resultId)`, `download(url)` | 六段式渲染：指标卡网格 + 证据链（含 confidence 角标）+ 结论/缺失/下一步；复制/导出/下载按钮；空态引导 |
| `ConfigTable` | `groups: ConfigGroup[]` | `update(items)` | 分组表格 + 行内编辑 + 保存；「重载」按钮调 adminStore.reload |
| `DataSourceForm` | `modelValue?: DataSourceForm`, `mode:'create'|'edit'` | `submit(form)`, `cancel` | 字段校验（F-P2-5）：host 必填、port 1–65535、db_type 下拉、is_readonly 开关；test 按钮 |
| `DataSourceList` | `dataSources: DataSource[]` | `create`, `edit(id)`, `remove(id)`, `test(id)` | 列表 + 启停徽标 |
| `LogTable` | `rows: LogRow[]`, `total: number` | `page-change(p)`, `filter(opts)` | 分页 + level/type 过滤 |
| `FeatureSwitches` | `flags: FlagItem[]` | `update(items)` | 开关列表，即时生效 |
| `LlmCostPanel` | `range`, `total_cost`, `rows: LlmCallRow[]` | `range-change(r)` | KPI 卡片（今日/本月成本 + token）+ 每步调用明细表 |
| `AuditLogTable` | `rows: AuditRow[]`, `total` | `page-change(p)` | 谁/何时/改了什么/前后值 |
| `Toast` | `type:'info'|'error'|'warn'`, `message: string` | `close` | 全局单例（D4），自动消失 3s |
| `ForbiddenView` | — | `back` | 403 页（D2）：权限图标 + 「无权限访问」+ 返回工作台按钮 |

### 9.6 wsClient 完整实现（D3 + F-P1-1/F-P1-2 定死）

```ts
class WsClient {
  private ws: WebSocket | null = null;
  private convId = '';
  private retry = 0;
  private maxSeq = 0;                          // 去重游标（§7.2）
  private cache = new Map<number, Envelope>(); // 乱序缓存（seq 大于 maxSeq+1 时暂存）
  private lastPongAt = 0;
  private timers: { ping?: number; watchdog?: number } = {};
  private listeners = new Map<WsEventType, ((e: Envelope) => void)[]>();

  on(type: WsEventType, cb: (e: Envelope) => void): void { /* 订阅 */ }
  private emit(env: Envelope): void { /* 分发到 listeners */ }

  async connect(conversationId: string): Promise<void> {
    this.convId = conversationId;
    const { websocket_token } = await api.post('/api/chat/ws-token', { conversation_id: conversationId });
    this.ws = new WebSocket(`${import.meta.env.VITE_WS_BASE}?websocket_token=${websocket_token}&conversation_id=${conversationId}`);
    this.ws.onmessage = (ev) => this.onMessage(ev);
    this.ws.onclose = () => this.scheduleReconnect();
    this.startWatchdog();                      // 60s 无 pong → 断线
  }

  private onMessage(raw: MessageEvent): void {
    const env = JSON.parse(raw.data) as Envelope;
    if (env.type === 'ping') { this.sendPong(); return; }   // 控制通道，不进 seq
    if (env.type === 'pong') { this.lastPongAt = Date.now(); return; }
    if (env.seq <= this.maxSeq) return;        // 去重（重启/重连后 maxSeq 已回填）
    if (env.seq > this.maxSeq + 1) { this.cache.set(env.seq, env); return; } // 乱序暂存
    this.deliver(env);                         // 顺序到达
    while (this.cache.has(this.maxSeq + 1)) {  // 补齐缓存
      const next = this.cache.get(this.maxSeq + 1)!;
      this.cache.delete(this.maxSeq + 1);
      this.deliver(next);
    }
  }
  private deliver(env: Envelope): void { this.maxSeq = env.seq; this.emit(env); }

  private startWatchdog(): void {
    this.lastPongAt = Date.now();
    this.timers.watchdog = setInterval(() => {
      if (Date.now() - this.lastPongAt > 60000) { this.ws?.close(); } // 60s 无 pong 断线
    }, 10000);
  }
  private sendPong(): void { this.ws?.send(JSON.stringify({ v: 1, type: 'pong', conversation_id: this.convId, seq: 0, ts: Date.now() })); }

  private scheduleReconnect(): void {
    if (this.retry >= 5) { toast.error('连接失败，请刷新页面'); return; }
    const delay = Math.min(1000 * 2 ** this.retry, 30000);  // 1→2→4→…→30s
    this.retry++;
    setTimeout(() => this.connect(this.convId), delay);
  }

  async reconnect(): Promise<void> { this.retry = 0; await this.connect(this.convId); }
  cancelTask(taskId: string): void { this.ws?.send(JSON.stringify({ v: 1, type: 'cancel_task', conversation_id: this.convId, task_id: taskId, seq: 0, ts: Date.now() })); }
  close(): void { clearInterval(this.timers.watchdog!); this.ws?.close(); this.ws = null; }
}
```

### 9.7 路由与守卫（D2 + D3 定死）

```ts
const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/auth/callback', component: CallbackView, meta: { public: true } },
  { path: '/chat', component: ChatView, meta: { requiresAuth: true } },
  { path: '/admin', component: AdminView, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/403', component: ForbiddenView, meta: { public: true } },  // D2
  { path: '/:pathMatch(.*)*', component: NotFoundView },
];

router.beforeEach(async (to) => {
  if (to.meta.public) {
    if (to.path === '/login' && isLoggedIn()) return '/chat';  // PRD 7.2
    return true;
  }
  const me = await getMe();                 // GET /api/auth/me
  if (!me) return '/login';                 // 401 → 登录
  if (to.meta.requiresAdmin && me.role !== 'admin') return '/403';  // D2 独立页
  return true;
});
// D3：wsClient 单例挂载于 App.vue；ChatView onMounted→wsStore.connect(currentId)；
//     切到 /admin 时 ChatView 不卸载 wsClient（保活）；切回 /chat 若 convId 变化则 wsStore.connect 重建。
```

### 9.8 全局错误与 Toast（D4 定死）

- `http.ts` 响应拦截：`2xx` 放行；非 `2xx` 读 `ApiError.code`：
  - `AUTH_EXPIRED(401)` → 触发刷新重放（§10.5），**不 Toast**；
  - `FORBIDDEN(403)` → `router.push('/403')`；
  - 其他 → 查 §2.2 映射表 Toast，无匹配则 `INTERNAL_ERROR` 文案。
- `Toast.vue` 全局单例挂载于 `App.vue`，`toast.error/warn/info(msg)` 由 `utils/toast.ts` 暴露。

### 9.9 样式与安全（D1 + F-P2-4）

- **CSS 变量**（`styles/variables.css`）：颜色/间距/圆角统一变量，零 UI 库，手写组件样式。
- **布局**：工作台三栏 `grid-template-columns: 260px 1fr 380px`；管理后台左侧 Tab 导航 + 右侧内容。
- **markdown 渲染（XSS 防护）**：`utils/markdown.ts` 使用 `marked` 解析后过 **DOMPurify**（白名单：p/br/strong/em/code/pre/ul/ol/li/h1-3/table/thead/tbody/tr/th/td/a[href]/blockquote）；`a` 强制 `rel="noopener noreferrer"`、`target="_blank"`。`flag` 关闭 DOMPurify 时退回纯文本（不渲染）。
- **响应式**：工作台窄屏（<1024px）结果区抽屉化；管理后台窄屏 Tab 转为顶部横向滚动。

### 9.10 管理后台 Tab 修正（F-P1-6 定死）

PRD 7.5 写「四 Tab」，但 SDD 上线决策已加 `llm_calls`/`audit_logs` 表。本 Spec **定死为六 Tab**（与上线决策一致，修正 SDD §9.3 笔误）：

1. 系统配置（`ConfigTable` + 重载）
2. 数据源（`DataSourceList` + `DataSourceForm` + 测试连接）
3. 功能开关（`FeatureSwitches`）
4. 运行日志（`LogTable`）
5. **LLM 成本（`LlmCostPanel`）** ← 新增（依据 `llm_calls` 表）
6. **审计日志（`AuditLogTable`）** ← 新增（依据 `audit_logs` 表）

---

## 10. 关键流程伪代码（前端相关）

### 10.1 发送消息全链路（B6 + WS，F-P1-3 乐观渲染）

```
InputBar.send(content, attachmentIds):
  if taskStore.current?.task_status in ('queued','running'): toast.warn('已有分析进行中'); return
  localId = messageStore.appendLocal(content, attachments)   // 乐观占位
  try:
    { message_id, task_id } = await api.post('/api/chat/send',
        { conversation_id: chatStore.currentId, content, attachment_ids: attachmentIds })
    messageStore.bindServerId(localId, message_id)            // 占位转正
    if task_id:
      taskStore.setStatus({ task_id, task_status: 'queued' })
      wsStore.connect(chatStore.currentId)                    // 确保 WS 已连
  catch e:
    if e.code === 'TASK_BUSY': messageStore.markFailed(localId, '已有任务进行中'); taskStore.refresh()
    else: messageStore.rollbackLocal(localId); toast.error(e.message)
```

### 10.2 取消任务

```
InputBar.cancel() / taskStore.cancel():
  taskStore.cancelling = true
  await wsStore.cancelTask(taskStore.current.task_id)   // 优先 WS
  // 兜底：若 2s 内未收到 task_status=cancelled，调 POST /api/tasks/{id}/cancel
```

### 10.3 断线重连恢复（D3，幂等）

```
wsClient.onclose → scheduleReconnect → connect(convId):
  await connect;                       // 取新 token
  // REST 兜底重建 UI（防断线窗口事件丢失）：
  messages = GET /api/chat/ls/{convId}   → messageStore.replaceAll(messages); maxSeq = resp.last_ws_seq
  task     = GET /api/tasks/{currentTaskId} → taskStore.setStatus
  result   = GET /api/results/{currentTaskId} → resultStore.setResult
  // WS 增量续接（seq 去重防重放）
```

### 10.4 路由守卫（§9.7）

```
beforeEach(to):
  if to.public: return (已登录访问 /login → /chat)
  me = GET /api/auth/me
  if !me: return /login
  if to.requiresAdmin && me.role!='admin': return /403   // D2
  return true
```

### 10.5 401 刷新重放（§9.8 + §2.2）

```
http.interceptor.responseError(e):
  if e.status==401 && e.code=='AUTH_EXPIRED' && !e._retried:
    await POST /auth/refresh (refresh Cookie)             // 换新 access
    return http.request(e.config)                          // 重放（仅 1 次）
  if e.status==401 && e.code=='AUTH_INVALID': router.push('/login')
```

### 10.6 附件上传（F-P2-2）

```
AttachmentSidebar.upload(files):
  for f in files:
    attachment = POST /api/attachment/upload (XHR + onprogress → 进度条)
    chatStore.attachments.push(attachment {parse_status:'pending'})
  // 解析状态经 WS 'attachment_parse' 事件更新徽标（§7.4）
```

---

## 11. 部署与初始化（前端部分）

> 完整部署见 SDD §11。本节仅前端相关。

- 构建：`vite build` → `dist/` 静态资源，由 Nginx 托管（内存占用可忽略，2C2G 无压力）。
- Nginx 反代（前端相关路径）：
  - `location /api { proxy_pass http://backend:8000; }`（REST，同源，带 Cookie）
  - `location /ws { proxy_pass http://backend:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; }`（WS 升级）
  - `location /auth { proxy_pass http://auth:8001; }`（认证回调/登出）
  - `location / { root /usr/share/nginx/html; try_files $uri $uri/ /index.html; }`（SPA history 回退）
- 前端配置通过 `VITE_*` 在构建期注入；运行时不改（避免泄露后端内网地址）。

---

## 12. 差异清单（相对完整 SDD §9）

| # | SDD §9 原状 | 本模块 Spec 变更 | 理由 | 章节 |
|---|---|---|---|---|
| 1 | 跨 store 协作仅「wsStore 按 type 分发」一句 | 补 §9.4 完整分发表 + 会话切换清理顺序 | F-P0-1，解决各写各的 | §9.4 |
| 2 | §9.5「否则 403 页」无组件 | 补 §9.7 独立 ForbiddenView + 路由 `/403` | F-P0-2 / D2 / PRD 7.5 | §9.7 |
| 3 | WS 心跳注释「60s 无消息」 | 定死 30s ping / 60s 无 pong 断线 / 退避 1→30s / 5 次停 | F-P1-1 与概要对齐 | §9.6 |
| 4 | seq 重启基线未定 | 定死 maxSeq 初值 = REST `last_ws_seq` 回填 | F-P1-2 | §7.2/§9.6 |
| 5 | 乐观渲染仅签名 | 补 appendLocal/markFailed/rollback 逻辑 + 16ms 合并 | F-P1-3/F-P2-1 | §9.3/§10.1 |
| 6 | 组件 props 缺结构 | 全量补全（含 ToolCard/ResultPanel/ForbiddenView） | F-P1-4 | §9.5 |
| 7 | 全局错误未提 | 补 §9.8 Toast + 错误码映射 | F-P1-5 / D4 | §9.8 |
| 8 | §9.3「管理后台四 Tab」 | 修正为六 Tab（含 LLM 成本/审计） | F-P1-6 与上线决策一致 | §9.10 |
| 9 | UI 库未选型 | 定死纯手写原生 CSS（零 UI 库） | D1 | §9.1/§9.9 |
| 10 | 路由切换 WS 时机未定 | 定死全局单例保活（D3） | F-P2-3 | §9.7 |
| 11 | markdown XSS 未定 | 定死 marked + DOMPurify 白名单 | F-P2-4 | §9.9 |
| 12 | 表单校验未定 | 补 DataSourceForm 校验规则 | F-P2-5 | §9.5 |
| 13 | 附件进度未定 | 补 XHR onprogress 绑定 | F-P2-2 | §9.5/§10.6 |

> 上述变更**回写完整 SDD §9**（版本递增至 v1.1），保持两文档一致（spec 优先约定）。

---

## 13. 待验证风险（前端相关）

| # | 风险 | 等级 | 首个验证点 |
|---|---|---|---|
| 1 | Vue3 + TS 严格模式下 Pinia 跨 store 循环引用（wsStore↔各 store） | 低 | M1 联调 |
| 2 | WebSocket 在 Nginx 反代下的超时/缓冲（大 delta 被分包） | 中 | M3 联调（nginx `proxy_read_timeout` 调大） |
| 3 | DOMPurify 白名单是否覆盖六段式所有合法标签（表格/代码块） | 中 | M3 渲染验收 |
| 4 | 断线窗口内事件仅靠 REST 兜底是否完整（附件解析事件可能丢失） | 中 | M3 联调 |
| 5 | 2C2G 下浏览器端无压力，但 Nginx + backend 同机时 WS 长连接内存占用 | 低 | M5 压测 |
| 6 | `marked` + `DOMPurify` 双依赖体积（约 50KB gzip）是否接受 | 低 | M1 构建核查（如拒依赖可退回自研白名单） |
| 7 | 浏览器兼容：WebSocket / `requestAnimationFrame` / `crypto.randomUUID` | 低 | M1 选型确认（目标现代 Chromium） |

---

## 14. 验收映射（前端部分）

| PRD 验收项 | 对应本 Spec |
|---|---|
| 1. 授权登录入口 → 认证中心 → 回调 | §9.7 路由守卫 + CallbackView |
| 2. 聊天工作台（三栏 + 实时） | §9.5 组件 + §7 WS 协议 |
| 3. 消息发送触发分析 | §10.1 B6 + WS 事件链 |
| 4. 六段式结构化输出 | §6.4 SixSection + §9.5 ResultPanel |
| 5. 附件上传与解析 | §6.3 + §9.5 AttachmentSidebar + §10.6 |
| 6. 管理后台配置/数据源/开关/日志 | §6.6 + §9.5 + §9.10（六 Tab） |
| 7. 实时任务区状态 | §7.4 事件映射 + taskStore |
| 8. 多轮追问上下文 | messageStore 历史 + 后端 summarizer（范围外） |
