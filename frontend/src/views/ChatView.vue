<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationStore } from '../stores/conversation'
import { useMessageStore } from '../stores/message'
import { useTaskStore } from '../stores/task'
import { useDatasourceStore } from '../stores/datasource'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import { wsClient } from '../ws/wsClient'

const router = useRouter()
const convStore = useConversationStore()
const msgStore = useMessageStore()
const taskStore = useTaskStore()
const dsStore = useDatasourceStore()
const auth = useAuthStore()

const input = ref('')
const msgListEl = ref(null)
function scrollBottom() {
  nextTick(() => {
    if (msgListEl.value) msgListEl.value.scrollTop = msgListEl.value.scrollHeight
  })
}
const pollTimer = ref(null)
const startedAt = ref(null)
const clockTimer = ref(null)
const elapsed = ref(0)
// 新建会话弹窗
const showNew = ref(false)
const newTitle = ref('')
const newDsId = ref('')
// 删除确认
const delTarget = ref(null)
// 附件侧栏（PRD 2.1.3：文件名/类型/大小/上传时间/解析状态 + 上传/删除/下载）
const atts = ref([])
const attLoading = ref(false)
const uploading = ref(false)
const fileInput = ref(null)

const currentConv = computed(() => convStore.current)
const messages = computed(() => (currentConv.value ? msgStore.messages(currentConv.value.conversation_id) : []))
const currentTaskId = computed(() => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].task_id || msgs[i].message_type === 'result') return msgs[i].task_id
  }
  return null
})
const currentResult = computed(() => (currentTaskId.value ? msgStore.results[currentTaskId.value] : null))
const streaming = computed(() => (currentTaskId.value ? msgStore.streaming[currentTaskId.value] : null))
const taskStatus = computed(() => (currentTaskId.value ? taskStore.byId[currentTaskId.value]?.task_status : null))
const currentTools = computed(() => (currentTaskId.value ? msgStore.tools[currentTaskId.value] || [] : []))
const currentStep = computed(() => (currentTaskId.value ? taskStore.byId[currentTaskId.value]?.current_step || 0 : 0))
const maxSteps = 8
const currentDs = computed(() => {
  if (!currentConv.value?.data_source_id) return null
  return dsStore.list.find((d) => d.id === currentConv.value.data_source_id) || null
})

// ---- 任务区 5 步概念进度 ----
const STEP_LABELS = ['问题拆解', '数据查询', '交叉归因', '结论生成', '落库导出']
const stepProgress = computed(() => {
  const s = taskStatus.value
  if (s === 'success') return { done: 5, on: 5, fail: false }
  if (s === 'failed' || s === 'cancelled') return { done: 0, on: currentStep.value, fail: true }
  if (!s || s === 'queued') return { done: 0, on: 0, fail: false }
  const ratio = currentStep.value / maxSteps
  const on = Math.max(1, Math.min(5, Math.ceil(ratio * 5)))
  return { done: on - 1, on, fail: false }
})

// ---- 步骤耗时 / 记录数（客户端按 current_step 分段统计） ----
const stepTimes = ref({ 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 })
const records = ref({})
let segStart = null
let segStep = 0
function conceptualStep(cs) {
  if (!cs) return 0
  return Math.max(1, Math.min(5, Math.ceil((cs / maxSteps) * 5)))
}
function stepTick(cs, finalize = false) {
  const now = Date.now()
  const st = conceptualStep(cs)
  if (segStart && segStep && (finalize || segStep !== st)) {
    stepTimes.value[segStep] += (now - segStart) / 1000
  }
  if (finalize) { segStart = null; segStep = 0 }
  else if (!segStart || segStep !== st) { segStart = now; segStep = st }
}
const steps = computed(() => {
  const p = stepProgress.value
  return STEP_LABELS.map((lbl, i) => {
    const idx = i + 1
    let st = p.done >= idx ? 'done' : (p.on === idx ? 'on' : 'pending')
    if (p.fail && p.on === idx) st = 'fail'
    let meta = ''
    if (st === 'done') {
      if (idx === 2 && records.value[2]) meta = `${records.value[2].toLocaleString()} 条记录`
      else if (stepTimes.value[idx]) meta = `${stepTimes.value[idx].toFixed(1)}s`
    } else if (st === 'on') meta = '分析中…'
    return { label: lbl, st, meta, idx }
  })
})
// 从 db_query 工具结果中提取记录数（用于「数据查询」步骤展示）
watch(() => (currentTaskId.value ? msgStore.tools[currentTaskId.value] : null), (arr) => {
  if (!arr) return
  for (const t of arr) {
    if (t.status === 'success' && t.table && /query/.test(t.name)) {
      records.value[2] = Math.max(records.value[2] || 0, t.table.total || 0)
    }
  }
}, { deep: true })

