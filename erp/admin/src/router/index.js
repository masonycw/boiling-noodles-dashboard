import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue')
  },
  {
    path: '/vendors',
    name: 'vendors',
    component: () => import('@/views/VendorsView.vue')
  },
  {
    path: '/items',
    name: 'items',
    component: () => import('@/views/ItemsView.vue')
  },
  {
    path: '/orders',
    name: 'orders',
    component: () => import('@/views/OrdersView.vue')
  },
  {
    path: '/stocktake',
    name: 'stocktake',
    component: () => import('@/views/StocktakeView.vue')
  },
  {
    path: '/waste',
    name: 'waste',
    component: () => import('@/views/WasteView.vue')
  },
  {
    path: '/finance',
    name: 'finance',
    component: () => import('@/views/FinanceView.vue')
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UsersView.vue')
  },
  {
    path: '/stocktake-groups',
    name: 'stocktake-groups',
    component: () => import('@/views/StocktakeGroupsView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
})

export default router
