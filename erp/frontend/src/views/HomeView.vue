<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const loading = ref(true)
const lowStockItems = ref([])
const announcements = ref([])

const pendingStocktakeGroups = ref([])
const fixedOrderVendors = ref([])

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


async function loadData() {
  try {
    const [itemsRes, stocktakeRes, vendorRes, annRes] = await Promise.all([
      fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
      fetch(`${API_BASE}/stocktake/pending-groups`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
      fetch(`${API_BASE}/announcements`, { headers: authHeaders() }),
    ])
    if (itemsRes.ok) {
      const allItems = await itemsRes.json()
      lowStockItems.value = allItems.filter(i =>
        parseFloat(i.min_stock) > 0 && parseFloat(i.current_stock) <= parseFloat(i.min_stock)
      )
    }
    if (stocktakeRes.ok) {
      pendingStocktakeGroups.value = await stocktakeRes.json()
    }
    if (annRes.ok) announcements.value = await annRes.json()
    if (vendorRes.ok) {
      const allVendors = await vendorRes.json()
      const dow = new Date().getDay() || 7 // JS: 0=Sunday→7
      fixedOrderVendors.value = allVendors
        .filter(v => v.is_fixed_order && v.show_in_ordering && Array.isArray(v.order_days) && v.order_days.includes(dow))
        .sort((a, b) => (a.order_time || '99:99').localeCompare(b.order_time || '99:99'))
    }
  } finally {
    loading.value = false
  }
}

function orderDeadlineStatus(vendor) {
  if (!vendor.order_time) return null
  const now = new Date()
  const [h, m] = vendor.order_time.split(':').map(Number)
  const deadline = new Date(now)
  deadline.setHours(h, m, 0, 0)
  const diffMin = Math.round((deadline - now) / 60000)
  if (diffMin < 0) return { label: `截單已過 ${vendor.order_time}`, cls: 'bg-red-50 text-red-500', overdue: true }
  if (diffMin <= 60) return { label: `截單倒數 ${diffMin} 分`, cls: 'bg-amber-50 text-amber-600', overdue: false }
  return { label: `截單 ${vendor.order_time}`, cls: 'bg-orange-50 text-orange-500', overdue: false }
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
        </button>
      </div>
    </div>

    <!-- 公告欄 -->
    <div v-if="!loading && announcements.length > 0" class="px-4 mt-4 space-y-2">
      <div v-for="ann in announcements" :key="ann.id"
        class="rounded-xl px-4 py-3 flex items-start gap-2.5"
        style="background:#fffbeb;border:1.5px solid #fcd34d">
        <span class="text-lg mt-0.5 shrink-0">📢</span>
        <p class="text-sm font-medium leading-snug" style="color:#78350f">{{ ann.content }}</p>
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
          @click="router.push({ name: 'order', query: lowStockItems[0]?.vendor_id ? { vendorId: lowStockItems[0].vendor_id } : {} })"
          class="mt-3 w-full text-white font-extrabold rounded-lg active:scale-95 transition-transform"
          style="background:#dc2626;font-size:12px;padding:7px;text-align:center">
          一鍵前往叫貨 →
        </button>
      </div>
    </div>

    <!-- 今日待辦 -->
    <div v-if="!loading" class="px-4 mt-5">
      <h2 class="font-bold text-slate-700 mb-3" style="font-size:13px">今日待辦</h2>

      <!-- 待辦空狀態 -->
      <div v-if="pendingStocktakeGroups.length === 0 && fixedOrderVendors.length === 0"
        class="text-center py-8 text-slate-400 text-sm">
        今日無待辦事項 🎉
      </div>

      <!-- 📅 今日叫貨排程 -->
      <div v-if="fixedOrderVendors.length > 0" class="mb-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-extrabold text-slate-500 uppercase tracking-wide">📅 今日叫貨排程</span>
          <span class="text-xs font-bold text-orange-500">{{ fixedOrderVendors.length }} 家</span>
        </div>
        <div class="space-y-2">
          <button
            v-for="v in fixedOrderVendors" :key="v.id"
            @click="router.push({ name: 'order' })"
            class="w-full bg-white rounded-xl p-4 flex items-center gap-3 shadow-sm active:bg-slate-50 transition-colors text-left"
            style="border-radius:12px">
            <span style="font-size:22px">🏪</span>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800" style="font-size:14px">{{ v.name }}</p>
              <p class="mt-0.5" style="font-size:12px;color:#999">
                {{ v.order_time ? `截單 ${v.order_time}` : '今日需叫貨' }}
              </p>
            </div>
            <span v-if="orderDeadlineStatus(v)"
              class="font-bold shrink-0 text-[11px] px-2.5 py-1 rounded-full"
              :class="orderDeadlineStatus(v).cls">
              {{ orderDeadlineStatus(v).label }}
            </span>
            <span v-else class="font-bold shrink-0" style="background:#fff7ed;color:#ea580c;border-radius:12px;font-size:11px;padding:4px 10px">前往叫貨</span>
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
