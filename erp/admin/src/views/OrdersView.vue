<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const orders = ref([])
const loading = ref(true)
const filterStatus = ref('')
const expandedId = ref(null)
const orderDetails = ref({})   // { order_id: [items] }

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function load() {
  loading.value = true
  const params = filterStatus.value ? `?status=${filterStatus.value}` : ''
  const res = await fetch(`${API_BASE}/inventory/orders${params}&limit=100`, { headers: authHeaders() })
  if (res.ok) orders.value = await res.json()
  loading.value = false
}

onMounted(load)

async function toggleExpand(order) {
  if (expandedId.value === order.id) { expandedId.value = null; return }
  expandedId.value = order.id
  if (!orderDetails.value[order.id]) {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    if (res.ok) {
      const d = await res.json()
      // API returns array directly from get_order endpoint
      orderDetails.value[order.id] = Array.isArray(d) ? d : (d.items || [])
    }
  }
}

const statusOptions = [
  { value: '', label: '全部' },
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已確認' },
  { value: 'received', label: '已收貨' },
]

const statusLabel = (s) => ({ draft: '草稿', confirmed: '已確認', received: '已收貨' }[s] || s)
const statusColor = (s) => ({ draft: 'bg-gray-700 text-gray-300', confirmed: 'bg-blue-900/50 text-blue-400', received: 'bg-emerald-900/50 text-emerald-400' }[s] || '')

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '—'
}
function fmtMoney(n) { return Number(n).toLocaleString('zh-TW') }
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-5">
      <div class="flex rounded-lg overflow-hidden border border-[#374151]">
        <button v-for="opt in statusOptions" :key="opt.value"
          @click="filterStatus = opt.value; load()"
          class="px-4 py-2 text-sm font-medium transition-colors"
          :class="filterStatus === opt.value ? 'bg-blue-600 text-white' : 'bg-[#111827] text-gray-400 hover:bg-[#1f2937]'">
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <template v-else>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">日期</th>
              <th class="px-5 py-3 text-left">供應商</th>
              <th class="px-5 py-3 text-center">狀態</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-center">付款</th>
              <th class="px-5 py-3 text-center">展開</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="o in orders" :key="o.id">
              <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] transition-colors cursor-pointer"
                @click="toggleExpand(o)">
                <td class="px-5 py-3 text-gray-400">{{ fmtDate(o.created_at) }}</td>
                <td class="px-5 py-3 font-semibold text-gray-200">{{ o.vendor_name }}</td>
                <td class="px-5 py-3 text-center">
                  <span class="text-xs font-bold px-2 py-1 rounded-full" :class="statusColor(o.status)">
                    {{ statusLabel(o.status) }}
                  </span>
                </td>
                <td class="px-5 py-3 text-right font-mono text-gray-300">${{ fmtMoney(o.total_amount) }}</td>
                <td class="px-5 py-3 text-center">
                  <span class="text-xs font-bold" :class="o.is_paid ? 'text-emerald-400' : 'text-amber-400'">
                    {{ o.is_paid ? '已付' : '未付' }}
                  </span>
                </td>
                <td class="px-5 py-3 text-center text-gray-500">
                  {{ expandedId === o.id ? '▲' : '▼' }}
                </td>
              </tr>
              <!-- Expanded detail -->
              <tr v-if="expandedId === o.id" class="border-b border-[#2d3748] bg-[#0f1117]">
                <td colspan="6" class="px-8 py-4">
                  <div v-if="!orderDetails[o.id]" class="text-gray-500 text-sm">載入中…</div>
                  <table v-else class="w-full text-xs">
                    <thead>
                      <tr class="text-gray-500 border-b border-[#2d3748]">
                        <th class="pb-2 text-left">品項</th>
                        <th class="pb-2 text-right">叫貨量</th>
                        <th class="pb-2 text-right">收貨量</th>
                        <th class="pb-2 text-right">差異</th>
                        <th class="pb-2 text-right">小計</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="d in orderDetails[o.id]" :key="d.id" class="text-gray-400 border-b border-[#1a202c]">
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
            <tr v-if="orders.length === 0">
              <td colspan="6" class="px-5 py-10 text-center text-gray-600">無叫貨紀錄</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>
  </div>
</template>
