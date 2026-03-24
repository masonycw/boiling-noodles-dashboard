import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true }
  },

  // ── 總覽 ──
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue')
  },

  // ── 庫存管理 ──
  {
    path: '/inventory/orders',
    name: 'inventory-orders',
    component: () => import('@/views/OrdersView.vue')
  },
  {
    path: '/inventory/stocktakes',
    name: 'inventory-stocktakes',
    component: () => import('@/views/StocktakeView.vue')
  },
  {
    path: '/inventory/groups',
    name: 'inventory-groups',
    component: () => import('@/views/StocktakeGroupsView.vue')
  },
  {
    path: '/inventory/waste',
    name: 'inventory-waste',
    component: () => import('@/views/WasteView.vue')
  },
  {
    path: '/inventory/vendors',
    name: 'inventory-vendors',
    component: () => import('@/views/VendorsView.vue')
  },
  {
    path: '/inventory/items',
    name: 'inventory-items',
    component: () => import('@/views/ItemsView.vue')
  },

  // ── 金流管理 ──
  {
    path: '/cashflow/overview',
    name: 'cashflow-overview',
    component: () => import('@/views/CashFlowOverviewView.vue')
  },
  {
    path: '/cashflow/transactions',
    name: 'cashflow-transactions',
    component: () => import('@/views/CashFlowTransactionsView.vue')
  },
  {
    path: '/cashflow/petty-cash',
    name: 'cashflow-petty-cash',
    component: () => import('@/views/PettyCashView.vue')
  },
  {
    path: '/cashflow/payables',
    name: 'cashflow-payables',
    component: () => import('@/views/PayablesView.vue')
  },
  {
    path: '/cashflow/recurring',
    name: 'cashflow-recurring',
    component: () => import('@/views/RecurringChargesView.vue')
  },
  {
    path: '/cashflow/ratio-costs',
    name: 'cashflow-ratio-costs',
    component: () => import('@/views/ProportionalFeesView.vue')
  },

  // ── 財務管理 ──
  {
    path: '/financial/pl',
    name: 'financial-pl',
    component: () => import('@/views/ReportsView.vue')
  },

  // ── 系統管理 ──
  {
    path: '/settings/accounts',
    name: 'settings-accounts',
    component: () => import('@/views/AccountsView.vue')
  },
  {
    path: '/settings/finance',
    name: 'settings-finance',
    component: () => import('@/views/FinanceParamsView.vue')
  },
  {
    path: '/settings/display',
    name: 'settings-display',
    component: () => import('@/views/DisplaySettingsView.vue')
  },
  {
    path: '/settings/api',
    name: 'settings-api',
    component: () => import('@/views/ApiIntegrationsView.vue')
  },

  // ── 舊路由重定向 ──
  { path: '/vendors',            redirect: '/inventory/vendors' },
  { path: '/items',              redirect: '/inventory/items' },
  { path: '/orders',             redirect: '/inventory/orders' },
  { path: '/stocktake',          redirect: '/inventory/stocktakes' },
  { path: '/stocktake-groups',   redirect: '/inventory/groups' },
  { path: '/categories',         redirect: '/inventory/groups' },
  { path: '/waste',              redirect: '/inventory/waste' },
  { path: '/finance',            redirect: '/cashflow/overview' },
  { path: '/cash-flow-overview', redirect: '/cashflow/overview' },
  { path: '/recurring-charges',  redirect: '/cashflow/recurring' },
  { path: '/proportional-fees',  redirect: '/cashflow/ratio-costs' },
  { path: '/reports',            redirect: '/financial/pl' },
  { path: '/users',              redirect: '/settings/accounts' },
  { path: '/notifications',      redirect: '/settings/api' },
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
