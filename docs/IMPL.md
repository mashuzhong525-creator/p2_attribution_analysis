# IMPL 实现蓝图：经营归因分析系统（Python 方法级）

> 本文档是实现的唯一权威蓝图。每个模块给出方法签名、中文注释、伪代码。
> 实现代码必须与本文档一一对应。

## 1. app/config.py

```python
class Settings(BaseSettings):
    """应用配置模型：从环境变量和.env文件加载"""
    # 字段：app_name, host, port, db_path, upload_dir, export_dir,
    #       deepseek_api_key, deepseek_base_url, deepseek_model,
    #       ws_token_ttl, max_result_rows
    ...

settings = Settings()
```

```python
# 伪代码
Settings 类继承 BaseSettings:
    定义全部配置字段及默认值
    model_config = SettingsConfigDict(env_file=".env")
模块级单例 settings = Settings()
```

---

## 2. app/database.py

```python
def get_connection() -> sqlite3.Connection:
    """创建SQLite连接：启用外键、ROW工厂模式、WAL"""
    # 伪代码：
    # conn = sqlite3.connect(settings.db_path)
    # conn.row_factory = sqlite3.Row          # 结果按列名访问
    # conn.execute("PRAGMA foreign_keys=ON")  # 启用外键约束
    # conn.execute("PRAGMA journal_mode=WAL") # 写前日志提升并发
    # return conn

@contextmanager
def db():
    """事务上下文管理器：正常commit，异常rollback，最终close"""
    # 伪代码：
    # conn = get_connection()
    # try:
    #     yield conn
    #     conn.commit()
    # except:
    #     conn.rollback()
    #     raise
    # finally:
    #     conn.close()

def init_db():
    """初始化数据库：创建全部11张业务表 + 9张场景数据表 + 索引"""
    # 伪代码：
    # with db() as conn:
    #     for ddl in [USERS_DDL, CONVERSATIONS_DDL, ..., SALES_DDL, ORDERS_DDL]:
    #         conn.execute(ddl)
    #     for idx in INDEXES:
    #         conn.execute(idx)
```

---

## 3. app/utils.py

```python
def now_iso() -> str:
    """返回当前时间的ISO8601字符串（本地时区，秒级精度）"""
    # 伪代码：return datetime.now().isoformat(timespec="seconds")
```

---

## 4. app/models.py — 请求模型

```python
class LoginRequest(BaseModel):
    """登录请求"""
    username: str   # 用户名
    password: str   # 密码

class CreateConversationRequest(BaseModel):
    """创建会话请求"""
    title: str = "新会话"  # 会话标题，默认"新会话"

class UpdateConversationRequest(BaseModel):
    """更新会话请求"""
    conversation_id: int   # 目标会话ID
    title: str             # 新标题

class DeleteConversationRequest(BaseModel):
    """删除会话请求"""
    conversation_ids: list[int]  # 待删除会话ID列表

class WsTokenRequest(BaseModel):
    """WebSocket令牌请求"""
    conversation_id: int   # 目标会话ID

class DeleteAttachmentRequest(BaseModel):
    """删除附件请求"""
    attachment_id: int     # 附件ID
```

---

## 5. app/auth.py

```python
_TOKENS: dict[str, dict] = {}   # 内存令牌表 {token: {user_id, expires_at}}
TOKEN_TTL = 7200                # 令牌有效期（秒）

def login(username: str, password: str) -> dict | None:
    """用户登录：校验凭证并签发访问令牌
    返回 {access_token, token_type, user} 或 None（失败）
    """
    # 伪代码：
    # 1. 清理过期令牌
    # 2. with db(): 查询 users WHERE username=?
    # 3. 未找到或密码不匹配（Demo阶段明文比对）→ return None
    # 4. status != 'active' → return None
    # 5. token = uuid4().hex
    # 6. _TOKENS[token] = {user_id, expires_at=now+7200}
    # 7. return {"access_token": token, "token_type": "bearer",
    #            "user": {id, username, display_name, role}}

def get_current_user(token: str) -> dict | None:
    """令牌换用户：校验有效性与过期时间"""
    # 伪代码：
    # rec = _TOKENS.get(token)
    # rec不存在或已过期 → None（并清理）
    # with db(): 查询 users WHERE id=rec.user_id
    # return {id, username, display_name, role}

def require_user(authorization: str = Header(None)) -> dict:
    """FastAPI依赖：要求有效登录态，否则抛HTTPException 401"""
    # 伪代码：
    # 解析 "Bearer xxx" → get_current_user → None则 raise 401

def require_admin(authorization: str = Header(None)) -> dict:
    """FastAPI依赖：要求admin角色，否则401/403"""
    # 伪代码：
    # user = require_user(authorization)
    # user.role != "admin" → raise 403 "需要管理员权限"
```

