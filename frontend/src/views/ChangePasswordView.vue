<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'

const auth = useAuthStore()
const router = useRouter()
const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const busy = ref(false)

function validate() {
  if (!oldPassword.value) return '请输入当前密码'
  if (newPassword.value.length < 8) return '新密码长度至少 8 位'
  if (newPassword.value === oldPassword.value) return '新密码不能与原密码相同'
  if (newPassword.value !== confirmPassword.value) return '两次输入的新密码不一致'
  return ''
}

async function submit() {
  error.value = ''
  const msg = validate()
  if (msg) {
    error.value = msg
    return
  }
  busy.value = true
  try {
    await api.post('/api/auth/change-password', {
      old_password: oldPassword.value,
      new_password: newPassword.value
    })
    auth.mustChangePassword = false
    window.$toast('密码修改成功', 'success')
    router.push('/')
  } catch (e) {
    error.value = e.message || '修改失败'
  } finally {
    busy.value = false
  }
}

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <h1>修改初始密码</h1>
      <p class="muted">首次登录需修改密码后才能继续使用系统</p>
      <label>当前密码
        <input type="password" v-model="oldPassword" autocomplete="current-password" />
      </label>
      <label>新密码（至少 8 位）
        <input type="password" v-model="newPassword" autocomplete="new-password" />
      </label>
      <label>确认新密码
        <input type="password" v-model="confirmPassword" autocomplete="new-password" />
      </label>
      <p class="err" v-if="error">{{ error }}</p>
      <button class="btn primary block" :disabled="busy">{{ busy ? '提交中…' : '确认修改' }}</button>
      <button type="button" class="btn ghost block" @click="logout">退出登录</button>
    </form>
  </div>
</template>
