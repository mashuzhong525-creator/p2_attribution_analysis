# 接口设计文档：经营归因分析系统

## 1. 概述

- 基础路径：`http://host:port`
- 协议：HTTP/1.1 + WebSocket
- 认证方式：Bearer Token（HTTP Header `Authorization: Bearer <token>`）
- 内容类型：`application/json`
- 字符编码：UTF-8

## 2. 认证接口

### 2.1 POST /api/auth/login — 用户登录

**请求**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**成功响应** (200):
```json
{
  "access_token": "uuid-string",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "display_name": "管理员",
    "role": "admin"
  }
}
```

**失败响应** (401):
```json
{
  "detail": "用户名或密码错误"
}
```

---

### 2.2 GET /api/auth/me — 获取当前用户信息

**请求头**: `Authorization: Bearer <token>`

**成功响应** (200):
```json
{
  "id": 1,
  "username": "admin",
  "display_name": "管理员",
  "role": "admin"
}
```

---

## 3. 会话接口

### 3.1 POST /api/chat/create — 创建会话

**请求**:
```json
{
  "title": "7月库存异常分析"
}
```

**成功响应** (200):
```json
{
  "conversation_id": 1,
  "title": "7月库存异常分析",
  "status": "active"
}
```

---

### 3.2 POST /api/chat/delete — 删除会话

**请求**:
```json
{
  "conversation_ids": [1, 2, 3]
}
```

**成功响应** (200):
```json
{
  "status": "ok",
  "deleted_count": 3
}
```

> 级联删除：消息、附件、任务、结果、上下文摘要、WS令牌均同步删除。

---

### 3.3 POST /api/chat/update — 更新会话

**请求**:
```json
{
  "conversation_id": 1,
  "title": "新标题"
}
```

**成功响应** (200):
```json
{
  "conversation_id": 1,
  "title": "新标题",
  "status": "active"
}
```

---

### 3.4 GET /api/chat/ls — 会话列表

**成功响应** (200):
```json
{
  "conversations": [
    {
      "conversation_id": 1,
      "title": "7月库存异常分析",
      "status": "active",
      "last_message_at": "2026-07-15T10:30:00"
    }
  ]
}
```

---

### 3.5 GET /api/chat/ls/{conversation_id} — 会话消息列表

**成功响应** (200):
```json
{
  "conversation_id": 1,
  "messages": [
    {
      "message_id": 1,
      "role": "user",
      "content": "分析7月东仓库存积压原因",
      "attachments": [],
      "created_at": "2026-07-15T10:30:00"
    },
    {
      "message_id": 2,
      "role": "assistant",
      "content": "根据分析，7月东仓库存积压主要原因如下...",
      "attachments": [],
      "created_at": "2026-07-15T10:30:05"
    }
  ]
}
```

---

## 4. 附件接口

### 4.1 POST /api/attachment/upload — 上传附件

**请求**: `multipart/form-data`
- `conversation_id`: 会话ID（form字段）
- `file`: 文件对象

**成功响应** (200):
```json
{
  "attachment_id": 1,
  "file_name": "sales_report.csv",
  "file_path": "uploads/1/2/sales_report.csv",
  "file_type": "text/csv",
  "file_size": 1024,
  "parse_status": "pending",
  "created_at": "2026-07-15T10:30:00"
}
```

---

### 4.2 POST /api/attachment/delete — 删除附件

**请求**:
```json
{
  "attachment_id": 1
}
```

**成功响应** (200):
```json
{
  "status": "ok"
}
```

---

### 4.3 GET /api/attachment/get — 下载附件

**请求参数**: `attachment_id` (query)

**成功响应** (200): 文件流，`Content-Disposition: attachment; filename=xxx`

---

### 4.4 GET /api/attachment/ls — 附件列表

**请求参数**: `conversation_id` (query)

**成功响应** (200):
```json
{
  "attachments": [
    {
      "attachment_id": 1,
      "file_name": "sales_report.csv",
      "file_type": "text/csv",
      "file_size": 1024,
      "parse_status": "pending",
      "created_at": "2026-07-15T10:30:00"
    }
  ]
}
```

---

## 5. WebSocket接口

### 5.1 POST /api/chat/ws-token — 获取WebSocket令牌

**请求**:
```json
{
  "conversation_id": 1
}
```

**成功响应** (200):
```json
{
  "websocket_token": "uuid-one-time-token",
  "expires_in": 300
}
```

> 令牌一次性使用，有效期300秒，绑定用户和会话。

---

### 5.2 WS /api/chat/ws/chat — WebSocket实时连接

**连接参数**:
- `websocket_token`: 一次性令牌
- `conversation_id`: 会话ID

**客户端发送消息格式**:
```json
{
  "type": "question",
  "text": "分析7月东仓库存异常原因"
}
```

**服务端推送消息类型**:

| type | 说明 | 关键字段 |
|------|------|----------|
| `message_start` | 本轮分析开始 | `task_id`, `conversation_id` |
| `message_delta` | 模型增量文本 | `task_id`, `delta_text` |
| `tool_start` | 工具开始执行 | `task_id`, `tool_name` |
| `tool_finish` | 工具执行完成 | `task_id`, `tool_name`, `tool_result_summary` |
| `task_status` | 任务状态变化 | `task_id`, `task_status`, `current_step` |
| `result_ready` | 结构化结果已生成 | `task_id`, `result_id` |
| `error` | 分析失败 | `task_id`, `error_message` |
| `done` | 本轮分析结束 | `task_id`, `finished_at` |