---

## 6. app/chat.py

```python
def create_conversation(user_id: int, title: str) -> dict:
    """创建会话，返回 {conversation_id, title, status, created_at}"""
    # 伪代码：
    # INSERT INTO conversations(user_id, title, status='active', created_at, updated_at, last_message_at=NULL)
    # return {conversation_id: lastrowid, title, status: "active", ...}

def list_conversations(user_id: int) -> list[dict]:
    """列出用户所有非deleted会话，按last_message_at倒序（NULL排最后）"""
    # 伪代码：
    # SELECT ... FROM conversations WHERE user_id=? AND status != 'deleted'
    # ORDER BY last_message_at DESC NULLS LAST → SQLite: ORDER BY (last_message_at IS NULL), last_message_at DESC

def get_conversation(user_id: int, conversation_id: int) -> dict | None:
    """按ID取会话（校验归属），不存在或无权限返回None"""

def update_conversation(user_id: int, conversation_id: int, title: str) -> dict | None:
    """重命名会话，同时更新updated_at"""

def delete_conversation(user_id: int, conversation_ids: list[int]) -> int:
    """批量级联删除会话（单事务）：
    attachments→task_logs→analysis_results→analysis_tasks→
    context_summaries→websocket_tokens→messages→conversations
    以及 uploads/{uid}/{cid}/、exports/{uid}/{cid}/、workspace/{uid}/{cid}/ 物理目录
    返回实际删除数量
    """
    # 伪代码：
    # deleted = 0
    # with db() as conn:
    #     for cid in conversation_ids:
    #         校验会话存在且属于该用户 → 否则跳过
    #         收集附件file_path → 逐个删除物理文件（存在才删）
    #         DELETE FROM attachments WHERE conversation_id=cid
    #         DELETE FROM task_logs WHERE task_id IN (该会话所有任务)
    #         DELETE FROM analysis_results WHERE conversation_id=cid
    #         DELETE FROM analysis_tasks WHERE conversation_id=cid
    #         DELETE FROM context_summaries WHERE conversation_id=cid
    #         DELETE FROM websocket_tokens WHERE conversation_id=cid
    #         DELETE FROM messages WHERE conversation_id=cid
    #         DELETE FROM conversations WHERE id=cid
    #         shutil.rmtree(三个目录, ignore_errors=True)
    #         deleted += 1
    # return deleted

def add_message(conversation_id: int, role: str, content: str,
                message_type: str = "text",
                tool_name: str | None = None, tool_status: str | None = None) -> dict:
    """新增消息：seq_no = 会话内最大seq_no + 1；同时刷新会话last_message_at"""
    # 伪代码：
    # with db():
    #     seq = SELECT MAX(seq_no) FROM messages WHERE conversation_id=? 或0
    #     INSERT INTO messages(...)
    #     UPDATE conversations SET last_message_at=now, updated_at=now WHERE id=?
    # return {message_id: lastrowid, seq_no: seq+1, ...}

def list_messages(conversation_id: int) -> list[dict]:
    """查询会话全部消息，按seq_no升序"""

def add_attachment(conversation_id: int, file_name: str, file_path: str,
                   file_type: str, file_size: int) -> dict:
    """附件元数据入库，parse_status初始'pending'"""

def list_attachments(conversation_id: int) -> list[dict]:
    """查询会话全部附件，按created_at升序"""

def get_attachment(user_id: int, attachment_id: int) -> dict | None:
    """按ID取附件（join会话校验归属）"""
```

