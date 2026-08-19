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
// 全局 toast（支持 duration 毫秒，默认 3200）
window.$toast = (msg, type = 'info', duration = 3200) => {
  window.dispatchEvent(new CustomEvent('toast', { detail: { msg, type, duration } }))
}

app.mount('#app')
