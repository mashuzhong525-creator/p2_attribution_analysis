# DATA 数据设计文档：经营归因分析系统

## 1. 数据库概述

本系统使用 SQLite 作为主数据库（Demo阶段），生产环境可迁移至 MySQL/PostgreSQL。数据库包含 **11张业务表** 和 **9张业务数据表（示例场景）**。

## 2. 业务表设计

### 2.1 users — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户唯一标识 |
| external_user_id | TEXT | UNIQUE, NULLABLE | 外部系统用户ID（OAuth场景） |
| username | TEXT | NOT NULL, UNIQUE | 用户名 |
| display_name | TEXT | NULLABLE | 显示名称 |
| role | TEXT | NOT NULL, DEFAULT 'analyst' | 角色：analyst / admin |
| status | TEXT | NOT NULL, DEFAULT 'active' | 状态：active / disabled |
| created_at | TEXT | NOT NULL | 创建时间 ISO格式 |
| updated_at | TEXT | NOT NULL | 更新时间 ISO格式 |

**索引**: `idx_users_username ON users(username)`

---

### 2.2 conversations — 会话表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 会话唯一标识 |
| user_id | INTEGER | NOT NULL, FK→users.id | 所属用户 |
| title | TEXT | NOT NULL | 会话标题 |
| status | TEXT | NOT NULL, DEFAULT 'active' | 状态：active / archived / deleted |
| last_message_at | TEXT | NULLABLE | 最后消息时间 |
| created_at | TEXT | NOT NULL | 创建时间 |
| updated_at | TEXT | NOT NULL | 更新时间 |

**索引**: `idx_conv_user ON conversations(user_id)`, `idx_conv_last_msg ON conversations(last_message_at)`

---

### 2.3 messages — 消息表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 消息唯一标识 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 所属会话 |
| role | TEXT | NOT NULL | 角色：user / assistant / system |
| message_type | TEXT | NOT NULL, DEFAULT 'text' | 类型：text / tool_call / tool_result |
| content | TEXT | NOT NULL | 消息内容 |
| tool_name | TEXT | NULLABLE | 关联工具名称 |
| tool_status | TEXT | NULLABLE | 工具状态 |
| seq_no | INTEGER | NOT NULL | 消息序列号（会话内递增） |
| created_at | TEXT | NOT NULL | 创建时间 |

**索引**: `idx_msg_conv ON messages(conversation_id)`, `idx_msg_seq ON messages(conversation_id, seq_no)`

---

### 2.4 attachments — 附件表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 附件唯一标识 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 所属会话 |
| message_id | INTEGER | NULLABLE, FK→messages.id | 关联消息 |
| file_name | TEXT | NOT NULL | 文件名 |
| file_path | TEXT | NOT NULL | 存储路径 |
| file_type | TEXT | NOT NULL | 文件MIME类型 |
| file_size | INTEGER | NOT NULL | 文件大小（字节） |
| parse_status | TEXT | NOT NULL, DEFAULT 'pending' | 解析状态：pending / parsed / failed |
| created_at | TEXT | NOT NULL | 创建时间 |

**索引**: `idx_att_conv ON attachments(conversation_id)`

---

### 2.5 analysis_tasks — 分析任务表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 任务唯一标识 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 所属会话 |
| user_id | INTEGER | NOT NULL, FK→users.id | 发起用户 |
| input_text | TEXT | NOT NULL | 用户输入的分析问题 |
| task_status | TEXT | NOT NULL, DEFAULT 'queued' | 状态：queued/running/success/failed/cancelled |
| current_step | TEXT | NULLABLE | 当前执行步骤 |
| started_at | TEXT | NULLABLE | 开始时间 |
| finished_at | TEXT | NULLABLE | 完成时间 |
| error_message | TEXT | NULLABLE | 错误信息 |

**索引**: `idx_task_conv ON analysis_tasks(conversation_id)`, `idx_task_status ON analysis_tasks(task_status)`

---

### 2.6 analysis_results — 分析结果表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 结果唯一标识 |
| task_id | INTEGER | NOT NULL, FK→analysis_tasks.id | 关联任务 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 所属会话 |
| problem_definition | TEXT | NULLABLE | 问题定义 |
| key_metrics_json | TEXT | NULLABLE | 关键指标JSON数组 |
| evidence_list_json | TEXT | NULLABLE | 证据列表JSON数组 |
| conclusion_text | TEXT | NULLABLE | 归因结论 |
| missing_data_text | TEXT | NULLABLE | 待补充数据 |
| next_action_text | TEXT | NULLABLE | 下一步建议 |
| result_markdown | TEXT | NULLABLE | 完整Markdown结果 |
| result_file_path | TEXT | NULLABLE | 导出文件路径 |
| created_at | TEXT | NOT NULL | 创建时间 |

**索引**: `idx_result_task ON analysis_results(task_id)`, `idx_result_conv ON analysis_results(conversation_id)`

---