// ---- 六段式状态机（运行中渐进点亮，成功后全绿） ----
const SIX = [
  ['问题定义', 'problem_definition'], ['关键指标', 'key_metrics'], ['证据链', 'evidence_list'],
  ['归因结论', 'conclusion'], ['缺失数据', 'missing_data'], ['下一步建议', 'next_action']
]
function sixState(i) {
  const s = taskStatus.value
  if (!currentTaskId.value || !s) return 'ghost'
  if (s === 'success') return 'done'
  if (s === 'failed' || s === 'cancelled') return 'fail'
  const cs = currentStep.value
  if (i === 0) return cs >= 2 ? 'done' : 'on'
  if (i === 1) return cs >= 4 ? 'done' : (cs >= 2 ? 'on' : 'pending')
  if (i === 2) return cs >= 4 ? 'on' : 'pending'
  return 'pending'
}

// ---- 运行计时 ----
function startClock() {
  stopClock()
  startedAt.value = Date.now()
  elapsed.value = 0
  clockTimer.value = setInterval(() => { elapsed.value = Math.floor((Date.now() - startedAt.value) / 1000) }, 1000)
}
function stopClock() {
  if (clockTimer.value) { clearInterval(clockTimer.value); clockTimer.value = null }
}
function mmss(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

// ---- WS 事件绑定 ----
const handlers = {}
function bindWs() {
  ;['message_delta', 'tool_start', 'tool_end', 'result_ready', 'cancelled', 'error', 'task_status'].forEach((t) => {
    handlers[t] = (env) => {
      if (env.conversation_id !== convStore.current?.conversation_id) return
      if (t === 'task_status') {
        taskStore.applyStatus(env)
        const p = env.payload || {}
        if (p.task_status === 'running') { startClock(); stepTick(p.current_step) }
        else if (['success', 'failed', 'cancelled'].includes(p.task_status)) { stopClock(); stepTick(p.current_step, true) }
        else stepTick(p.current_step)
      } else msgStore.applyEvent(env)
      scrollBottom()
    }
    wsClient.on(t, handlers[t])
  })
  handlers.connected = () => window.$toast('实时通道已连接', 'success')
  handlers.disconnected = () => window.$toast('实时通道断开，重连中…', 'warn')
  wsClient.on('connected', handlers.connected)
  wsClient.on('disconnected', handlers.disconnected)
}
function unbindWs() {
  Object.entries(handlers).forEach(([t, fn]) => wsClient.off(t, fn))
}

// ---- 会话 ----
async function newConv() {
  if (!dsStore.list.length) { try { await dsStore.fetch() } catch {} }
  newTitle.value = ''
  newDsId.value = dsStore.list.length ? dsStore.list[0].id : ''
  showNew.value = true
}
async function confirmNew() {
  if (!newTitle.value.trim()) newTitle.value = '新会话'
  const conv = await convStore.create(newTitle.value.trim(), newDsId.value || null)
  showNew.value = false
  await selectConv(conv)
}
async function selectConv(conv) {
  if (convStore.current?.conversation_id === conv.conversation_id) return
  stopClock()
  convStore.select(conv)
  await msgStore.loadHistory(conv.conversation_id)
  await loadAtts()
  // 回填历史六段式结果
  if (currentTaskId.value && !msgStore.results[currentTaskId.value]) {
    try {
      const res = await fetch(`/api/results/${currentTaskId.value}`, { credentials: 'include' })
      if (res.ok) msgStore.results[currentTaskId.value] = await res.json()
    } catch { /* 回填失败不阻塞 */ }
  }
  // 回填历史任务状态（避免任务区误显示 queued）
  if (currentTaskId.value && !taskStore.byId[currentTaskId.value]?.task_status) {
    try {
      const t = await taskStore.fetch(currentTaskId.value)
      if (t.task_status === 'running') { startClock(); stepTick(t.current_step) }
    } catch { /* 状态回填失败不阻塞 */ }
  }
  if (!dsStore.list.length) { try { await dsStore.fetch() } catch {} }
  try { await taskStore.connectWs(conv.conversation_id) } catch { /* WS 失败不阻塞 */ }
  scrollBottom()
}
function askDelete(conv) {
  delTarget.value = conv
}

// ---- 附件侧栏 ----
async function loadAtts() {
  const cid = convStore.current?.conversation_id
  if (!cid) { atts.value = []; return }
  attLoading.value = true
  try {
    const data = await api.attachmentsList(cid)
    atts.value = data.items || []
  } catch { atts.value = [] } finally { attLoading.value = false }
}
async function onFilePick(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file || !currentConv.value || uploading.value) return
  uploading.value = true
  const fd = new FormData()
  fd.append('conversation_id', currentConv.value.conversation_id)
  fd.append('file', file)
  try {
    await api.upload(fd)
    window.$toast('上传成功', 'success')
    await loadAtts()
  } catch (err) { window.$toast(err.message || '上传失败', 'error') }
  finally { uploading.value = false }
}
async function delAtt(a) {
  try {
    await api.attachmentDel(a.attachment_id)
    atts.value = atts.value.filter((x) => x.attachment_id !== a.attachment_id)
    window.$toast('附件已删除', 'success')
  } catch (e) { window.$toast(e.message, 'error') }
}
function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
function parseLabel(s) {
  return { pending: '待解析', parsing: '解析中', parsed: '已解析', failed: '解析失败' }[s] || s || ''
}
async function confirmDelete() {
  if (!delTarget.value) return
  try {
    await convStore.remove([delTarget.value.conversation_id])
    window.$toast('会话已删除', 'success')
    // 若当前会话被删，回到空态
    if (!convStore.current) msgStore.byConv = {}
  } catch (e) { window.$toast(e.message, 'error') }
  delTarget.value = null
}
async function logout() {
  await auth.logout()
  router.push('/login')
}

