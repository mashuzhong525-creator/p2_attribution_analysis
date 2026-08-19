import { defineStore } from 'pinia'
import { api } from '../api/client'
import { wsClient } from '../ws/wsClient'

// 消息与结果：按会话缓存 + WS 增量 + REST 补偿
export const useMessageStore = defineStore('message', {
  state: () => ({
    byConv: {},       // convId -> messages[]
    results: {},      // taskId -> 六段式结果
    streaming: {},    // taskId -> { text, done }
    tools: {},        // taskId -> [{name,status,summary}]
    ready: false
  }),
  actions: {
    messages(convId) {
      return this.byConv[convId] || []
    },

    async loadHistory(convId, options = {}) {
      const data = await api.get(`/api/chat/ls/${convId}`)
      this.byConv[convId] = data.items || []
      // REST 补偿：把 WS 游标抬到历史最大 seq（若从未连过）
      if (!options.keepWs) {
        const maxSeq = (data.items || []).reduce((m, i) => Math.max(m, i.seq_no || 0), 0)
        if (wsClient.maxSeq < maxSeq) wsClient.maxSeq = maxSeq
      }
      return this.byConv[convId]
    },

    // ---- WS 事件分发（wsClient 各 type handler 汇聚到这里）----
    applyEvent(env) {
      const { type, payload, conversation_id: cid, task_id } = env
      if (!cid || !this.byConv[cid]) return
      if (type === 'message_delta' && payload.delta_text) {
        if (!this.streaming[task_id]) this.streaming[task_id] = { text: '', done: false }
        this.streaming[task_id].text += payload.delta_text
      }
      if (type === 'tool_start') {
        const arg = payload.args ? JSON.stringify(payload.args) : ''
        this.tools[task_id] = this.tools[task_id] || []
        this.tools[task_id].push({ name: payload.name, status: 'running', summary: '', arg: arg.slice(0, 60), t0: Date.now() })
      }
      if (type === 'tool_end') {
        const arr = this.tools[task_id] || []
        const t = arr[arr.length - 1]
        if (t && t.name === payload.name) {
          t.status = payload.success ? 'success' : 'failed'
          t.summary = payload.summary || payload.error || ''
          t.duration = t.t0 ? Math.round((Date.now() - t.t0) / 100) / 10 : null
          t.table = payload.table || null
        }
      }
      if (type === 'result_ready') {
        this.results[payload.task_id] = payload.result
        this.streaming[task_id] = { text: payload.result?.conclusion_text || '', done: true }
        // 同步进消息列表（assistant result 消息）
        this.byConv[cid].push({
          message_id: `ws-${payload.result_id}`,
          role: 'assistant',
          message_type: 'result',
          content: payload.result?.conclusion_text || '',
          seq_no: env.seq,
          task_id: payload.task_id
        })
      }
      if (type === 'cancelled') {
        this.streaming[task_id] = this.streaming[task_id] || { text: '', done: true }
        this.streaming[task_id].done = true
      }
      if (type === 'error') {
        this.streaming[task_id] = { text: `分析失败：${payload.message || '未知错误'}`, done: true }
      }
    },

    clearConv(convId) {
      delete this.byConv[convId]
    }
  }
})
