<script setup>
import { ref } from 'vue'
import LoginView from './views/LoginView.vue'
import InventoryView from './views/InventoryView.vue'
import HistoryView from './views/HistoryView.vue'
import ManagementView from './views/ManagementView.vue'
import FinanceView from './views/FinanceView.vue'

// Session & Navigation State
const isLoggedIn = ref(false)
const currentView = ref('inventory') // 'inventory', 'history', 'management', 'finance'

// For development, we can auto-login
// isLoggedIn.value = true

const handleLogin = () => {
  isLoggedIn.value = true
}
</script>

<template>
  <div class="h-screen bg-slate-50 overflow-hidden flex flex-col">
    <!-- Main Content -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="!isLoggedIn">
        <LoginView @login-success="handleLogin" />
      </template>

      <template v-else>
        <InventoryView v-if="currentView === 'inventory'" />
        <HistoryView v-if="currentView === 'history'" />
        <ManagementView v-if="currentView === 'management'" />
        <FinanceView v-if="currentView === 'finance'" />
      </template>
    </div>

    <!-- Navigation Bar -->
    <nav v-if="isLoggedIn" class="bg-white border-t border-slate-200 pb-safe shadow-[0_-4px_20px_rgba(0,0,0,0.05)] z-50">
      <div class="flex justify-around items-center h-16">
        <button 
          @click="currentView = 'inventory'"
          class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="currentView === 'inventory' ? 'text-orange-500' : 'text-slate-400'"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <span class="text-[10px] font-bold">叫貨作業</span>
        </button>

        <button 
          @click="currentView = 'history'"
          class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="currentView === 'history' ? 'text-orange-500' : 'text-slate-400'"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-[10px] font-bold">歷史紀錄</span>
        </button>

        <button 
          @click="currentView = 'finance'"
          class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="currentView === 'finance' ? 'text-orange-500' : 'text-slate-400'"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span class="text-[10px] font-bold">金流管理</span>
        </button>

        <button 
          @click="currentView = 'management'"
          class="flex-1 flex flex-col items-center justify-center space-y-1 transition-all"
          :class="currentView === 'management' ? 'text-orange-500' : 'text-slate-400'"
        >
          <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          <span class="text-[10px] font-bold">系統管理</span>
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

/* Safe area for mobile */
.pb-safe {
  padding-bottom: env(safe-area-inset-bottom);
}
</style>
