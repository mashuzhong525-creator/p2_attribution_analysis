# 提示词资产清单（Prompt Assets）

> 本目录集中存放经营归因分析系统的全部提示词（prompt）资产，供开发与调优直接引用。
> 依据：《经营归因分析系统-需求规格说明书PRD.md》6.6 分析引擎章节。
> 状态：**v0.1 草案**——待 M2 分析引擎开发时结合真实表结构、真实模型与演示场景实测校准。

## 资产一览

| 文件 | 用途 | 关联 PRD 章节 | 状态 |
|---|---|---|---|
| `agent-system-prompt.md` | 归因 Agent 主系统提示词（角色/流程/约束/输出模板） | 6.6.2 Agent 循环 | 草案 |
| `tool-descriptions.md` | 6 个工具的 function calling 描述（JSON） | 6.6.1 工具集 | 草案 |
| `context-summary-prompt.md` | 多轮追问的上下文摘要压缩提示词 | 5.3 上下文管理 | 草案 |

## 使用说明

1. **主提示词**（`agent-system-prompt.md`）由代码按"模板 + 动态注入"拼装：
   - 动态注入部分：`{data_source_schema}`（当前数据源表结构描述）、`{scenario_prompt}`（当前业务场景说明）、`{attachment_meta}`（会话附件元信息）、`{history_summary}`（历史摘要）。
   - 注入数据来自：`data_sources` 配置 / 场景示例库 schema / `attachments` 表 / `context_summaries` 表。
2. **工具描述**（`tool-descriptions.md`）直接作为 Chat Completions `tools` 参数传入，与主提示词中"可用工具清单"保持一致，两处同步维护。
3. **摘要提示词**（`context-summary-prompt.md`）在每轮分析结束后调用一次，输出写入 `context_summaries`。

## 维护约定

- 所有提示词变更走管理后台配置重载（`system_configs` 的 `prompt_*` 配置项可覆盖模板片段），不直接改代码。
- 模型切换（DeepSeek/通义/Kimi/OpenAI）时先在本目录验证提示词兼容性再上线。
- 每次调优后在本 README 更新版本号与变更说明。
