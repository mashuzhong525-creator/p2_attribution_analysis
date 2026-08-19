# 经营归因分析系统 需求规格说明书（PRD）

| 项 | 内容 |
|---|---|
| 文档名称 | 经营归因分析系统需求规格说明书（PRD） |
| 版本 | v1.2 |
| 日期 | 2026-08-19 |
| 状态 | 修订稿（v1.2：对照《项目实战》2.1 逐项合规核查；架构/部署/接口/数据模型与实际实现对齐；新增云服务器部署与运维章节；待评审确认） |
| 依据 | 《项目实战要求》2.1 节（经营归因分析系统）+ 需求评审会四轮决策 + 2026-08-19 需求交流（grill-me）确认项 |

## 修订记录

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| v1.0 | 2026-08-16 | 初稿：基于《项目实战》2.1 与需求评审会决策形成 |
| v1.1 | 2026-08-18 | 按 2C2G 资源约束修订规模/性能/部署预算 |
| v1.2 | 2026-08-19 | ① 对照 2.1 逐项合规核查：接口（8.2）、实时消息（8.4）、验收标准（12）补充需求↔实现对照表；② 架构与部署按当前可运行实现对齐：认证中心合并进 backend、四容器编排、前端 8080 对外、backend 仅本机 8001；③ 修正技术栈描述（前端纯手写 CSS，无 UI 组件库）；④ 数据模型修正为 13 张业务表 + 4 张认证表（2.1.7 实际列示 10 张表，v1.1 误写 11 张）；⑤ 新增 11.6 云服务器部署与运维要求（4C4G 轻量云、与 P1 项目共存、端口与内存规划）；⑥ 标注"结果导出/下载"为待完善项（见 15 风险与开放问题） |

---

## 1. 项目概述

### 1.1 背景与目标

企业经营管理中，"指标波动为什么发生、影响有多大、下一步该怎么办"是决策者最高频的问题。传统 BI 只能回答"发生了什么"，归因分析需要分析师手工取数、交叉验证、写报告，周期 1~3 天，错过决策窗口。

本项目目标是构建一个**面向经营分析场景的多轮归因分析系统**：用户围绕一个业务问题持续追问，系统通过 AI Agent 自主规划分析路径、调用数据与文件工具收集证据，生成带证据链的阶段性结论，最终产出六段式结构化分析报告。交付形式为可运行的前端、后端、认证中心、数据库初始化脚本、示例数据、接口说明，以及至少两组完整分析示例；系统须能在 4C4G 轻量云服务器上运行（与 P1 知识库平台共存）。

### 1.2 产品定位

一句话定位：**把"分析师 1~3 天的归因分析"压缩到"一次对话 + 可回溯的证据链"，让决策者快速拿到可执行结论。**

- 核心对象：业务问题（如"华东区 Q2 转化率为什么下降 8%"）
- 核心能力：多轮追问、证据补充、阶段性结论、最终报告
- 核心差异化：证据可回溯（每条结论带来源与置信度）、过程透明（工具执行实时可见）、场景开箱即用（内置示例库与预置演示会话）

### 1.3 项目范围

**In Scope（本版本交付）：**

1. 基础能力：认证登录、会话管理、附件管理、配置热更新、运行日志
2. 分析能力：LLM 驱动的归因 Agent（工具集含数据库查询、文件读写、文本检索、命令执行（默认关闭）、结果文件生成）；未配置 LLM 时提供离线确定性分析兜底（演示开箱即用）
3. 交付能力：聊天工作台、管理后台、结果保存/复制、2 个完整业务场景（商品目录优化、库存异常分析）的示例数据、预置演示会话与演示链路
4. 工程交付：Docker Compose 单机部署（四服务）、数据库初始化脚本、接口说明、部署文档、云服务器部署验证

**Out of Scope（本版本不做）：**

- 多租户隔离（仅单租户 + 用户角色）
- 报表/大屏可视化编辑
- 定时任务 / 主动监控告警（"数据找人"）
- 附件类型超出 csv/xlsx/txt 的解析（如 PDF、图片 OCR）
- 多模型混合路由、模型微调
- 独立部署的认证中心前端页（认证中心已合并进 backend；如需"跳转独立认证中心页面"体验，列为开放问题）

### 1.4 术语表

| 术语 | 定义 |
|---|---|
| 归因分析 | 对指标变化进行原因拆解，量化各因子贡献，输出主因与影响范围的结论 |
| 分析任务（Task） | 一条用户消息对应一次分析执行，有独立状态机（queued/running/success/failed/cancelled） |
| 工具（Tool） | Agent 可调用的原子能力：数据库查询、文件读写、文本检索、命令执行（默认关闭） |
| 证据（Evidence） | 归因结论的支撑材料，含来源类型、来源名、文本、关联指标、置信度 |
| 六段式输出 | 问题定义、关键指标、证据列表、归因结论、待补充数据、下一步建议 |
| 会话（Conversation） | 用户与系统围绕主题的一组连续对话，含消息、附件、任务、结果，绑定数据源 |
| 数据源（DataSource） | 分析引擎可查询的业务库（内置示例库或管理员配置的外部 MySQL 库） |
| OIDC | OpenID Connect；本项目采用自建认证中心（授权码模式，RS256 + JWKS），合并进 backend 运行 |
| 离线确定性分析 | 未配置 LLM 时，对场景库执行预置 SQL 并产出六段式结论的兜底路径 |

---

## 2. 竞品对标

### 2.1 对标对象

| 竞品 | 厂商 | 路线 | 核心能力 |
|---|---|---|---|
| Quick BI 智能小Q | 瓴羊（阿里） | 预设归因树 | NL2Data、因子拆解→交叉归因→结论、报告生成 |
| Smartbi AIChat | 思迈特 | Agent BI | 指标语义底座、智能体+工作流、归因与预测 |
| 帆软 FineBI | 帆软 | 传统 BI+AI | 报表可视化强，AI 问答独立 |
| 观远 Copilot | 观远数据 | 行业 Copilot | 零售/快消场景化 AI 分析 |
| ThoughtSpot | ThoughtSpot | 搜索式分析 | 搜索即分析、SpotIQ 自动洞察 |
| Power BI Copilot | 微软 | Copilot | 微软生态内多轮对话分析 |

### 2.2 对比结论（事实）

- IDC《2025 中国 GenBI 厂商技术能力评估》指出：ChatBI 正演进为 **Agent BI**——大模型分步拆解、自动调用数据源、加工指标，串联 Work Flow 与 Data Flow。
- 技术路线分两派：
  1. **预设归因路径**（瓴羊 Quick BI）：路径固定、可解释，但"只告诉你发生了什么，不告诉你结论是否可信"，扩展性弱；
  2. **自主 Agent 编排**（思迈特 AIChat）：灵活、可处理开放问题，但依赖语义底座建设，纯 LLM 自主结果稳定性弱。
- 共同短板：**过程不透明、证据不可回溯、演示绑定厂商生态**。

### 2.3 本项目差异化定位（判断）

依据需求文档"工具执行 + 六段式输出 + 长连接过程可见"的强信号，本项目采用**混合路线**：

> **Agent 自主规划分析路径 + 六段式结构化输出约束 + 全链路过程透明 + 证据可回溯 + 离线确定性兜底**

| 维度 | 瓴羊 Quick BI | 思迈特 AIChat | 本项目 |
|---|---|---|---|
| 分析路径 | 预设归因树 | Agent 编排 | Agent 自主 + 结构约束 |
| 证据可回溯 | 弱 | 中 | 强（source/confidence 全量记录） |
| 过程透明 | 弱 | 中 | 强（工具执行逐条实时推送） |
| 无 LLM 可用性 | 不可用 | 不可用 | 离线确定性分析兜底（演示开箱即用） |
| 场景演示 | 绑定阿里生态 | 需语义底座建设 | 内置示例库 + 预置演示会话 |
| 部署 | 云/私有化 | 私有化 | Docker Compose 单机（4C4G 与 P1 共存） |

---

## 3. 用户角色与权限

| 角色 | 编码 | 权限范围 |
|---|---|---|
| 分析用户 | `analyst` | 创建/删除/重命名/切换会话；上传/删除/下载附件；发送消息、取消分析；查看历史消息与结果；复制结果（导出/下载待完善） |
| 系统管理员 | `admin` | 分析用户全部权限 + 管理后台：系统配置查看/编辑/重载、数据源连接管理、功能开关启停、运行日志/LLM 成本/审计日志查看 |

权限控制原则：前端路由守卫 + 后端接口鉴权双层校验；管理接口仅 `admin` 角色可访问；用户仅能访问自己的会话/附件/任务/结果（按 `user_id` 隔离）。首次登录强制修改密码（`must_change_password`），改密前无法进入工作台。

---

## 4. 总体架构

### 4.1 架构分层

