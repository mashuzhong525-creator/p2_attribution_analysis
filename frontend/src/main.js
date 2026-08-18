import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 全局登录态失效处理
window.addEventListener('auth:expired', () => {
  router.push('/login')
})
// 全局 toast
window.$toast = (msg, type = 'info') => {
  window.dispatchEvent(new CustomEvent('toast', { detail: { msg, type } }))
}

app.mount('#app')
