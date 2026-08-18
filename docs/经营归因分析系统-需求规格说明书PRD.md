# 经营归因分析系统 需求规格说明书（PRD）

| 项 | 内容 |
|---|---|
| 文档名称 | 经营归因分析系统需求规格说明书（PRD） |
| 版本 | v1.1 |
| 日期 | 2026-08-18 |
| 状态 | 评审稿（v1.1：按 2C2G 资源约束修订规模/性能/部署预算；待技术评审确认） |
| 依据 | 《项目实战要求》2.1 节 + 需求评审会四轮决策 |

---

## 1. 项目概述

### 1.1 背景与目标

企业经营管理中，"指标波动为什么发生、影响有多大、下一步该怎么办"是决策者最高频的问题。传统 BI 只能回答"发生了什么"，归因分析需要分析师手工取数、交叉验证、写报告，周期 1~3 天，错过决策窗口。

本项目目标是构建一个**面向经营分析场景的多轮归因分析系统**：用户围绕一个业务问题持续追问，系统通过 AI Agent 自主规划分析路径、调用数据与文件工具收集证据，生成带证据链的阶段性结论，最终产出六段式结构化分析报告。交付形式为可运行的前端、后端、认证中心、数据库初始化脚本、示例数据、接口说明，以及至少两组完整分析示例。

### 1.2 产品定位

一句话定位：**把"分析师 1~3 天的归因分析"压缩到"一次对话 + 可回溯的证据链"，让决策者秒级拿到可执行结论。**

- 核心对象：业务问题（如"华东区 Q2 转化率为什么下降 8%"）
- 核心能力：多轮追问、证据补充、阶段性结论、最终报告
- 核心差异化：证据可回溯（每条结论带来源与置信度）、过程透明（工具执行实时可见）、场景开箱即用（内置示例库）

### 1.3 项目范围

**In Scope（本版本交付）：**

1. 基础能力：OIDC 授权登录、会话管理、附件管理、配置热更新、运行日志
2. 分析能力：LLM 驱动的归因 Agent，工具集含数据库查询、文件读写、文本检索、命令执行（沙箱化）、结果文件生成
3. 交付能力：聊天工作台、管理后台、结果保存/导出/下载、2 个完整业务场景（商品目录优化、库存异常分析）的示例数据与演示链路
4. 工程交付：Docker Compose 单机部署、初始化脚本、接口文档、部署文档

**Out of Scope（本版本不做）：**

- 多租户隔离（仅单租户 + 用户角色）
- 报表/大屏可视化编辑
- 定时任务 / 主动监控告警（"数据找人"）
- 附件类型超出 csv/xlsx/txt 的解析（如 PDF、图片 OCR）
- 多模型混合路由、模型微调

### 1.4 术语表

| 术语 | 定义 |
|---|---|
| 归因分析 | 对指标变化进行原因拆解，量化各因子贡献，输出主因与影响范围的结论 |
| 分析任务（Task） | 一条用户消息对应一次分析执行，有独立状态机 |
| 工具（Tool） | Agent 可调用的原子能力：数据库查询、文件读写、文本检索、命令执行、结果生成 |
| 证据（Evidence） | 归因结论的支撑材料，含来源类型、来源名、文本、关联指标、置信度 |
| 六段式输出 | 问题定义、关键指标、证据列表、归因结论、待补充数据、下一步建议 |
| 会话（Conversation） | 用户与系统围绕主题的一组连续对话，含消息、附件、任务、结果 |
| OIDC | OpenID Connect，基于 OAuth2 的身份认证协议 |

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

> **Agent 自主规划分析路径 + 六段式结构化输出约束 + 全链路过程透明 + 证据可回溯**

| 维度 | 瓴羊 Quick BI | 思迈特 AIChat | 本项目 |
|---|---|---|---|
| 分析路径 | 预设归因树 | Agent 编排 | Agent 自主 + 结构约束 |
| 证据可回溯 | 弱 | 中 | 强（source/confidence 全量记录） |
| 过程透明 | 弱 | 中 | 强（工具执行逐条实时推送） |
| 场景演示 | 绑定阿里生态 | 需语义底座建设 | 内置示例库开箱即用 |
| 部署 | 云/私有化 | 私有化 | Docker Compose 单机 |

---

## 3. 用户角色与权限

| 角色 | 编码 | 权限范围 |
|---|---|---|
| 分析用户 | `analyst` | 创建/删除/重命名/切换会话；上传/删除/下载附件；发送消息、取消分析；查看历史消息与结果；复制/导出/下载结果文件 |
| 系统管理员 | `admin` | 分析用户全部权限（企业级交付，管理员可自建会话）+ 访问管理后台：认证配置查看、系统配置查看与重载、数据源连接管理、功能开关启停、运行日志查看 |

权限控制原则：前端路由守卫 + 后端接口鉴权双层校验；管理接口仅 `admin` 角色可访问；用户仅能访问自己的会话/附件/任务/结果（按 `user_id` 隔离）。

---

## 4. 总体架构

### 4.1 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│ 前端（Vue3 SPA）                                              │
│  认证入口页 / 登录回调页 / 聊天工作台 / 管理后台 /admin         │
└──────────────┬──────────────────────────────┬──────────────┘
               │ HTTPS / REST + WebSocket      │
┌──────────────▼──────────────────────────────▼──────────────┐
│ 业务后端（FastAPI 单体）                                      │
│  认证接入 │ 会话 │ 消息 │ 附件 │ 长连接 │ 任务 │ 分析 │ 结果 │ 配置 │ 日志 │ 数据源 │
└──────┬──────────────┬──────────────┬──────────────┬────────┘
       │              │              │              │