```
┌──────────────────────────────────────────────────────────────┐
│ 前端（Vue3 SPA，Nginx 托管 + 反代）                             │
│  /login 登录页 /change-password 改密页 / 聊天工作台 /admin 管理后台 │
└──────────────┬───────────────────────────────┬──────────────┘
               │ HTTP(S) 8080                    │ WebSocket /api/ws
┌──────────────▼───────────────────────────────▼──────────────┐
│ 业务后端（FastAPI 单体，容器内 :8000，宿主机仅 127.0.0.1:8001）   │
│  认证中心(OIDC·合并) │ 会话 │ 消息 │ 附件 │ 长连接 │ 任务 │ 分析 │ 结果 │ 配置 │ 数据源 │
└──────┬──────────────┬──────────────┬──────────────┬──────────┘
       │              │              │              │
┌──────▼─────┐  ┌─────▼──────┐  ┌───▼─────────┐  ┌─▼────────────────┐
│ MySQL 8    │  │ Redis 7    │  │ 外部 LLM API │  │ 文件系统（数据卷）  │
│ bia 业务库  │  │ WS seq/限流 │  │ OpenAI 兼容  │  │ uploads/exports/  │
│ +场景示例库 │  │ /锁        │  │ (DeepSeek等) │  │ workspace        │
└────────────┘  └────────────┘  └─────────────┘  └──────────────────┘
```

- **认证中心与业务系统同进程**（合并进 backend 部署）：认证中心相关表（`auth_` 前缀）与业务表同库（`bia`），通过 `POST /api/auth/login → POST /api/auth/token`（授权码模式）完成登录，JWT（RS256）本地 JWKS 验签。此方案满足 2.1"认证中心登录"的功能要求，且与当前可运行实现一致。
- 分析引擎通过 OpenAI 兼容接口调用外部 LLM（DeepSeek/通义/Kimi/OpenAI 任选，配置化）；未配置 API Key 时走**离线确定性分析**（对场景库执行预置 SQL，产出六段式结果）。
- 示例库与业务库同 MySQL 实例多库：`bia`（业务库）、`scenario_goods`（商品目录优化示例）、`scenario_inventory`（库存异常分析示例）。

### 4.2 技术栈（评审决策，以实际实现为准）

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3 + Vite + Pinia + Vue Router，**纯手写 CSS（无 UI 组件库）** | 轻量、无第三方 UI 依赖，构建产物由 Nginx 托管 |
| 后端 | Python FastAPI + SQLAlchemy 2.0（asyncmy 异步）+ Pydantic v2 | LLM/Agent 生态成熟；异步支持 WebSocket；单体承载业务 API + WS + OIDC |
| 数据库 | MySQL 8.0（业务库 `bia` + 示例库 `scenario_goods`/`scenario_inventory`） | 初始化脚本 + 示例数据交付成熟 |
| 缓存 | Redis 7 | WS 会话级 seq（去重/排序）、限流、锁 |
| 认证 | 自建 OIDC 认证中心（授权码模式，RS256 + JWKS），**合并进 backend** | 登录表单→一次性授权码→换 JWT；HttpOnly Cookie 会话 |
| LLM | OpenAI 兼容 API（可配置 base_url/api_key/model） | 国内可用 DeepSeek/通义/Kimi；未配置时离线确定性分析兜底 |
| 部署 | Docker Compose 单机（mysql + redis + backend + frontend，命名空间 `bia`） | 4C4G 云服务器与 P1 共存，本项目按 2C2G 预算；前端 8080 对外 |

### 4.3 部署拓扑（4C4G 轻量云服务器，与 P1 共存）

- 云服务器：**轻量级 4C4G**；P1（知识库平台）与 P2（本项目）共存，P2 按 **2C2G 预算** 规划（docker-compose 已按此收敛）。
- 端口规划（避免与 P1 冲突）：

| 服务 | 宿主机监听 | 说明 |
|---|---|---|
| `frontend`（Nginx） | `0.0.0.0:8080` | 唯一公网入口；反代 `/api`、`/api/ws`、`/.well-known/jwks.json` 到 backend |
| `backend`（FastAPI） | `127.0.0.1:8001 → 容器 8000` | 仅本机回环，公网不可达（避开 P1 占用的 8000） |
| `mysql` | `127.0.0.1:3306` | 仅本机回环 |
| `redis` | `127.0.0.1:6379` | 仅本机回环 |
| P1 知识库平台 | `8000`（或 443 via Caddy） | 与 P2 无端口冲突 |

- 容器内存配额（docker-compose `deploy.resources.limits.memory`）：

| 容器 | 内存配额 | 关键调优 |
|---|---|---|
| `mysql` | 768M | `innodb_buffer_pool_size=256M`、`performance_schema=OFF`、`max_connections` 收敛 |
| `backend` | 768M | uvicorn 单 worker；LLM 流式逐块转发；`db_query` 结果行数上限；并发任务 ≤3 |
| `redis` | 128M | 仅存 WS seq/锁/计数类轻量状态 |
| `frontend`(nginx) | 64M | 静态资源 + 反代，无业务内存 |

- 首次启动自动执行（entrypoint）：等待 MySQL 就绪 → `alembic upgrade head`（建 17 张表）→ 基线种子（配置/认证用户/客户端/业务用户/数据源）→ 生成两个场景示例库数据 → 生成两组预置演示会话 → 启动 uvicorn。

---

## 5. 核心业务流程

### 5.1 端到端主流程

```
打开登录页（账号密码）→ POST /api/auth/login 校验 → 签发一次性授权码
  → POST /api/auth/token 换 JWT（HttpOnly Cookie）→ 进入聊天工作台
  →（首次登录先强制改密）→ 新建会话（选择数据源，默认示例库）
  →（可选）上传附件 → 输入业务问题 → POST /api/chat/send
  → 创建分析任务（queued）→ WS 推送 message_start
  → Agent 循环执行（在线 LLM 或离线确定性路径；tool_start/tool_end 实时推送）
  → 生成六段式结果（result_ready）→ 任务 success（task_status）
  → 结果展示区渲染 + Markdown 落库
  → 用户可继续追问（携带上下文摘要）或复制/导出（导出待完善）结果
```

### 5.2 单轮分析内部流程

```
输入：用户问题 + 会话上下文摘要 + 附件元信息 + 可用工具清单 + 绑定数据源 schema
路径 A（在线，配置了 LLM API Key）：
 1. 问题理解与任务规划：LLM 拆解问题，产出分析计划
 2. 循环执行（上限 agent_max_steps=8 步、总时长 agent_timeout_sec=600s，均可配置）：
     - LLM 决策下一步工具调用（function calling）
     - 执行工具（db_query / file_read / file_write / text_search / command_exec），推送 tool_start/tool_end
     - 观察结果，更新中间结论；证据不足时输出"待补充数据"并建议追问
 3. 结论生成：LLM 依据全部证据按六段式模板输出结构化结果
 4. 落库与文件生成：analysis_results 落库 + 生成 Markdown（result_markdown）
 5. 上下文摘要压缩：对本轮消息+结果做摘要，写入 context_summaries
路径 B（离线兜底，未配置 LLM）：
 - 按会话绑定数据源路由到确定性分析器（scenario_goods→商品归因 / scenario_inventory→库存归因）
 - 先做"语义半径"判断：问题不在场景库覆盖维度内时，如实返回"超出离线分析半径"六段式（无指标/无证据），
   并提示配置 LLM 或切换数据源；否则执行预置 SQL 链（含工具事件回放），产出与在线一致的六段式结果
```

约束（防失控）：

- 单轮工具调用 ≤ 8 步（`agent_max_steps` 可调）；单轮总时长 ≤ 600s（可调），超时任务置 `failed` 并推送 `error`
- 同一会话同一时间仅允许 1 个 queued/running 任务（服务端互斥校验，冲突返回 `TASK_BUSY`）
- 任务队列上限 10（`TASK_QUEUE_FULL`），同时运行任务 ≤ 3（Semaphore），取消支持 queued 与 running 两种状态
- 工具调用前做参数校验；`command_exec` 默认关闭（云上安全），开启后限工作区沙箱 + 命令白名单

### 5.3 多轮追问与上下文管理

- 追问输入 = 用户新消息 + 最近消息 + `context_summaries` 摘要（start_seq_no ~ end_seq_no 区间）
- 每轮结束后生成摘要（问题、结论、已用证据、未决问题），压缩存储，避免上下文无限膨胀
- 历史消息按 `seq_no` 严格排序（会话内唯一），重放时保持顺序
- 删除会话软删除（status=deleted + deleted_at），级联清理消息/附件/任务/结果/摘要/ws 令牌（应用层实现）

---

## 6. 功能需求

### 6.1 认证模块（自建 OIDC 认证中心，合并进 backend）

