# P2 经营归因分析系统

面向通用经营分析场景的多轮归因分析系统：围绕业务问题持续追问、补充证据、生成六部分结构化归因报告。
演示场景：**库存异常分析**、**客户行为分析**（含 3 个月模拟数据与 7 月异常注入）。

## 快速开始

```bash
pip install -r requirements.txt
copy .env.example .env   # 填写 DEEPSEEK_API_KEY（无 key 走离线降级）

python scripts/gen_data.py    # 生成演示数据 + 管理员（admin/admin123）
python run.py                 # http://127.0.0.1:8001

python -m pytest tests -v     # 运行测试
```

## 核心能力

- Text2SQL：schema/指标口径注入 → SQL 生成 → 只读校验（禁写操作）→ 执行 → 失败自愈一次
- 六部分结果：问题定义 / 关键指标 / 证据列表 / 归因结论 / 待补充数据 / 下一步建议
- 实时链路：WebSocket（一次性 ws-token），事件 message_start / tool_start / tool_finish / task_status / result_ready / error / done
- 会话/附件/导出：Markdown + JSON
- 管理：配置热更新（POST /api/admin/reload）、任务日志

## 主要接口

- `POST /api/auth/login`、`GET /api/auth/me`
- `POST /api/chat/create`、`GET /api/chat/ls`、`GET /api/chat/ls/{id}`
- `POST /api/chat/ws-token`、`WS /api/chat/ws/chat?token=&conversation_id=`
- `GET /api/tasks/{id}`、`GET /api/results/{id}`、`GET /api/results/{id}/export`
- `POST /api/admin/reload`、`GET /api/admin/logs`

## 说明

- 演示账号：admin / admin123（单管理员，极简）
- 附件为最小实现（上传/删除/下载，不做内容解析）
- 离线模式下 SQL 与归因结果为确定性示例，配置 DeepSeek key 后为真实分析