### 2.7 context_summaries — 上下文摘要表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 摘要唯一标识 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 所属会话 |
| start_seq_no | INTEGER | NOT NULL | 起始消息序列号 |
| end_seq_no | INTEGER | NOT NULL | 结束消息序列号 |
| summary_text | TEXT | NOT NULL | 摘要文本 |
| created_at | TEXT | NOT NULL | 创建时间 |

---

### 2.8 websocket_tokens — WebSocket令牌表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 令牌唯一标识 |
| user_id | INTEGER | NOT NULL, FK→users.id | 所属用户 |
| conversation_id | INTEGER | NOT NULL, FK→conversations.id | 关联会话 |
| token | TEXT | NOT NULL, UNIQUE | 令牌字符串（UUID） |
| expires_at | TEXT | NOT NULL | 过期时间 |
| consumed_at | TEXT | NULLABLE | 消费时间（一次性） |
| created_at | TEXT | NOT NULL | 创建时间 |

**索引**: `idx_ws_token ON websocket_tokens(token)`

---

### 2.9 system_configs — 系统配置表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 配置唯一标识 |
| config_key | TEXT | NOT NULL, UNIQUE | 配置键 |
| config_value | TEXT | NOT NULL | 配置值 |
| config_group | TEXT | NOT NULL | 配置分组 |
| updated_at | TEXT | NOT NULL | 更新时间 |

---

### 2.10 task_logs — 任务日志表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 日志唯一标识 |
| task_id | INTEGER | NOT NULL, FK→analysis_tasks.id | 关联任务 |
| log_level | TEXT | NOT NULL | 日志级别：INFO / WARN / ERROR |
| log_type | TEXT | NOT NULL | 日志类型：step / tool / system |
| log_content | TEXT | NOT NULL | 日志内容 |
| created_at | TEXT | NOT NULL | 创建时间 |

**索引**: `idx_log_task ON task_logs(task_id, created_at)`

---

## 3. 业务数据表（示例场景）

### 3.1 inventory — 库存表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| warehouse | TEXT | NOT NULL | 仓库 |
| sku | TEXT | NOT NULL | SKU编码 |
| quantity | INTEGER | NOT NULL | 库存数量 |
| record_date | TEXT | NOT NULL | 记录日期 |

### 3.2 inbound — 入库表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| warehouse | TEXT | NOT NULL | 仓库 |
| sku | TEXT | NOT NULL | SKU编码 |
| qty | INTEGER | NOT NULL | 入库数量 |
| record_date | TEXT | NOT NULL | 记录日期 |

### 3.3 outbound — 出库表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| warehouse | TEXT | NOT NULL | 仓库 |
| sku | TEXT | NOT NULL | SKU编码 |
| qty | INTEGER | NOT NULL | 出库数量 |
| record_date | TEXT | NOT NULL | 记录日期 |

### 3.4 sales — 销量表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| warehouse | TEXT | NOT NULL | 仓库 |
| sku | TEXT | NOT NULL | SKU编码 |
| quantity | INTEGER | NOT NULL | 销量 |
| amount | REAL | NOT NULL | 销售额 |
| record_date | TEXT | NOT NULL | 记录日期 |

### 3.5 customers — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| user_id | TEXT | NOT NULL | 用户ID |
| register_date | TEXT | NOT NULL | 注册日期 |
| city | TEXT | NULLABLE | 城市 |

### 3.6 visits — 访问事件表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| user_id | TEXT | NOT NULL | 用户ID |
| page | TEXT | NOT NULL | 访问页面 |
| event_date | TEXT | NOT NULL | 事件日期 |

### 3.7 add_to_cart — 加购事件表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| user_id | TEXT | NOT NULL | 用户ID |
| sku | TEXT | NOT NULL | SKU编码 |
| event_date | TEXT | NOT NULL | 事件日期 |

### 3.8 orders — 下单事件表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PK | 唯一标识 |
| user_id | TEXT | NOT NULL | 用户ID |
| sku | TEXT | NOT NULL | SKU编码 |
| amount | REAL | NOT NULL | 订单金额 |
| event_date | TEXT | NOT NULL | 事件日期 |

---

## 4. 文件存储规范

| 类型 | 路径格式 | 说明 |
|------|----------|------|
| 附件存储 | `uploads/{user_id}/{conversation_id}/` | 用户上传的分析资料 |
| 导出结果 | `exports/{user_id}/{conversation_id}/` | 导出的分析报告文件 |
| 临时文件 | `workspace/{user_id}/{conversation_id}/` | 分析过程中的中间文件 |

## 5. ER关系图（文字描述）

```
users 1──N conversations
conversations 1──N messages
conversations 1──N attachments
conversations 1──N analysis_tasks
conversations 1──N context_summaries
analysis_tasks 1──1 analysis_results
analysis_tasks 1──N task_logs
conversations 1──N websocket_tokens
messages 1──N attachments (可选关联)
```

## 6. 初始化数据

| 数据项 | 内容 |
|--------|------|
| 默认管理员 | username=admin, password=admin123, role=admin |
| 系统配置 | LLM模型参数、默认分析场景配置 |
| 库存场景数据 | 3个月（2026-05~07），含东仓异常数据 |
| 客户行为数据 | 3个月（2026-05~07），含转化率下降异常 |