| 功能 | 说明 |
|---|---|
| 登录 | `POST /api/auth/login`（用户名+密码）：校验 `auth_users` 凭证 → 签发一次性授权码（10 分钟有效）→ 返回 code 与 must_change_password |
| 换令牌 | `POST /api/auth/token`：授权码换 RS256 access_token（JWT，15 分钟）+ refresh_token（30 天，轮换制），写入 HttpOnly Cookie（prod 下 Secure） |
| 刷新 | `POST /api/auth/refresh`：refresh_token 轮换（旧 token 作废） |
| 当前用户 | `GET /api/auth/me`：返回 id/username/display_name/role/must_change_password |
| 首次改密 | `POST /api/auth/change-password`：新密码 ≥8 位且不能与原密码相同；成功后清除 must_change_password 并吊销该用户全部 refresh_token |
| 退出 | `POST /api/auth/logout`：清除 Cookie |
| 登录保护 | 登录失败阈值 `security_max_login_fail=5`（超限锁定，可配置）；未登录/过期分别返回 AUTH_REQUIRED/AUTH_EXPIRED，前端跳登录页 |
| JWKS | `GET /.well-known/jwks.json`、`GET /api/auth/jwks`、`GET /api/auth/userinfo`：OIDC 发现与用户信息端点（本地验签，无需外部拉取） |
| 用户同步 | 种子脚本创建默认管理员（admin/admin123）与分析用户（analyst/analyst123）；业务库 `users` 与认证库 `auth_users` 通过 external_user_id 关联（业务用户由 seed 预置） |

合规说明：2.1 要求"授权登录入口页展示登录按钮，点击后跳转认证中心完成授权登录"。本实现将认证中心合并进 backend，登录入口页直接以表单完成认证中心登录（认证中心功能等价，验收目标"通过授权登录进入聊天工作台"达成）；如需严格"跳转独立认证中心页面"的交互形态，列为开放问题（15.2）。

### 6.2 会话模块

| 功能 | 说明 |
|---|---|
| 新建 | `POST /api/chat/create`（title 可为空，默认"新会话"；data_source_id 可选，默认绑定第一个启用数据源） |
| 列表 | `GET /api/chat/ls`：按 last_message_at 倒序，分页（page/page_size，page_size ≤100） |
| 重命名 | `POST /api/chat/update` |
| 删除 | `POST /api/chat/delete`（支持批量 conversation_ids）：软删除（status=deleted + deleted_at），级联清理消息/附件/任务/结果/摘要/ws 令牌记录 |
| 切换 | 前端本地切换 + 拉取 `GET /api/chat/ls/{conversation_id}` 历史消息 |
| 状态机 | `active` → `deleted`（软删除标记）；`archived` 为预留状态（本版本未启用归档入口，状态字段保留） |
| 数据源绑定 | 会话创建时绑定数据源，后续分析按会话数据源路由 |

### 6.3 聊天模块

| 功能 | 说明 |
|---|---|
| 消息发送 | `POST /api/chat/send`（conversation_id、content、attachment_ids 可选）：互斥校验 → 用户消息落库（seq_no=MAX+1）→ 关联附件 → 创建任务（queued）→ 入队，返回 message_id/task_id/queue_position |
| 流式渲染 | WS 接收 message_delta（30 字/块）增量渲染；tool_start/tool_end 渲染工具卡片（工具名/参数摘要/状态/耗时/结果摘要） |
| 取消分析 | `POST /api/tasks/{task_id}/cancel`：queued 直接置 cancelled；running 取消引擎协程，推送 cancelled 事件 |
| 历史回放 | 进入会话加载 messages（role/message_type/content/task_id/seq_no/created_at），按 seq_no 顺序渲染 |
| 消息落库 | 用户问题（text）与最终结果（result，content=结论文本）落库；过程流式文本与工具事件仅经 WS 实时推送（工具明细记录于 task_logs），历史重放以落库消息为准 |
| 一条消息一个任务 | 用户消息创建分析任务，任务与消息一一对应（message.task_id 关联） |

### 6.4 附件模块

| 功能 | 说明 |
|---|---|
| 支持格式 | csv、xlsx、txt（评审决策；暂不支持 PDF/图片） |
| 上传 | `POST /api/attachments/upload`（multipart）：存 `uploads/{user_id}/{conversation_id}/`，记录 attachments，异步解析 |
| 解析 | 异步任务：读取文件 → 结构抽取（表头/行列/摘要）→ 解析状态流转 `pending → parsing → parsed / failed`；解析结果（parse_result_json）供分析引擎文本检索与 system prompt 注入 |
| 元信息 | 文件名、文件类型（MIME + 扩展名）、文件大小、上传时间、解析状态（2.1.3 附件侧栏字段全部覆盖） |
| 列表/删除/下载 | `GET /api/attachments/list`、`DELETE /api/attachments/{id}`（删记录 + 物理文件）、`GET /api/attachments/{id}/download`（鉴权 + 路径校验后流式返回） |
| 安全 | 路径规范化白名单校验（防目录穿越）；大小上限 20MB（`attachment_max_size_mb` 可调）；类型白名单 |

### 6.5 实时任务模块（WebSocket）

| 功能 | 说明 |
|---|---|
| 连接建立 | `WS /api/ws?token=xxx&conversation_id=yyy`；token 由 `POST /api/chat/ws-token` 签发（一次性、TTL 默认 300s、会话绑定） |
| 鉴权 | 连接时校验 token 未消费、未过期、会话归属当前用户，成功后标记 consumed |
| 统一信封 | `{v:1, type, conversation_id, task_id, ts, payload, seq?}`；业务事件带 seq（Redis per-conversation 单调递增），控制消息（ping）不带 |
| 心跳 | 服务端每 30s 发 ping，客户端回 pong；客户端 60s 无消息判定异常主动重连（指数退避，重连前刷新一次性 token，并用 REST 拉历史补偿） |
| 乱序处理 | 客户端按 seq 去重/排序（缓存 2s 乱序窗口），断线重连不丢事件 |
| 会话级互斥 | 任务创建时校验会话无 queued/running 任务，冲突返回 TASK_BUSY |
| 并发 | 单用户可开多个会话连接；连接数 ≤ `ws_max_connections`(10)，同时运行任务 ≤3 |

### 6.6 分析引擎

#### 6.6.1 工具集（Tool Registry）

| 工具 | 能力 | 安全约束 |
|---|---|---|
| `db_query` | 对目标数据源（示例库/外部源）执行 SQL | 仅 SELECT；结果行数上限；超时限制；外部数据源默认关闭（`FLAG_EXTERNAL_DS=false`） |
| `file_read` | 读取会话工作区内文件（附件/中间文件） | 路径校验限 `workspace/{user_id}/{conversation_id}/` |
| `file_write` | 写中间结果文件 | 同上目录内 |
| `text_search` | 附件/工作区文本全文检索（关键词 + 片段返回） | 检索范围限当前会话 |
| `command_exec` | 在会话工作区沙箱内执行命令（如 python 数据分析脚本） | **默认关闭**（`flag_tool_command_exec=false`，云上安全）；开启后仅限工作区 cwd、命令/参数白名单、超时强制终止 |

> 说明：工具默认开关 `flag_tool_db_query/file_read/file_write/text_search=true`、`flag_tool_command_exec=false`，运行时可在系统配置/环境变量覆盖。`result_generate` 暂未注册为 Agent 工具，结果文件以 `result_markdown` 落库（导出接口待完善，见 6.7/15）。

#### 6.6.2 Agent 循环

- 在线路径：OpenAI 兼容 Chat Completions + 工具调用（function calling）实现；系统提示词内置业务场景说明、数据源 schema 提示、工具清单与约束、六段式输出模板
- 循环收敛条件：LLM 判定证据充分 → 直接输出六段式 JSON
- 兜底：达到步骤上限或超时 → 基于已有证据尽力输出部分结果 + 明确标注"待补充数据"
- 离线路径：确定性分析器（`analyze_goods` / `analyze_inventory`）对场景库执行预置 SQL 链，产出与在线一致的六段式结构与工具事件回放；"语义半径"之外的问题如实返回不可答结论

#### 6.6.3 六段式输出（结构化结果，对齐 2.1.11）

| 段 | 字段 | 说明 |
|---|---|---|
| 问题定义 | `problem_definition` | 当前分析要回答的业务问题 |
| 关键指标 | `key_metrics`（数组） | 每项：metric_name、metric_value、metric_unit、metric_period |
| 证据列表 | `evidence_list`（数组） | 每项：source_type、source_name、evidence_text、related_metric、confidence |
| 归因结论 | `conclusion_text` | 自然语言：主要原因 + 影响范围 |
| 待补充数据 | `missing_data_text` | 缺失数据项清单 |
| 下一步建议 | `next_action_text` | ≥2 条建议动作 |

#### 6.6.4 安全边界（评审决策：工作区沙箱 + 白名单）

