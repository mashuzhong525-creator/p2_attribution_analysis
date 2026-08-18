# 概要设计文档：经营归因分析系统

## 1. 技术选型

| 层次 | 技术方案 | 版本 | 选型理由 |
|------|----------|------|----------|
| 后端框架 | FastAPI | 0.100+ | 高性能异步API框架，原生WebSocket支持，自动OpenAPI文档 |
| 编程语言 | Python | 3.12 | 丰富的AI/数据分析生态，异步支持完善 |
| 数据库 | SQLite | 3.x | Demo阶段零配置，可迁移至MySQL/PostgreSQL |
| LLM服务 | DeepSeek API | - | 高性价比中文大模型，OpenAI兼容接口 |
| HTTP客户端 | httpx | 0.24+ | 异步HTTP客户端，用于调用LLM API |
| 数据校验 | Pydantic | 2.x | 请求/响应模型校验，JSON Schema生成 |
| 配置管理 | pydantic-settings | 2.x | 类型安全的配置管理，支持.env文件 |
| 前端框架 | Vanilla JS + HTML/CSS | - | Demo阶段无构建依赖，快速交付 |
| 异步服务器 | Uvicorn | 0.23+ | ASGI服务器，支持WebSocket |
| 包管理 | pip + requirements.txt | - | 简单直接 |

## 2. 系统架构

### 2.1 整体架构图（文字描述）

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (前端)                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ 会话列表  │  │  聊天对话区   │  │  结果展示区       │   │
│  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘   │
│       │               │ WebSocket          │             │
│       │ HTTP          │ Connection         │ HTTP        │
└───────┼───────────────┼───────────────────┼─────────────┘
        │               │                   │
┌───────▼───────────────▼───────────────────▼─────────────┐
│                  FastAPI Backend                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────┐  │
│  │ Auth    │ │ Chat    │ │Attach   │ │ Task/Result  │  │
│  │ Module  │ │ Module  │ │ Module  │ │ Module       │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └──────┬───────┘  │
│       │           │           │             │           │
│  ┌────▼───────────▼───────────▼─────────────▼───────┐   │
│  │              Analysis Engine                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────────────┐  │   │
│  │  │Text2SQL │ │Executor │ │ Attribution Gen   │  │   │
│  │  │ Generator│ │(安全执行)│ │ (归因结论生成)    │  │   │
│  │  └────┬────┘ └────┬────┘ └────────┬─────────┘  │   │
│  │       │          │               │              │   │
│  │  ┌────▼──────────▼───────────────▼─────────┐   │   │
│  │  │          SQL Guard (安全守卫)            │   │   │
│  │  └─────────────────────────────────────────┘   │   │
│  └───────────────────────────────────────────────┘   │
│       │                                              │
│  ┌────▼──────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ SQLite DB │  │ File Sys │  │ LLM (DeepSeek)   │ │
│  │           │  │(附件/导出)│  │                  │ │
│  └───────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 2.2 分层架构

| 层次 | 模块 | 职责 |
|------|------|------|
| **API层** | auth_routes, chat_routes, attachment_routes, task_routes, admin_routes | HTTP路由、参数校验、响应序列化 |
| **业务层** | auth, chat, tasks, results, admin, tokens | 业务逻辑、状态管理、权限校验 |
| **引擎层** | engine/schema, engine/pipeline, engine/sql_gen, engine/sql_guard, engine/executor, engine/attribution | Text2SQL生成、安全执行、归因分析 |
| **基础设施层** | database, config, llm, ws, utils | 数据库连接、配置管理、LLM调用、WebSocket、工具函数 |

## 3. 核心流程

### 3.1 用户登录流程

```
用户输入用户名密码
    → auth_routes.login()
    → auth.login() 校验密码
    → 生成access_token（UUID）
    → 存入内存token字典
    → 返回token和用户信息
    → 前端保存token到localStorage
```

### 3.2 分析任务执行流程（核心）

```
用户在WebSocket发送问题
    → ws.py接收消息
    → pipeline.run_analysis() 同步执行：
        1. tasks.create_task() — 创建任务（校验无重复运行任务）
        2. tasks.transition(queued→running) — 状态流转
        3. emit: message_start
        4. emit: task_status(running, "生成SQL")
        5. sql_gen.generate_sql() — 调用LLM生成SQL
            → schema注入 + 指标定义 + 问题
            → llm.chat_completion()
            → 正则提取SQL
            → sql_guard.validate_select() 校验
        6. emit: tool_start(sql_generation)
        7. emit: tool_finish(sql_generation)
        8. emit: task_status(running, "执行查询")
        9. executor.execute_with_retry() — 执行SQL
            → 只读连接 + 结果集限制
            → 失败时调用LLM修正SQL重试一次
        10. emit: tool_start(sql_execution)
        11. emit: tool_finish(sql_execution)
        12. emit: task_status(running, "生成归因结论")
        13. attribution.generate_attribution() — 生成归因
            → 构建Prompt（问题+SQL+数据）
            → LLM调用获取JSON
            → 解析为六维度结构
            → 失败时降级为确定性结果
        14. emit: message_delta（增量文本）
        15. results.save_result() — 保存结果
        16. tasks.transition(running→success)
        17. emit: result_ready
        18. emit: done

异常处理：
    → tasks.mark_failed()
    → emit: error
```