---

## 7. app/tasks.py

```python
ALLOWED_TRANSITIONS = {
    "queued": ["running"],
    "running": ["success", "failed", "cancelled"],
}

def log_task(task_id: int, level: str, log_type: str, content: str):
    """写任务日志：log_level∈{INFO,WARN,ERROR}，log_type∈{step,tool,system}"""

def create_task(conversation_id: int, user_id: int, input_text: str) -> dict:
    """创建分析任务：
    - 若该会话已存在 queued/running 任务 → 抛RuntimeError（409）
    - 否则插入 queued 状态任务
    """
    # 伪代码：
    # with db():
    #     exists = SELECT id FROM analysis_tasks
    #              WHERE conversation_id=? AND task_status IN ('queued','running')
    #     exists → raise RuntimeError("该会话已有运行中的任务")
    #     INSERT INTO analysis_tasks(...) VALUES (..., 'queued', now)
    # return {task_id: lastrowid, task_status: "queued", ...}

def transition(task_id: int, from_status: str, to_status: str,
               current_step: str | None = None) -> dict:
    """任务状态流转：
    - 校验 from→to 在 ALLOWED_TRANSITIONS 中，否则抛RuntimeError
    - running时写started_at；success/failed/cancelled时写finished_at
    """
    # 伪代码：
    # to_status not in ALLOWED_TRANSITIONS[from_status] → raise
    # UPDATE analysis_tasks SET task_status=?, current_step=?
    #   started_at = now if to=='running'
    #   finished_at = now if to in 终态
    # WHERE id=? AND task_status=?   # 乐观锁防并发
    # 返回更新后任务

def mark_failed(task_id: int, error_message: str) -> dict:
    """标记任务失败：running→failed + error_message + 写ERROR日志"""

def list_tasks(conversation_id: int | None = None,
               status: str | None = None) -> list[dict]:
    """查询任务列表，支持会话与状态过滤"""
```

---

## 8. app/results.py

```python
def result_markdown(result: dict) -> str:
    """将六维结果渲染为Markdown报告"""
    # 伪代码：
    # 拼接：
    # "# 经营归因分析报告"
    # "## 一、问题定义"  problem_definition
    # "## 二、关键指标"  Markdown表格：指标名|值|单位|周期
    # "## 三、证据列表"  表格：来源类型|来源名|证据内容|关联指标|置信度
    # "## 四、归因结论"  conclusion_text
    # "## 五、待补充数据" missing_data_text
    # "## 六、下一步建议" next_action_text（按行渲染列表）
    # return 拼接结果

def save_result(task_id: int, conversation_id: int, data: dict) -> dict:
    """保存分析结果：
    - key_metrics / evidence_list 序列化为JSON字符串
    - 生成result_markdown
    - INSERT INTO analysis_results
    """
    # 伪代码：
    # md = result_markdown(data)
    # with db():
    #     INSERT INTO analysis_results(
    #         task_id, conversation_id, problem_definition,
    #         key_metrics_json, evidence_list_json, conclusion_text,
    #         missing_data_text, next_action_text, result_markdown, created_at)
    # return {result_id: lastrowid, ...data, result_markdown: md}

def get_result(task_id: int) -> dict | None:
    """按任务ID取结果，JSON字段反序列化为数组"""
    # 伪代码：
    # SELECT * FROM analysis_results WHERE task_id=?
    # 无记录 → None
    # json.loads(key_metrics_json) → key_metrics
    # json.loads(evidence_list_json) → evidence_list
```

---

## 9. app/tokens.py