- 命令执行：默认关闭；开启后 cwd 固定为会话工作区，参数注入校验 + 命令黑名单 + 超时强制终止
- 数据库：默认只读；外部数据源由管理员配置只读账号，默认关闭
- 文件：所有路径经规范化校验，禁止 `..` 逃逸与绝对路径越界
- LLM 输出：SQL/命令先经规则校验再执行，非法输入拒绝并记录日志

### 6.7 结果模块

| 功能 | 说明 |
|---|---|
| 结构化展示 | 结果展示区六段式渲染：问题定义、指标卡片、证据列表（来源+置信度徽标）、结论、待补充、建议；运行中六段渐进点亮 |
| 复制 | 一键复制全文 Markdown（result_markdown）到剪贴板 |
| 落库 | analysis_results 六段式 + result_markdown 落库；`GET /api/results/{task_id}` 返回结构化结果 |
| 导出/下载 | **待完善**：前端导出按钮当前为禁用态（"导出功能开发中"）；结果文件目录规范 `exports/{user_id}/{conversation_id}/` 已在配置中预留。该项对应 2.1.13 验收第 6 条，列为 v1.2 开放问题（15.1） |

### 6.8 管理后台模块（/admin 页）

| 功能组 | 说明 |
|---|---|
| 系统配置 | 查看/编辑 `system_configs`（LLM base_url/api_key/model、任务步数上限、超时、附件上限等）；保存后重载即时生效 |
| 数据源管理 | 查看/新增/编辑/删除外部数据源（MySQL 连接串、只读账号、启用/停用）；测试连接；内置示例库为预置数据源 |
| 功能开关 | 启停功能：场景数据、附件、外部数据源、命令执行、结果生成、WS 心跳等 |
| 运行日志 | `GET /api/admin/logs`：task_logs 级别过滤、任务关联、分页；`GET /api/admin/llm-costs`（LLM 调用成本）；`GET /api/admin/audit-logs`（审计记录） |

### 6.9 配置与日志模块

| 功能 | 说明 |
|---|---|
| 配置读取/更新 | `GET /api/admin/config`（按 config_group 分组）、`POST /api/admin/config`（批量更新） |
| 配置热更新 | `POST /api/admin/reload`：从 MySQL 重载 system_configs 到内存缓存（ConfigCache），全量即时生效 |
| 默认配置 | 初始化脚本写入默认值（LLM、安全限额、功能开关）；环境变量可覆盖 |
| 日志 | 结构化日志（task_id 关联）；task_logs 落库 + 容器 stdout；级别 DEBUG/INFO/WARN/ERROR |
| 审计 | 管理员配置/数据源/开关变更记录 audit_logs（只增不改） |

### 6.10 数据源模块

- 数据源登记于 `data_sources` 表：名称、类型（当前支持 MySQL）、host/port/database/账号、AES 加密密码（`APP_ENCRYPTION_KEY`）、只读标记、启用标记
- 内置示例库（scenario_goods、scenario_inventory）由种子脚本预置为启用数据源；`FLAG_EXTERNAL_DS=false` 时外部数据源不可用，演示以内置示例库为主
- 会话创建时可选择数据源；不选默认绑定第一个启用数据源

---

## 7. 页面需求

### 7.1 页面清单与路由

| 页面 | 路由 | 角色 | 说明 |
|---|---|---|---|
| 授权登录页 | `/login` | 匿名 | 账号密码表单 + 登录按钮（认证中心合并部署，直接完成认证登录） |
| 首次改密页 | `/change-password` | 需改密用户 | 首次登录强制进入；未改密前无法访问其他页面 |
| 聊天工作台页 | `/` | analyst/admin | 三栏布局（会话列表/对话区/结果区）+ 附件侧栏 + 实时任务区 |
| 管理后台页 | `/admin` | admin | 系统配置/数据源/功能开关/日志（含 LLM 成本、审计） |
| 403/404 | `/403`、`/404` | 全部 | 权限不足/页面不存在兜底 |

路由守卫：未登录跳 `/login?redirect=`；admin 页面非 admin 跳 403；must_change_password=true 时仅放行改密页。

### 7.2 授权登录页

- 展示系统名称、简要说明、账号密码登录表单（2.1.3"授权登录入口"的功能等价实现）
- 登录成功进入工作台；失败展示错误信息（含账号锁定提示）
- 已登录用户访问自动跳转工作台

### 7.3 首次登录改密页

- 输入原密码 + 新密码（≥8 位）两次确认；成功后清除标记并进入工作台
- 该页为独立路由，未改密前路由守卫强制拦截

### 7.4 聊天工作台页

**布局：**

```
┌──────────┬──────────────────────────┬────────────────────┐
│ 会话列表  │ 对话区                    │ 结果展示区          │
│ (左栏)   │  消息流（流式渲染/工具卡片）│  六段式结果 + 复制/导出 │
│          │  附件侧栏（对话区上方折叠） │  实时任务区(状态条)   │
│          │  底部输入框 + 取消按钮     │                    │
└──────────┴──────────────────────────┴────────────────────┘
```

| 区域 | 需求要点 |
|---|---|
| 会话列表 | 新建按钮（可带数据源选择）；列表项（标题/时间）；选中态；重命名、删除 |
| 对话区 | 气泡消息：用户问题、助手结论（result 消息）按序渲染；运行中流式文本实时追加；工具卡片（工具名/参数/状态/耗时/摘要） |
| 附件侧栏 | 当前会话附件列表：文件名/类型/大小/上传时间/解析状态徽标（2.1.3 字段全覆盖）；上传（拖拽+选择，进度）、删除、下载 |
| 实时任务区 | 当前轮状态（queued/running/success/failed/cancelled）、当前步骤（问题拆解/数据查询/交叉归因/结论生成/落库导出五段状态条）、错误信息、工具执行过程 |
| 结果展示区 | 六段式渲染（问题定义/关键指标/证据列表/归因结论/待补充数据/下一步建议）；复制按钮；导出按钮（待完善，当前禁用）；空态引导 |
| 输入区 | 文本域（Enter 发送 / Shift+Enter 换行）、发送按钮、取消按钮（任务运行中显示）、附件上传入口 |

### 7.5 管理后台页

- Tab：**系统配置**（配置表 + 编辑 + 重载）、**数据源**（列表 + 新增/编辑弹窗 + 测试连接）、**功能开关**（开关列表 + 即时生效）、**运行日志**（过滤 + 分页 + 详情）；支持 LLM 成本与审计日志查看
- 顶部显示当前管理员信息与退出登录；仅 admin 角色可访问，非 admin 跳 403

### 7.6 异常页

- 403：权限不足；404：页面不存在；登录态过期统一跳转登录页（前端监听 auth:expired 事件）

---

## 8. 接口需求

> 说明：2.1.9 规定的接口路径与本实现存在少量等价差异（如附件接口单复数、WS 路径），功能一一对应。下表以"实际实现"为主列，并给出 2.1.9 对照；如需严格按 2.1.9 路径验收，可增加兼容别名路由（开放问题 15.2）。

### 8.1 认证接口

| 方法/路径 | 说明 | 关键字段 |
|---|---|---|
| `POST /api/auth/login` | 账号密码登录（等价 2.1.9 的 /auth/login 跳转能力） | 入参 username/password；响应 code、must_change_password |
| `POST /api/auth/token` | 授权码换令牌（等价 /auth/callback 的换令牌能力） | 入参 grant_type=authorization_code、code；响应 access_token、refresh_token、expires_in |
| `POST /api/auth/refresh` | 刷新令牌（轮换） | 入参 refresh_token；响应 access_token、refresh_token |
| `GET /api/auth/me` | 当前用户信息 | username、display_name、role、must_change_password |
| `POST /api/auth/change-password` | 首次登录改密 | 入参 old_password、new_password |
| `POST /api/auth/logout` | 退出登录 | — |
| `GET /.well-known/jwks.json` / `GET /api/auth/jwks` | JWKS 发现 | — |
| `GET /api/auth/userinfo` | 用户信息端点 | sub、username、display_name、role |

### 8.2 业务接口（实际实现 + 2.1.9 对照）

