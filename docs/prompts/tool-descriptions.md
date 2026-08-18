# 工具集 LLM 描述（function calling / tools 参数）

> 关联 PRD：6.6.1 工具集 / 6.6.4 安全边界
> 使用方式：作为 Chat Completions `tools` 参数原样传入（OpenAI 兼容格式）。
> 维护约定：与 `agent-system-prompt.md` 中"工具调用规范"同步维护；工具开关受 `system_configs` 的 `flag_tool_*` 控制，被禁用的工具不注入。

---

## tools 参数（JSON）

```json
[
  {
    "type": "function",
    "function": {
      "name": "db_query",
      "description": "对当前数据源执行只读 SQL 查询（仅 SELECT）。用于获取指标数据、拆解因子、交叉验证。示例：按日期聚合点击率、按渠道拆解曝光量、关联商品表定位主力 SKU。",
      "parameters": {
        "type": "object",
        "properties": {
          "sql": {
            "type": "string",
            "description": "只读 SELECT 语句。只能引用当前数据源中存在的表与字段；禁止 INSERT/UPDATE/DELETE/DDL；结果行数受上限约束（默认 500 行），建议用 LIMIT/聚合控制返回量。"
          },
          "data_source_name": {
            "type": "string",
            "description": "目标数据源名称（内置示例库或管理员配置的外部数据源）；缺省使用当前会话绑定的数据源。"
          }
        },
        "required": ["sql"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "file_read",
      "description": "读取当前会话工作区内的文件（附件或中间文件）。用于查看用户上传的报表、导出数据、脚本输出。支持 csv/xlsx/txt；二进制文件返回结构摘要。",
      "parameters": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "相对会话工作区的文件路径（如 'uploads/xxx.csv'）；禁止绝对路径与 '..' 逃逸。"
          },
          "max_rows": {
            "type": "integer",
            "description": "最多读取行数（默认 100，上限 500），大文件请配合该参数控制。"
          }
        },
        "required": ["file_path"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "file_write",
      "description": "在会话工作区内写入中间结果或分析产物（如清洗后的 csv、中间表）。供后续工具复用或生成结果文件。",
      "parameters": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "相对会话工作区的目标路径；禁止绝对路径与 '..' 逃逸。"
          },
          "content": {
            "type": "string",
            "description": "文件内容（文本）。"
          }
        },
        "required": ["file_path", "content"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "text_search",
      "description": "在当前会话的附件与工作区文本中进行关键词全文检索，返回命中片段。用于在用户上传的报表/说明文档中定位关键内容。",
      "parameters": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "检索关键词（可含多个词，空格分隔表示 AND）。"
          },
          "max_results": {
            "type": "integer",
            "description": "最多返回命中条数（默认 10，上限 50）。"
          }
        },
        "required": ["query"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "command_exec",
      "description": "在当前会话工作区沙箱内执行命令（如 python 脚本做数据分析、文本处理）。输出为 stdout/stderr 摘要。注意：仅限工作区内操作，禁联网、禁系统级修改。",
      "parameters": {
        "type": "object",
        "properties": {
          "command": {
            "type": "string",
            "description": "要执行的命令。工作目录为会话工作区；禁止 rm -rf、curl/wget 外联、修改工作区外文件等危险操作；单次执行超时 60s。"
          },
          "timeout": {
            "type": "integer",
            "description": "超时秒数（默认 30，上限 60）。"
          }
        },
        "required": ["command"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "result_generate",
      "description": "将当前六段式结论生成为 Markdown 结果文件（存入 exports 目录），供用户导出/下载。在输出六段式 JSON 后按需调用一次。",
      "parameters": {
        "type": "object",
        "properties": {
          "markdown": {
            "type": "string",
            "description": "完整的 Markdown 结果文档（含问题定义、指标、证据、结论、待补充、建议）。"
          }
        },
        "required": ["markdown"]
      }
    }
  }
]
```

---

## 安全约束对照（执行端强制，LLM 侧仅提示）

| 工具 | LLM 侧提示 | 执行端强制 |
|---|---|---|
| `db_query` | 只读、限表 | 仅 SELECT；表白名单；行数上限 500；超时 30s |
| `file_read` / `file_write` | 限工作区 | 路径规范化校验，禁 `..` 逃逸与绝对路径越界 |
| `text_search` | 限当前会话 | 检索范围限会话附件/工作区 |
| `command_exec` | 沙箱、禁危险命令 | cwd 固定工作区；参数注入校验；危险命令黑名单；超时 60s 强杀 |
| `result_generate` | 固定目录 | 路径固定 `exports/{user_id}/{conversation_id}/` |

> 注：执行端校验独立于 LLM 侧描述，即使模型输出违规参数，也会被执行层拦截并记入 `task_logs`。