**示例推送**:
```json
{"type": "message_start", "task_id": 1, "conversation_id": 2}
{"type": "tool_start", "task_id": 1, "tool_name": "sql_generation"}
{"type": "tool_finish", "task_id": 1, "tool_name": "sql_generation", "tool_result_summary": "生成SQL: SELECT ..."}
{"type": "tool_start", "task_id": 1, "tool_name": "sql_execution"}
{"type": "tool_finish", "task_id": 1, "tool_name": "sql_execution", "tool_result_summary": "返回25行数据"}
{"type": "message_delta", "task_id": 1, "delta_text": "根据数据分析，"}
{"type": "result_ready", "task_id": 1, "result_id": 1}
{"type": "done", "task_id": 1, "finished_at": "2026-07-15T10:30:10"}
```

---

## 6. 任务与结果接口

### 6.1 GET /api/tasks/{task_id} — 查询任务状态

**成功响应** (200):
```json
{
  "task_id": 1,
  "conversation_id": 1,
  "task_status": "success",
  "current_step": "完成",
  "started_at": "2026-07-15T10:30:00",
  "finished_at": "2026-07-15T10:30:10",
  "error_message": null
}
```

---

### 6.2 GET /api/results/{task_id} — 查询分析结果

**成功响应** (200):
```json
{
  "task_id": 1,
  "problem_definition": "分析7月东仓库存积压原因",
  "key_metrics": [
    {
      "metric_name": "库存周转率",
      "metric_value": "1.2",
      "metric_unit": "次/月",
      "metric_period": "2026年7月"
    }
  ],
  "evidence_list": [
    {
      "source_type": "database",
      "source_name": "inventory表",
      "evidence_text": "东仓7月库存量较6月增长60%",
      "related_metric": "库存量",
      "confidence": 0.95
    }
  ],
  "conclusion_text": "7月东仓库存积压主要原因是出库量骤降...",
  "missing_data_text": "缺少供应商交货延迟数据和促销计划数据",
  "next_action_text": "1. 核实东仓出库量骤降的业务原因\n2. 检查供应商交货是否异常"
}
```

---

### 6.3 GET /api/results/{task_id}/export — 导出结果

**请求参数**: `format` (query, 可选值: `md` / `json`, 默认 `md`)

**成功响应** (200): 文件流下载

---

## 7. 管理接口

### 7.1 GET /api/admin/config — 查询系统配置

**成功响应** (200):
```json
{
  "configs": [
    {
      "config_key": "llm_model",
      "config_value": "deepseek-chat",
      "config_group": "llm",
      "updated_at": "2026-07-15T00:00:00"
    }
  ]
}
```

---

### 7.2 POST /api/admin/reload — 热更新配置

**成功响应** (200):
```json
{
  "status": "ok",
  "message": "配置已重新加载"
}
```

---

### 7.3 GET /api/admin/logs — 查询运行日志

**请求参数**: `offset` (query), `limit` (query)

**成功响应** (200):
```json
{
  "logs": [
    {
      "id": 1,
      "task_id": 1,
      "log_level": "INFO",
      "log_type": "step",
      "log_content": "开始生成SQL",
      "created_at": "2026-07-15T10:30:01"
    }
  ],
  "total": 10
}
```

---

## 8. 通用响应格式

### 8.1 错误响应

```json
{
  "detail": "错误描述信息"
}
```

### 8.2 HTTP状态码说明

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 / 认证失败 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 状态冲突（如重复运行任务） |
| 500 | 服务器内部错误 |

---

## 9. 接口清单汇总

| 序号 | 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|------|
| 1 | POST | /api/auth/login | 否 | 用户登录 |
| 2 | GET | /api/auth/me | 是 | 获取当前用户 |
| 3 | POST | /api/chat/create | 是 | 创建会话 |
| 4 | POST | /api/chat/delete | 是 | 删除会话 |
| 5 | POST | /api/chat/update | 是 | 更新会话标题 |
| 6 | GET | /api/chat/ls | 是 | 会话列表 |
| 7 | GET | /api/chat/ls/{id} | 是 | 会话消息列表 |
| 8 | POST | /api/chat/ws-token | 是 | 获取WS令牌 |
| 9 | WS | /api/chat/ws/chat | 令牌 | 实时分析通道 |
| 10 | POST | /api/attachment/upload | 是 | 上传附件 |
| 11 | POST | /api/attachment/delete | 是 | 删除附件 |
| 12 | GET | /api/attachment/get | 是 | 下载附件 |
| 13 | GET | /api/attachment/ls | 是 | 附件列表 |
| 14 | GET | /api/tasks/{id} | 是 | 查询任务状态 |
| 15 | GET | /api/results/{id} | 是 | 查询分析结果 |
| 16 | GET | /api/results/{id}/export | 是 | 导出结果文件 |
| 17 | GET | /api/admin/config | 管理员 | 查询系统配置 |
| 18 | POST | /api/admin/reload | 管理员 | 热更新配置 |
| 19 | GET | /api/admin/logs | 管理员 | 查询运行日志 |
| 20 | GET | /health | 否 | 健康检查 |