| 方法/路径 | 请求字段 | 响应字段 | 2.1.9 对照 |
|---|---|---|---|
| `POST /api/chat/create` | title、data_source_id | conversation_id、title、status、data_source_id | ✓ 一致 |
| `POST /api/chat/delete` | conversation_ids | status、message、deleted_ids | ✓ 一致 |
| `POST /api/chat/update` | conversation_id、title | conversation_id、title、status | ✓ 一致 |
| `GET /api/chat/ls` | page、page_size | items（conversation_id、title、status、last_message_at）、total | ✓ 一致（增加分页） |
| `GET /api/chat/ls/{conversation_id}` | — | conversation_id、items（message_id、task_id、role、message_type、content、seq_no、created_at） | ✓ 一致 |
| `POST /api/chat/send` | conversation_id、content、attachment_ids | message_id、task_id、queue_position | 新增（2.1.9 未列，消息发送入口） |
| `POST /api/chat/ws-token` | conversation_id | websocket_token、expires_in | ✓ 一致 |
| `POST /api/attachments/upload` | conversation_id + 文件（multipart） | attachment_id、file_name、file_path | 等价 `POST /api/attachment/upload` |
| `DELETE /api/attachments/{attachment_id}` | — | status、message | 等价 `POST /api/attachment/delete` |
| `GET /api/attachments/{attachment_id}` | — | attachment_id、file_name、file_type、file_size、parse_status、created_at | 等价 `GET /api/attachment/get` |
| `GET /api/attachments/list` | conversation_id | 附件数组 | 补充 |
| `GET /api/attachments/{attachment_id}/download` | — | 文件流 | 补充 |
| `WS /api/ws` | 连接参数 token、conversation_id | 实时消息（见 8.4） | 等价 `WS /api/chat/ws/chat` |
| `POST /api/tasks/{task_id}/cancel` | — | task_status、message | 补充 |
| `GET /api/tasks/{task_id}` | — | task_status、current_step、queue_position、started_at、finished_at、error_message | ✓ 一致 |
| `GET /api/results/{task_id}` | — | result_id、problem_definition、key_metrics、evidence_list、conclusion_text、missing_data_text、next_action_text、result_markdown | ✓ 一致 |

### 8.3 管理接口

| 方法/路径 | 说明 |
|---|---|
| `GET /api/admin/config` | 系统配置列表（按 config_group 分组） |
| `POST /api/admin/config` | 更新配置（批量） |
| `POST /api/admin/reload` | 重载配置，响应 status、message |
| `GET /api/admin/datasources` | 数据源列表 |
| `POST /api/admin/datasources` | 新增数据源 |
| `PUT /api/admin/datasources/{ds_id}` | 更新数据源 |
| `DELETE /api/admin/datasources/{ds_id}` | 删除数据源 |
| `POST /api/admin/datasources/test` | 测试连接 |
| `GET /api/admin/logs` | 运行日志（过滤：level/type/task_id，分页） |
| `GET /api/admin/llm-costs` | LLM 调用成本统计 |
| `GET /api/admin/audit-logs` | 审计日志 |

### 8.4 实时消息类型（实际实现 + 2.1.10 对照）

**出站（服务端 → 客户端）：**

| 类型 | 必含字段 | 说明 | 2.1.10 对照 |
|---|---|---|---|
| `message_start` | task_id | 本轮分析开始 | ✓ 一致 |
| `message_delta` | task_id、delta_text | 模型增量文本（30 字/块） | ✓ 一致 |
| `tool_start` | task_id、name、args | 工具开始执行 | ✓ 一致 |
| `tool_end` | task_id、name、success、summary/error | 工具执行完成（含结果摘要） | 等价 `tool_finish`（含 tool_result_summary） |
| `task_status` | task_id、task_status、current_step | 任务状态变化（queued/running/success/failed/cancelled） | ✓ 一致 |
| `result_ready` | task_id、result（六段式） | 结构化结果已生成 | ✓ 一致 |
| `error` | task_id、message | 本轮分析失败 | ✓ 一致 |
| `cancelled` | task_id | 用户取消 | 等价 `done`（本轮结束；结束时间可从任务接口获取） |
| `ping` | ts | 心跳（服务端每 30s） | 补充 |

**入站（客户端 → 服务端）：**

| 类型 | 必含字段 | 说明 |
|---|---|---|
| `pong` | — | 心跳响应 |

> 说明：所有业务事件统一信封 `{v:1, type, conversation_id, task_id, ts, payload, seq}`；seq 单调递增用于去重与排序。2.1.10 的 8 种消息类型在本实现中均有等价表达。

### 8.5 错误码规范

| 码 | 含义 | HTTP |
|---|---|---|
| `AUTH_REQUIRED` | 未登录 | 401 |
| `AUTH_EXPIRED` | 登录态过期 | 401 |
| `PASSWORD_CHANGE_REQUIRED` | 首次登录需先修改密码 | 403 |
| `FORBIDDEN` | 无权限 | 403 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `VALIDATION_ERROR` | 参数校验失败 | 422 |
| `TASK_BUSY` | 会话已有运行中任务 | 409 |
| `TASK_NOT_CANCELLABLE` | 终态任务不可取消 | 409 |
| `TASK_QUEUE_FULL` | 任务队列已满 | 429 |
| `RATE_LIMITED` | 接口限流 | 429 |
| `FILE_TYPE_NOT_ALLOWED` | 附件类型不允许 | 400 |
| `FILE_TOO_LARGE` | 附件超限 | 400 |
| `FILE_PARSE_FAILED` | 附件解析失败 | 400 |
| `DATA_SOURCE_UNAVAILABLE` | 数据源不可用 | 400 |
| `CONFIG_RELOAD_FAILED` | 配置重载失败 | 500 |
| `INTERNAL_ERROR` | 服务器内部错误 | 500 |

统一响应结构：`{code, message, detail}`。

---

## 9. 数据模型

### 9.0 数据模型设计决策（评审决策，2026-08-18 深化评审）

> 字段级定义见独立文档 `docs/design/数据模型设计.md`。

| # | 决策项 | 决策 | 影响 |
|---|---|---|---|
| 1 | 主键策略 | 全表 **UUIDv7**（VARCHAR(32) 无横线，时间有序、防枚举） | 所有表主键、初始化脚本、示例数据 |
| 2 | 关联约束 | **逻辑外键 + 复合索引**（应用层保证一致性） | 级联删除在应用层实现（6.2） |
| 3 | 删除语义 | **软删除**（deleted_at/status=deleted 标记）+ 后续定时物理清理（保留期可配置，默认 90 天） | conversations/messages/attachments |
| 4 | 审计追踪 | `audit_logs`（谁/何时/改了什么/前后值），只增不改、永久保留 | 管理后台写操作留痕 |
| 5 | LLM 成本 | `llm_calls` 每次 LLM 请求一行（模型/token/耗时/费用/任务关联） | 成本可精确到单步调用 |
| 6 | 附件解析 | `attachments.parse_result_json`（表头/行列/摘要） | text_search 检索该字段 + 工作区文本 |
| 7 | 结果存储 | `analysis_results` 的 key_metrics/evidence_list 保持 JSON 列 + result_markdown | 展示/复制直接读整行 |
| 8 | 时间口径 | 全库 **UTC + DATETIME**（应用层转本地展示） | 所有时间字段与接口序列化 |
| 9 | 配置类型 | `system_configs.config_type`（bool/int/float/string/json）+ description | 校验 + 管理后台控件自动匹配 |
| 10 | 登录追踪 | `users.last_login_at` | 登录/刷新令牌时更新 |
| 11 | 日志保留 | `task_logs` 保留 90 天、`llm_calls` 保留 180 天，超期随定时任务清理 | 与软删清理同一调度 |
| 12 | 示例数据 | 示例库保留 + 功能开关 `flag_scenario_data`（可关场景 schema 注入） | 验收开箱即用，上线可关 |
| 13 | 迁移策略 | **Alembic 版本化迁移**（0001_initial / 0002_message_task_id / 0003_auth_must_change_password） | 上线后加表/加列走 alembic upgrade |
| 14 | 认证表归属 | 认证中心 4 张表（auth_ 前缀）与业务表**同库（bia）独立表域**（v1.2 对齐实现：非独立 schema） | 单库单连接，运维简单 |

### 9.1 业务库表（2.1.7 全部 10 张 + 新增 3 张 = 13 张）

> 约定：PK 均为 UUIDv7（VARCHAR(32) 无横线）；时间一律 DATETIME（UTC）；软删表含 deleted_at；逻辑外键列一律建索引。v1.2 修正：2.1.7 实际列示 10 张表（v1.1 误写 11 张）。

**文档规定的表（字段严格对齐 2.1.7）：**

