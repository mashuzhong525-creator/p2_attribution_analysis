<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const toasts = ref([])
let toastId = 0

function onToast(e) {
  const { msg, type } = e.detail || {}
  const id = ++toastId
  toasts.value.push({ id, msg, type: type || 'info' })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, 3200)
}

async function logout() {
  await auth.logout()
  router.push('/login')
}

onMounted(() => window.addEventListener('toast', onToast))
onUnmounted(() => window.removeEventListener('toast', onToast))
</script>

<template>
  <div class="app-shell">
    <header class="topbar" v-if="auth.user && !route.meta.public">
      <div class="brand">经营归因分析系统</div>
      <nav class="topnav">
        <router-link to="/">工作台</router-link>
        <router-link v-if="auth.isAdmin" to="/admin">管理后台</router-link>
      </nav>
      <div class="userbox">
        <span class="uname">{{ auth.user?.display_name || auth.user?.username }}</span>
        <span class="urole" :class="auth.user?.role">{{ auth.user?.role }}</span>
        <button class="btn sm ghost" @click="logout">退出</button>
      </div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
    <div class="toasts">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.msg }}</div>
    </div>
  </div>
</template>