```python
def issue_ws_token(user_id: int, conversation_id: int) -> dict:
    """签发一次性WebSocket令牌（UUID，TTL默认300秒）"""
    # 伪代码：
    # token = uuid4().hex
    # expires_at = now + settings.ws_token_ttl 秒
    # INSERT INTO websocket_tokens(user_id, conversation_id, token, expires_at, created_at)
    # return {"websocket_token": token, "expires_in": settings.ws_token_ttl}

def consume_ws_token(token: str, user_id: int, conversation_id: int) -> bool:
    """消费令牌（一次性）：
    校验 存在/未消费/未过期/用户匹配/会话匹配 → 写consumed_at
    """
    # 伪代码：
    # with db():
    #     row = SELECT * FROM websocket_tokens WHERE token=?
    #     row不存在 → False
    #     row.consumed_at 非空 → False（已使用）
    #     row.expires_at < now → False（已过期）
    #     row.user_id != user_id → False
    #     row.conversation_id != conversation_id → False
    #     UPDATE websocket_tokens SET consumed_at=now WHERE id=row.id
    # return True
```

---

## 10. app/llm.py

```python
def chat_completion(messages: list[dict], temperature: float = 0.2) -> str:
    """调用LLM（DeepSeek OpenAI兼容接口）：
    - 无API Key → 走离线确定性模式 default_llm_call
    - httpx POST {base_url}/chat/completions，60秒超时
    - 网络异常/非200 → 降级 default_llm_call
    """
    # 伪代码：
    # if not settings.deepseek_api_key:
    #     return default_llm_call(messages)
    # try:
    #     resp = httpx.post(f"{base_url}/chat/completions",
    #         headers={"Authorization": f"Bearer {key}"},
    #         json={"model": model, "messages": messages, "temperature": temperature},
    #         timeout=60)
    #     resp.raise_for_status()
    #     return resp.json()["choices"][0]["message"]["content"]
    # except Exception:
    #     return default_llm_call(messages)   # 降级

def default_llm_call(messages: list[dict]) -> str:
    """离线确定性应答（演示/降级模式）：
    - 拼接messages文本，做关键词路由
    - 含Schema+生成SQL提示 → 返回预设分析SQL（库存/转化率/周转）
    - 含"归因/JSON"提示 → 返回模板化六维JSON
    - 其他 → 返回通用说明文本
    """
    # 伪代码：
    # text = " ".join(m["content"] for m in messages)
    # if 是SQL生成类提示（含"SQLite"与"SELECT"）:
    #     if 含"转化率": return CONVERSION_SQL
    #     elif 含"库存"或"周转": return INVENTORY_SQL
    #     else: return DEFAULT_MONTHLY_SQL
    # if 含"归因"与"JSON": return ATTRIBUTION_JSON_TEMPLATE（含占位结论）
    # return "（离线演示模式）无法调用真实模型，返回确定性结果。"
```

---

## 11. app/engine/schema.py

```python
SCHEMA_TEXT = """..."""
# 9张场景表的结构说明文本：
# inventory(warehouse,sku,quantity,record_date)、
# inbound/outbound(warehouse,sku,qty,record_date)、
# sales(warehouse,sku,quantity,amount,record_date)、
# customers(user_id,register_date,city)、
# visits(user_id,page,event_date)、
# add_to_cart(user_id,sku,event_date)、
# orders(user_id,sku,amount,event_date)

METRICS_TEXT = """..."""
# 指标口径定义文本：
# 库存周转率 = 月销量 / 月均库存
# 周转天数 = 30 / 周转率
# 转化率 = 下单人数 / 访问人数
# 异常判定：环比变化超过 ±30% 视为显著异常
```

---

## 12. app/engine/sql_guard.py

