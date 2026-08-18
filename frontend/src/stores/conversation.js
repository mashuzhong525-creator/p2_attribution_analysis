import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useConversationStore = defineStore('conversation', {
  state: () => ({
    list: [],
    current: null,
    loading: false
  }),
  actions: {
    async fetchList() {
      const data = await api.get('/api/chat/ls?page=1&page_size=50')
      this.list = data.items || []
      return this.list
    },
    async create(title = '新会话', dataSourceId = null) {
      const conv = await api.post('/api/chat/create', { title, data_source_id: dataSourceId })
      this.list.unshift(conv)
      return conv
    },
    async rename(conversationId, title) {
      const conv = await api.post('/api/chat/update', { conversation_id: conversationId, title })
      const i = this.list.findIndex((c) => c.conversation_id === conversationId)
      if (i >= 0) this.list[i] = conv
      return conv
    },
    async remove(ids) {
      const res = await api.post('/api/chat/delete', { conversation_ids: ids })
      this.list = this.list.filter((c) => !ids.includes(c.conversation_id))
      if (this.current && ids.includes(this.current.conversation_id)) this.current = null
      return res
    },
    select(conv) {
      this.current = conv
    }
  }
})
