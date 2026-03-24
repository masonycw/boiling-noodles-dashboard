<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const loading = ref(true)
const lowStockItems = ref([])
const pendingOrders = ref([])
const pendingStocktakeGroups = ref([])

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

const formattedDate = computed(() => {
  return new Date().toLocaleDateString('zh-TW', {
    year: 'numeric', month: 'numeric', day: 'numeric', weekday: 'short'
  })
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h >= 5 && h < 12) return '早安'
  if (h >= 12 && h < 18) return '午安'
  return '晚安'
})

const overdueReceive = computed(() => {
  if (!pendingOrders.value.length) return null
  const today = new Date().toDateString()
  return pendingOrders.value.find(o => {
    if (!o.expected_delivery_date) return false
    return new Date(o.expected_delivery_date).toDateString() === today
  }) || null
})

async function loadData() {
  try {
    const [itemsRes, ordersRes, stocktakeRes] = await Promise.all([
      fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/orders?status=confirmed&limit=20`, { headers: authHeaders() }),
      fetch(`${API_BASE}/stocktake/pending-groups`, { headers: authHeaders() }),
    ])
    if (itemsRes.ok) {
      const allItems = await itemsRes.json()
      lowStockItems.value = allItems.filter(i =>
        parseFloat(i.min_stock) > 0 && parseFloat(i.current_stock) <= parseFloat(i.min_stock)
      )
    }
    if (ordersRes.ok) {
      pendingOrders.value = await ordersRes.json()
    }
    if (stocktakeRes.ok) {
      pendingStocktakeGroups.value = await stocktakeRes.json()
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

function fmtTime(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function stocktakeDueLabel(group) {
  const od = group.overdue_days
  if (od > 0) return `逾期 ${od} 天`
  const due = group.next_stocktake_due
  const today = new Date().toISOString().split('T')[0]
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0]
  if (due === today) return '今天到期'
  if (due === tomorrow) return '明天到期'
  return '即將到期'
}

function goToStocktake(groupId) {
  router.push({ name: 'stocktake', query: { group: groupId } })
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-24">

    <!-- 橘色問候語橫幅 -->
    <div style="background:#e85d04" class="text-white px-5 pt-12 pb-6">
      <div class="flex items-start justify-between">
        <div>
          <p class="text-2xl font-extrabold leading-snug">
            {{ greeting }}，{{ auth.user?.full_name || auth.user?.username || '使用者' }} 👋
          </p>
          <p class="text-sm mt-1" style="opacity:0.85">{{ formattedDate }}</p>
        </div>
        <button class="mt-1 relative">
          <span style="font-size:22px">🔔</span>
          <span v-if="pendingOrders.length > 0"
            class="absolute -top-1 -right-1 w-4 h-4 bg-red-600 text-white text-[8px] font-bold rounded-full flex items-center justify-center">
            {{ pendingOrders.length }}
          </span>
        </button>
      </div>
    </div>

    <!-- 低庫存警示卡片 -->
    <div v-if="!loading && lowStockItems.length > 0" class="px-4 mt-4">
      <div class="rounded-xl p-4" style="border:1.5px solid #fca5a5;background:#fef2f2">
        <p class="font-extrabold mb-3" style="font-size:11px;color:#dc2626">🚨 低庫存警示 — 需補貨</p>
        <div class="space-y-2">
          <div v-for="item in lowStockItems.slice(0, 5)" :key="item.id"
            class="flex items-center justify-between">
            <span class="font-semibold" style="font-size:12px;color:#7f1d1d">{{ item.name }}</span>
            <span class="font-bold" style="font-size:11px;color:#dc2626">
              庫存 {{ item.current_stock }} ／安全 {{ item.min_stock }} {{ item.unit }}
            </span>
          </div>
          <div v-if="lowStockItems.length > 5" class="text-center" style="font-size:11px;color:#ef4444">
            還有 {{ lowStockItems.length - 5 }} 項…
          </div>
        </div>
        <button
          @click="router.push({ name: 'order' })"
          class="mt-3 w-full text-white font-extrabold rounded-lg active:scale-95 transition-transform"
          style="background:#dc2626;font-size:12px;padding:7px;text-align:center">
          一鍵前往叫貨 →
        </button>
      </div>
    </div>

    <!-- 今日待辦 -->
    <div v-if="!loading" class="px-4 mt-5">
      <h2 class="font-bold text-slate-700 mb-3" style="font-size:13px">今日待辦</h2>

      <!-- 黃色警示條 -->
      <div v-if="overdueReceive"
        @click="router.push({ name: 'order' })"
        class="rounded-lg px-3 py-2.5 mb-3 cursor-pointer"
        style="background:#fefce8;border:1px solid #fde68a;font-size:12px;font-weight:600;color:#92400e">
        ⚠️ {{ overdueReceive.vendor_name }} 今日到貨，尚未簽收 — 點此處理
      </div>

      <!-- 待簽收訂單卡片 -->
      <div v-if="pendingOrders.length === 0 && pendingStocktakeGroups.length === 0"
        class="text-center py-8 text-slate-400 text-sm">
        今日無待辦事項 🎉
      </div>

      <!-- 📦 待收貨 -->
      <div v-if="pendingOrders.length > 0" class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-extrabold text-slate-500 uppercase tracking-wide">📦 待收貨</span>
          <span class="text-xs font-bold text-orange-500">{{ pendingOrders.length }} 筆</span>
        </div>
        <div class="space-y-2">
          <button
            v-for="order in pendingOrders.slice(0, 5)" :key="order.id"
            @click="router.push({ name: 'order' })"
            class="w-full bg-white rounded-xl p-4 flex items-center gap-3 shadow-sm active:bg-slate-50 transition-colors text-left"
            style="border-radius:12px">
            <span style="font-size:24px">🚚</span>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800" style="font-size:14px">{{ order.vendor_name }}</p>
              <p class="mt-0.5" style="font-size:12px;color:#999">
                {{ order.expected_delivery_date ? fmtTime(order.expected_delivery_date) : '時間未定' }}
                · {{ order.total_items || '?' }} 項品項
              </p>
            </div>
            <span class="font-bold shrink-0" style="background:#fff7ed;color:#ea580c;border-radius:12px;font-size:11px;padding:4px 10px">待收</span>
            <span style="color:#ccc;font-size:16px">›</span>
          </button>
        </div>
      </div>

      <!-- 📋 待盤點 -->
      <div v-if="pendingStocktakeGroups.length > 0" class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-extrabold text-slate-500 uppercase tracking-wide">📋 待盤點</span>
          <span class="text-xs font-bold text-blue-500">{{ pendingStocktakeGroups.length }} 組</span>
        </div>
        <div class="space-y-2">
          <button
            v-for="group in pendingStocktakeGroups" :key="group.group_id"
            @click="goToStocktake(group.group_id)"
            class="w-full bg-white rounded-xl p-4 flex items-center gap-3 shadow-sm active:bg-slate-50 transition-colors text-left"
            style="border-radius:12px">
            <span style="font-size:24px">📋</span>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800" style="font-size:14px">{{ group.group_name }}</p>
              <p class="mt-0.5" style="font-size:12px;color:#999">{{ stocktakeDueLabel(group) }}</p>
            </div>
            <span class="font-bold shrink-0"
              :style="group.overdue_days > 0
                ? 'background:#fef2f2;color:#dc2626;border-radius:12px;font-size:11px;padding:4px 10px'
                : 'background:#eff6ff;color:#2563eb;border-radius:12px;font-size:11px;padding:4px 10px'">
              {{ group.overdue_days > 0 ? '逾期' : '待盤' }}
            </span>
            <span style="color:#ccc;font-size:16px">›</span>
          </button>
        </div>
      </div>

    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex justify-center py-16">
      <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>

  </div>
</template>
