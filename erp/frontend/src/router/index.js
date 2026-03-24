import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// O7: 角色層級（數字越大權限越高）
const ROLE_LEVELS = { admin: 4, manager: 3, staff: 2, cashier: 1 }

function hasRole(userRole, required) {
  return (ROLE_LEVELS[userRole] ?? 0) >= (ROLE_LEVELS[required] ?? 0)
}

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue')
  },
  {
    path: '/order',
    name: 'order',
    component: () => import('@/views/InventoryView.vue'),
    meta: { requiredRole: 'staff' }
  },
  {
    path: '/finance',
    name: 'finance',
    component: () => import('@/views/FinanceView.vue'),
    meta: { requiredRole: 'cashier' }
  },
  {
    path: '/more',
    name: 'more',
    component: () => import('@/views/MoreView.vue')
  },
  {
    path: '/waste',
    name: 'waste',
    component: () => import('@/views/WasteView.vue'),
    meta: { requiredRole: 'staff' }
  },
  {
    path: '/stocktake',
    name: 'stocktake',
    component: () => import('@/views/StocktakeView.vue'),
    meta: { requiredRole: 'staff' }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { requiredRole: 'staff' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  // 未登入 → 跳登入頁
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login' }
  }

  // 已登入不需要登入頁
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'home' }
  }

  // O7: 角色權限守衛
  if (to.meta.requiredRole && auth.user) {
    if (!hasRole(auth.user.role, to.meta.requiredRole)) {
      return { name: 'home' }
    }
  }
})

export default router
