<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useConversationStore } from '../stores/conversation'
import { useMessageStore } from '../stores/message'
import { useTaskStore } from '../stores/task'
import { useDatasourceStore } from '../stores/datasource'
import { wsClient } from '../ws/wsClient'

const convStore = useConversationStore()
const msgStore = useMessageStore()
const taskStore = useTaskStore()
const dsStore = useDatasourceStore()

const input = ref('')
const msgListEl = ref(null)
const pollTimer = ref(null)

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

// ---- WS 事件绑定 ----
const handlers = {}
function bindWs() {
  ;['message_delta', 'tool_start', 'tool_end', 'result_ready', 'cancelled', 'error', 'task_status'].forEach((t) => {
    handlers[t] = (env) => {
      if (env.conversation_id !== convStore.current?.conversation_id) return
      if (t === 'task_status') taskStore.applyStatus(env)
      else msgStore.applyEvent(env)
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
  const conv = await convStore.create('新会话')
  await selectConv(conv)
}
async function selectConv(conv) {
  if (convStore.current?.conversation_id === conv.conversation_id) return
  convStore.select(conv)
  await msgStore.loadHistory(conv.conversation_id)
  if (dsStore.list.length === 0) { try { await dsStore.fetch() } catch {} }
  // 建立 WS
  try {
    await taskStore.connectWs(conv.conversation_id)
  } catch (e) {
    window.$toast('实时通道连接失败：' + e.message, 'warn')
  }
  scrollBottom()
}
function scrollBottom() {
  nextTick(() => { if (msgListEl.value) msgListEl.value.scrollTop = msgListEl.value.scrollHeight })
}

// ---- 发送 ----
async function send() {
  const content = input.value.trim()
  if (!content || !currentConv.value) return
  input.value = ''
  msgStore.byConv[currentConv.value.conversation_id] = msgStore.byConv[currentConv.value.conversation_id] || []
  msgStore.byConv[currentConv.value.conversation_id].push({
    message_id: 'local-' + Date.now(), role: 'user', message_type: 'text', content, seq_no: Date.now()
  })
  scrollBottom()
  try {
    const res = await taskStore.send(currentConv.value.conversation_id, content)
    msgStore.byConv[currentConv.value.conversation_id].push({
      message_id: 't-' + res.task_id, role: 'assistant', message_type: 'stream',
      content: '', seq_no: Date.now() + 1, task_id: res.task_id
    })
    startPoll(res.task_id)
  } catch (e) {
    window.$toast(e.message, 'error')
  }
}
function startPoll(taskId) {
  clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const t = await taskStore.fetch(taskId)
      if (['success', 'failed', 'cancelled'].includes(t.task_status)) {
        clearInterval(pollTimer.value)
        pollTimer.value = null
        // 终态后补拉历史（拿到落库的 result 消息）
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

// ---- 结果面板辅助 ----
function evList(res) { return res?.evidence_list || [] }
function kmList(res) { return res?.key_metrics || [] }

onMounted(() => {
  convStore.fetchList().catch(() => {})
  bindWs()
})
onUnmounted(() => {
  clearInterval(pollTimer.value)
  unbindWs()
})
</script>

<template>
  <div class="chat-layout">
    <!-- 左栏：会话列表 -->
    <aside class="conv-panel">
      <div class="panel-head">
        <span>会话</span>
        <button class="btn sm primary" @click="newConv">+ 新建</button>
      </div>
      <ul class="conv-list">
        <li v-for="c in convStore.list" :key="c.conversation_id"
            :class="{ active: c.conversation_id === currentConv?.conversation_id }"
            @click="selectConv(c)">
          <div class="conv-title">{{ c.title }}</div>
          <div class="conv-time muted">{{ c.last_message_at ? c.last_message_at.slice(0, 16).replace('T', ' ') : '' }}</div>
        </li>
        <li v-if="!convStore.list.length" class="empty muted">暂无会话，点「新建」开始</li>
      </ul>
    </aside>

    <!-- 中栏：对话 -->
    <section class="chat-panel">
      <div class="chat-head">
        <span>{{ currentConv?.title || '选择或新建会话' }}</span>
        <span v-if="taskStatus" class="chip" :class="taskStatus">{{ taskStatus }}</span>
      </div>
      <div class="msg-list" ref="msgListEl">
        <div v-for="(m, i) in messages" :key="m.message_id || i" class="msg" :class="m.role">
          <div class="bubble" :class="m.role">
            <template v-if="m.message_type === 'result' || (m.role === 'assistant' && m.content)">
              <div class="stream-text">{{ m.content || streaming?.text }}</div>
              <div v-if="m.message_type === 'stream' && !streaming?.done" class="caret"></div>
            </template>
            <template v-else>{{ m.content }}</template>
          </div>
        </div>
        <div v-if="streaming && !streaming.done" class="msg assistant">
          <div class="bubble assistant"><span class="stream-text">{{ streaming.text }}</span><span class="caret"></span></div>
        </div>
      </div>
      <div class="chat-input">
        <textarea v-model="input" rows="2" placeholder="输入经营问题，如：为什么 6 月信息流渠道点击量下滑？"
                  @keydown.ctrl.enter.prevent="send"></textarea>
        <div class="input-bar">
          <span class="muted">Ctrl+Enter 发送</span>
          <button class="btn primary" :disabled="taskStore.sending" @click="send">发送</button>
          <button v-if="taskStatus === 'running'" class="btn ghost danger" @click="cancelTask">取消</button>
        </div>
      </div>
    </section>

    <!-- 右栏：结果 -->
    <aside class="result-panel">
      <div class="panel-head"><span>归因结果</span></div>
      <template v-if="currentResult">
        <div class="res-sec">
          <h4>问题定义</h4>
          <p>{{ currentResult.problem_definition }}</p>
        </div>
        <div class="res-sec">
          <h4>关键指标</h4>
          <table class="km-table">
            <tr v-for="km in kmList(currentResult)" :key="km.metric_name">
              <td>{{ km.metric_name }}</td>
              <td class="km-val">{{ km.metric_value }}<span class="muted"> {{ km.metric_unit }} {{ km.metric_period }}</span></td>
            </tr>
          </table>
        </div>
        <div class="res-sec">
          <h4>证据链</h4>
          <ul class="ev-list">
            <li v-for="(ev, i) in evList(currentResult)" :key="i">
              <span class="ev-src">[{{ ev.source_name }}]</span> {{ ev.evidence_text }}
              <span class="muted">({{ Math.round(ev.confidence * 100) }}%)</span>
            </li>
          </ul>
        </div>
        <div class="res-sec">
          <h4>归因结论</h4>
          <p class="conclusion">{{ currentResult.conclusion_text }}</p>
        </div>
        <div v-if="currentResult.missing_data_text" class="res-sec">
          <h4>数据缺口</h4><p>{{ currentResult.missing_data_text }}</p>
        </div>
        <div v-if="currentResult.next_action_text" class="res-sec">
          <h4>下一步建议</h4><p>{{ currentResult.next_action_text }}</p>
        </div>
      </template>
      <div v-else class="empty muted">选择会话并提问后，六段式结论将展示在这里</div>
    </aside>
  </div>
</template>
