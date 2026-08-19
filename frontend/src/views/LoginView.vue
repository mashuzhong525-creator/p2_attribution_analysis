<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref('login') // 'login' | 'change'
const username = ref('admin')
const password = ref('')
const error = ref('')
const busy = ref(false)

const change = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const changeError = ref('')
const changeBusy = ref(false)
let redirectTarget = '/'

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    redirectTarget = String(route.query.redirect || '/')
    if (auth.mustChangePassword) {
      // 首次登录：原地展开改密表单，不跳独立改密页
      change.value.oldPassword = password.value
      change.value.newPassword = ''
      change.value.confirmPassword = ''
      changeError.value = ''
      mode.value = 'change'
      return
    }
    router.push(redirectTarget)
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    busy.value = false
  }
}

function validateChange() {
  if (!change.value.oldPassword) return '请输入当前密码'
  if (change.value.newPassword.length < 8) return '新密码长度至少 8 位'
  if (change.value.newPassword === change.value.oldPassword) return '新密码不能与原密码相同'
  if (change.value.newPassword !== change.value.confirmPassword) return '两次输入的新密码不一致'
  return ''
}

async function submitChange() {
  changeError.value = ''
  const msg = validateChange()
  if (msg) {
    changeError.value = msg
    return
  }
  changeBusy.value = true
  try {
    await api.post('/api/auth/change-password', {
      old_password: change.value.oldPassword,
      new_password: change.value.newPassword
    })
    auth.mustChangePassword = false
    window.$toast('密码修改成功', 'success')
    router.push(redirectTarget)
  } catch (e) {
    changeError.value = e.message || '修改失败'
    // 登录态失效（如 token 过期）→ 退回登录表单重新登录
    if (String(e.message || '').includes('过期') || String(e.message || '').includes('登录')) {
      mode.value = 'login'
    }
  } finally {
    changeBusy.value = false
  }
}

function backToLogin() {
  mode.value = 'login'
  error.value = ''
}
</script>

<template>
  <div class="login-wrap">
    <!-- 登录表单 -->
    <form v-if="mode === 'login'" class="login-card" @submit.prevent="submit">
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
      <!-- 提示：登录页不再显示默认账号信息（安全：避免外部访问者看到凭据）。
           首次部署的初始账号/密码请查阅部署文档或询问管理员 -->
    </form>

    <!-- 首次登录改密表单（内嵌在登录界面） -->
    <form v-else class="login-card" @submit.prevent="submitChange">
      <div class="login-logo" aria-hidden="true">
        <span class="ll-main">📊</span>
        <span class="ll-spark s1">✨</span>
        <span class="ll-spark s2">🍃</span>
      </div>
      <h1>修改初始密码</h1>
      <p class="login-sub muted">首次登录需修改密码后才能继续使用系统</p>
      <label>当前密码
        <input class="textinput" type="password" v-model="change.oldPassword" autocomplete="current-password" />
      </label>
      <label>新密码（至少 8 位）
        <input class="textinput" type="password" v-model="change.newPassword" autocomplete="new-password" />
      </label>
      <label>确认新密码
        <input class="textinput" type="password" v-model="change.confirmPassword" autocomplete="new-password" />
      </label>
      <p class="err" style="color: var(--red); margin: 0; font-size: 13px;" v-if="changeError">{{ changeError }}</p>
      <button class="btn primary block" :disabled="changeBusy">{{ changeBusy ? '提交中…' : '确认修改' }}</button>
      <button type="button" class="btn ghost block" @click="backToLogin">重新登录</button>
    </form>
  </div>
</template>