```python
BLOCKED_KEYWORDS = ["DELETE","UPDATE","INSERT","DROP","ALTER","ATTACH","DETACH",
                    "CREATE","EXEC","EXECUTE","GRANT","REVOKE","PRAGMA",
                    "REPLACE","VACUUM","BEGIN","COMMIT","ROLLBACK"]

def validate_select(sql: str) -> tuple[bool, str]:
    """SQL安全校验：返回(是否合法, 原因)
    规则：
    1. 剥离 -- 行注释与 /* */ 块注释
    2. 必须以 SELECT 或 WITH 开头（CTE）
    3. 词边界匹配阻断18个危险关键字
    4. 分号最多1个（禁止多语句）
    """
    # 伪代码：
    # cleaned = 正则去除注释
    # stripped = cleaned.strip().rstrip(";").strip()
    # if not (upper以SELECT或WITH开头): return False, "仅允许SELECT查询"
    # for kw in BLOCKED_KEYWORDS:
    #     if re.search(rf"\b{kw}\b", stripped, IGNORECASE):
    #         return False, f"检测到禁止关键字: {kw}"
    # if stripped内分号计数 > 0: return False, "不允许执行多条语句"
    # return True, "ok"
```

---

## 13. app/engine/sql_gen.py

```python
def build_prompt(question: str) -> list[dict]:
    """构建Text2SQL消息列表：system（规则+Schema+指标口径）+ user（问题）"""
    # 伪代码：
    # system = f"""你是资深经营分析师。基于以下SQLite表结构生成查询SQL。
    # 规则：1.只输出一条SELECT语句 2.不要使用markdown代码块以外内容
    # 3.时间字段为TEXT格式YYYY-MM-DD，用strftime/substr做月份聚合
    # {SCHEMA_TEXT}
    # {METRICS_TEXT}"""
    # return [{"role":"system","content":system},
    #         {"role":"user","content":question}]

def extract_sql(text: str) -> str | None:
    """从LLM输出提取SQL：优先```sql代码块，其次裸SELECT语句"""
    # 伪代码：
    # m = re.search(r"```sql\s*(.*?)```", text, DOTALL|IGNORECASE)
    # if m: return m.group(1).strip()
    # m = re.search(r"(SELECT\b.*)", text, IGNORECASE|DOTALL)
    # return m.group(1).strip() if m else None

def generate_sql(question: str, fix_context: str | None = None) -> str:
    """生成并校验SQL：
    - fix_context非空时（重试场景）追加错误上下文
    - LLM → extract_sql → validate_select
    - 提取失败或校验失败 → 抛RuntimeError
    """
    # 伪代码：
    # messages = build_prompt(question)
    # if fix_context: messages.append({"role":"user","content":
    #     f"上次SQL执行失败：{fix_context}\n请修正并重新生成SQL。"})
    # text = llm.chat_completion(messages)
    # sql = extract_sql(text)
    # sql为空 → raise RuntimeError("LLM未返回有效SQL")
    # ok, reason = sql_guard.validate_select(sql)
    # not ok → raise RuntimeError(f"SQL安全校验失败: {reason}")
    # return sql
```

---

## 14. app/engine/executor.py

```python
def execute_sql(sql: str) -> dict:
    """只读执行SQL，返回 {rows, columns, truncated}"""
    # 伪代码：
    # uri = f"file:{settings.db_path}?mode=ro"      # 只读连接
    # conn = sqlite3.connect(uri, uri=True)
    # cur = conn.execute(sql)
    # columns = [d[0] for d in cur.description]
    # rows = cur.fetchmany(settings.max_result_rows + 1)
    # truncated = len(rows) > settings.max_result_rows
    # rows = rows[:settings.max_result_rows]        # 截断
    # rows = [字符串化None→"" 每行值]
    # conn.close()
    # return {"rows": rows, "columns": columns, "truncated": truncated}

def execute_with_retry(sql: str, fix_fn) -> dict:
    """带自愈执行：首次失败 → fix_fn(错误,原SQL)生成修正SQL → 重试一次
    仍失败 → 抛RuntimeError
    """
    # 伪代码：
    # try: return execute_sql(sql)
    # except Exception as e1:
    #     fixed_sql = fix_fn(str(e1), sql)     # fix_fn内部调generate_sql(fix_context=...)
    #     try: return execute_sql(fixed_sql)
    #     except Exception as e2: raise RuntimeError(f"SQL重试仍失败: {e2}")
```

---

## 15. app/engine/attribution.py

```python
class Metric(BaseModel):
    """关键指标"""
    metric_name: str; metric_value: str
    metric_unit: str; metric_period: str

class Evidence(BaseModel):
    """证据条目"""
    source_type: str; source_name: str; evidence_text: str
    related_metric: str; confidence: float

class AttributionResult(BaseModel):
    """六维归因结果"""
    problem_definition: str
    key_metrics: list[Metric]
    evidence_list: list[Evidence]
    conclusion_text: str
    missing_data_text: str
    next_action_text: str

def build_prompt(question: str, sql: str, exec_result: dict) -> list[dict]:
    """构建归因生成消息：system（输出JSON Schema说明）+ user（问题+SQL+数据）"""
    # 伪代码：
    # rows_text = 前若干行数据格式化文本（≤30行）
    # system = "你是经营归因分析专家。基于查询数据输出严格JSON，字段：
    #   problem_definition/key_metrics[{metric_name,metric_value,metric_unit,metric_period}]
    #   /evidence_list[{source_type,source_name,evidence_text,related_metric,confidence}]
    #   /conclusion_text/missing_data_text/next_action_text。
    #   next_action_text至少2条用换行分隔。只输出JSON。"
    # user = f"问题：{question}\nSQL：{sql}\n数据：{rows_text}"
    # return [system消息, user消息]

def parse_result(text: str) -> AttributionResult:
    """解析LLM输出为AttributionResult：
    优先提取```json代码块，其次首个{...}花括号块
    json.loads → AttributionResult.model_validate
    """
    # 伪代码：
    # m = re.search(r"```(?:json)?\s*(.*?)```", ...) 或 r"\{.*\}" DOTALL
    # data = json.loads(提取文本)
    # return AttributionResult.model_validate(data)
    # 任一步失败 → raise ValueError

def build_fallback_result(question: str, exec_result: dict) -> AttributionResult:
    """降级归因：从查询结果确定性构建六维结构
    - problem_definition = 原问题
    - key_metrics = 数值列聚合（列名/总和/单位行）
    - evidence_list = 前5行数据作为database证据（confidence=0.7）
    - conclusion_text = 模板化结论（数据行数+列）
    - missing_data_text = 固定提示
    - next_action_text = 2条固定建议
    """

def generate_attribution(question: str, sql: str, exec_result: dict) -> dict:
    """归因入口：LLM优先 → 解析失败 → build_fallback_result 降级
    始终返回dict（六维结构），保证不抛异常
    """
    # 伪代码：
    # try:
    #     text = llm.chat_completion(build_prompt(...))
    #     result = parse_result(text)
    # except Exception:
    #     result = build_fallback_result(question, exec_result)   # 降级
    # return result.model_dump()
```

