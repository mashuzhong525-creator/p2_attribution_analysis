import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    loading: false,
    mustChangePassword: false
  }),
  getters: {
    isAdmin: (s) => s.user?.role === 'admin'
  },
  actions: {
    async login(username, password) {
      const { code } = await api.post('/api/auth/login', { username, password })
      await api.post('/api/auth/token', { grant_type: 'authorization_code', code })
      await this.fetchMe()
    },
    async fetchMe() {
      try {
        this.user = await api.get('/api/auth/me')
        this.mustChangePassword = !!this.user?.must_change_password
      } catch {
        this.user = null
        this.mustChangePassword = false
      }
      return this.user
    },
    async logout() {
      try { await api.post('/api/auth/logout', {}) } catch {}
      this.user = null
      this.mustChangePassword = false
    }
  }
})
