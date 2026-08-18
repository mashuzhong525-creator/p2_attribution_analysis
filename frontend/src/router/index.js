import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/change-password', component: () => import('../views/ChangePasswordView.vue'), meta: { standalone: true } },
  { path: '/', component: () => import('../views/ChatView.vue') },
  { path: '/admin', component: () => import('../views/AdminView.vue'), meta: { admin: true } },
  { path: '/403', component: () => import('../views/ForbiddenView.vue'), meta: { public: true } },
  { path: '/404', component: () => import('../views/NotFoundView.vue'), meta: { public: true } },
  { path: '/:pathMatch(.*)*', redirect: '/404' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.user) {
    const u = await auth.fetchMe()
    if (!u) return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.admin && !auth.isAdmin) return { path: '/403' }
  // 首次登录：未改密前只能访问改密页；改密后不允许再停留在改密页
  if (auth.mustChangePassword && to.path !== '/change-password') return { path: '/change-password' }
  if (!auth.mustChangePassword && to.path === '/change-password') return { path: '/' }
  return true
})

export default router