---

## 16. app/engine/metrics.py

```python
def inventory_turnover(sales_qty: float, avg_inventory: float) -> float:
    """库存周转率 = 销量 / 平均库存（除零返回0.0）"""

def turnover_days(turnover: float, days: int = 30) -> float:
    """周转天数 = days / turnover（除零返回0.0）"""

def conversion_rate(conversions: float, visits: float) -> float:
    """转化率 = 转化数 / 访问数（除零返回0.0，保留4位小数）"""
```

---

## 17. app/engine/pipeline.py — 核心管线

```python
def run_analysis(conversation_id: int, user_id: int,
                 question: str, emit) -> None:
    """执行完整分析流程（阻塞函数，由ws层放入线程池）：
    emit(type, **fields) 将事件写入WebSocket队列。

    流程：
    1. 创建任务（校验无并发运行）→ emit(message_start)
    2. queued→running → emit(task_status, step="任务启动")
    3. 用户消息入库 add_message(role="user")
    4. 循环执行三个步骤 steps = [
         ("sql_generation", "生成SQL", 生成函数),
         ("sql_execution", "执行查询", 执行函数),
         ("attribution_generation", "生成归因结论", 归因函数)]
       每步骤：
         emit(tool_start) → 执行 → emit(tool_finish, 摘要)
         emit(message_delta, 过程说明文本)
         emit(task_status, current_step)
         log_task记录
    5. save_result + add_message(role="assistant", content=conclusion)
       → emit(result_ready, result_id)
    6. running→success → emit(done, finished_at)
    异常兜底：mark_failed → emit(error, error_message)
    """
    # 伪代码：
    # try:
    #     task = tasks.create_task(cid, uid, question)
    #     emit("message_start", task_id=task.id, conversation_id=cid)
    #     tasks.transition(id, "queued", "running", "任务启动")
    #     emit("task_status", task_status="running", current_step="任务启动")
    #     chat.add_message(cid, "user", question)
    #     emit("message_delta", delta_text=f"收到问题：{question}\n")
    #
    #     # 步骤1：生成SQL
    #     emit("tool_start", tool_name="sql_generation")
    #     sql = sql_gen.generate_sql(question)
    #     emit("tool_finish", tool_name="sql_generation",
    #          tool_result_summary=f"SQL: {sql[:100]}")
    #     emit("message_delta", delta_text=f"已生成查询SQL。\n")
    #
    #     # 步骤2：执行SQL（带自愈重试）
    #     emit("tool_start", tool_name="sql_execution")
    #     result = executor.execute_with_retry(
    #         sql, fix_fn=lambda err, s: sql_gen.generate_sql(
    #             question, fix_context=f"{err}\n原SQL:{s}"))
    #     emit("tool_finish", tool_name="sql_execution",
    #          tool_result_summary=f"返回{len(rows)}行×{len(cols)}列")
    #     emit("message_delta", delta_text=f"查询完成，共{len(rows)}行数据。\n")
    #
    #     # 步骤3：生成归因
    #     emit("tool_start", tool_name="attribution_generation")
    #     attribution = attribution.generate_attribution(question, sql, result)
    #     emit("tool_finish", tool_name="attribution_generation",
    #          tool_result_summary="六维归因结果已生成")
    #     emit("message_delta", delta_text=attribution["conclusion_text"])
    #
    #     # 保存与收尾
    #     saved = results.save_result(task_id, cid, attribution)
    #     chat.add_message(cid, "assistant", attribution["conclusion_text"])
    #     emit("result_ready", result_id=saved["result_id"])
    #     tasks.transition(id, "running", "success", "完成")
    #     emit("done", finished_at=now_iso())
    # except Exception as e:
    #     tasks.mark_failed(task_id, str(e))
    #     emit("error", error_message=str(e))
```