// ---- 发送 ----
async function send() {
  const content = input.value.trim()
  if (!content || !currentConv.value) return
  input.value = ''
  const cid = currentConv.value.conversation_id
  msgStore.byConv[cid] = msgStore.byConv[cid] || []
  msgStore.byConv[cid].push({ message_id: 'local-' + Date.now(), role: 'user', message_type: 'text', content, seq_no: Date.now() })
  scrollBottom()
  try {
    const res = await taskStore.send(cid, content)
    msgStore.byConv[cid].push({
      message_id: 't-' + res.task_id, role: 'assistant', message_type: 'stream',
      content: '', seq_no: Date.now() + 1, task_id: res.task_id
    })
    startPoll(res.task_id)
  } catch (e) { window.$toast(e.message, 'error') }
}
function startPoll(taskId) {
  clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const t = await taskStore.fetch(taskId)
      if (t.task_status === 'running') { startClock(); stepTick(t.current_step) }
      if (['success', 'failed', 'cancelled'].includes(t.task_status)) {
        clearInterval(pollTimer.value); pollTimer.value = null
        stopClock(); stepTick(t.current_step, true)
        if (currentConv.value) await msgStore.loadHistory(currentConv.value.conversation_id, { keepWs: true })
        if (t.task_status === 'success') {
          const res = await fetch(`/api/results/${taskId}`, { credentials: 'include' })
          if (res.ok) msgStore.results[taskId] = await res.json()
        }
      }
    } catch { clearInterval(pollTimer.value); pollTimer.value = null }
  }, 2000)
}
async function cancelTask() {
  if (!currentTaskId.value) return
  try { await taskStore.cancel(currentTaskId.value) } catch (e) { window.$toast(e.message, 'error') }
}
function fillExample(q) { input.value = q }

