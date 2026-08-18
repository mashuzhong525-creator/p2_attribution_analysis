import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useConfigStore = defineStore('config', {
  state: () => ({ groups: [], loading: false }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        this.groups = await api.get('/api/admin/config')
      } finally {
        this.loading = false
      }
      return this.groups
    },
    async update(items) {
      const res = await api.post('/api/admin/config', { items })
      await this.fetch()
      return res
    },
    async reload() {
      const res = await api.post('/api/admin/reload', {})
      await this.fetch()
      return res
    }
  }
})
