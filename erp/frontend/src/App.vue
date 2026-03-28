<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const pendingCount = ref(0)

// O7: 角色白名單（與 router/index.js 保持一致）
const OPERATIONAL_ROLES = ['admin', 'manager', 'staff']
const FINANCE_ROLES = ['admin', 'manager', 'cashier']

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) {
    await auth.fetchMe()
  }
  if (auth.isLoggedIn) loadPendingCount()
})

async function loadPendingCount() {
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?status=confirmed&limit=50`, {
      headers: { Authorization: `Bearer ${auth.token}` }
    })
    if (res.ok) {
      const data = await res.json()
      pendingCount.value = Array.isArray(data) ? data.length : 0
    }
  } catch {}
}

const isActive = (name) => route.name === name

function goTo(name) {
  router.push({ name })
}

// O7: 依角色過濾底部導覽項目（與 router allowedRoles 保持一致）
const navItems = computed(() => {
  const role = auth.user?.role
  const all = [
    { name: 'home',    label: '首頁', allowedRoles: null },
    { name: 'order',   label: '訂單', allowedRoles: OPERATIONAL_ROLES, showBadge: true },
    { name: 'finance', label: '金流', allowedRoles: FINANCE_ROLES, accessKey: 'petty_cash_access' },
    { name: 'more',    label: '更多', allowedRoles: null },
  ]
  return all.filter(item => {
    if (!item.allowedRoles && !item.accessKey) return true
    const roleOk = item.allowedRoles?.includes(role)
    const accessOk = item.accessKey && !!auth.user?.[item.accessKey]
    return roleOk || accessOk
  })
})
</script>

<template>
  <div class="h-screen bg-slate-50 overflow-hidden flex flex-col">
    <div class="flex-1 overflow-y-auto">
      <router-view />
    </div>

    <nav
      v-if="auth.isLoggedIn"
      class="bg-white border-t border-slate-200 pb-safe shadow-[0_-4px_20px_rgba(0,0,0,0.05)] z-50"
    >
      <div class="flex justify-around items-center h-16">

        <!-- 動態導覽項目（O7 依角色過濾） -->
        <template v-for="item in navItems" :key="item.name">

          <!-- 首頁 -->
          <button v-if="item.name === 'home'" @click="goTo('home')"
            class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
            :class="isActive('home') ? 'text-orange-500' : 'text-slate-400'">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span class="text-[10px] font-bold">首頁</span>
          </button>

          <!-- 訂單（含待收貨紅點） -->
          <button v-else-if="item.name === 'order'" @click="goTo('order')"
            class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
            :class="isActive('order') ? 'text-orange-500' : 'text-slate-400'">
            <div class="relative">
              <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 10V7" />
              </svg>
              <span v-if="pendingCount > 0"
                class="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[8px] font-bold rounded-full flex items-center justify-center leading-none">
                {{ pendingCount > 9 ? '9+' : pendingCount }}
              </span>
            </div>
            <span class="text-[10px] font-bold">訂單</span>
          </button>

          <!-- 金流 -->
          <button v-else-if="item.name === 'finance'" @click="goTo('finance')"
            class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
            :class="isActive('finance') ? 'text-orange-500' : 'text-slate-400'">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-[10px] font-bold">金流</span>
          </button>

          <!-- 更多 -->
          <button v-else-if="item.name === 'more'" @click="goTo('more')"
            class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
            :class="isActive('more') ? 'text-orange-500' : 'text-slate-400'">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
            </svg>
            <span class="text-[10px] font-bold">更多</span>
          </button>

        </template>

      </div>
    </nav>
  </div>
</template>

<style>
body {
  margin: 0;
  padding: 0;
  -webkit-tap-highlight-color: transparent;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  user-select: none;
}

#app {
  height: 100vh;
}

.pb-safe {
  padding-bottom: max(16px, env(safe-area-inset-bottom));
}
</style>
