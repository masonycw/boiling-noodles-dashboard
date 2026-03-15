<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const kpi = ref({ balance: 0, petty_cash: 0, waste_count: 0, pending_payables: 0 })
const loading = ref(true)
const today = new Date()
const dateStr = today.toLocaleDateString('zh-TW', { month: 'long', day: 'numeric', weekday: 'short' })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function loadKpi() {
  try {
    const [balRes, pettyCashRes, wasteRes, payRes] = await Promise.all([
      fetch(`${API_BASE}/finance/balance`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
      fetch(`${API_BASE}/waste/summary?days_limit=1`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/accounts-payable?is_paid=false&limit=200`, { headers: authHeaders() }),
    ])

    if (balRes.ok) kpi.value.balance = (await balRes.json()).balance
    if (pettyCashRes.ok) kpi.value.petty_cash = (await pettyCashRes.json()).balance
    if (wasteRes.ok) {
      const w = await wasteRes.json()
      kpi.value.waste_count = w.total_records ?? 0
    }
    if (payRes.ok) {
      const arr = await payRes.json()
      kpi.value.pending_payables = arr.length
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadKpi)

const quickActions = [
  { label: '開始叫貨', icon: '📋', route: 'order',     color: 'bg-orange-50 text-orange-600' },
  { label: '盤點庫存', icon: '📊', route: 'stocktake', color: 'bg-blue-50 text-blue-600' },
  { label: '記錄損耗', icon: '🗑️',  route: 'waste',     color: 'bg-red-50 text-red-600' },
  { label: '零用金',   icon: '💰', route: 'finance',   color: 'bg-green-50 text-green-600' },
]

function fmt(n) {
  return Number(n).toLocaleString('zh-TW', { minimumFractionDigits: 0 })
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-4">
    <!-- Header -->
    <div class="bg-gradient-to-br from-slate-800 to-slate-900 text-white px-5 pt-12 pb-8">
      <p class="text-slate-400 text-sm">{{ dateStr }}</p>
      <h1 class="text-2xl font-extrabold mt-1">
        嗨，{{ auth.user?.full_name || auth.user?.username || '使用者' }} 👋
      </h1>
      <p class="text-slate-400 text-sm mt-1">滾麵 ERP · 智慧管理</p>
    </div>

    <!-- KPI Cards -->
    <div class="px-4 -mt-5">
      <div class="grid grid-cols-2 gap-3">
        <!-- 零用金餘額 -->
        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">零用金餘額</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold text-slate-800 mt-1">
            ${{ fmt(kpi.petty_cash) }}
          </p>
          <p class="text-[10px] text-slate-400 mt-1">目前現金</p>
        </div>

        <!-- 現金流餘額 -->
        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">現金流餘額</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold mt-1"
            :class="kpi.balance >= 0 ? 'text-emerald-600' : 'text-rose-500'">
            ${{ fmt(kpi.balance) }}
          </p>
          <p class="text-[10px] text-slate-400 mt-1">收入 - 支出</p>
        </div>

        <!-- 今日損耗筆數 -->
        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">今日損耗</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold text-slate-800 mt-1">
            {{ kpi.waste_count }} <span class="text-sm font-normal text-slate-400">筆</span>
          </p>
          <p class="text-[10px] text-slate-400 mt-1">今日記錄</p>
        </div>

        <!-- 待付帳款 -->
        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">待付帳款</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold mt-1"
            :class="kpi.pending_payables > 0 ? 'text-amber-500' : 'text-slate-800'">
            {{ kpi.pending_payables }} <span class="text-sm font-normal text-slate-400">筆</span>
          </p>
          <p class="text-[10px] text-slate-400 mt-1">尚未付清</p>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="px-4 mt-5">
      <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-3">快速操作</h2>
      <div class="grid grid-cols-2 gap-3">
        <button
          v-for="action in quickActions"
          :key="action.route"
          @click="router.push({ name: action.route })"
          class="flex items-center gap-3 p-4 rounded-2xl shadow-sm active:scale-95 transition-transform"
          :class="action.color"
        >
          <span class="text-2xl">{{ action.icon }}</span>
          <span class="font-bold text-sm">{{ action.label }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
