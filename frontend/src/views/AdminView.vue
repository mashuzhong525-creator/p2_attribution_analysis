<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConfigStore } from '../stores/config'
import { useDatasourceStore } from '../stores/datasource'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'

const router = useRouter()
const cfgStore = useConfigStore()
const dsStore = useDatasourceStore()
const auth = useAuthStore()

const TABS = [
  { key: 'config', label: '系统配置' },
  { key: 'datasource', label: '数据源' },
  { key: 'flags', label: '功能开关' },
  { key: 'logs', label: '运行日志' },
  { key: 'costs', label: 'LLM 成本' },
  { key: 'audit', label: '审计日志' },
]
const tab = ref('config')

const saving = ref(false)

onMounted(async () => {
  try { await cfgStore.fetch() } catch (e) { window.$toast(e.message, 'error') }
  try { await dsStore.fetch() } catch (e) { window.$toast(e.message, 'error') }
})

// ==================== 系统配置 ====================
function serialize(v, type) {
  if (type === 'bool') return v === true || v === 'true' || v === '1'
  if (type === 'int') return Number(v) || 0
  if (type === 'float') return Number(v) || 0
  if (type === 'json') { try { return JSON.parse(v) } catch { return v } }
  return String(v)
}
function inputType(t) {
  if (t === 'bool') return 'checkbox'
  if (t === 'int' || t === 'float') return 'number'
  if (t === 'json') return 'text'
  return 'text'
}
async function saveConfig(group) {
  saving.value = true
  try {
    const items = group.items.map((i) => ({ config_key: i.config_key, config_value: serialize(i.config_value, i.config_type) }))
    const res = await cfgStore.update(items)
    window.$toast(`「${group.group}」已保存并热加载${res.updated_keys?.length ? `（更新 ${res.updated_keys.length} 项）` : ''}`, 'success')
  } catch (e) { window.$toast(e.message, 'error') }
  finally { saving.value = false }
}
async function reloadAll() {
  try {
    const res = await cfgStore.reload()
    window.$toast(`配置已热加载（更新 ${res.updated_keys?.length || 0} 项）`, 'success')
  } catch (e) { window.$toast(e.message, 'error') }
}

// ==================== 功能开关（bool 配置） ====================
const flagItems = computed(() => {
  const out = []
  for (const g of cfgStore.groups) {
    for (const i of g.items) {
      if (i.config_type === 'bool' && i.config_key.startsWith('flag_')) out.push({ ...i, group: g.group })
    }
  }
  return out
})
async function toggleFlag(item) {
  item.config_value = !item.config_value
  try {
    const res = await cfgStore.update([{ config_key: item.config_key, config_value: item.config_value }])
    window.$toast(`「${item.config_key}」已${item.config_value ? '开启' : '关闭'}（即时生效）`, 'success')
  } catch (e) {
    item.config_value = !item.config_value
    window.$toast(e.message, 'error')
  }
}

// ==================== 数据源 ====================
const editForm = ref({ show: false, id: null, name: '', host: '', port: 3306, database: '', username: '', password: '', is_readonly: true, is_enabled: true })
const testMsg = ref('')
const delTarget = ref(null)

function openEdit(ds) {
  editForm.value = ds ? {
    show: true, id: ds.id, name: ds.name, host: ds.host, port: ds.port,
    database: ds.database, username: ds.username, password: '', is_readonly: ds.is_readonly, is_enabled: ds.is_enabled
  } : { show: true, id: null, name: '', host: '', port: 3306, database: '', username: '', password: '', is_readonly: true, is_enabled: true }
  testMsg.value = ''
}
async function saveDs() {
  saving.value = true
  const f = editForm.value
  const body = { name: f.name, db_type: 'mysql', host: f.host, port: Number(f.port) || 3306, database: f.database, username: f.username, password: f.password, is_readonly: f.is_readonly, is_enabled: f.is_enabled }
  try {
    if (f.id) await dsStore.update(f.id, body)
    else await dsStore.create(body)
    editForm.value.show = false
    window.$toast('数据源已保存', 'success')
  } catch (e) { window.$toast(e.message, 'error') }
  finally { saving.value = false }
}
async function testDs() {
  const f = editForm.value
  const body = f.id ? { id: f.id } : { host: f.host, port: Number(f.port) || 3306, database: f.database, username: f.username, password: f.password }
  testMsg.value = '测试中…'
  try {
    const r = await dsStore.test(body)
    testMsg.value = r.message
    window.$toast(r.message, r.ok ? 'success' : 'error')
  } catch (e) { testMsg.value = e.message }
}
function askDelete(ds) { delTarget.value = ds }
async function confirmDelete() {
  if (!delTarget.value) return
  try { await dsStore.remove(delTarget.value.id); window.$toast('数据源已删除', 'success') }
  catch (e) { window.$toast(e.message, 'error') }
  delTarget.value = null
}

