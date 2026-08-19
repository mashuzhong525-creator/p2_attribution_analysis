import { defineStore } from 'pinia'
import { api } from '../api/client'
import { wsClient } from '../ws/wsClient'

export const useTaskStore = defineStore('task', {
  state: () => ({
    byId: {},       // taskId -> {status, current_step, ...}
    sending: false
  }),
  actions: {
    async send(conversationId, content, attachmentIds = []) {
      this.sending = true
      try {
        const res = await api.post('/api/chat/send', {
          conversation_id: conversationId,
          content,
          attachment_ids: attachmentIds.length ? attachmentIds : null
        })
        this.byId[res.task_id] = { task_id: res.task_id, task_status: 'queued', queue_position: res.queue_position }
        return res
      } finally {
        this.sending = false
      }
    },
    async cancel(taskId) {
      await api.post(`/api/tasks/${taskId}/cancel`, {})
      this.byId[taskId] = { ...(this.byId[taskId] || {}), task_status: 'cancelled' }
    },
    async fetch(taskId) {
      const t = await api.get(`/api/tasks/${taskId}`)
      this.byId[taskId] = t
      return t
    },
    // WS task_status 事件 → 同步状态
    applyStatus(env) {
      const t = env.payload || {}
      this.byId[t.task_id] = { ...(this.byId[t.task_id] || {}), ...t }
    },
    // 连接会话：取 ws-token 并建连；自动重连时同样刷新一次性令牌
    async connectWs(conversationId) {
      const mint = async () => {
        const { websocket_token: token } = await api.post('/api/chat/ws-token', { conversation_id: conversationId })
        return token
      }
      wsClient.tokenRefresher = mint
      await wsClient.connect(conversationId, await mint())
    }
  }
})
