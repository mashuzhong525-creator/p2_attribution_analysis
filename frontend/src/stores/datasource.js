import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useDatasourceStore = defineStore('datasource', {
  state: () => ({ list: [], loading: false }),
  actions: {
    async fetch() {
      this.loading = true
      try {
        this.list = await api.get('/api/admin/datasources')
      } finally {
        this.loading = false
      }
      return this.list
    },
    async create(body) {
      const ds = await api.post('/api/admin/datasources', body)
      this.list.push(ds)
      return ds
    },
    async update(id, body) {
      const ds = await api.put(`/api/admin/datasources/${id}`, body)
      const i = this.list.findIndex((d) => d.id === id)
      if (i >= 0) this.list[i] = ds
      return ds
    },
    async remove(id) {
      await api.del(`/api/admin/datasources/${id}`)
      this.list = this.list.filter((d) => d.id !== id)
    },
    async test(body) {
      return api.post('/api/admin/datasources/test', body)
    }
  }
})
