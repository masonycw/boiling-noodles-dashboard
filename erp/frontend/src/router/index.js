import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// O7: 角色權限設計（精確 allowedRoles 陣列，不用線性層級）
// admin / manager → 全部功能
// staff → 庫存/盤點/耗損，無金流
// cashier → 金流，無庫存/盤點/耗損
const ALL_OPERATIONAL = ['admin', 'manager', 'staff']
const ALL_FINANCE = ['admin', 'manager', 'cashier']

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
    meta: { allowedRoles: ALL_OPERATIONAL }
  },
  {
    path: '/finance',
    name: 'finance',
    component: () => import('@/views/FinanceView.vue'),
    meta: { allowedRoles: ALL_FINANCE }
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
    meta: { allowedRoles: ALL_OPERATIONAL }
  },
  {
    path: '/stocktake',
    name: 'stocktake',
    component: () => import('@/views/StocktakeView.vue'),
    meta: { allowedRoles: ALL_OPERATIONAL }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { allowedRoles: ALL_OPERATIONAL }
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

  // O7: 角色守衛（精確 allowedRoles 陣列）
  if (to.meta.allowedRoles && auth.user) {
    const roleOk = to.meta.allowedRoles.includes(auth.user.role)
    // petty_cash_access 開啟時允許進入金流頁面
    const accessOk = to.name === 'finance' && !!auth.user.petty_cash_access
    if (!roleOk && !accessOk) {
      return { name: 'home' }
    }
  }
})

export default router