// ==================== 运行日志 ====================
const logLevel = ref('')
const logType = ref('')
const logKeyword = ref('')
const logs = ref([])
const logsTotal = ref(0)
const logsPage = ref(1)
const logsLoading = ref(false)
const LOG_LEVELS = ['DEBUG', 'INFO', 'WARN', 'ERROR']
const LOG_TYPES = ['', 'system', 'tool', 'llm', 'task']
async function fetchLogs(page = 1) {
  logsLoading.value = true
  try {
    const params = new URLSearchParams({ page, page_size: 20 })
    if (logLevel.value) params.set('level', logLevel.value)
    if (logType.value) params.set('log_type', logType.value)
    if (logKeyword.value.trim()) params.set('keyword', logKeyword.value.trim())
    const d = await api.get('/api/admin/logs?' + params.toString())
    logs.value = d.items; logsTotal.value = d.total; logsPage.value = d.page
  } catch (e) { window.$toast(e.message, 'error') }
  finally { logsLoading.value = false }
}

// ==================== LLM 成本 ====================
const costKpi = ref(null)
const costItems = ref([])
const costTotal = ref(0)
const costPage = ref(1)
async function fetchCosts(page = 1) {
  try {
    const d = await api.get(`/api/admin/llm-costs?page=${page}&page_size=20`)
    costKpi.value = d.kpi; costItems.value = d.items; costTotal.value = d.total; costPage.value = d.page
  } catch (e) { window.$toast(e.message, 'error') }
}

// ==================== 审计日志 ====================
const auditItems = ref([])
const auditTotal = ref(0)
const auditPage = ref(1)
async function fetchAudit(page = 1) {
  try {
    const d = await api.get(`/api/admin/audit-logs?page=${page}&page_size=20`)
    auditItems.value = d.items; auditTotal.value = d.total; auditPage.value = d.page
  } catch (e) { window.$toast(e.message, 'error') }
}

// Tab 切换时懒加载
function onTab(key) {
  tab.value = key
  if (key === 'logs' && !logsTotal.value) fetchLogs(1)
  if (key === 'costs' && !costKpi.value) fetchCosts(1)
  if (key === 'audit' && !auditTotal.value) fetchAudit(1)
}

// 辅助
function fmtDt(s) { return s ? s.replace('T', ' ').slice(0, 19) : '' }
function fmtMoney(v) { return `¥${Number(v || 0).toFixed(4)}` }
function fmtNum(v) { return Number(v || 0).toLocaleString() }
function truncate(s, n = 80) { return s && s.length > n ? s.slice(0, n) + '…' : s }
function pages(total, size) { return Math.max(1, Math.ceil(total / size)) }
function pageList(total, cur, size) {
  const p = pages(total, size)
  if (p <= 1) return []
  const arr = []
  for (let i = 1; i <= p; i++) arr.push(i)
  return arr
}
function pageCount(total, size) { return pages(total, size) }
function logout() { auth.logout().then(() => router.push('/login')) }
</script>