| 表 | 关键字段（类型） | 索引/约束 | 说明 |
|---|---|---|---|
| `users` | id PK；external_user_id VARCHAR(64)；username VARCHAR(64)；display_name VARCHAR(64)；role VARCHAR(16)；status VARCHAR(16)；last_login_at DATETIME；created_at/updated_at | UK: external_user_id、username | 业务用户；与认证中心 upsert 同步 |
| `conversations` | id PK；user_id；data_source_id（可空）；title VARCHAR(128)；status VARCHAR(16)；last_message_at DATETIME；deleted_at；created_at/updated_at | IDX(user_id, last_message_at)；IDX(data_source_id) | status: active/deleted（archived 预留）；会话绑定数据源 |
| `messages` | id PK；conversation_id；task_id（可空）；role VARCHAR(16)；message_type VARCHAR(16)；content TEXT；tool_name/tool_status（预留）；seq_no INT；created_at；deleted_at | UK(conversation_id, seq_no)；IDX(conversation_id, created_at)；IDX(task_id) | seq_no 会话内递增；message_type: text/result |
| `attachments` | id PK；conversation_id；message_id（可空）；file_name VARCHAR(255)；file_path VARCHAR(512)；file_type VARCHAR(32)；file_size BIGINT；parse_status VARCHAR(16)；parse_result_json JSON；created_at；deleted_at | IDX(conversation_id) | parse_status: pending/parsing/parsed/failed |
| `analysis_tasks` | id PK；conversation_id；user_id；input_text TEXT；task_status VARCHAR(16)；current_step INT；started_at/finished_at DATETIME；error_message TEXT；created_at | IDX(conversation_id, task_status) | task_status: queued/running/success/failed/cancelled |
| `analysis_results` | id PK；task_id；conversation_id；problem_definition TEXT；key_metrics_json JSON；evidence_list_json JSON；conclusion_text TEXT；missing_data_text TEXT；next_action_text TEXT；result_markdown TEXT；result_file_path VARCHAR(512)；created_at | UK(task_id)；IDX(conversation_id) | 六段式落库 + Markdown 副本 |
| `context_summaries` | id PK；conversation_id；start_seq_no/end_seq_no INT；summary_text TEXT；created_at | IDX(conversation_id, end_seq_no) | 上下文摘要（5.3） |
| `websocket_tokens` | id PK；user_id；conversation_id；token VARCHAR(64)；expires_at DATETIME；consumed_at DATETIME；created_at | UK(token)；IDX(user_id, conversation_id) | 一次性 WS 令牌 |
| `system_configs` | id PK；config_key VARCHAR(64)；config_value TEXT；config_type VARCHAR(16)；config_group VARCHAR(32)；description VARCHAR(255)；updated_at | UK(config_key) | 配置热更新来源 |
| `task_logs` | id PK；task_id；log_level VARCHAR(8)；log_type VARCHAR(32)；log_content TEXT；created_at | IDX(task_id, created_at) | 任务日志；保留 90 天 |

**新增业务表（v1.2 对齐实现）：**

| 表 | 关键字段（类型） | 索引/约束 | 说明 |
|---|---|---|---|
| `data_sources` | id PK；name VARCHAR(64)；db_type VARCHAR(16)；host VARCHAR(128)；port INT；database VARCHAR(64)；username VARCHAR(64)；password_encrypted VARCHAR(512)；is_readonly TINYINT；is_enabled TINYINT；created_at/updated_at | UK(name) | 数据源连接；内置示例库预置为启用状态；密码 AES 加密 |
| `audit_logs` | id PK；user_id；action_type VARCHAR(32)；target_type VARCHAR(32)；target_id VARCHAR(64)；before_value JSON；after_value JSON；ip VARCHAR(64)；user_agent VARCHAR(255)；created_at | IDX(user_id, created_at)；IDX(target_type, target_id) | 管理操作审计；只增不改 |
| `llm_calls` | id PK；task_id；conversation_id；user_id；model VARCHAR(64)；prompt_tokens/completion_tokens/total_tokens INT；cost DECIMAL(10,4)；latency_ms INT；status VARCHAR(16)；error_message TEXT；created_at | IDX(task_id)；IDX(created_at) | 每次 LLM 请求一行；保留 180 天 |

### 9.2 认证中心表（4 张，同库 auth_ 前缀）

| 表 | 关键字段 | 说明 |
|---|---|---|
| `auth_users` | id PK；username UK；password_hash；must_change_password TINYINT；display_name；role；status；created_at | 认证用户（默认 admin/analyst） |
| `auth_clients` | id PK；client_id UK；client_secret_hash；redirect_uris JSON；scopes JSON；status；created_at | OAuth 客户端（预置 bia-web） |
| `auth_auth_codes` | id PK；code UK；client_id；user_id；redirect_uri；scope JSON；expires_at；consumed_at；created_at | 一次性授权码（10 分钟） |
| `auth_refresh_tokens` | id PK；token_hash UK；client_id；user_id；expires_at；revoked_at；created_at | 刷新令牌（30 天，轮换制） |

### 9.3 功能开关与配置项

**功能开关（config_group='feature_flag'）：**

| key | 默认 | 说明 |
|---|---|---|
| `flag_scenario_data` | true | 示例数据 schema 注入与检索 |
| `flag_attachment` | true | 附件上传与解析 |
| `flag_external_ds` | false | 外部数据源连接（仅 MySQL） |
| `flag_command_exec` | false | 命令执行工具（云上默认关闭） |
| `flag_result_generate` | false | 结果文件生成（预留） |
| `flag_ws_heartbeat` | true | WS 心跳通道 |
| `flag_tool_db_query` | true | db_query 工具 |
| `flag_tool_file_read` | true | file_read 工具 |
| `flag_tool_file_write` | true | file_write 工具 |
| `flag_tool_text_search` | true | text_search 工具 |
| `flag_tool_command_exec` | false | command_exec 工具 |

**运行参数（system_configs 可配置）：**

| key | 默认 | 说明 |
|---|---|---|
| `llm_base_url` / `llm_model` / `llm_api_key` | deepseek 网关 / deepseek-chat / 空 | LLM 接入（也可用环境变量 LLM_* 注入） |
| `llm_temperature` / `llm_max_tokens` | 0.0 / 4096 | 采样参数 |
| `llm_cost_per_1k_input` / `llm_cost_per_1k_output` | 0.001 / 0.002 | 成本估算单价（元/1k） |
| `agent_max_steps` / `agent_timeout_sec` | 8 / 600 | Agent 步数上限与单任务超时 |
| `attachment_max_size_mb` | 20 | 单附件大小上限 |
| `ws_max_connections` | 10 | WS 并发会话上限 |
| `ws_token_ttl_seconds` | 300 | WS 一次性令牌有效期 |
| `task_max_running` / `task_queue_maxsize` | 3 / 10 | 并发任务数 / 队列上限 |
| `security_max_login_fail` | 5 | 登录失败锁定阈值 |
| `cleanup_llm_calls_days` | 180 | llm_calls 保留期 |

### 9.4 文件存储目录规范（对齐 2.1.8）

| 目录 | 内容 | 归属 |
|---|---|---|
| `uploads/{user_id}/{conversation_id}/` | 附件 | 容器数据卷 |
| `exports/{user_id}/{conversation_id}/` | 导出结果文件（预留，导出接口待完善） | 容器数据卷 |
| `workspace/{user_id}/{conversation_id}/` | 临时中间文件 / 命令执行工作区 | 容器数据卷 |

删除会话时级联清理：3 个对应目录 + 数据库记录（消息、附件、任务、结果、摘要、ws 令牌）。

### 9.5 索引与约束策略

- 逻辑外键索引：所有关联列（user_id、conversation_id、task_id、message_id、client_id）一律建索引
- 唯一约束：users.external_user_id、users.username、messages(conversation_id, seq_no)、websocket_tokens.token、system_configs.config_key、data_sources.name、auth_users.username、auth_clients.client_id、auth_auth_codes.code、auth_refresh_tokens.token_hash、analysis_results.task_id
- 复合索引：会话列表 (user_id, last_message_at)、任务互斥 (conversation_id, task_status)、日志 (task_id, created_at)、审计 (user_id, created_at)
- 2C2G 节制原则：每表索引 ≤4 个；JSON 列不建索引（检索走 text_search 而非 SQL LIKE）

### 9.6 数据保留与清理策略

| 数据 | 保留策略 | 执行 |
|---|---|---|
| conversations/messages/attachments（软删） | deleted_at 标记后保留 90 天（可配置），超期物理删除记录 + 文件目录 | 定时清理任务（预留调度位） |
| analysis_results | 会话数据资产，随会话清理删除 | 同上 |
| task_logs | 保留 90 天 | 同上 |
| llm_calls | 保留 180 天（成本审计窗口） | 同上 |
| websocket_tokens / auth_auth_codes / auth_refresh_tokens | 过期/吊销即清 | 应用内 + 清理任务 |
| audit_logs | 永久保留（合规审计，只增不改） | — |

### 9.7 Schema 迁移策略（Alembic）

- 初始化 = 基线迁移（0001_initial 建 17 张表）+ 增量迁移（0002_message_task_id、0003_auth_must_change_password）+ seed 脚本（默认配置、认证用户/客户端、业务用户、预置数据源、示例数据、演示会话），幂等可重复执行
- 上线后任何 schema 变更一律新增 Alembic 迁移文件，执行 `alembic upgrade head`；禁止手工改表
- 后端容器启动自动执行 `alembic upgrade head`（幂等），失败则容器不对外服务

---

## 10. 示例业务场景（评审决策：商品目录优化 + 库存异常分析）

> 2.1.12 提供六个可选场景（商品目录优化、客户行为分析、库存异常分析、评论反馈分析、市场表现分析、退款模式分析），至少任选两个完成全链路演示。本版本选用**商品目录优化 + 库存异常分析**（与代码、示例数据、预置演示会话一致）。

