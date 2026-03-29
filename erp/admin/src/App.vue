<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const sidebarOpen = ref(false)

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) {
    await auth.fetchMe()
  }
})

router.afterEach(() => {
  sidebarOpen.value = false
})

const navGroups = [
  {
    label: '總覽',
    items: [
      { name: 'dashboard',     label: '儀表板', icon: '📊' },
      { name: 'announcements', label: '公告管理', icon: '📢' },
    ]
  },
  {
    label: '庫存管理',
    items: [
      { name: 'inventory-orders',    label: '叫貨／收貨',  icon: '🚚' },
      { name: 'inventory-stocktakes',label: '盤點紀錄',    icon: '🗂️' },
      { name: 'inventory-groups',    label: '盤點群組',    icon: '🏷️' },
      { name: 'inventory-waste',     label: '耗損紀錄',    icon: '🗑️' },
      { name: 'inventory-vendors',   label: '供應商管理',  icon: '🏪' },
      { name: 'inventory-items',     label: '品項管理',    icon: '📦' },
    ]
  },
  {
    label: '金流管理',
    items: [
      { name: 'cashflow-overview',    label: '金流總覽',    icon: '💳' },
      { name: 'cashflow-transactions',label: '金流紀錄',    icon: '📋' },
      { name: 'cashflow-petty-cash',  label: '零用金管理',  icon: '💰' },
      { name: 'cashflow-payables',    label: '應付帳款',    icon: '🧾' },
      { name: 'cashflow-payees',      label: '費用對象',    icon: '🏷️' },
      { name: 'cashflow-recurring',   label: '重複預約設定', icon: '🔁' },
      { name: 'cashflow-ratio-costs', label: '比例費用設定', icon: '📐' },
    ]
  },
  {
    label: '財務管理',
    items: [
      { name: 'financial-pl', label: '損益報表', icon: '📈' },
    ]
  },
  {
    label: '系統管理',
    items: [
      { name: 'settings-accounts', label: '帳號管理',  icon: '👥' },
      { name: 'settings-finance',  label: '財務參數',  icon: '⚙️' },
      { name: 'settings-display',  label: '顯示設置',  icon: '🖥️' },
      { name: 'settings-api',      label: '串接管理',  icon: '🔌' },
    ]
  },
]

const allItems = navGroups.flatMap(g => g.items)
const isActive = (name) => route.name === name

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <!-- Login page: full screen, no sidebar -->
  <router-view v-if="!auth.isLoggedIn" />

  <!-- Admin layout -->
  <div v-else class="flex h-screen overflow-hidden bg-[#0f1117]">

    <!-- Mobile Sidebar Overlay -->
    <div v-show="sidebarOpen" class="fixed inset-0 bg-black/70 z-40 md:hidden" @click="sidebarOpen = false"></div>

    <!-- Sidebar -->
    <aside 
      class="fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 w-60 bg-[#111827] border-r border-[#2d3748] flex flex-col overflow-y-auto md:relative md:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- Logo -->
      <div class="px-5 py-5 border-b border-[#2d3748]">
        <h1 class="text-lg font-extrabold text-white">🍜 滾麵 ERP</h1>
        <p class="text-xs text-gray-500 mt-0.5">管理後台 v4.0</p>
      </div>

      <!-- Nav -->
      <nav class="flex-1 py-4 px-2 space-y-4">
        <div v-for="group in navGroups" :key="group.label">
          <p class="text-[11px] font-bold text-gray-500 uppercase tracking-widest px-3 mb-1.5">
            {{ group.label }}
          </p>
          <router-link
            v-for="item in group.items" :key="item.name"
            :to="{ name: item.name }"
            class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all mb-0.5"
            :class="isActive(item.name)
              ? 'bg-blue-500/10 text-blue-400 border-l-2 border-blue-400 pl-[10px]'
              : 'text-gray-400 hover:bg-[#1f2937] hover:text-gray-200'"
          >
            <span class="text-base leading-none">{{ item.icon }}</span>
            <span class="font-medium">{{ item.label }}</span>
          </router-link>
        </div>
      </nav>

      <!-- User card -->
      <div class="border-t border-[#2d3748] px-4 py-3 flex items-center gap-3">
        <div class="w-8 h-8 rounded-full bg-blue-400 text-[#0f1117] font-extrabold flex items-center justify-center text-sm shrink-0">
          {{ (auth.user?.full_name || auth.user?.username || '?')[0] }}
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-bold text-gray-200 truncate">{{ auth.user?.full_name || auth.user?.username }}</p>
          <p class="text-xs text-gray-500">{{ auth.user?.role === 'admin' ? '管理員' : auth.user?.role === 'manager' ? '店長' : '員工' }}</p>
        </div>
        <button @click="logout" title="登出" class="text-gray-500 hover:text-red-400 transition-colors text-lg">⏻</button>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Topbar -->
      <header class="h-14 bg-[#0f1117] border-b border-[#2d3748] flex items-center justify-between px-4 md:px-6 shrink-0">
        <div class="flex items-center gap-3">
          <button @click="sidebarOpen = true" class="md:hidden text-gray-400 hover:text-gray-200">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
            </svg>
          </button>
          <h2 class="text-base font-semibold text-gray-200">
            {{ allItems.find(i => i.name === route.name)?.label || '滾麵後台' }}
          </h2>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-sm text-gray-500">{{ new Date().toLocaleDateString('zh-TW') }}</span>
        </div>
      </header>

      <!-- Page -->
      <main class="flex-1 overflow-x-hidden overflow-y-auto p-4 md:p-6">
        <router-view />
      </main>
    </div>

  </div>
</template>
