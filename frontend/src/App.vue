<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

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

onMounted(() => window.addEventListener('toast', onToast))
onUnmounted(() => window.removeEventListener('toast', onToast))
</script>

<template>
  <div class="app-shell">
    <main class="app-main">
      <router-view />
    </main>
    <div class="toasts">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.msg }}</div>
    </div>
  </div>
</template>