### 10.1 场景一：商品目录优化（示例库 schema `scenario_goods`）

**业务问题示例**："为什么 6 月信息流渠道点击量明显下滑？" / "哪些商品应进入首页推荐位？"

**数据表（实际实现，10 张基础表 + 4 张补齐维度表）：**

| 表 | 类型 | 规模（示例） |
|---|---|---|
| `dim_sku` / `dim_channel` / `dim_category` / `dim_brand` / `dim_date` | 维度表 | 200 SKU / 6 渠道 / 40 类目 / 品牌 / 日期 |
| `fact_sku_daily` | 事实表 | 约 12 万行（200×6×100 天） |
| `fact_channel_daily` | 渠道聚合事实 | 渠道日粒度 |
| `sku_offline_log` / `creative_change_log` / `promotion_calendar` | 事件/日志表 | 下架、素材更换、促销日历 |
| `dim_creative` / `fact_creative_daily` / `dim_sku_ctr_baseline` / `dim_channel_budget_daily` | 补齐维度（enrich） | 素材级 CTR、SKU CTR 基线、渠道预算时序 |

**演示链路（完整问答路径）：**

1. 问："为什么 6 月信息流渠道的点击量明显下滑？帮我定位一下原因并给出优化建议。"
2. Agent：查询信息流 6 月 vs 5 月点击 → 交叉核对素材更换日志、SKU 下架日志、渠道预算时序、素材级 CTR → 产出六段式结果（主因：主素材 6/3 更换导致 CTR 下滑 + 头部 5 SKU 6/10 下架削减曝光基数 + 预算再分配）
3. 追问："如果把下滑 SKU 的流量转移到新品，预计影响多少 GMV？"
4. Agent：基于已有证据 + 追加查询 → 输出量化影响与建议（下一步建议 ≥2 条）
5. 结果区六段式展示 → 复制/导出（导出待完善）

### 10.2 场景二：库存异常分析（示例库 schema `scenario_inventory`）

**业务问题示例**："华东仓 SKU0001 最近出现缺货和负库存，是什么原因导致的？如何解决？"

**数据表（实际实现，7 张基础表 + 3 张补齐维度表）：**

| 表 | 类型 | 说明 |
|---|---|---|
| `dim_warehouse` / `dim_sku` / `dim_date` | 维度表 | 仓库/商品/日期 |
| `fact_inventory_daily` | 库存日快照 | SKU×仓库存序列 |
| `stock_anomaly_log` | 异常事件表 | 低库存/负库存事件 |
| `purchase_order` | 采购单 | 下单日、数量、ETA |
| `sales_daily` | 销售日表 | 日均销量（排除销售暴增假设） |
| `dim_sku_safety` / `dim_warehouse_transfer` / `fact_supplier_leadtime_daily` | 补齐维度（enrich） | 安全阈值/提前期、跨仓调拨、供应商提前期波动 |

**演示链路（完整问答路径）：**

1. 问："华东仓 SKU0001 最近出现缺货和负库存，是什么原因导致的？如何解决？"
2. Agent：查询异常事件统计 → 库存序列 → 采购单 ETA → 安全阈值/跨仓调拨/供应商提前期 → 六段式结果（主因：PO0001 到货延迟 + 安全阈值被击穿 + 供应商 SUP1 提前期恶化，非销售暴增）
3. 追问："哪些 SKU 需要优先处理积压？" / "能否用跨仓调拨缓解？"
4. Agent：按库存天数排序 + 近 30 天销量 → 输出优先处理清单与建议动作
5. 结果区六段式展示 → 复制/导出（导出待完善）

### 10.3 预置演示会话与离线兜底

- 种子脚本预置两组完整演示会话（admin 与 analyst 账号各一套）：
  - **商品目录优化 · 6月信息流点击下滑归因**
  - **库存异常分析 · SKU0001 华东仓断货归因**
- 每组会话完整落库链路：conversations → messages（用户/思路/中间结论/result）→ analysis_tasks → analysis_results（六段式）→ context_summaries → task_logs → llm_calls
- 六段式结论由离线确定性分析器实时查询场景库产出，与运行时无 LLM 演示路径一致；前端可直接历史回放与查看结果区
- 未配置 LLM API Key 时，运行期新问题走离线路径；配置后走在线 LLM 路径（DeepSeek 等）

---

## 11. 非功能需求

### 11.1 性能与资源（4C4G 云服务器、本项目按 2C2G 预算，≤10 并发）

| 指标 | 目标 |
|---|---|
| 并发 | 同时在线 ≤10 会话连接；同时运行任务 ≤3（超出排队/拒绝并提示 TASK_QUEUE_FULL） |
| API 延迟 | p95 < 500ms（非分析类接口）；分析类接口异步不阻塞 |
| WS 延迟 | 消息推送端到端 < 1s |
| LLM 首 token | 配置模型能力内，流式边到边体验（本地仅转发） |
| 附件解析 | 20MB 内 xlsx/csv 解析 ≤10s（异步队列） |

**容器内存预算（本项目 2C2G ≈ 2048MB，与 P1 共享 4C4G）：**

| 容器 | 内存配额 | 关键调优 |
|---|---|---|
| `mysql` | 768M | innodb_buffer_pool_size=256M、performance_schema=OFF |
| `backend` | 768M | uvicorn 单 worker；LLM 流式逐块转发；db_query 结果行数上限；并发任务 ≤3 |
| `redis` | 128M | 仅 WS seq/限流/锁 |
| `frontend`(nginx) | 64M | 静态资源 + 反代 |
| 合计 | ~1.73G | 预留 ~300M 给系统/日志/临时文件峰值，防 OOM |

> 说明：LLM 推理在云端 API 完成，本地只做流式转发，不占用 GPU/大内存；2C2G 的主要约束是 backend 进程内存与并发任务数，因此单 worker + ≤3 并发任务为本规格硬性设计。

### 11.2 安全

- 认证：授权码 + RS256 JWT + HttpOnly Cookie（prod 下 Secure）；WS 一次性令牌
- 越权防护：所有资源按 user_id 归属校验；管理接口 admin 校验
- 注入防护：SQL 仅只读白名单；命令执行默认关闭，开启后参数校验 + 黑名单 + 沙箱
- 文件安全：路径规范化防目录穿越；类型/大小白名单
- 密钥管理：密码哈希存储（bcrypt）；数据源密码 AES 加密（APP_ENCRYPTION_KEY）；JWT 私钥挂载 secrets（OIDC_RSA_PRIVATE_KEY）；生产强口令
- 首次登录强制改密；登录失败锁定（5 次）

### 11.3 可靠性

- 任务状态机防呆：queued → running → success/failed/cancelled，终态不可逆（非法流转返回 INVALID_TRANSITION）
- 崩溃恢复：服务重启后 running 态任务置 failed 并记录原因（引擎异常处理）；WS 断线自动重连 + REST 补偿
- 幂等：seed/演示会话按 title 重建幂等；消息 seq 冲突兜底
- 限流：WS 令牌签发限流（同用户 1 分钟 30 次）、任务队列上限、连接数上限

### 11.4 可维护性与可配置性

- 运行参数（LLM、步数上限、超时、附件限制、功能开关）走 system_configs，管理后台热更新即时生效
- 结构化日志可过滤、可关联任务；task_logs 落库 + stdout
- Docker Compose 一键部署；初始化/迁移/种子脚本幂等可重复执行
- 预置验证脚本：`scripts/smoke_test.py`（登录→改密→建会话→提问→任务终态→六段式→历史→WS token 全链路）、`scripts/verify_demo_data.py`（演示数据可回放校验）

### 11.5 兼容性

- 浏览器：Chrome/Edge/Firefox 近两年版本
- 数据库：MySQL 8.x；外部数据源当前支持 MySQL（FLAG_EXTERNAL_DS 开启时）
- LLM：OpenAI 兼容 API（chat/completions + tools）

### 11.6 部署与运维（云服务器）

**目标环境（本次确认）：** 轻量云服务器 **4C4G**，与 P1（知识库平台）共存；P2 独立 Docker Compose 命名空间 `bia`，本项目按 2C2G 预算运行。

**部署要求：**

1. **系统与运行时**：推荐 Ubuntu 22.04 LTS；Docker Engine 24+ 与 Docker Compose v2
2. **部署目录**：`/opt/bia`（或任意目录），上传项目代码；`.env` 与 `secrets/` 不入库
3. **环境变量（按 .env.production.example）**：
   - `DB_PASSWORD` / `MYSQL_ROOT_PASSWORD`：强随机密码（缺失时 docker compose 拒绝启动）
   - `OIDC_CLIENT_SECRET`：强随机串
   - `OIDC_REDIRECT_URI=http://<公网IP>:8080/auth/callback`（有域名则用域名）
   - `CORS_ORIGINS=["http://<公网IP>:8080"]`（与浏览器实际访问地址一致）
   - `APP_ENCRYPTION_KEY`：32 字节 url-safe base64（数据源密码加密）
   - `LLM_API_KEY`：可选，不配则走离线确定性分析
   - `FLAG_COMMAND_EXEC=false`、`FLAG_EXTERNAL_DS=false`（生产安全默认）
   - `APP_ENV=prod`（Cookie 仅 HTTPS；若纯 HTTP 访问需按部署文档调整）
