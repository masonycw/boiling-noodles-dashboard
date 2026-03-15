<script setup>
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

onMounted(async () => {
  if (auth.isLoggedIn && !auth.user) {
    await auth.fetchMe()
  }
})

const navItems = [
  { name: 'home',      label: '首頁',   icon: 'home' },
  { name: 'order',     label: '訂單',   icon: 'clipboard' },
  { name: 'stocktake', label: '盤點',   icon: 'chart' },
  { name: 'finance',   label: '金流',   icon: 'cash' },
  { name: 'more',      label: '更多',   icon: 'dots' },
]

const isActive = (name) => route.name === name

function goTo(name) {
  router.push({ name })
}
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

        <!-- 首頁 -->
        <button @click="goTo('home')" class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="isActive('home') ? 'text-orange-500' : 'text-slate-400'">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span class="text-[10px] font-bold">首頁</span>
        </button>

        <!-- 訂單 -->
        <button @click="goTo('order')" class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="isActive('order') ? 'text-orange-500' : 'text-slate-400'">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span class="text-[10px] font-bold">叫貨</span>
        </button>

        <!-- 盤點 -->
        <button @click="goTo('stocktake')" class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="isActive('stocktake') ? 'text-orange-500' : 'text-slate-400'">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <span class="text-[10px] font-bold">盤點</span>
        </button>

        <!-- 金流 -->
        <button @click="goTo('finance')" class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="isActive('finance') ? 'text-orange-500' : 'text-slate-400'">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-[10px] font-bold">金流</span>
        </button>

        <!-- 更多 -->
        <button @click="goTo('more')" class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="isActive('more') ? 'text-orange-500' : 'text-slate-400'">
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
          </svg>
          <span class="text-[10px] font-bold">更多</span>
        </button>

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
  padding-bottom: env(safe-area-inset-bottom);
}
</style>
