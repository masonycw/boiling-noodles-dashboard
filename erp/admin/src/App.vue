<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) {
    await auth.fetchMe()
  }
})

const navGroups = [
  {
    label: '總覽',
    items: [
      { name: 'dashboard', label: '儀表板', icon: '📊' },
    ]
  },
  {
    label: '庫存管理',
    items: [
      { name: 'vendors',   label: '供應商管理', icon: '🏪' },
      { name: 'items',     label: '品項管理',   icon: '📦' },
      { name: 'orders',    label: '叫貨 / 收貨', icon: '🚚' },
      { name: 'stocktake', label: '盤點紀錄',   icon: '🗂️' },
      { name: 'waste',     label: '損耗紀錄',   icon: '🗑️' },
    ]
  },
  {
    label: '財務管理',
    items: [
      { name: 'finance', label: '金流 / 財務', icon: '💰' },
    ]
  },
  {
    label: '系統管理',
    items: [
      { name: 'users', label: '人員管理', icon: '👥' },
    ]
  }
]

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

    <!-- Sidebar -->
    <aside class="w-60 shrink-0 bg-[#111827] border-r border-[#2d3748] flex flex-col overflow-y-auto">
      <!-- Logo -->
      <div class="px-5 py-5 border-b border-[#2d3748]">
        <h1 class="text-lg font-extrabold text-white">🍜 滾麵 ERP</h1>
        <p class="text-xs text-gray-500 mt-0.5">管理後台 v3.0</p>
      </div>

      <!-- Nav -->
      <nav class="flex-1 py-4 px-2 space-y-5">
        <div v-for="group in navGroups" :key="group.label">
          <p class="text-[11px] font-bold text-gray-500 uppercase tracking-widest px-3 mb-1.5">
            {{ group.label }}
          </p>
          <router-link
            v-for="item in group.items" :key="item.name"
            :to="{ name: item.name }"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all mb-0.5"
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
          <p class="text-xs text-gray-500">{{ auth.user?.role === 'admin' ? '管理員' : '員工' }}</p>
        </div>
        <button @click="logout" title="登出" class="text-gray-500 hover:text-red-400 transition-colors text-lg">⏻</button>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Topbar -->
      <header class="h-14 bg-[#0f1117] border-b border-[#2d3748] flex items-center justify-between px-6 shrink-0">
        <h2 class="text-base font-semibold text-gray-200">
          {{ navGroups.flatMap(g => g.items).find(i => i.name === route.name)?.label || '滾麵後台' }}
        </h2>
        <div class="flex items-center gap-3">
          <span class="text-sm text-gray-500">{{ new Date().toLocaleDateString('zh-TW') }}</span>
        </div>
      </header>

      <!-- Page -->
      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>

  </div>
</template>