┌──────▼─────┐  ┌─────▼──────┐  ┌───▼─────────┐  ┌─▼──────────────┐
│ MySQL      │  │ Redis      │  │ 认证中心(OIDC)│  │ 文件系统(卷)    │
│ 业务库      │  │ 会话/限流/  │  │ 授权码/令牌   │  │ uploads/exports │
│ +示例库     │  │ 缓存       │  │ 用户/客户端   │  │ /workspace     │
└────────────┘  └────────────┘  └─────────────┘  └────────────────┘
```

- 认证中心与业务系统**同仓库、同 MySQL 实例、独立 schema**（`auth_` 前缀表），单独容器运行，通过 OIDC 标准协议与业务系统交互。
- 分析引擎通过 OpenAI 兼容接口调用外部 LLM（DeepSeek/通义/Kimi/OpenAI 任选，配置化）。
- 示例库与业务库同实例多 schema：`business`（业务表）、`scenario_goods`（商品目录优化示例）、`scenario_inventory`（库存异常分析示例）。

### 4.2 技术栈（评审决策）

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Naive UI | 中文生态好、开发效率高；企业级组件覆盖管理后台 |
| 后端 | Python FastAPI | LLM/Agent 生态最成熟（openai SDK、工具调用链路天然契合）；异步支持 WebSocket |
| 数据库 | MySQL 8（业务库 + 示例库） | 企业级事实标准；初始化脚本 + 示例数据交付成熟 |
| 缓存 | Redis 7 | 会话级临时状态、WS 心跳、接口限流、附件解析状态 |
| LLM | OpenAI 兼容 API（可配置 base_url/api_key/model） | 国内可用 DeepSeek/通义/Kimi，不锁定厂商 |
| 部署 | Docker Compose（mysql + redis + auth + backend + frontend(nginx)） | 单机云服务器一键起，**2C2G（4C4G 服务器分配一半）满足 ≤10 并发**；容器内存配额见 11.1 |

### 4.3 部署拓扑

- 单台云服务器（目标规格 **2C2G**，即 4C4G 云服务器分配给本项目的上限；Docker Compose 编排内按此配额设计）：
  - `mysql`：3306，数据卷持久化；`innodb_buffer_pool_size=192M`、`max_connections=50`（内存预算 400MB）
  - `redis`：6379，仅内网；`maxmemory 128mb` + LRU 淘汰（内存预算 180MB）
  - `auth`：OIDC 认证中心，8001，单 worker（内存预算 180MB）
  - `backend`：业务 API + WebSocket，8000，单 worker + 异步任务队列（内存预算 600MB）
  - `frontend`：Nginx 托管静态资源并反代 `/api`、`/ws`、`/auth`，443 对外（内存预算 40MB）
- 全部容器以 `mem_limit` 限定内存配额；预留 ~650MB 给系统、日志、临时文件与附件解析峰值（见 11.1 预算表）。
- 首次启动自动执行：建库 → 迁移表结构 → 初始化系统配置 → 灌入示例数据 → 创建默认管理员与示例用户。

---

## 5. 核心业务流程

### 5.1 端到端主流程

```
授权登录 → 登录回调换令牌 → 进入聊天工作台
  → 新建会话 →（可选）上传附件 → 输入业务问题 → 发送
  → 服务端创建分析任务（queued）→ WS 推送 message_start
  → Agent 循环执行（工具调用实时推送 tool_start/tool_finish）
  → 生成六段式结果（result_ready）→ 任务 success（done）
  → 结果展示区渲染 + 自动生成 Markdown 文件
  → 用户可继续追问（携带上下文摘要）或导出/下载结果
```

### 5.2 单轮分析内部流程（混合路线 Agent 循环）

```
输入：用户问题 + 会话上下文摘要 + 附件元信息 + 可用工具清单
步骤：
 1. 问题理解与任务规划：LLM 拆解问题，产出分析计划（查询哪些表/读哪些文件/检索什么）
 2. 循环执行（上限 8 步、总时长 10 分钟，均可配置）：
     - LLM 决策下一步工具调用
     - 执行工具（DB 查询 / 文件读写 / 文本检索 / 命令执行），记录 tool_start/tool_finish
     - 观察结果，更新中间结论
     - 若证据不足，生成"待补充数据"并建议追问
 3. 结论生成：LLM 依据全部证据，按六段式模板输出结构化结果
 4. 落库与文件生成：analysis_results 落库 + 生成 Markdown 文件
 5. 上下文摘要压缩：对本轮消息+结果做摘要，写入 context_summaries
