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
      <div class="login-logo" aria-hidden="true">
        <span class="ll-main">📊</span>
        <span class="ll-spark s1">✨</span>
        <span class="ll-spark s2">🍃</span>
      </div>
      <h1>经营归因分析系统</h1>
      <p class="login-sub muted">对话式 BI · Agent 自动归因 · 六段式结论</p>
      <label>用户名
        <input class="textinput" v-model="username" autocomplete="username" />
      </label>
      <label>密码
        <input class="textinput" type="password" v-model="password" autocomplete="current-password" />
      </label>
      <p class="err" style="color: var(--red); margin: 0; font-size: 13px;" v-if="error">{{ error }}</p>
      <button class="btn primary block" :disabled="busy">{{ busy ? '登录中…' : '授权登录 →' }}</button>
      <p class="login-hint muted">通过统一身份认证登录 · 初始账号 admin / admin123</p>
    </form>
  </div>
</template>