4. **JWT 签名私钥**：`mkdir -p secrets && openssl genrsa -out secrets/oidc_rsa_private.pem 2048`（不配置则重启后登录态失效）
5. **端口与安全组**：公网放行 `22`（SSH）、`80`、`443`、`8080`（P2 前端）；`3306/6379/8001` 仅绑定 127.0.0.1，**不得放行**；P1 占用的 8000 保持不动
6. **启动**：`docker compose up -d --build` → `docker compose ps` 等待四服务 healthy → 浏览器访问 `http://<公网IP>:8080`
7. **验证**：`curl http://127.0.0.1:8001/health`（或经 8080 反代）；登录默认账号并首次改密；运行 `python scripts/smoke_test.py` 完成端到端验证；打开预置演示会话回放两组链路
8. **HTTPS（可选但推荐）**：安装 Caddy/nginx，443 反代 `127.0.0.1:8080`；同步修改 OIDC_REDIRECT_URI 与 CORS_ORIGINS 为 `https://域名`；与 P1 的 Caddy 配置互不冲突（不同 server 块/端口）
9. **备份**：数据卷 `bia_mysql_data` 定期 `mysqldump` 导出（业务库 + 场景库）；`.env` 与 `secrets/oidc_rsa_private.pem` 单独备份；docker-compose 文件纳入版本管理
10. **运维**：`docker compose logs -f backend` 查看日志；配置变更走管理后台热更新；升级镜像后 `docker compose up -d --build`（迁移自动执行）；异常排查参考 `docs/部署运维文档.md`

---

## 12. 验收标准（对照 2.1.13 逐条映射 + 云服务器部署项）

| # | 验收项（2.1.13） | 满足方式 | 实现状态 |
|---|---|---|---|
| 1 | 能通过授权登录进入聊天工作台 | 6.1：登录表单→授权码→JWT；首次改密拦截；路由守卫 | 已实现 |
| 2 | 能创建会话、上传附件、发送消息并查看历史记录 | 6.2/6.3/6.4、8.2 | 已实现 |
| 3 | 能通过实时连接看到分析过程状态变化、工具执行和最终结果 | 6.5/6.6、8.4（WS /api/ws + 9 类事件） | 已实现 |
| 4 | 能查询历史消息、切换旧会话并继续追问 | 5.3 多轮上下文 + 会话切换 + seq 排序 | 已实现 |
| 5 | 能在结果区看到六部分结构化输出 | 6.6.3/6.7、7.4 六段式面板 | 已实现 |
| 6 | 能导出分析结果文件并重新下载 | 6.7：结果 Markdown 已落库、前端可复制；导出/下载接口与按钮待完善 | **部分实现（待完善）** |
| 7 | 能通过配置重载接口更新配置并即时生效 | 6.9、POST /api/admin/config + /api/admin/reload | 已实现 |
| 8 | 完成至少两个业务场景完整演示 | 第 10 章：商品目录优化 + 库存异常分析，预置演示会话可回放 | 已实现 |
| 9 | （新增）云服务器部署完成并通过演示验证 | 11.6：4C4G 与 P1 共存部署、端口/安全组、健康检查、冒烟测试、两组演示 | 待执行（验收动作） |

---

## 13. 交付物清单

| # | 交付物 | 说明 |
|---|---|---|
| 1 | 前端工程 | Vue3 SPA：登录/改密/工作台/管理后台，Nginx 托管 + 反代 |
| 2 | 后端工程 | FastAPI：业务 API + WS + Agent 分析引擎 + OIDC 认证中心（合并部署） |
| 3 | 认证中心服务 | 内嵌于 backend：登录/授权码/令牌/JWKS/userinfo |
| 4 | 数据库初始化脚本 | 建库 + Alembic 迁移 + 种子（配置/认证用户/客户端/业务用户/数据源） |
| 5 | 示例数据脚本 | 场景一（scenario_goods）/场景二（scenario_inventory）全量表数据 + 补齐维度 + 演示会话 |
| 6 | 接口说明文档 | 8.1~8.5 全部接口 + 错误码 + 2.1.9 对照 |
| 7 | Docker Compose 编排 | mysql/redis/backend/frontend 四服务（命名空间 bia） |
| 8 | 部署文档 | 云服务器初始化 → 起服 → 验证 → 运维（docs/部署运维文档.md + 11.6） |
| 9 | 演示链路说明 | 两组场景的演示脚本（问题 → 预期结果 → 讲解点），预置演示会话 |
| 10 | 验证脚本 | smoke_test.py / verify_demo_data.py / seed_demo_conversations.py |

---

## 14. 里程碑建议

| 阶段 | 内容 | 输出 |
|---|---|---|
| M1 基础骨架 | 认证登录 + 会话/消息 CRUD + WS 通道 + 改密 | 可登录、可建会话、可收发消息 |
| M2 分析引擎 | Agent 循环 + 工具集 + 六段式输出 + 任务状态机 + 离线兜底 | 单场景可跑通一轮归因 |
| M3 工作台完善 | 附件、结果区、取消、历史追问、摘要压缩 | 场景一全链路演示 |
| M4 管理后台 | 配置/数据源/开关/日志/成本/审计 + 热更新 | 管理验收项全过 |
| M5 场景二 + 工程化 | 库存场景、示例数据、Compose、部署文档、接口文档 | 全量功能验收 |
| M6 云服务器部署 | 4C4G 与 P1 共存部署、安全组/端口、HTTPS（可选）、冒烟验证 | 云服务器验收项（12.#9）+ 两组演示 |
| M7 收尾完善 | 结果导出/下载接口（15.1）、2.1.9 兼容别名（15.2） | 补齐 2.1.13 #6 完整验收 |

---

## 15. 风险与开放问题

### 15.1 风险清单

| # | 风险/问题 | 等级 | 应对 |
|---|---|---|---|
| 1 | **结果导出/下载未实现**（2.1.13 #6 验收缺口）：前端导出按钮禁用、无导出/下载接口 | 中 | 结果 Markdown 已落库（result_markdown），补齐 `POST /api/results/{task_id}/export` + `GET /api/results/download/{result_id}` 与导出按钮即可闭环；列为 M7 收尾项 |
| 2 | 2.1.9 接口路径与实现存在等价差异（附件接口单复数、WS 路径、登录流程） | 低 | 8.2/8.4 对照表已说明；如需严格按 2.1.9 路径验收，可增加兼容别名路由（不改业务逻辑） |
| 3 | 4C4G 与 P1 共存资源竞争（内存/CPU/端口） | 中 | 本项目按 2C2G 预算 + 容器 mem_limit + backend 单 worker + 并发硬上限；端口已避开（P2 8001/8080 vs P1 8000）；若实测 OOM 可下调并发阈值 |
| 4 | 纯 LLM 归因结果不稳定，演示翻车 | 高 | 混合路线结构化约束 + 步骤/超时上限 + 离线确定性兜底 + 演示脚本预演 |
| 5 | LLM API 成本与限流 | 中 | 配置化模型切换；单轮步数上限控制 token 消耗；llm_calls 记录成本 |
| 6 | 命令执行安全 | 高 | FLAG_COMMAND_EXEC=false（生产默认关闭）；开启时工作区沙箱 + 白名单 + 超时 + 日志审计 |
| 7 | xlsx 大数据量解析性能 | 中 | 异步队列 + 行数上限 |
| 8 | 云服务器无 HTTPS 时明文传输（含登录口令） | 中 | 建议配置域名 + Caddy/nginx 443；纯 IP 演示场景可接受，生产必须 HTTPS |
| 9 | 外部数据源口径映射（表结构未知） | 中 | 系统提示词注入 schema 描述；演示以内置示例库为主；FLAG_EXTERNAL_DS 默认关闭 |

### 15.2 开放问题（不影响本期运行，留待后续版本）

- 多租户隔离、主动监控告警（"数据找人"）、PDF/图片附件解析、多模型混合路由、指标语义层
- 独立认证中心前端页（"跳转认证中心登录"交互形态）
- 结果导出范围定义（单个 Markdown 文件 vs zip 含证据附件）
- `archived` 会话状态的前端入口（当前仅保留状态字段）
- 定时物理清理任务（软删数据与过期票据）的调度实现

---

> 本 PRD 为 v1.2 修订稿，以《项目实战》2.1 为基准、以当前可运行实现为准绳。文档与代码不一致处已逐一修正并标注；"待完善"项（结果导出/下载）已列入 15.1 风险与 M7 里程碑，作为下一迭代的首要收尾工作。
