<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const kpi = ref({ balance: 0, petty_cash: 0, waste_count: 0, pending_payables: 0 })
const loading = ref(true)
const lowStockItems = ref([])
const pendingOrders = ref([])

const today = new Date()
const dateStr = today.toLocaleDateString('zh-TW', { month: 'long', day: 'numeric', weekday: 'short' })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function loadKpi() {
  try {
    const [balRes, pettyCashRes, wasteRes, payRes, itemsRes, ordersRes] = await Promise.all([
      fetch(`${API_BASE}/finance/balance`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
      fetch(`${API_BASE}/waste/summary?days_limit=1`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/accounts-payable?is_paid=false&limit=200`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/orders?status=confirmed&limit=20`, { headers: authHeaders() }),
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
    if (itemsRes.ok) {
      const allItems = await itemsRes.json()
      lowStockItems.value = allItems.filter(i =>
        parseFloat(i.min_stock) > 0 && parseFloat(i.current_stock) <= parseFloat(i.min_stock)
      )
    }
    if (ordersRes.ok) {
      pendingOrders.value = await ordersRes.json()
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadKpi)

const quickActions = [
  { label: '開始叫貨', icon: '📋', route: 'order',     color: 'bg-orange-50 text-orange-600 border border-orange-100' },
  { label: '盤點庫存', icon: '📊', route: 'stocktake', color: 'bg-blue-50 text-blue-600 border border-blue-100' },
  { label: '記錄損耗', icon: '🗑️',  route: 'waste',     color: 'bg-red-50 text-red-600 border border-red-100' },
  { label: '零用金',   icon: '💰', route: 'finance',   color: 'bg-green-50 text-green-600 border border-green-100' },
]

function fmt(n) {
  return Number(n).toLocaleString('zh-TW', { minimumFractionDigits: 0 })
}

function fmtTime(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const greetingEmoji = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '☀️'
  if (h < 18) return '🌤️'
  return '🌙'
})
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-4">
    <!-- Orange brand header -->
    <div class="bg-gradient-to-br from-orange-500 to-orange-600 text-white px-5 pt-12 pb-8">
      <div class="flex items-start justify-between">
        <div>
          <p class="text-orange-200 text-sm">{{ dateStr }}</p>
          <h1 class="text-2xl font-extrabold mt-1">
            {{ greetingEmoji }} 嗨，{{ auth.user?.full_name || auth.user?.username || '使用者' }}
          </h1>
          <p class="text-orange-200 text-sm mt-1">滾麵 ERP · 智慧管理</p>
        </div>
        <button class="mt-1 relative">
          <svg class="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span v-if="pendingOrders.length > 0"
            class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
            {{ pendingOrders.length }}
          </span>
        </button>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="px-4 -mt-5">
      <div class="grid grid-cols-2 gap-3">
        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">零用金餘額</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold text-slate-800 mt-1">${{ fmt(kpi.petty_cash) }}</p>
          <p class="text-[10px] text-slate-400 mt-1">目前現金</p>
        </div>

        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">現金流餘額</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold mt-1"
            :class="kpi.balance >= 0 ? 'text-emerald-600' : 'text-rose-500'">
            ${{ fmt(kpi.balance) }}
          </p>
          <p class="text-[10px] text-slate-400 mt-1">收入 - 支出</p>
        </div>

        <div class="bg-white rounded-2xl p-4 shadow-sm">
          <p class="text-xs text-slate-400 font-medium">今日損耗</p>
          <p v-if="loading" class="text-xl font-bold text-slate-300 mt-1 animate-pulse">---</p>
          <p v-else class="text-xl font-bold text-slate-800 mt-1">
            {{ kpi.waste_count }} <span class="text-sm font-normal text-slate-400">筆</span>
          </p>
          <p class="text-[10px] text-slate-400 mt-1">今日記錄</p>
        </div>

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

    <!-- Low Stock Alert -->
    <div v-if="!loading && lowStockItems.length > 0" class="px-4 mt-5">
      <div class="bg-red-50 border border-red-200 rounded-2xl p-4">
        <p class="text-xs font-extrabold text-red-600 mb-3">🚨 低庫存警示 — 需補貨</p>
        <div class="space-y-2">
          <div v-for="item in lowStockItems.slice(0, 4)" :key="item.id"
            class="flex items-center justify-between">
            <span class="text-sm font-semibold text-red-800">{{ item.name }}</span>
            <span class="text-xs font-bold text-red-500">
              庫存 {{ item.current_stock }} ／安全 {{ item.min_stock }} {{ item.unit }}
            </span>
          </div>
          <div v-if="lowStockItems.length > 4" class="text-xs text-red-400 text-center">
            還有 {{ lowStockItems.length - 4 }} 項低庫存品項…
          </div>
        </div>
        <button
          @click="router.push({ name: 'order' })"
          class="mt-3 w-full bg-red-500 text-white text-sm font-bold py-2.5 rounded-xl active:scale-95 transition-transform">
          一鍵前往叫貨 →
        </button>
      </div>
    </div>

    <!-- Pending Deliveries -->
    <div v-if="!loading && pendingOrders.length > 0" class="px-4 mt-4">
      <h2 class="text-sm font-bold text-slate-500 uppercase tracking-wider mb-2">今日待辦</h2>
      <div class="bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 mb-2">
        <p class="text-xs font-bold text-amber-700">⚠️ 有 {{ pendingOrders.length }} 筆訂貨尚未簽收</p>
      </div>
      <div class="space-y-2">
        <button
          v-for="order in pendingOrders.slice(0, 3)" :key="order.id"
          @click="router.push({ name: 'order' })"
          class="w-full bg-white border border-slate-200 rounded-2xl p-4 flex items-center gap-3 shadow-sm active:bg-slate-50 transition-colors text-left">
          <span class="text-xl">🚚</span>
          <div class="flex-1 min-w-0">
            <p class="font-bold text-slate-800 text-sm">{{ order.vendor_name }} — 待簽收</p>
            <p class="text-xs text-slate-400 mt-0.5">
              {{ order.expected_delivery_date ? fmtTime(order.expected_delivery_date) : '時間未定' }}
              · {{ order.total_items }} 項品項
            </p>
          </div>
          <span class="shrink-0 bg-amber-100 text-amber-600 text-xs font-bold px-2 py-1 rounded-full">待收</span>
        </button>
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