---

## 18. app/ws.py

```python
@router.websocket("/api/chat/ws/chat")
async def chat_ws(websocket: WebSocket, websocket_token: str, conversation_id: int):
    """WebSocket实时分析端点：

    连接建立：
    1. consume_ws_token鉴权 → 失败 close(code=4001)
    2. accept()
    3. queue = asyncio.Queue()  # 事件队列
    4. 启动发送协程 _pump(websocket, queue)：循环get→send_json

    消息循环：
    while True:
        raw = await websocket.receive_json()
        if raw.type == "question":
            if 该会话已有运行任务: send {"type":"error", error_message="..."}
            else: asyncio.to_thread(pipeline.run_analysis, cid, uid, text,
                                    lambda t, **kw: queue.put_nowait({"type":t, **kw}))
        其他type忽略

    连接关闭（WebSocketDisconnect）→ 清理退出
    """
```

---

## 19. app/admin.py

```python
_CONFIG_CACHE: dict[str, dict] = {}   # {key: {config_key, config_value, config_group, updated_at}}

def load_config():
    """启动时全量加载system_configs表到内存缓存"""

def reload_config() -> int:
    """热更新：清空缓存重新加载，返回配置条数"""

def get_config(key: str, default: str | None = None) -> str | None:
    """读缓存，未命中返回default"""

def set_config(key: str, value: str, group: str = "general"):
    """upsert配置：存在则UPDATE，不存在则INSERT；刷新缓存"""

def list_task_logs(offset: int = 0, limit: int = 50) -> dict:
    """分页查询任务日志，返回 {logs: [...], total: 总数}"""
```

---

## 20. app/api/* 路由层