```

约束（防失控）：

- 单轮工具调用 ≤ 8 步（`system_configs` 可调）
- 单轮总时长 ≤ 10 分钟（可调），超时任务置 `failed` 并推送 `error`
- 同一会话同时仅 1 个运行中任务（服务端互斥校验）
- 工具调用前做参数校验；命令执行限工作区沙箱（见 6.6.4）

### 5.3 多轮追问与上下文管理

- 追问输入 = 用户新消息 + 最近 N 轮消息 + `context_summaries` 摘要（start_seq_no ~ end_seq_no 区间）
- 每轮结束后生成摘要（问题、结论、已用证据、未决问题），压缩存储，避免上下文无限膨胀
- 历史消息按 `seq_no` 严格排序，重放时保持顺序
- 删除会话级联删除：消息、附件记录与文件、任务、结果、上下文摘要

---

## 6. 功能需求

### 6.1 认证模块（OIDC 授权码流程）

**认证中心（自建 OIDC Server，评审决策）：**

| 功能 | 说明 |
|---|---|
| 授权端点 | `GET /authorize`：校验客户端、用户登录态，签发一次性授权码（5 分钟有效） |
| 令牌端点 | `POST /token`：授权码换 access_token（JWT，15 分钟）+ refresh_token（7 天） |
| 用户信息端点 | `GET /userinfo`：返回 sub、username、display_name、role |
| 客户端管理 | 预置系统客户端（client_id/secret），管理后台可查看 |
| 用户管理 | 初始化脚本创建默认管理员与示例用户；登录页支持账号密码（表单）+ 记住我 |

**业务系统接入（客户端）：**

| 功能 | 说明 |
|---|---|
| 授权跳转 | `GET /auth/login`：拼装 authorize URL 302 跳转认证中心 |
| 回调换令牌 | `GET /auth/callback`：收 code → POST /token 换令牌 → 存服务端会话 → 种 HttpOnly Cookie → 302 到工作台 |
| 令牌校验 | 中间件解析 Cookie/Authorization，调 userinfo 或本地验 JWT，识别当前用户 |
| 登录态管理 | 会话表（服务端）或 JWT；退出登录清理 Cookie 与后端会话 |
| 用户同步 | 首次登录将认证中心用户 upsert 进业务库 `users`（external_user_id 关联） |

### 6.2 会话模块

| 功能 | 说明 |
|---|---|
| 新建 | `POST /api/chat/create`（title 可为空，默认"新会话"） |
| 列表 | `GET /api/chat/ls`：按 last_message_at 倒序，分页 |
| 重命名 | `POST /api/chat/update` |
| 删除 | `POST /api/chat/delete`（支持批量 conversation_ids）：级联删除消息/附件/任务/结果/摘要记录及对应目录文件 |
| 切换 | 前端本地切换 + 拉取 `GET /api/chat/ls/{id}` 历史消息 |
| 状态机 | `active` → `archived` → `deleted`（deleted 为软删除标记 + 物理清理任务） |

### 6.3 聊天模块

| 功能 | 说明 |
|---|---|
| 消息发送 | 提交问题 → 创建任务（queued）→ 经 WS 推送 message_start |
| 流式渲染 | WS 接收 message_delta（按块推送）增量渲染；tool_start/tool_finish 渲染工具卡片 |
| 取消分析 | 输入区取消按钮 → WS 发送 `cancel_task` → 服务端终止任务（置 cancelled，终止 LLM 流与子进程） |
| 历史回放 | 进入会话加载 messages（role/content/attachments/created_at），按 seq_no 顺序渲染 |
| 消息类型 | `text`（用户问题/助手文本）、`tool`（工具执行记录）、`result`（六段式结果） |
| 一条消息一个任务 | 用户消息创建分析任务，任务与消息一一对应（message_id 关联） |

### 6.4 附件模块

| 功能 | 说明 |
|---|---|
| 支持格式 | csv、xlsx、txt（评审决策；暂不支持 PDF/图片） |
| 上传 | `POST /api/attachment/upload`：存 `uploads/{user_id}/{conversation_id}/`，记录 attachments，异步解析 |
| 解析 | 异步任务：读取文件 → 结构抽取（表头/行列/摘要）→ 解析状态流转 `pending → parsing → parsed / failed`；解析结果供分析引擎文本检索 |
| 元信息 | 文件名、文件类型（MIME + 扩展名）、文件大小、上传时间、解析状态 |
| 删除 | `POST /api/attachment/delete`：删记录 + 物理文件 |
| 下载 | `GET /api/attachment/download/{attachment_id}`：鉴权 + 路径校验后流式返回 |
| 安全 | 路径白名单校验（防目录穿越）；大小上限 20MB；类型白名单 |

### 6.5 实时任务模块（WebSocket）

| 功能 | 说明 |
|---|---|
| 连接建立 | `WS /api/chat/ws/chat?websocket_token=xxx&conversation_id=yyy`；token 由 `POST /api/chat/ws-token` 签发（单次有效、可过期、会话绑定） |
| 鉴权 | 连接时校验 ws_token 未消费且未过期、会话归属当前用户，成功后标记 consumed |
| 入站消息 | `cancel_task`（取消当前任务） |
| 出站消息 | 见 8.4 消息类型（8 种文档要求 + ping 心跳） |
| 心跳 | 服务端每 30s ping，客户端 pong；断线自动重连（指数退避） |
| 会话级互斥 | 连接建立/任务创建时校验会话无运行中任务，冲突返回明确错误 |
| 并发 | 单用户可开多个会话连接；连接数与任务数受限流保护（Redis 计数，≤10 并发目标，同时运行任务 ≤3） |

### 6.6 分析引擎

#### 6.6.1 工具集（Tool Registry）

| 工具 | 能力 | 安全约束 |
|---|---|---|
| `db_query` | 对目标数据源（示例库/外部源）执行 SQL | 仅 SELECT；表白名单；结果行数上限（默认 500）；超时 30s |
| `file_read` | 读取会话工作区内文件（附件/中间文件） | 路径校验限 `workspace/{user_id}/{conversation_id}/` |
| `file_write` | 写中间结果/结果文件 | 同上目录内 |
| `text_search` | 附件/工作区文本全文检索（关键词 + 片段返回） | 检索范围限当前会话 |
| `command_exec` | 在会话工作区沙箱内执行命令（如 python 脚本做数据分析） | 仅限工作区 cwd；注入参数校验；禁用危险命令（rm -rf、curl 外联等黑名单）；超时 60s |
| `result_generate` | 生成 Markdown 结果文件到 exports | 路径固定 `exports/{user_id}/{conversation_id}/` |

#### 6.6.2 Agent 循环

- 采用 OpenAI 兼容 Chat Completions + 工具调用（function calling）实现
- 系统提示词内置：业务场景说明、表结构描述（或数据源 schema 提示）、工具清单与约束、六段式输出模板
- 循环收敛条件：LLM 判定证据充分 → 直接输出六段式 JSON
- 兜底：达到步骤上限或超时 → 基于已有证据尽力输出部分结果 + 明确标注"待补充数据"

#### 6.6.3 六段式输出（结构化结果）

| 段 | 字段 | 说明 |
|---|---|---|
| 问题定义 | `problem_definition` | 当前分析要回答的业务问题 |
| 关键指标 | `key_metrics`（数组） | 每项：metric_name、metric_value、metric_unit、metric_period |
| 证据列表 | `evidence_list`（数组） | 每项：source_type、source_name、evidence_text、related_metric、confidence |
| 归因结论 | `conclusion_text` | 自然语言：主要原因 + 影响范围 |
| 待补充数据 | `missing_data_text` | 缺失数据项清单 |
| 下一步建议 | `next_action_text` | ≥2 条建议动作 |

#### 6.6.4 安全边界（评审决策：工作区沙箱 + 白名单）

- 命令执行：cwd 固定为会话工作区；参数注入校验（转义/白名单）；危险命令黑名单；超时强制终止
- 数据库：默认只读；示例库表白名单；外部数据源由管理员配置只读账号
- 文件：所有路径经规范化校验，禁止 `..` 逃逸与绝对路径越界
- LLM 输出：SQL/命令先经规则校验再执行，非法输入拒绝并记录日志

### 6.7 结果模块

| 功能 | 说明 |
|---|---|
| 结构化展示 | 结果展示区六段式渲染：问题定义、指标卡片、证据列表（来源+置信度徽标）、结论、待补充、建议 |
| 复制 | 一键复制全文 Markdown |
| 导出 | `POST /api/results/{task_id}/export`：生成/返回 result_file_path |
| 下载 | `GET /api/results/download/{result_id}`：下载 Markdown 文件 |
| 结果文件管理 | 文件存 `exports/{user_id}/{conversation_id}/`；删除会话级联删除 |

### 6.8 管理后台模块（独立 /admin 页，评审决策）

| 功能组 | 说明 |
|---|---|
| 系统配置 | 查看/编辑 `system_configs`（LLM base_url/api_key/model、任务步数上限、超时、附件上限等）；保存后点击"重载"即时生效 |
| 认证配置 | 查看 OIDC 客户端信息、令牌过期策略；密钥仅管理员可见 |
| 数据源管理 | 查看/新增/编辑/删除外部数据源（MySQL/PostgreSQL 连接串、只读账号）；测试连接；启用/停用 |
| 功能开关 | 启停功能：分析工具开关（db_query/file_read/text_search/command_exec 逐个）、附件上传、结果导出等 |
| 运行日志 | 查看 task_logs / 系统日志：级别过滤、任务关联、错误高亮、分页 |

### 6.9 配置与日志模块

| 功能 | 说明 |
|---|---|
| 配置热更新 | `POST /api/admin/reload`：从 MySQL 重载 system_configs 到内存缓存，全量生效；配置项按 `config_group` 分组 |
| 默认配置 | 初始化脚本写入默认值（含 LLM 接入、安全限额、功能开关） |
| 日志 | 结构化日志（task_id 关联）；task_logs 表落库 + 容器 stdout；级别：DEBUG/INFO/WARN/ERROR |
| 审计 | 管理员配置变更、数据源变更记录 WARN 级日志 |

---

## 7. 页面需求

### 7.1 页面清单与路由

| 页面 | 路由 | 角色 | 说明 |
|---|---|---|---|
| 授权登录入口页 | `/login` | 匿名 | 品牌 + "授权登录"按钮 → 跳认证中心 |
| 登录回调页 | `/auth/callback` | 匿名 | 处理回调、换令牌、302 到工作台 |
| 聊天工作台页 | `/chat` | analyst/admin | 三栏布局（会话列表 / 对话区 / 结果区）+ 附件侧栏 + 实时任务区 |
| 管理后台页 | `/admin` | admin | 配置 / 数据源 / 开关 / 日志 四个 Tab |
| 404 | `*` | 全部 | 兜底 |

### 7.2 授权登录入口页

- 展示系统名称、简要说明、登录按钮
- 点击后 `location.href = /auth/login`，后端 302 至认证中心 authorize 端点
- 已登录用户访问自动跳转工作台

### 7.3 登录回调页

- 接收 `code` 参数 → 调 `/auth/callback` → 成功后 302 `/chat`
- 失败展示错误信息与重试入口
- 该页极简（白屏过渡 + loading），主要逻辑在后端

### 7.4 聊天工作台页

**布局：**

```
┌──────────┬──────────────────────────┬────────────────────┐
│ 会话列表  │ 对话区                    │ 结果展示区          │
│ (左栏)   │  消息流（流式渲染/工具卡片）│  六段式结果 + 导出   │
│          │  附件侧栏（折叠在对话区上） │  实时任务区(状态条)  │
│          │  底部输入框 + 取消按钮     │                    │
└──────────┴──────────────────────────┴────────────────────┘
```

| 区域 | 需求要点 |
|---|---|
| 会话列表 | 新建按钮；列表项（标题/时间）；选中态；右键/悬浮菜单：重命名、删除、归档 |
| 对话区 | 气泡消息：用户问题、助手文本流式渲染、工具卡片（工具名/状态/摘要）；历史回放按序渲染；滚动到底部按钮 |
| 附件侧栏 | 当前会话附件列表：文件名/类型/大小/上传时间/解析状态徽标；上传（拖拽+选择，进度条）、删除、下载 |
| 实时任务区 | 当前轮状态（queued/running/success/failed/cancelled）、当前步骤、错误信息、工具执行过程、结果文件生成状态 |
| 结果展示区 | 六段式渲染（见 6.7）；复制/导出/下载按钮；空态引导"输入一个业务问题开始分析" |
| 输入区 | 文本域（Enter 发送 / Shift+Enter 换行）、发送按钮、取消按钮（任务运行中显示）、附件上传入口 |

### 7.5 管理后台页

- 四个 Tab：**系统配置**（配置表 + 编辑 + 重载按钮）、**数据源**（列表 + 新增/编辑弹窗 + 测试连接）、**功能开关**（开关列表 + 即时生效）、**运行日志**（过滤 + 分页 + 详情）
- 顶部显示当前管理员信息与退出登录
- 仅 admin 角色可访问；非 admin 跳转 403

---

## 8. 接口需求

### 8.1 认证接口

| 方法/路径 | 说明 | 关键字段 |
|---|---|---|
| `GET /auth/login` | 跳转认证中心发起授权登录 | 302 → authorize |
| `GET /auth/callback` | 处理授权回调并建立登录态 | 入参 code；成功 302 /chat |
| `POST /auth/logout` | 退出登录 | — |
| `GET /api/auth/me` | 当前用户信息 | username、display_name、role |

认证中心内部（OIDC Server，非业务 API）：

| 方法/路径 | 说明 |
|---|---|
| `GET /authorize` | 授权端点 |
| `POST /token` | 令牌端点 |
| `GET /userinfo` | 用户信息端点 |
| `GET /.well-known/openid-configuration` | OIDC 发现文档 |

### 8.2 业务接口（含文档 2.1.9 全部要求）

| 方法/路径 | 请求字段 | 响应字段 | 说明 |
|---|---|---|---|
| `POST /api/chat/create` | `title` | `conversation_id`、`title`、`status` | 新建会话 |
| `POST /api/chat/delete` | `conversation_ids` | `status`、`message`、`deleted_ids` | 批量删除 |
| `POST /api/chat/update` | `conversation_id`、`title` | `conversation_id`、`title`、`status` | 重命名 |
| `GET /api/chat/ls` | — | `conversation_id`、`title`、`status`、`last_message_at`（数组） | 会话列表 |
| `GET /api/chat/ls/{conversation_id}` | — | `message_id`、`role`、`content`、`attachments`、`created_at`（数组） | 历史消息 |
| `POST /api/attachment/upload` | `conversation_id` + 文件 | `attachment_id`、`file_name`、`file_path` | 上传附件 |
| `POST /api/attachment/delete` | `attachment_id` | `status`、`message` | 删除附件 |
| `GET /api/attachment/get` | `attachment_id`（query） | `attachment_id`、`file_name`、`file_type`、`file_size`、`parse_status`、`created_at` | 附件元信息 |
| `GET /api/attachment/download/{attachment_id}` | — | 文件流 | 附件下载 |
| `POST /api/chat/ws-token` | `conversation_id` | `websocket_token`、`expires_in` | 签发 WS 令牌 |
| `WS /api/chat/ws/chat` | 连接参数 `websocket_token`、`conversation_id` | 实时消息（见 8.4） | 长连接 |
| `POST /api/tasks/{task_id}/cancel` | — | `task_status`、`message` | 取消任务（WS 与 HTTP 双通道） |
| `GET /api/tasks/{task_id}` | — | `task_status`、`current_step`、`started_at`、`finished_at`、`error_message` | 任务状态 |
| `GET /api/results/{task_id}` | — | `problem_definition`、`key_metrics`、`evidence_list`、`conclusion_text`、`missing_data_text`、`next_action_text` | 结构化结果 |
| `POST /api/results/{task_id}/export` | — | `result_id`、`result_file_path` | 生成导出文件 |
| `GET /api/results/download/{result_id}` | — | 文件流 | 下载结果文件 |

### 8.3 管理接口

| 方法/路径 | 说明 |
|---|---|
| `GET /api/admin/configs` | 系统配置列表（按 config_group 分组） |
| `PUT /api/admin/configs` | 更新配置（批量） |
| `POST /api/admin/reload` | 重载配置，响应 `status`、`message` |
| `GET /api/admin/data-sources` | 数据源列表 |
| `POST /api/admin/data-sources` | 新增数据源 |
| `PUT /api/admin/data-sources/{id}` | 更新数据源 |
| `DELETE /api/admin/data-sources/{id}` | 删除数据源 |
| `POST /api/admin/data-sources/{id}/test` | 测试连接 |
| `GET /api/admin/logs` | 运行日志（过滤：level/type/task_id，分页） |
| `PUT /api/admin/feature-flags` | 更新功能开关 |

### 8.4 实时消息类型（文档 8 种 + 补充）

**出站（服务端 → 客户端）：**

| 类型 | 必含字段 | 说明 |
|---|---|---|
| `message_start` | `task_id`、`conversation_id` | 本轮分析开始 |
| `message_delta` | `task_id`、`delta_text` | 模型增量文本（按块推送，块大小约 20~50 字） |
| `tool_start` | `task_id`、`tool_name` | 工具开始执行 |
| `tool_finish` | `task_id`、`tool_name`、`tool_result_summary` | 工具执行完成 |
| `task_status` | `task_id`、`task_status`、`current_step` | 任务状态变化 |
| `result_ready` | `task_id`、`result_id` | 结构化结果已生成 |
| `error` | `task_id`、`error_message` | 本轮分析失败 |
| `done` | `task_id`、`finished_at` | 本轮分析结束 |
| `attachment_parsed` | `attachment_id`、`parse_status` | （补充）附件解析完成通知 |

**入站（客户端 → 服务端）：**

| 类型 | 必含字段 | 说明 |
|---|---|---|
| `cancel_task` | `task_id` | 取消当前任务 |
| `pong` | — | 心跳响应 |

### 8.5 错误码规范

| 码 | 含义 | 场景 |
|---|---|---|
| `AUTH_REQUIRED` | 未登录 | 401 |
| `AUTH_EXPIRED` | 登录态过期 | 401，前端跳登录 |
| `FORBIDDEN` | 无权限 | 403，非 admin 访问管理接口 |
| `NOT_FOUND` | 资源不存在 | 404 |
| `TASK_BUSY` | 会话已有运行中任务 | 409 |
| `TASK_NOT_CANCELLABLE` | 任务不可取消 | 409（终态任务） |
| `FILE_TYPE_NOT_ALLOWED` | 附件类型不允许 | 400 |
| `FILE_TOO_LARGE` | 附件超限 | 400 |
| `CONFIG_RELOAD_FAILED` | 配置重载失败 | 500 |

---

## 9. 数据模型

### 9.0 数据模型设计决策（评审决策，2026-08-18 深化评审）

> 本轮评审将第 9 章升级为"可上线级"设计。字段级定义见独立文档 `docs/design/数据模型设计.md`。

| # | 决策项 | 决策 | 影响 |
|---|---|---|---|
| 1 | 主键策略 | 全表 **UUIDv7**（时间有序、防枚举、可作索引） | 所有表主键、初始化脚本、示例数据 |
| 2 | 关联约束 | **逻辑外键 + 复合索引**（应用层保证一致性，生产 MySQL 惯例） | 级联删除在应用层实现（6.2/9.6） |
| 3 | 删除语义 | **软删除**（`deleted_at` 标记）+ **定时物理清理**（保留期可配置，默认 90 天） | conversations/messages/attachments 等 |
| 4 | 审计追踪 | 新增 **`audit_logs`**（谁/何时/改了什么/前后值） | 管理后台全部写操作记录 |
| 5 | LLM 成本 | 新增 **`llm_calls`**，**每次请求一行**（模型/token/耗时/费用/任务关联） | 成本可精确到单步调用 |
| 6 | 附件解析 | `attachments` 加 **`parse_result_json`** 列（表头/行列/摘要） | text_search 检索该字段 + 工作区文本 |
| 7 | 结果存储 | `analysis_results` 的 key_metrics/evidence_list **保持 JSON 列** | 展示/导出直接读整行，无按字段 SQL 需求 |
| 8 | 时间口径 | 全库 **UTC + DATETIME**（应用层转本地展示，无 2038 问题） | 所有时间字段与接口序列化 |
| 9 | 配置类型 | `system_configs` 加 **`config_type`**（bool/int/float/string/json） | 校验 + 管理后台控件自动匹配 |
| 10 | 登录追踪 | `users` 加 **`last_login_at`** | 登录/刷新令牌时更新 |
| 11 | 日志保留 | `task_logs` 保留 **90 天**，超期随定时任务清理 | 与软删清理同一调度 |
| 12 | 示例数据 | 示例库**保留 + 功能开关 `flag_scenario_data`**（可关场景 schema 注入） | 验收开箱即用，上线可关 |
| 13 | 迁移策略 | **Alembic 版本化迁移**（上线后加表/加列走 `alembic upgrade`） | 替代"初始化脚本幂等重建" |

### 9.1 业务库表（文档 2.1.7 全部 11 张 + 新增，字段级定义）

> 约定：PK 均为 UUIDv7（VARCHAR(32) 无横线）；时间字段一律 DATETIME（UTC）；软删表含 `deleted_at`；逻辑外键列一律建索引。

**文档规定的表（字段严格对齐）：**

| 表 | 字段（类型） | 索引 / 约束 | 说明 |
|---|---|---|---|
| `users` | id PK；external_user_id VARCHAR(64)；username VARCHAR(64)；display_name VARCHAR(64)；role VARCHAR(16)；status VARCHAR(16)；**last_login_at** DATETIME；created_at/updated_at | UK: external_user_id、username | 与认证中心 upsert 同步（6.1）；last_login_at 登录时更新 |
| `conversations` | id PK；user_id；title VARCHAR(128)；status VARCHAR(16)；last_message_at DATETIME；**deleted_at**；created_at/updated_at | IDX(user_id, last_message_at) | status: active/archived/deleted；列表按 last_message_at 倒序 |
| `messages` | id PK；conversation_id；role VARCHAR(16)；message_type VARCHAR(16)；content LONGTEXT；tool_name VARCHAR(64)；tool_status VARCHAR(16)；seq_no INT；created_at；**deleted_at** | **UK(conversation_id, seq_no)**；IDX(conversation_id, created_at) | seq_no 会话内递增；内容按消息类型存储（text/tool/result） |
| `attachments` | id PK；conversation_id；message_id（可空）；file_name VARCHAR(255)；file_path VARCHAR(512)；file_type VARCHAR(32)；file_size BIGINT；parse_status VARCHAR(16)；**parse_result_json JSON**；created_at；**deleted_at** | IDX(conversation_id) | parse_status: pending/parsing/parsed/failed；parse_result_json 存表头/行列数/摘要/sheet 清单 |
| `analysis_tasks` | id PK；conversation_id；user_id；input_text TEXT；task_status VARCHAR(16)；current_step INT；started_at/finished_at DATETIME；error_message TEXT；created_at | IDX(conversation_id, task_status) | task_status: queued/running/success/failed/cancelled；互斥查询"会话无运行中任务" |
| `analysis_results` | id PK；task_id（UK）；conversation_id；problem_definition TEXT；key_metrics_json JSON；evidence_list_json JSON；conclusion_text TEXT；missing_data_text TEXT；next_action_text TEXT；result_markdown LONGTEXT；result_file_path VARCHAR(512)；created_at | UK(task_id)；IDX(conversation_id) | 六段式落库；结论为数据资产，**不随软删清理**（随会话删除） |
| `context_summaries` | id PK；conversation_id；start_seq_no/end_seq_no INT；summary_text TEXT；created_at | IDX(conversation_id, end_seq_no) | 上下文摘要（5.3） |
| `websocket_tokens` | id PK；user_id；conversation_id；token VARCHAR(64)；expires_at DATETIME；consumed_at DATETIME；created_at | **UK(token)**；IDX(user_id, conversation_id) | 一次性 WS 令牌（6.5）；过期行随定时任务清理 |
| `system_configs` | id PK；config_key VARCHAR(64)；config_value TEXT；**config_type VARCHAR(16)**；config_group VARCHAR(32)；description VARCHAR(255)；updated_at | UK(config_key) | config_type: bool/int/float/string/json；热更新来源（6.9） |
| `task_logs` | id PK；task_id；log_level VARCHAR(8)；log_type VARCHAR(32)；log_content TEXT；created_at | IDX(task_id, created_at) | 任务日志；保留 90 天（9.6） |

**新增业务表：**

| 表 | 字段（类型） | 索引 / 约束 | 说明 |
|---|---|---|---|
| `data_sources` | id PK；name VARCHAR(64)；db_type VARCHAR(16)；host VARCHAR(128)；port INT；database VARCHAR(64)；username VARCHAR(64)；password_encrypted VARCHAR(512)；is_readonly TINYINT；is_enabled TINYINT；created_at/updated_at | UK(name) | 外部数据源连接（管理后台维护）；内置示例库也登记为一条预置数据源；密码 AES 加密（密钥走环境变量） |
| `audit_logs` | id PK；user_id；action_type VARCHAR(32)；target_type VARCHAR(32)；target_id VARCHAR(64)；before_value JSON；after_value JSON；ip VARCHAR(64)；user_agent VARCHAR(255)；created_at | IDX(user_id, created_at)；IDX(target_type, target_id) | 管理操作审计（配置/数据源/开关变更）；只增不改 |
| `llm_calls` | id PK；task_id；conversation_id；user_id；model VARCHAR(64)；prompt_tokens INT；completion_tokens INT；total_tokens INT；cost DECIMAL(10,4)；latency_ms INT；status VARCHAR(16)；error_message TEXT；created_at | IDX(task_id)；IDX(created_at) | 每次 LLM 请求一行（含 Agent 循环内全部调用）；cost 单位元 |

### 9.2 认证中心表（新 schema `auth_` 前缀）

| 表 | 字段（类型） | 索引 / 约束 | 说明 |
|---|---|---|---|
| `auth_users` | id PK；username VARCHAR(64)；password_hash VARCHAR(255)；display_name VARCHAR(64)；role VARCHAR(16)；status VARCHAR(16)；created_at | UK(username) | 认证中心用户（初始化创建管理员与示例用户） |
| `auth_clients` | id PK；client_id VARCHAR(64)；client_secret_hash VARCHAR(255)；redirect_uris JSON；scopes JSON；status VARCHAR(16)；created_at | UK(client_id) | OAuth 客户端（预置业务系统客户端） |
| `auth_auth_codes` | id PK；code VARCHAR(64)；client_id；user_id；redirect_uri VARCHAR(512)；scope JSON；expires_at DATETIME；consumed_at DATETIME；created_at | UK(code) | 授权码（5 分钟有效）；过期随定时任务清理 |
| `auth_refresh_tokens` | id PK；token_hash VARCHAR(128)；client_id；user_id；expires_at DATETIME；revoked_at DATETIME；created_at | UK(token_hash)；IDX(user_id) | 刷新令牌（7 天）；吊销/过期清理 |

### 9.3 功能开关

不新增表：使用 `system_configs`，`config_group = 'feature_flag'`，如 `flag_attachment`、`flag_export`、`flag_tool_db_query`、`flag_tool_command_exec` 等。

### 9.4 文件存储目录规范（对齐文档 2.1.8）

| 目录 | 内容 | 归属 |
|---|---|---|
| `uploads/{user_id}/{conversation_id}/` | 附件 | 容器数据卷 `data/uploads` |
| `exports/{user_id}/{conversation_id}/` | 导出结果文件 | 容器数据卷 `data/exports` |
| `workspace/{user_id}/{conversation_id}/` | 临时中间文件 / 命令执行工作区 | 容器数据卷 `data/workspace` |

删除会话时级联删除：3 个对应目录 + 数据库记录（消息、附件、任务、结果、摘要、ws 令牌）。

### 9.5 索引与约束策略

- **逻辑外键索引**：所有关联列（user_id、conversation_id、task_id、message_id、client_id）一律建索引，保证关联查询不产生全表扫描。
- **唯一约束清单**：`users.external_user_id`、`users.username`、`messages(conversation_id, seq_no)`、`websocket_tokens.token`、`system_configs.config_key`、`data_sources.name`、`auth_users.username`、`auth_clients.client_id`、`auth_auth_codes.code`、`auth_refresh_tokens.token_hash`、`analysis_results.task_id`。
- **复合索引**：会话列表 `(user_id, last_message_at)`；任务互斥 `(conversation_id, task_status)`；日志查询 `(task_id, created_at)`；审计查询 `(user_id, created_at)`。
- **2C2G 节制原则**：每表索引 ≤ 4 个；不使用前缀索引以外的冗余索引；JSON 列不建索引（检索走 text_search 而非 SQL LIKE）。

### 9.6 数据保留与清理策略

| 数据 | 保留策略 | 执行 |
|---|---|---|
| conversations/messages/attachments（软删） | `deleted_at` 标记后保留 **90 天**（可配置），超期物理删除记录 + 文件目录 | 定时任务（每日一次，Redis 分布式锁防重） |
| analysis_results | 会话数据资产，随会话软删保留 90 天，随物理清理删除 | 同上 |
| task_logs | 保留 **90 天**，超期物理删除 | 同上 |
| llm_calls | 保留 **180 天**（成本审计窗口），超期物理删除 | 同上 |
| websocket_tokens / auth_auth_codes | 过期即清（每次过期扫描顺手删除） | 应用内 |
| auth_refresh_tokens | 过期/吊销清理 | 定时任务 |
| audit_logs | **永久保留**（合规审计，只增不改） | — |

> 说明：清理为"物理删除 + 文件目录删除"，删除前无归档（结论已在 analysis_results 留痕）；若后续需要离线归档，可在 V1.1 增加导出到对象存储。

### 9.7 Schema 迁移策略（Alembic）

- 初始化 = **基线迁移**（建全部表 + 索引）+ seed 脚本（默认配置、预置数据源、示例数据、默认管理员/示例用户），幂等可重复执行。
- 上线后任何 schema 变更（加表/加列/改索引）一律新增 Alembic 迁移文件，执行 `alembic upgrade head`；禁止手工改表。
- 2C2G 单机小表量：DDL 使用 MySQL 8 在线 DDL（ALGORITHM=INPLACE），无需锁表窗口。
- 迁移与业务版本解耦：后端镜像启动时自动执行 `alembic upgrade head`（幂等），失败则容器健康检查不过、不对外服务。

---

## 10. 示例业务场景（评审决策：商品目录优化 + 库存异常分析）

### 10.1 场景一：商品目录优化

**业务问题示例**："为什么夏季连衣裙品类的搜索点击率连续两周下滑？" / "哪些商品应该进入首页推荐位？"

**数据表（示例库 schema `scenario_goods`）：**

| 表 | 关键字段 | 规模（示例） |
|---|---|---|
| `products` | product_id、product_name、category_id、price、status、created_at | 800 行 |
| `categories` | category_id、category_name、parent_id、level | 40 行 |
| `search_exposures` | exposure_id、product_id、channel、exposure_date、exposure_count | 12 万行（近 90 天） |
| `clicks` | click_id、product_id、channel、click_date、click_count、click_rate | 12 万行 |
| `conversions` | conversion_id、product_id、channel、conv_date、order_count、conv_rate、gmv | 12 万行 |

**演示链路（完整问答路径）：**

1. 问："分析近 30 天连衣裙类目点击率变化的原因"
2. Agent：规划 → db_query 聚合日粒度点击率 → 发现下滑拐点 → 交叉查询曝光/点击/转化分渠道拆解 → 检索商品表确认主力 SKU 上下架变动 → 生成六段式结果（主因：某渠道曝光结构变化 + 主力 SKU 下架）
3. 追问："如果把下滑 SKU 的流量转移到新品，预计影响多少 GMV？"
4. Agent：基于已有证据 + 追加查询 → 输出量化影响与建议（下一步建议 ≥2 条）
5. 导出结果 Markdown → 下载

### 10.2 场景二：库存异常分析

**业务问题示例**："为什么华东仓 A 类商品库存周转率本月下降 20%？" / "哪些 SKU 存在积压风险？"

**数据表（示例库 schema `scenario_inventory`）：**

| 表 | 关键字段 | 规模（示例） |
|---|---|---|
| `inventory` | sku_id、warehouse_id、category、stock_qty、available_qty、updated_at | 2,000 行 |
| `inbound` | id、sku_id、warehouse_id、inbound_date、qty、supplier | 6 万行 |
| `outbound` | id、sku_id、warehouse_id、outbound_date、qty、order_type | 6 万行 |
| `sales` | id、sku_id、warehouse_id、sale_date、qty、amount | 6 万行 |

**演示链路（完整问答路径）：**

1. 问："分析华东仓库存周转率下降的原因"
2. Agent：db_query 计算周转率（出库/平均库存）→ 拆 SKU 与品类 → 发现某品类入库激增但销量走平 → 关联销量表验证 → 六段式结果（主因：A 品类备货过量 + 该品类销量下滑）
3. 追问："哪些 SKU 需要优先处理积压？"
4. Agent：按库存天数排序 + 近 30 天销量 → 输出 Top 积压清单与建议动作
5. 导出/下载

---

## 11. 非功能需求

### 11.1 性能与资源（评审决策：小规格 2C2G，≤10 并发）

| 指标 | 目标 |
|---|---|
| 并发 | 同时在线 ≤10 会话连接；同时运行任务 ≤3（backend 单 worker + 异步队列，超出排队/拒绝并提示） |
| API 延迟 | p95 < 500ms（非分析类接口）；分析类接口异步不阻塞 |
| WS 延迟 | 消息推送端到端 < 1s |
| LLM 首 token | 配置模型能力内，流式边到边体验（本地仅转发，不缓存全文） |
| 附件解析 | 20MB 内 xlsx/csv 解析 ≤ 10s（异步队列，同一时间最多 1 个解析任务） |

**容器内存预算（2C2G = 2048MB）：**

| 容器 | 内存配额 | 关键调优 |
|---|---|---|
| `mysql` | 400MB | `innodb_buffer_pool_size=192M`、`max_connections=50`、`innodb_flush_log_at_trx_commit=2` |
| `backend` | 600MB | uvicorn 单 worker；LLM 流式逐块转发不聚合全文；`db_query` 结果行数上限（默认 500）；附件解析峰值另行占用预留池 |
| `auth` | 180MB | 单 worker，无额外依赖 |
| `redis` | 180MB | `maxmemory 128mb`、`maxmemory-policy allkeys-lru` |
| `frontend`(nginx) | 40MB | 静态资源 + 反代，无业务内存 |
| 预留（系统/日志/临时文件/附件解析峰值） | 650MB | 附件解析限制同时 1 个，避免峰值叠加；预留池兜底防 OOM |

> 说明：LLM 推理在云端 API 完成，本地只做流式转发，不占用 GPU/大内存，2C2G 的主要约束是 backend 进程内存与并发任务数，因此**单 worker + ≤3 并发任务**是本规格下的硬性设计。若实测附件解析或长任务叠加超预算，可通过管理后台调小附件大小上限或调低并发阈值（`system_configs` 可配置）。

### 11.2 安全

- 认证：OIDC 授权码 + JWT + HttpOnly Cookie；WS 一次性令牌
- 越权防护：所有资源按 user_id 归属校验；管理接口 admin 校验
- 注入防护：SQL 仅白名单只读；命令注入参数校验 + 黑名单
- 文件安全：路径规范化防目录穿越；类型/大小白名单
- 密钥管理：密码/密钥哈希存储；数据源密码加密（环境变量注入密钥）

### 11.3 可靠性

- 任务状态机防呆：queued → running → success/failed/cancelled，终态不可逆
- 崩溃恢复：服务重启后 running 态任务置 failed 并记录原因；WS 断线重连
- 幂等：任务创建、附件上传去重
- 限流：Redis 令牌桶（接口级 + 会话连接级）

### 11.4 可维护性与可配置性

- 全部运行参数（LLM、步数上限、超时、附件限制、功能开关）走 system_configs，管理后台热更新
- 结构化日志可过滤、可关联任务
- Docker Compose 一键部署；初始化脚本可重复执行（幂等）

### 11.5 兼容性

- 浏览器：Chrome/Edge/Firefox 近两年版本
- 数据库：MySQL 8.x；外部数据源支持 MySQL 8 / PostgreSQL 14+
- LLM：OpenAI 兼容 API（chat/completions + tools）

---

## 12. 验收标准（对照《项目实战要求》2.1.13 逐条映射）

| # | 验收项 | 满足方式 |
|---|---|---|
| 1 | 能通过授权登录进入聊天工作台 | OIDC 授权码全流程（6.1、8.1） |
| 2 | 能创建会话、上传附件、发送消息并查看历史记录 | 6.2/6.3/6.4、8.2 |
| 3 | 能通过实时连接看到分析过程状态、工具执行、最终结果 | 6.5/6.6、8.4 九类出站消息 |
| 4 | 能查询历史消息、切换旧会话并继续追问 | 5.3 多轮上下文 + 会话切换 |
| 5 | 能在结果区看到六部分结构化输出 | 6.6.3 六段式 + 7.4 结果区 |
| 6 | 能导出分析结果文件并重新下载 | 6.7、8.2 export/download |
| 7 | 能通过配置重载接口更新配置并即时生效 | 6.9、`POST /api/admin/reload` |
| 8 | 完成至少两个业务场景完整演示 | 第 10 章两条演示链路 |

---

## 13. 交付物清单

| # | 交付物 | 说明 |
|---|---|---|
| 1 | 前端工程 | Vue3 SPA：登录/回调/工作台/管理后台 |
| 2 | 后端工程 | FastAPI：业务 API + WS + Agent 分析引擎 |
| 3 | 认证中心服务 | OIDC Server（授权码/令牌/userinfo） |
| 4 | 数据库初始化脚本 | 建库 + 迁移 + 默认配置 + 预置数据源 + 管理员/示例用户 |
| 5 | 示例数据脚本 | 场景一/场景二全量表数据（含生成脚本） |
| 6 | 接口说明文档 | 8.1~8.4 全部接口 + 示例 |
| 7 | Docker Compose 编排 | mysql/redis/auth/backend/frontend 五服务 |
| 8 | 部署文档 | 云服务器初始化 → 起服 → 验证 → 运维 |
| 9 | 演示链路说明 | 两组场景的演示脚本（问题 → 预期结果 → 讲解点） |

---

## 14. 里程碑建议

| 阶段 | 内容 | 输出 |
|---|---|---|
| M1 基础骨架 | 认证中心 + 登录流程 + 会话/消息 CRUD + WS 通道 | 可登录、可建会话、可收发消息 |
| M2 分析引擎 | Agent 循环 + 工具集 + 六段式输出 + 任务状态机 | 单场景可跑通一轮归因 |
| M3 工作台完善 | 附件、结果区、取消、历史追问、摘要压缩 | 场景一全链路演示 |
| M4 管理后台 | 配置/数据源/开关/日志 + 热更新 | 管理验收项全过 |
| M5 场景二 + 工程化 | 库存场景、示例数据、Compose、部署文档、接口文档 | 全量验收 |

---

## 15. 风险与开放问题

| # | 风险/问题 | 等级 | 应对 |
|---|---|---|---|
| 1 | 纯 LLM 归因结果不稳定，演示翻车 | 高 | 混合路线结构化约束 + 步骤/超时上限 + 兜底部分输出；演示脚本预演 |
| 2 | LLM API 成本与限流 | 中 | 配置化模型切换；单轮步数上限控制 token 消耗 |
| 3 | 命令执行沙箱安全 | 高 | 工作区隔离 + 黑名单 + 超时 + 日志审计；生产可整体禁用 |
| 4 | xlsx 大数据量解析性能 | 中 | 异步队列 + 行数上限 |
| 5 | 2C2G 资源紧张：五容器共存 + LLM 流式 + 附件解析峰值叠加 | 中 | 容器 `mem_limit` 配额（11.1 预算表）+ backend 单 worker + 并发硬上限（≤10 在线 / ≤3 运行）+ Redis 限流；附件解析限并发 1；超预算可在管理后台下调附件上限与并发阈值 |
| 6 | 外部数据源口径映射（表结构未知） | 中 | 系统提示词注入 schema 描述；演示以内置示例库为主 |

**开放问题（不影响本期开发，留待 V1.1）：** 多租户、主动监控告警、PDF 附件、多模型路由、指标语义层。
