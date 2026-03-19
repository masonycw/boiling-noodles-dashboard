<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const orders = ref([])
const vendors = ref([])
const loading = ref(true)
const expandedId = ref(null)
const orderDetails = ref({})

// Filters
const filterDateFrom = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10))
const filterDateTo = ref(new Date().toISOString().slice(0, 10))
const filterVendor = ref('')
const filterStatus = ref('')

// Pagination
const page = ref(1)
const PAGE_SIZE = 10

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function load() {
  loading.value = true
  const [ordRes, vendRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/orders?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (ordRes.ok) orders.value = await ordRes.json()
  if (vendRes.ok) vendors.value = await vendRes.json()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  let list = orders.value
  if (filterDateFrom.value) {
    list = list.filter(o => o.created_at >= filterDateFrom.value)
  }
  if (filterDateTo.value) {
    const to = filterDateTo.value + 'T23:59:59'
    list = list.filter(o => o.created_at <= to)
  }
  if (filterVendor.value) {
    list = list.filter(o => String(o.vendor_id) === filterVendor.value)
  }
  if (filterStatus.value) {
    list = list.filter(o => o.status === filterStatus.value)
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paginated = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

function changePage(p) {
  page.value = Math.max(1, Math.min(p, totalPages.value))
}

function applyFilters() {
  page.value = 1
}

async function toggleExpand(order) {
  if (expandedId.value === order.id) { expandedId.value = null; return }
  expandedId.value = order.id
  if (!orderDetails.value[order.id]) {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    if (res.ok) {
      const d = await res.json()
      orderDetails.value[order.id] = Array.isArray(d) ? d : (d.items || [])
    }
  }
}

const statusLabel = (s) => ({ draft: '草稿', confirmed: '已確認', received: '已收貨', pending: '待送出', shipped: '已送出' }[s] || s)
const statusBadge = (s) => ({
  received: 'bg-[#10b981] text-white',
  shipped: 'bg-[#3b82f6] text-white',
  confirmed: 'bg-[#3b82f6] text-white',
  pending: 'bg-[#f59e0b] text-white',
  draft: 'bg-gray-700 text-gray-300',
}[s] || 'bg-gray-700 text-gray-300')

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '—'
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
</script>

<template>
  <div>
    <!-- Filters -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <input v-model="filterDateFrom" @change="applyFilters" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <span class="text-gray-500 text-sm">至</span>
      <input v-model="filterDateTo" @change="applyFilters" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterVendor" @change="applyFilters"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部供應商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <select v-model="filterStatus" @change="applyFilters"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部狀態</option>
        <option value="pending">待送出</option>
        <option value="shipped">已送出</option>
        <option value="received">已收貨</option>
        <option value="draft">草稿</option>
      </select>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <template v-else>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
              <th class="px-4 py-3 text-left">日期</th>
              <th class="px-4 py-3 text-left">供應商</th>
              <th class="px-4 py-3 text-center">品項數</th>
              <th class="px-4 py-3 text-right">總金額</th>
              <th class="px-4 py-3 text-center">狀態</th>
              <th class="px-4 py-3 text-center">付款</th>
              <th class="px-4 py-3 text-center">查看</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="o in paginated" :key="o.id">
              <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] transition-colors cursor-pointer"
                @click="toggleExpand(o)">
                <td class="px-4 py-3 text-gray-400 text-xs">{{ fmtDate(o.created_at) }}</td>
                <td class="px-4 py-3 font-semibold text-gray-200">{{ o.vendor_name }}</td>
                <td class="px-4 py-3 text-center text-gray-400">{{ o.total_items }}</td>
                <td class="px-4 py-3 text-right font-mono text-gray-300">${{ fmtMoney(o.total_amount) }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="statusBadge(o.status)">
                    {{ statusLabel(o.status) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold" :class="o.is_paid ? 'text-emerald-400' : 'text-amber-400'">
                    {{ o.is_paid ? '✓ 已付' : '未付' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center text-[#63b3ed] text-xs font-bold">
                  {{ expandedId === o.id ? '▲' : '查看' }}
                </td>
              </tr>
              <!-- Expanded detail -->
              <tr v-if="expandedId === o.id" class="border-b border-[#2d3748] bg-[#0f1117]">
                <td colspan="7" class="px-6 py-4">
                  <div v-if="!orderDetails[o.id]" class="text-gray-500 text-sm">載入中…</div>
                  <table v-else class="w-full text-xs">
                    <thead>
                      <tr class="text-[#9ca3af] border-b border-[#2d3748]">
                        <th class="pb-2 text-left">品項</th>
                        <th class="pb-2 text-right">叫貨量</th>
                        <th class="pb-2 text-right">收貨量</th>
                        <th class="pb-2 text-right">差異</th>
                        <th class="pb-2 text-right">小計</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="d in orderDetails[o.id]" :key="d.id || d.name"
                        class="text-gray-400 border-b border-[#1a202c]"
                        :class="d.discrepancy ? 'bg-red-900/10' : ''">
                        <td class="py-1.5">{{ d.name || d.adhoc_name }}</td>
                        <td class="py-1.5 text-right">{{ d.qty }}</td>
                        <td class="py-1.5 text-right">{{ d.actual_qty ?? '—' }}</td>
                        <td class="py-1.5 text-right" :class="d.discrepancy ? 'text-amber-400' : ''">
                          {{ d.discrepancy ? d.discrepancy : '—' }}
                        </td>
                        <td class="py-1.5 text-right text-gray-300">${{ fmtMoney(d.subtotal ?? 0) }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="o.note" class="text-gray-500 text-xs mt-3">備註：{{ o.note }}</p>
                </td>
              </tr>
            </template>
            <tr v-if="filtered.length === 0">
              <td colspan="7" class="px-5 py-10 text-center text-gray-600">無叫貨紀錄</td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 px-5 py-4 border-t border-[#2d3748]">
          <button @click="changePage(page - 1)" :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30 transition-colors">
            上一頁
          </button>
          <button v-for="p in totalPages" :key="p" @click="changePage(p)"
            class="w-8 h-8 rounded-lg text-sm font-bold transition-colors"
            :class="p === page ? 'bg-[#63b3ed] text-black' : 'text-gray-400 hover:bg-[#1f2937]'">
            {{ p }}
          </button>
          <button @click="changePage(page + 1)" :disabled="page === totalPages"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30 transition-colors">
            下一頁
          </button>
        </div>
        <div class="px-5 py-2 text-xs text-gray-600 text-right">
          共 {{ filtered.length }} 筆
        </div>
      </template>
    </div>
  </div>
</template>