```python
# auth_routes.py
@router.post("/api/auth/login")
def login(req: LoginRequest):
    """登录：失败raise 401；成功返回token+user"""

@router.get("/api/auth/me")
def me(user=Depends(require_user)):
    """返回当前登录用户信息"""

# chat_routes.py
@router.post("/api/chat/create")      # 建会话（require_user）
@router.post("/api/chat/delete")      # 批量删除（require_user）
@router.post("/api/chat/update")      # 重命名（require_user）
@router.get("/api/chat/ls")           # 会话列表（require_user）
@router.get("/api/chat/ls/{cid}")     # 消息列表：逐条消息join其附件（require_user）
@router.post("/api/chat/ws-token")    # 签发WS令牌（require_user）

# attachment_routes.py
@router.post("/api/attachment/upload")
def upload(conversation_id: int = Form(...), file: UploadFile = File(...),
           user=Depends(require_user)):
    """上传：校验会话归属 → 目录uploads/{uid}/{cid}/自动创建
    → 写文件（文件名加时间戳防冲突）→ add_attachment入库 → 返回附件信息"""

@router.post("/api/attachment/delete")
def delete_attachment(req: DeleteAttachmentRequest, user=Depends(require_user)):
    """删除：get_attachment校验归属 → 删物理文件 → 删记录"""

@router.get("/api/attachment/get")
def download(attachment_id: int, user=Depends(require_user)):
    """下载：FileResponse(path, filename=原名)"""

@router.get("/api/attachment/ls")
def ls(conversation_id: int, user=Depends(require_user)):
    """会话附件列表"""

# task_routes.py
@router.get("/api/tasks/{task_id}")          # 任务状态详情
@router.get("/api/results/{task_id}")        # 六维结果（get_result）
@router.get("/api/results/{task_id}/export")
def export(task_id: int, format: str = "md", user=Depends(require_user)):
    """导出：md→result_markdown；json→json.dumps六维结构
    写入exports/{uid}/{cid}/result_{task_id}.{ext} → FileResponse下载"""

# admin_routes.py
@router.get("/api/admin/config")    # require_admin → 配置列表
@router.post("/api/admin/reload")   # require_admin → {status:"ok", message, count}
@router.get("/api/admin/logs")      # require_admin → 分页日志
```

---

## 21. app/main.py

```python
def create_app() -> FastAPI:
    """应用工厂：
    1. lifespan: 启动时 init_db() + admin.load_config()
    2. include全部路由（auth/chat/attachment/task/admin/ws）
    3. mount("/static", StaticFiles(web/static))
    4. GET / → FileResponse(index.html)
    5. GET /health → {"status":"ok"}
    """
app = create_app()
```

---

## 22. scripts/gen_data.py

```python
def main():
    """生成演示数据（确定性，seed=42）：
    1. init_db()
    2. 种子用户：admin/admin123（role=admin）
    3. 种子配置：llm_model/max_result_rows/analysis_scenario
    4. 库存场景（5/6/7月）：
       - 正常月份：东/南/西/北仓 各SKU 库存/入库/出库/销量正常波动
       - 7月异常注入：东仓入库×1.6、出库×0.5 → 库存积压60%+；销量整体×0.6
    5. 客户行为场景（5/6/7月）：
       - 200用户，正常月份访问→加购→下单漏斗稳定
       - 7月异常注入：访问量持平、下单量×0.5 → 转化率骤降
    """
```

---

## 23. 实现顺序（TDD建议）

| 批次 | 模块 | 前置测试 |
|------|------|----------|
| 1 | config/database/utils | - |
| 2 | sql_guard/metrics | test_sql_guard / test_metrics |
| 3 | tasks/results/tokens | test_tasks / test_results / test_ws_token |
| 4 | llm/sql_gen/executor/attribution | - |
| 5 | pipeline（离线模式） | test_engine |
| 6 | auth/chat/admin + API路由 | - |
| 7 | ws + main | 手动集成 |
| 8 | gen_data + 前端 | E2E验证 |