### 3.3 文件存储流程

```
附件上传：
    POST /api/attachment/upload
    → 校验conversation_id有效性
    → 保存文件到 uploads/{user_id}/{conversation_id}/
    → 记录附件元数据到attachments表
    → 返回附件信息

结果导出：
    GET /api/results/{task_id}/export
    → 查询分析结果
    → 根据format生成Markdown或JSON文件
    → 保存到 exports/{user_id}/{conversation_id}/
    → 返回文件流
```

### 3.4 会话删除流程

```
POST /api/chat/delete
    → 在事务中执行：
        1. 删除 attachments 记录 + 物理文件
        2. 删除 task_logs 记录
        3. 删除 analysis_results 记录
        4. 删除 analysis_tasks 记录
        5. 删除 context_summaries 记录
        6. 删除 websocket_tokens 记录
        7. 删除 messages 记录
        8. 删除 conversations 记录
        9. 删除 uploads/ 和 exports/ 目录
    → 返回删除数量
```

## 4. 数据结构

### 4.1 分析结果六维结构

```python
# 归因分析结果结构
{
    "problem_definition": str,      # 问题定义
    "key_metrics": [                # 关键指标数组
        {
            "metric_name": str,     # 指标名称
            "metric_value": str,    # 指标值
            "metric_unit": str,     # 指标单位
            "metric_period": str    # 统计周期
        }
    ],
    "evidence_list": [              # 证据列表数组
        {
            "source_type": str,    # 来源类型：database/file/text
            "source_name": str,    # 来源名称
            "evidence_text": str,  # 证据内容
            "related_metric": str,  # 关联指标
            "confidence": float    # 置信度 0-1
        }
    ],
    "conclusion_text": str,         # 归因结论（自然语言）
    "missing_data_text": str,       # 待补充数据
    "next_action_text": str        # 下一步建议
}
```

### 4.2 WebSocket消息结构

```python
# 统一消息格式
{
    "type": str,                    # 消息类型标识
    "task_id": int,                 # 关联任务ID
    # ... 各类型特有字段
}
```

### 4.3 任务状态机

```
         ┌──────────┐
         │  queued  │
         └────┬─────┘
              │ transition()
         ┌────▼─────┐
         │ running  │
         └──┬───┬───┘
      成功  │   │  失败/取消
    ┌───────┘   └────────┐
    ▼                    ▼
┌─────────┐  ┌───────────┐
│ success │  │  failed   │
└─────────┘  │ cancelled │
             └───────────┘
```

合法状态转换：`queued→running`，`running→success`，`running→failed`，`running→cancelled`

## 5. 安全设计

### 5.1 SQL安全守卫规则

- 仅允许SELECT语句
- 阻止18种危险关键字：DELETE、UPDATE、INSERT、DROP、ALTER、ATTACH、DETACH、CREATE、EXEC、EXECUTE、GRANT、REVOKE、PRAGMA、REPLACE、VACUUM、BEGIN、COMMIT、ROLLBACK
- 剥离SQL注释
- 仅允许单条SQL语句

### 5.2 认证与授权

- API接口通过Bearer Token认证
- WebSocket通过一次性令牌认证（UUID + TTL + 用户/会话绑定）
- 管理接口通过角色校验（admin）
- 令牌存储在内存字典中（Demo阶段）

## 6. 降级策略

| 场景 | 降级方案 |
|------|----------|
| LLM API不可用 | 使用离线确定性模式，返回预设SQL和模板化归因结果 |
| SQL生成失败 | 返回错误信息，标记任务为failed |
| SQL执行失败 | 调用LLM修正SQL重试一次，仍失败则标记failed |
| 归因解析失败 | 使用fallback模式从查询结果构建简化归因 |
| WebSocket断开 | 客户端自动重连，服务端保留任务状态可查询 |

## 7. 部署架构

```
┌──────────────────────────────────┐
│         Docker Container          │
│  ┌────────────────────────────┐  │
│  │   Uvicorn (Port 8001)     │  │
│  │   ┌──────────────────┐    │  │
│  │   │   FastAPI App    │    │  │
│  │   └──────────────────┘    │  │
│  ├────────────────────────────┤  │
│  │   /data (Volume)           │  │
│  │   ├── db.sqlite3           │  │
│  │   ├── uploads/              │  │
│  │   └── exports/              │  │
│  ├────────────────────────────┤  │
│  │   /web/static               │  │
│  │   └── index.html            │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```
