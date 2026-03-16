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
    name: 'home',
    component: () => import('@/views/HomeView.vue')
  },
  {
    path: '/order',
    name: 'order',
    component: () => import('@/views/InventoryView.vue')
  },
  {
    path: '/finance',
    name: 'finance',
    component: () => import('@/views/FinanceView.vue')
  },
  {
    path: '/more',
    name: 'more',
    component: () => import('@/views/MoreView.vue')
  },
  {
    path: '/waste',
    name: 'waste',
    component: () => import('@/views/WasteView.vue')
  },
  {
    path: '/stocktake',
    name: 'stocktake',
    component: () => import('@/views/StocktakeView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'home' }
  }
})

export default router