<template>
  <div class="admin-wrap">
    <div class="admin-top">
      <div class="avatar blue">A</div>
      <div>
        <div style="font-size: 13px; font-weight: 600;">{{ auth.user?.display_name || auth.user?.username }}</div>
        <div class="muted" style="font-size: 11px;">系统管理员 · 管理后台</div>
      </div>
      <span class="spacer"></span>
      <button class="btn sm" @click="router.push('/')">← 返回工作台</button>
      <button class="btn sm" @click="logout">退出登录</button>
    </div>
    <div class="admin-tabs">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ on: tab === t.key }" @click="onTab(t.key)">{{ t.label }}</button>
    </div>
    <div class="admin-body">

      <!-- ===== Tab1 系统配置 ===== -->
      <div v-if="tab === 'config'">
        <div class="info-bar">配置来自 system_configs（seed 清单），编辑后点「保存本组」热更新，不重启服务；变更写入 audit_logs。敏感项（API Key）以 *** 掩码显示。</div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 6px;">
          <button class="btn sm primary" :disabled="saving" @click="reloadAll">🔄 重载全部配置</button>
        </div>
        <div v-for="g in cfgStore.groups" :key="g.group">
          <div class="group-title">{{ g.group }} <span class="count">{{ g.items.length }} 项</span>
            <span class="spacer"></span>
            <button class="btn sm" :disabled="saving" @click="saveConfig(g)">保存本组</button>
          </div>
          <div style="background: var(--paper); border: 1px solid var(--line-soft); border-radius: 8px; overflow: hidden;">
            <div class="cfg-row head"><span>配置键 key</span><span>类型</span><span>值</span><span>说明</span><span></span></div>
            <div class="cfg-row" v-for="i in g.items" :key="i.config_key">
              <span class="mono">{{ i.config_key }}</span>
              <span><span class="chip pending">{{ i.config_type }}</span></span>
              <span v-if="i.config_type === 'bool'">
                <span class="switch" :class="{ on: !!i.config_value }" @click="i.config_value = !i.config_value"></span>
                <span class="muted" style="margin-left: 6px;">{{ i.config_value ? 'ON' : 'OFF' }}</span>
              </span>
              <span v-else>
                <input class="textinput" :type="inputType(i.config_type)" v-model="i.config_value" />
              </span>
              <span class="muted" style="font-size: 12px;">{{ i.description }}</span>
              <span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== Tab2 数据源 ===== -->
      <div v-else-if="tab === 'datasource'">
        <div class="info-bar">会话绑定的数据源是 Agent 查询的唯一边界；外部源连接密码 AES 加密存储。删除数据源将断开连接，已绑定会话无法再查询。</div>
        <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
          <button class="btn primary sm" @click="openEdit(null)">＋ 新增数据源</button>
        </div>
        <table class="table">
          <thead><tr><th>名称</th><th>类型</th><th>主机:端口</th><th>库</th><th>只读</th><th>状态</th><th style="width: 210px;">操作</th></tr></thead>
          <tbody>
            <tr v-for="d in dsStore.list" :key="d.id">
              <td>{{ d.name }}</td>
              <td>{{ d.db_type }}</td>
              <td class="mono">{{ d.host }}:{{ d.port }}</td>
              <td class="mono">{{ d.database }}</td>
              <td>{{ d.is_readonly ? '✓' : '—' }}</td>
              <td><span class="chip" :class="d.is_enabled ? 'success' : 'pending'">{{ d.is_enabled ? '已启用' : '已停用' }}</span></td>
              <td>
                <button class="btn sm" @click="openEdit(d)">编辑</button>
                <button class="btn sm danger" @click="askDelete(d)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ===== Tab3 功能开关 ===== -->
      <div v-else-if="tab === 'flags'">
        <div class="info-bar">功能开关走 system_configs（bool），切换即时生效（PRD 6.8），变更写 audit_logs。</div>
        <div style="background: var(--paper); border: 1px solid var(--line-soft); border-radius: 8px; overflow: hidden;">
          <div class="cfg-row head" style="grid-template-columns: 200px 90px 1fr 80px;"><span>开关</span><span>状态</span><span>说明</span><span>操作</span></div>
          <div class="cfg-row" style="grid-template-columns: 200px 90px 1fr 80px;" v-for="f in flagItems" :key="f.config_key">
            <span class="mono" style="font-weight: 600;">{{ f.config_key }}</span>
            <span><span class="chip" :class="f.config_value ? 'success' : 'pending'">{{ f.config_value ? 'ON' : 'OFF' }}</span></span>
            <span class="muted">{{ f.description }}</span>
            <span><span class="switch" :class="{ on: !!f.config_value }" @click="toggleFlag(f)"></span></span>
          </div>
          <div v-if="!flagItems.length" class="empty">未找到开关配置</div>
        </div>
      </div>

      <!-- ===== Tab4 运行日志 ===== -->
      <div v-else-if="tab === 'logs'">
        <div class="filters">
          <button v-for="l in LOG_LEVELS" :key="l" class="filter" :class="{ sel: logLevel === l }" @click="logLevel = logLevel === l ? '' : l; fetchLogs(1)">{{ l }}</button>
          <button v-for="t in LOG_TYPES" :key="t || 'all'" class="filter" :class="{ sel: logType === t }" @click="logType = logType === t ? '' : t; fetchLogs(1)">{{ t ? t : '全部类型' }}</button>
          <input class="textinput" v-model="logKeyword" placeholder="搜索关键词…" @keydown.enter.prevent="fetchLogs(1)" />
          <button class="btn sm primary" @click="fetchLogs(1)">查询</button>
        </div>
        <table class="table">
          <thead><tr><th>时间 (UTC)</th><th>级别</th><th>类型</th><th>任务</th><th>内容</th></tr></thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td class="mono" style="white-space: nowrap;">{{ fmtDt(l.created_at) }}</td>
              <td><span class="chip" :class="l.log_level === 'ERROR' ? 'failed' : (l.log_level === 'WARN' ? 'cancelled' : 'running')">{{ l.log_level }}</span></td>
              <td>{{ l.log_type }}</td>
              <td class="mono">{{ (l.task_id || '—').slice(0, 12) }}…</td>
              <td>{{ truncate(l.log_content, 90) }}</td>
            </tr>
            <tr v-if="!logsLoading && !logs.length"><td colspan="5" class="empty">暂无日志</td></tr>
          </tbody>
        </table>
        <div class="pager" v-if="pageCount(logsTotal, 20) > 1">
          <button class="pg" :disabled="logsPage <= 1" @click="fetchLogs(logsPage - 1)">‹</button>
          <button v-for="i in pageList(logsTotal, logsPage, 20)" :key="i" class="pg" :class="{ on: i === logsPage }" @click="fetchLogs(i)">{{ i }}</button>
          <button class="pg" :disabled="logsPage >= pageCount(logsTotal, 20)" @click="fetchLogs(logsPage + 1)">›</button>
        </div>
        <div class="info-bar">task_logs 保留期默认 90 天，超期随清理任务归档/删除。</div>
      </div>

      <!-- ===== Tab5 LLM 成本 ===== -->
      <div v-else-if="tab === 'costs'">
        <div class="info-bar">每次 LLM 调用一行（llm_calls 表），哪一步烧 token、花多少钱可精确追溯。</div>
        <div class="kpi">
          <div class="card"><div class="l">今日成本</div><div class="v">{{ fmtMoney(costKpi?.today_cost) }}</div></div>
          <div class="card"><div class="l">本月成本</div><div class="v">{{ fmtMoney(costKpi?.month_cost) }}</div></div>
          <div class="card"><div class="l">今日调用次数</div><div class="v">{{ fmtNum(costKpi?.today_calls) }}</div></div>
          <div class="card"><div class="l">Token 总量 (今日)</div><div class="v">{{ fmtNum(costKpi?.today_tokens) }}<small> tokens</small></div></div>
        </div>
        <table class="table">
          <thead><tr><th>时间 (UTC)</th><th>任务</th><th>模型</th><th>输入 token</th><th>输出 token</th><th>耗时</th><th>费用</th></tr></thead>
          <tbody>
            <tr v-for="c in costItems" :key="c.id">
              <td class="mono" style="white-space: nowrap;">{{ fmtDt(c.created_at) }}</td>
              <td class="mono">{{ (c.task_id || '').slice(0, 12) }}…</td>
              <td>{{ c.model }}</td>
              <td>{{ fmtNum(c.prompt_tokens) }}</td>
              <td>{{ fmtNum(c.completion_tokens) }}</td>
              <td>{{ (c.latency_ms / 1000).toFixed(1) }}s</td>
              <td style="font-weight: 600;">{{ fmtMoney(c.cost) }}</td>
            </tr>
            <tr v-if="!costItems.length"><td colspan="7" class="empty">暂无 LLM 调用记录</td></tr>
          </tbody>
        </table>
        <div class="pager" v-if="pageCount(costTotal, 20) > 1">
          <button class="pg" :disabled="costPage <= 1" @click="fetchCosts(costPage - 1)">‹</button>
          <button v-for="i in pageList(costTotal, costPage, 20)" :key="i" class="pg" :class="{ on: i === costPage }" @click="fetchCosts(i)">{{ i }}</button>
          <button class="pg" :disabled="costPage >= pageCount(costTotal, 20)" @click="fetchCosts(costPage + 1)">›</button>
        </div>
      </div>

      <!-- ===== Tab6 审计日志 ===== -->
      <div v-else-if="tab === 'audit'">
        <div class="info-bar">谁 / 何时 / 改了什么 / 前后值——管理后台全部写操作留痕（audit_logs）。</div>
        <table class="table">
          <thead><tr><th>时间 (UTC)</th><th>操作人</th><th>动作</th><th>对象</th><th>变更前</th><th>变更后</th></tr></thead>
          <tbody>
            <tr v-for="a in auditItems" :key="a.id">
              <td class="mono" style="white-space: nowrap;">{{ fmtDt(a.created_at) }}</td>
              <td>{{ (a.user_id || '—').slice(0, 10) }}</td>
              <td><span class="chip running">{{ a.action_type }}</span></td>
              <td class="mono">{{ a.target_type }}<span v-if="a.target_id">:{{ a.target_id.slice(0, 12) }}</span></td>
              <td class="muted">{{ a.before_value ? truncate(JSON.stringify(a.before_value), 60) : '—' }}</td>
              <td class="muted">{{ a.after_value ? truncate(JSON.stringify(a.after_value), 60) : '—' }}</td>
            </tr>
            <tr v-if="!auditItems.length"><td colspan="6" class="empty">暂无审计记录</td></tr>
          </tbody>
        </table>
        <div class="pager" v-if="pageCount(auditTotal, 20) > 1">
          <button class="pg" :disabled="auditPage <= 1" @click="fetchAudit(auditPage - 1)">‹</button>
          <button v-for="i in pageList(auditTotal, auditPage, 20)" :key="i" class="pg" :class="{ on: i === auditPage }" @click="fetchAudit(i)">{{ i }}</button>
          <button class="pg" :disabled="auditPage >= pageCount(auditTotal, 20)" @click="fetchAudit(auditPage + 1)">›</button>
        </div>
      </div>

    </div>

    <!-- 数据源编辑弹窗 -->
    <div v-if="editForm.show" class="modal-mask" @click.self="editForm.show = false">
      <div class="modal">
        <div class="mh">{{ editForm.id ? '编辑数据源' : '新增数据源' }}</div>
        <div class="mb">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <label class="f-label" style="grid-column: 1 / -1;">名称<input class="textinput" v-model="editForm.name" /></label>
            <label class="f-label">主机<input class="textinput" v-model="editForm.host" placeholder="10.0.0.8" /></label>
            <label class="f-label">端口<input class="textinput" type="number" v-model="editForm.port" /></label>
            <label class="f-label">库名<input class="textinput" v-model="editForm.database" /></label>
            <label class="f-label">账号<input class="textinput" v-model="editForm.username" /></label>
            <label class="f-label">密码<input class="textinput" type="password" v-model="editForm.password" :placeholder="editForm.id ? '留空则不修改' : ''" /></label>
            <label class="f-label" style="display: flex; align-items: center; gap: 8px; flex-direction: row;">
              <span class="switch" :class="{ on: editForm.is_readonly }" @click="editForm.is_readonly = !editForm.is_readonly"></span> 只读
            </label>
            <label class="f-label" style="display: flex; align-items: center; gap: 8px; flex-direction: row;">
              <span class="switch" :class="{ on: editForm.is_enabled }" @click="editForm.is_enabled = !editForm.is_enabled"></span> 启用
            </label>
          </div>
          <p v-if="testMsg" class="muted" style="margin: 10px 0 0;">{{ testMsg }}</p>
        </div>
        <div class="mf">
          <button class="btn" @click="testDs">测试连接</button>
          <span class="spacer"></span>
          <button class="btn" @click="editForm.show = false">取消</button>
          <button class="btn primary" :disabled="saving" @click="saveDs">保存</button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗（P2-2） -->
    <div v-if="delTarget" class="modal-mask" @click.self="delTarget = null">
      <div class="modal">
        <div class="mh">确认删除数据源</div>
        <div class="mb">
          <div class="note" style="margin: 0;">删除数据源「{{ delTarget.name }}」将断开该连接，已绑定会话无法再查询。此操作不可恢复。</div>
        </div>
        <div class="mf">
          <button class="btn" @click="delTarget = null">取消</button>
          <button class="btn danger" @click="confirmDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>