// ---- 结果面板辅助 ----
function evList(res) { return res?.evidence_list || [] }
function kmList(res) { return res?.key_metrics || [] }
function fmtTime(sec) {
  if (!sec) return '0s'
  const m = Math.floor(sec / 60), s = sec % 60
  return m ? `${m}m${s}s` : `${s}s`
}
function fmtDt(s) { return s ? s.slice(0, 16).replace('T', ' ') : '' }
function fmtClock(s) {
  if (!s) return ''
  const d = new Date(s)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
function fmtConvTime(s) {
  if (!s) return ''
  const d = new Date(s)
  const now = new Date()
  const sod = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((sod(now) - sod(d)) / 86400000)
  if (diff === 0) return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  if (diff === 1) return '昨天'
  return `${d.getMonth() + 1}/${d.getDate()}`
}
function copyResult() {
  const res = currentResult.value
  if (!res) return
  const parts = [
    `【问题定义】${res.problem_definition}`,
    `【关键指标】${kmList(res).map(m => `${m.metric_name}: ${m.metric_value} ${m.metric_unit}（${m.metric_period}）`).join('；')}`,
    `【证据链】${evList(res).map(e => `[${e.source_name}] ${e.evidence_text}（${Math.round(e.confidence * 100)}%）`).join('；')}`,
    `【归因结论】${res.conclusion_text}`,
    res.missing_data_text ? `【数据缺口】${res.missing_data_text}` : '',
    res.next_action_text ? `【下一步建议】${res.next_action_text}` : '',
  ].filter(Boolean).join('\n\n')
  navigator.clipboard?.writeText(parts).then(() => window.$toast('已复制到剪贴板', 'success'))
}

onMounted(() => {
  convStore.fetchList().catch(() => {}).then(() => {
    // 自动恢复最近分析任务（无选中会话时默认选中最新一条）
    if (!convStore.current && convStore.list.length) {
      selectConv(convStore.list[0])
    }
  })
  dsStore.fetch().catch(() => {})
  bindWs()
  if (currentConv.value) loadAtts()
})
onUnmounted(() => {
  clearInterval(pollTimer.value)
  stopClock()
  unbindWs()
})
</script>

<template>
  <div class="chat-layout">
    <!-- 左栏：分析任务列表 -->
    <aside class="conv-panel">
      <div class="conv-new">
        <button class="btn primary block" @click="newConv">＋ 新建分析</button>
      </div>
      <div class="conv-sec">分析任务 <span class="muted">{{ convStore.list.length }}</span></div>
      <ul class="conv-list">
        <li v-for="c in convStore.list" :key="c.conversation_id"
            class="conv-item" :class="{ active: c.conversation_id === currentConv?.conversation_id }"
            @click="selectConv(c)">
          <div class="t">{{ c.title }}</div>
          <div class="d">
            <span>{{ fmtConvTime(c.last_message_at) }}</span>
            <span v-if="c.conversation_id === currentConv?.conversation_id && taskStatus === 'running'" class="st">进行中</span>
            <span class="del" @click.stop="askDelete(c)">删除</span>
          </div>
        </li>
        <li v-if="!convStore.list.length" class="empty">暂无分析任务<br />点「新建分析」开始</li>
      </ul>
      <div class="conv-user">
        <div class="avatar" :class="auth.user?.role === 'admin' ? 'blue' : 'green'">
          {{ (auth.user?.display_name || auth.user?.username || 'U').slice(0, 1).toUpperCase() }}
        </div>
        <div style="flex: 1; min-width: 0;">
          <div class="nm">{{ auth.user?.display_name || auth.user?.username }}</div>
          <div class="rl">{{ auth.user?.role === 'admin' ? '系统管理员' : '分析师' }}</div>
        </div>
        <button v-if="auth.isAdmin" class="btn sm" title="管理后台" @click="router.push('/admin')">⚙</button>
        <button class="btn sm" title="退出登录" @click="logout">退出</button>
      </div>
    </aside>

    <!-- 中栏：对话区 -->
    <section class="chat-panel">
      <div class="chat-head">
        <span>{{ currentConv?.title || '选择或新建分析' }}</span>
        <span v-if="taskStatus" class="chip" :class="taskStatus">{{ taskStatus }}</span>
        <span class="spacer"></span>
        <span v-if="currentDs" class="muted" style="font-size: 12px;">{{ currentDs.name }}</span>
      </div>
      <!-- 附件侧栏（PRD 2.1.3） -->
      <div v-if="currentConv" class="attachbar">
        <span class="att-title">📎 附件</span>
        <div class="att-list">
          <div v-for="a in atts" :key="a.attachment_id" class="att-item">
            <span class="att-ico" :class="'t-' + (a.file_type || 'bin').split('/')[0].split('.')[0]">{{ (a.file_type || '?').slice(0, 4) }}</span>
            <a class="att-name" :href="api.attachmentDownloadUrl(a.attachment_id)" :download="a.file_name" :title="a.file_name">{{ a.file_name }}</a>
            <span class="att-meta">{{ fmtSize(a.file_size) }} · {{ fmtDt(a.created_at) }}</span>
            <span class="chip" :class="a.parse_status">{{ parseLabel(a.parse_status) }}</span>
            <button class="att-del" title="删除" @click="delAtt(a)">✕</button>
          </div>
          <span v-if="!attLoading && !atts.length" class="att-empty">暂无附件，上传 csv/txt/md 等供分析引用</span>
        </div>
        <button class="btn sm att-upload" :disabled="uploading" @click="fileInput && fileInput.click()">
          {{ uploading ? '上传中…' : '＋ 上传' }}
        </button>
        <input ref="fileInput" type="file" class="file-input"
               accept=".txt,.csv,.md,.json,.log,.tsv,.yaml,.yml,.pdf,.xlsx,.xls,.docx,.png,.jpg,.jpeg,.zip"
               @change="onFilePick" />
      </div>
      <div class="msg-list" ref="msgListEl">
        <!-- 空态 -->
        <div v-if="!messages.length" class="chat-empty">
          <div class="ico-wrap" aria-hidden="true">
            <span class="bubble-e e1">💬</span>
            <span class="bubble-e e2">📊</span>
            <span class="bubble-e e3">✨</span>
          </div>
          <div class="tip">你好呀，我是你的归因分析小助手 🌱</div>
          <div class="sub">试着问点业务问题，从下面挑一个开始吧</div>
          <button class="ex" @click="fillExample('为什么 6 月信息流渠道点击量下滑？')">🍦 为什么 6 月信息流渠道点击量下滑？</button>
          <button class="ex" @click="fillExample('分析 6 月各渠道 GMV 排名与环比变化，谁表现最好？')">🍬 6 月各渠道 GMV 排名与环比，谁表现最好？</button>
        </div>

        <!-- 消息 -->
        <div v-for="(m, i) in messages" :key="m.message_id || i" class="msg" :class="m.role">
          <template v-if="m.role === 'user'">
            <div class="bubble user">
              <div v-if="m.created_at" class="meta">{{ fmtClock(m.created_at) }}</div>
              {{ m.content }}
            </div>
          </template>
          <template v-else>
            <div class="bubble assistant" :class="{ failed: taskStatus === 'failed', cancelled: taskStatus === 'cancelled' }">
              <div v-if="m.created_at" class="meta">{{ fmtClock(m.created_at) }}</div>
              <div v-if="m.message_type === 'stream'" class="stream-text">
                {{ m.content || streaming?.text || '' }}<span v-if="streaming && !streaming.done" class="caret"></span>
              </div>
              <div v-else-if="m.message_type === 'result'" class="stream-text">{{ m.content }}</div>
              <div v-else>{{ m.content }}</div>
            </div>
            <!-- 工具卡片（当前任务） -->
            <div v-if="m.task_id && m.task_id === currentTaskId" class="msg assistant" style="width: 100%;">
              <div v-for="(tc, ti) in currentTools" :key="ti" class="toolcard" :class="{ failed: tc.status === 'failed' }">
                <div class="hd">
                  <span class="chip" :class="tc.status === 'running' ? 'running' : (tc.status === 'failed' ? 'failed' : 'success')">{{ tc.status }}</span>
                  <span class="nm">{{ tc.name }}</span>
                  <span class="muted" style="font-size: 11px;">{{ tc.arg }}</span>
                  <span class="spacer"></span>
                  <span v-if="tc.duration" class="dur">{{ tc.duration.toFixed(1) }}s</span>
                </div>
                <div class="bd">{{ tc.summary || '执行中…' }}</div>
                <table v-if="tc.table && tc.table.rows && tc.table.rows.length" class="tool-table">
                  <thead>
                    <tr><th v-for="(c, ci) in tc.table.columns" :key="ci">{{ c }}</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(r, ri) in tc.table.rows" :key="ri">
                      <td v-for="(v, vi) in r" :key="vi" :title="String(v ?? '')">{{ v ?? '' }}</td>
                    </tr>
                  </tbody>
                </table>
                <div v-if="tc.table && tc.table.rows && tc.table.rows.length" class="tmeta">数据行数: {{ (tc.table.total || tc.table.rows.length).toLocaleString() }}</div>
              </div>
            </div>
          </template>
        </div>
        <!-- 流式进行中的独立渲染 -->
        <div v-if="streaming && !streaming.done && !messages.some(m => m.message_type === 'stream' && m.task_id === currentTaskId)" class="msg assistant">
          <div class="bubble assistant"><span class="stream-text">{{ streaming.text }}</span><span class="caret"></span></div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <textarea class="textinput" v-model="input" rows="2" placeholder="输入你的分析需求，Enter 发送，Shift+Enter 换行…"
                  @keydown.enter.exact.prevent="send" @keydown.shift.enter.prevent></textarea>
        <div class="input-bar">
          <span class="hint">Enter 发送 · Shift+Enter 换行</span>
          <span class="spacer"></span>
          <button class="btn primary sm" :disabled="taskStore.sending || !input.trim()" @click="send">发送</button>
        </div>
      </div>
    </section>

    <!-- 右栏：实时任务区 + 六级式结果 -->
    <aside class="result-panel">
      <div class="taskbar">
        <div class="hd">
          <b>实时任务区</b>
          <span class="chip" :class="taskStatus || 'queued'">{{ taskStatus || (currentTaskId ? 'queued' : '—') }}</span>
          <span class="spacer"></span>
          <span v-if="currentTaskId" class="timer">{{ mmss(elapsed) }}</span>
        </div>
        <div class="step-row">
          <div v-for="s in steps" :key="s.label" class="step" :class="s.st">
            <span class="step-dot" :class="s.st">{{ s.st === 'done' ? '✓' : (s.st === 'fail' ? '✕' : (s.st === 'on' ? '◉' : s.idx)) }}</span>
            <span class="step-lbl">{{ s.label }}</span>
            <span v-if="s.meta" class="step-meta">{{ s.meta }}</span>
          </div>
          <div class="step cancel">
            <button class="btn sm danger" :disabled="taskStatus !== 'running'" @click="cancelTask">✕ 取消任务</button>
          </div>
        </div>
        <div class="meta-line" v-if="currentTaskId">步骤 {{ currentStep }}/{{ maxSteps }} · 已运行 {{ fmtTime(elapsed) }}</div>
      </div>

      <div class="six-head">六段式分析结果</div>
      <div class="cloud-divider">·　·　·</div>
      <div class="six">
        <!-- 六段式：运行中渐进点亮 / 成功后全绿 / 未开始 ghost 占位 -->
        <div v-for="(s, i) in SIX" :key="i" class="item" :class="sixState(i)">
          <div class="k">
            <span class="idx">{{ sixState(i) === 'done' ? '✓' : i + 1 }}</span>{{ s[0] }}<span class="en">{{ s[1] }}</span>
            <span v-if="sixState(i) === 'on' && i === 2" class="chip running" style="margin-left: auto;">交叉验证中</span>
          </div>
          <!-- 1 问题定义 -->
          <div v-if="currentResult && i === 0" class="body">{{ currentResult.problem_definition }}</div>
          <!-- 2 关键指标 -->
          <div v-else-if="currentResult && i === 1" class="body">
            <div v-for="m in kmList(currentResult)" :key="m.metric_name" class="km">
              <span>{{ m.metric_name }}</span><span class="v">{{ m.metric_value }} <small class="muted">{{ m.metric_unit }} {{ m.metric_period }}</small></span>
            </div>
            <p v-if="!kmList(currentResult).length" class="muted">—</p>
          </div>
          <!-- 3 证据链（含交叉验证进度条） -->
          <div v-else-if="i === 2" class="body">
            <template v-if="currentResult">
              <div v-for="(e, ei) in evList(currentResult)" :key="ei" class="ev">
                <span class="src">[{{ e.source_name }}]</span> {{ e.evidence_text }}
                <span class="conf">{{ Math.round((e.confidence || 0) * 100) }}%</span>
              </div>
              <p v-if="!evList(currentResult).length" class="muted">—</p>
            </template>
            <div v-if="sixState(2) === 'on'" class="ev-progress indet"><div class="bar"></div></div>
            <div v-else-if="sixState(2) === 'done'" class="ev-progress done"><div class="bar"></div></div>
          </div>
          <!-- 4 归因结论 -->
          <div v-else-if="currentResult && i === 3" class="body">{{ currentResult.conclusion_text }}</div>
          <!-- 5 缺失数据 -->
          <div v-else-if="currentResult && i === 4" class="body">{{ currentResult.missing_data_text || '—' }}</div>
          <!-- 6 下一步建议 -->
          <div v-else-if="currentResult && i === 5" class="body">{{ currentResult.next_action_text || '—' }}</div>
          <!-- 运行中未产出的段 -->
          <div v-else-if="sixState(i) === 'on'" class="body muted">分析中…</div>
        </div>
        <div v-if="!currentTaskId" class="empty" style="padding: 14px;">选择分析任务并提问后，六级式结论将展示在这里</div>
      </div>
      <div class="actions">
        <button class="btn sm" :class="{ disabled: !currentResult }" @click="copyResult">复制</button>
        <button class="btn sm" :class="{ disabled: true }" title="导出功能开发中">导出</button>
      </div>
    </aside>

    <!-- 新建分析弹窗（P5） -->
    <div v-if="showNew" class="modal-mask" @click.self="showNew = false">
      <div class="modal">
        <div class="mh">新建分析 <span style="color: var(--gray); font-weight: 400; font-size: 12px; cursor: pointer;" @click="showNew = false">✕</span></div>
        <div class="mb">
          <label class="f-label">分析标题</label>
          <input class="textinput" v-model="newTitle" placeholder="例如：7 月商品目录优化" @keydown.enter.prevent="confirmNew" />
          <label class="f-label" style="margin-top: 14px;">数据源（会话绑定，分析引擎只在此源内查询）</label>
          <div v-for="d in dsStore.list" :key="d.id" class="ds-opt" :class="{ sel: newDsId === d.id, disabled: !d.is_enabled }" @click="d.is_enabled && (newDsId = d.id)">
            <div class="ico">{{ d.database === 'scenario_goods' ? '🛒' : (d.database === 'scenario_inventory' ? '📦' : '🗄️') }}</div>
            <div class="info">
              <div class="n">{{ d.name }}</div>
              <div class="d">schema: {{ d.database }} · {{ d.host }}:{{ d.port }} {{ d.is_enabled ? '' : '（已停用）' }}</div>
            </div>
            <div class="radio"></div>
          </div>
          <div v-if="!dsStore.list.length" class="empty">暂无可选数据源</div>
        </div>
        <div class="mf">
          <button class="btn" @click="showNew = false">取消</button>
          <button class="btn primary" @click="confirmNew">创建并进入</button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗（P2-2） -->
    <div v-if="delTarget" class="modal-mask" @click.self="delTarget = null">
      <div class="modal">
        <div class="mh">确认删除会话</div>
        <div class="mb">
          <div class="note" style="margin: 0;">删除会话「{{ delTarget.title }}」将移除其全部消息与结果，此操作不可恢复。</div>
        </div>
        <div class="mf">
          <button class="btn" @click="delTarget = null">取消</button>
          <button class="btn danger" @click="confirmDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>
