<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('admin')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    router.push(String(route.query.redirect || '/'))
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>经营归因分析系统</h1>
      <p class="muted">对话式 BI · Agent 归因 · 六段式结论</p>
      <label>用户名<input v-model="username" autocomplete="username" /></label>
      <label>密码<input type="password" v-model="password" autocomplete="current-password" /></label>
      <p class="err" v-if="error">{{ error }}</p>
      <button class="btn primary block" :disabled="busy">{{ busy ? '登录中…' : '登 录' }}</button>
      <p class="hint muted">初始账号 admin / admin123（认证库种子）</p>
    </form>
  </div>
</template>
