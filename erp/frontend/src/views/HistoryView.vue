<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const activeTab = ref('orders') // 'orders' | 'stocktake'

// Orders tab
const orders = ref([])
const ordersLoading = ref(false)
const expandedOrders = ref(new Set())
const orderItems = ref({})  // { orderId: [...items] }

// Stocktake tab
const sessions = ref([])
const stocktakeLoading = ref(false)
const expandedSessions = ref(new Set())

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  return `${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }

async function loadOrders() {
  ordersLoading.value = true
  const res = await fetch(`${API_BASE}/inventory/orders?status=received&days_limit=60&limit=100`, { headers: authHeaders() })
  if (res.ok) orders.value = await res.json()
  ordersLoading.value = false
}

async function loadStocktake() {
  stocktakeLoading.value = true
  const res = await fetch(`${API_BASE}/stocktake/?days_limit=60&limit=50`, { headers: authHeaders() })
  if (res.ok) sessions.value = await res.json()
  stocktakeLoading.value = false
}

async function toggleOrder(order) {
  const s = new Set(expandedOrders.value)
  if (s.has(order.id)) {
    s.delete(order.id)
  } else {
    s.add(order.id)
    if (!orderItems.value[order.id]) {
      const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
      if (res.ok) {
        const data = await res.json()
        orderItems.value[order.id] = data.items || []
      }
    }
  }
  expandedOrders.value = s
}

function toggleSession(id) {
  const s = new Set(expandedSessions.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedSessions.value = s
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'orders' && orders.value.length === 0) await loadOrders()
  if (tab === 'stocktake' && sessions.value.length === 0) await loadStocktake()
}

onMounted(loadOrders)
</script>

<template>
  <div class="min-h-full pb-24" style="background:#f8f9fb">

    <!-- Header + Tabs -->
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-0">
      <div class="flex items-center gap-3 pb-3">
        <h1 class="text-lg font-extrabold text-slate-800">歷史紀錄</h1>
      </div>
      <div class="flex border-b border-slate-100">
        <button v-for="t in [{k:'orders',l:'叫貨紀錄'},{k:'stocktake',l:'盤點紀錄'}]" :key="t.k"
          @click="switchTab(t.k)"
          class="flex-1 py-2.5 text-sm font-bold transition-colors"
          :style="activeTab===t.k ? 'color:#e85d04;border-bottom:2px solid #e85d04' : 'color:#94a3b8'">
          {{ t.l }}
        </button>
      </div>
    </div>

    <!-- ── 叫貨紀錄 Tab ── -->
    <div v-if="activeTab === 'orders'" class="px-4 py-4">
      <div v-if="ordersLoading" class="flex justify-center py-12">
        <div class="animate-spin h-6 w-6 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="orders.length === 0" class="text-center py-12 text-slate-400 text-sm">
        近 60 天無已收貨紀錄
      </div>
      <div v-else class="space-y-2">
        <div v-for="o in orders" :key="o.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
          <!-- Card header -->
          <div @click="toggleOrder(o)" class="px-4 py-3 cursor-pointer active:bg-slate-50">
            <div class="flex items-center justify-between mb-1">
              <p class="font-extrabold text-slate-800">{{ o.vendor_name }}</p>
              <p class="text-xs text-slate-400">{{ fmtDate(o.created_at) }}</p>
            </div>
            <div class="flex items-center justify-between text-xs text-slate-500">
              <span>
                <span v-if="o.ordered_by">叫貨：{{ o.ordered_by.name }}</span>
                <span v-if="o.received_by"> · 簽收：{{ o.received_by.name }}</span>
              </span>
              <span class="font-bold" style="color:#e85d04">
                {{ o.total_items }} 品項 · ${{ fmtMoney(o.total_amount) }}
              </span>
            </div>
            <div class="flex items-center justify-between mt-1">
              <span class="text-[10px] px-2 py-0.5 rounded-full font-bold"
                :style="o.is_paid ? 'background:#f0fdf4;color:#16a34a' : 'background:#fef9c3;color:#92400e'">
                {{ o.is_paid ? '已付款 ✓' : '未付款' }}
              </span>
              <span class="text-slate-400 text-xs">{{ expandedOrders.has(o.id) ? '▲' : '▼' }}</span>
            </div>
          </div>
          <!-- Expanded items -->
          <div v-if="expandedOrders.has(o.id)" class="border-t border-slate-100 px-4 py-3">
            <div v-if="!orderItems[o.id]" class="text-center text-slate-400 text-xs py-2">載入中…</div>
            <div v-else class="space-y-1">
              <div v-for="item in orderItems[o.id]" :key="item.id"
                class="flex items-center justify-between text-sm py-0.5">
                <span class="text-slate-700">{{ item.name }}</span>
                <span class="text-slate-500 text-xs">
                  叫 {{ item.ordered_qty }} / 到 {{ item.received_qty ?? item.ordered_qty }} {{ item.unit }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 盤點紀錄 Tab ── -->
    <div v-else class="px-4 py-4">
      <div v-if="stocktakeLoading" class="flex justify-center py-12">
        <div class="animate-spin h-6 w-6 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="sessions.length === 0" class="text-center py-12 text-slate-400 text-sm">
        近 60 天無盤點紀錄
      </div>
      <div v-else class="space-y-2">
        <div v-for="s in sessions" :key="s.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
          <div @click="toggleSession(s.id)" class="px-4 py-3 cursor-pointer active:bg-slate-50">
            <div class="flex items-center justify-between mb-1">
              <p class="font-extrabold text-slate-800">{{ s.group_name || '全部品項' }}</p>
              <p class="text-xs text-slate-400">{{ fmtDate(s.created_at) }}</p>
            </div>
            <div class="flex items-center justify-between text-xs text-slate-500">
              <span v-if="s.created_by">執行人：{{ s.created_by.name || s.created_by }}</span>
              <span>{{ s.total_items || 0 }} 品項</span>
            </div>
            <div class="flex items-center justify-between mt-1">
              <span class="text-[10px] font-bold"
                :class="(s.diff_count || 0) > 0 ? 'text-red-500' : 'text-emerald-600'">
                {{ (s.diff_count || 0) > 0 ? `差異 ${s.diff_count} 項` : '無差異 ✓' }}
              </span>
              <span class="text-slate-400 text-xs">{{ expandedSessions.has(s.id) ? '▲' : '▼' }}</span>
            </div>
          </div>
          <!-- Expanded diff items -->
          <div v-if="expandedSessions.has(s.id) && s.discrepancies?.length" class="border-t border-slate-100 px-4 py-3 space-y-1">
            <div v-for="d in s.discrepancies" :key="d.item_id"
              class="flex items-center justify-between text-sm">
              <span class="text-slate-700">{{ d.item_name }}</span>
              <span class="text-red-500 text-xs font-bold">系統 {{ d.system_qty }} / 實盤 {{ d.counted_qty }} {{ d.unit }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>