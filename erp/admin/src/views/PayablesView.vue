<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const payables = ref([])
const vendors = ref([])
const loading = ref(true)
const payVendor = ref('')
const payStatus = ref('')
const toast = ref('')

const now = new Date()

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' })
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

function daysUntil(dateStr) {
  if (!dateStr) return null
  return Math.ceil((new Date(dateStr) - now) / 86400000)
}
function payableStatusInfo(p) {
  if (p.is_paid) return { label: '✓ 已匯款', cls: 'bg-emerald-700 text-white' }
  const days = daysUntil(p.due_date)
  if (days === null) return { label: '待付款', cls: 'bg-amber-600 text-white' }
  if (days < 0) return { label: '逾期', cls: 'bg-red-600 text-white' }
  if (days <= 3) return { label: `${days}天後到期`, cls: 'bg-red-600 text-white' }
  if (days <= 14) return { label: `${days}天後到期`, cls: 'bg-amber-600 text-white' }
  return { label: '下月到期', cls: 'bg-[#374151] text-gray-300' }
}

async function load() {
  loading.value = true
  const [payRes, vendorRes] = await Promise.all([
    fetch(`${API_BASE}/finance/accounts-payable?limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (payRes.ok) payables.value = await payRes.json()
  if (vendorRes.ok) vendors.value = await vendorRes.json()
  loading.value = false
}
onMounted(load)

const filtered = computed(() => {
  let list = payables.value
  if (payVendor.value) list = list.filter(p => String(p.vendor_id) === payVendor.value)
  if (payStatus.value === 'paid') list = list.filter(p => p.is_paid)
  if (payStatus.value === 'unpaid') list = list.filter(p => !p.is_paid)
  return list
})

const pendingTotal = computed(() =>
  payables.value.filter(p => !p.is_paid).reduce((s, p) => s + parseFloat(p.amount || 0), 0)
)
const unpaidVendors = computed(() => {
  const ids = [...new Set(payables.value.filter(p => !p.is_paid && p.vendor_id).map(p => p.vendor_id))]
  return vendors.value.filter(v => ids.includes(v.id))
})

async function markPaid(p) {
  if (!confirm(`確認結清 ${p.vendor_name || '帳款'} NT$${p.amount}？`)) return
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}/pay`, {
    method: 'PUT', headers: authHeaders()
  })
  if (res.ok) { showToast('已標記匯款'); await load() }
}
</script>

<template>
  <div class="space-y-5">
    <!-- 篩選 + 待付提示 -->
    <div class="flex flex-wrap items-center gap-3">
      <select v-model="payVendor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部廠商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <select v-model="payStatus"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部狀態</option>
        <option value="unpaid">待付款</option>
        <option value="paid">已匯款</option>
      </select>
      <div v-if="pendingTotal > 0"
        class="ml-auto px-4 py-2 rounded-lg text-sm font-bold bg-purple-900/40 border border-purple-500/50 text-purple-300">
        ⚠ 待付合計 NT$ {{ fmtMoney(pendingTotal) }}
      </div>
    </div>

    <!-- 表格 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="py-10 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-3 text-left">廠商</th>
            <th class="px-5 py-3 text-left">收貨日</th>
            <th class="px-5 py-3 text-left">付款條件</th>
            <th class="px-5 py-3 text-right">應付金額</th>
            <th class="px-5 py-3 text-left">到期日</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="p in filtered" :key="p.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-3 font-semibold text-gray-200">{{ p.vendor_name || '—' }}</td>
            <td class="px-5 py-3 text-gray-400 text-xs">{{ fmtDate(p.created_at) }}</td>
            <td class="px-5 py-3 text-gray-400 text-xs">{{ p.payment_terms || p.note || '—' }}</td>
            <td class="px-5 py-3 text-right font-mono" :class="p.is_paid ? 'text-gray-500' : 'text-amber-400'">
              NT$ {{ fmtMoney(p.amount) }}
            </td>
            <td class="px-5 py-3 text-gray-400 text-xs">
              {{ p.due_date ? new Date(p.due_date).toLocaleDateString('zh-TW') : '未設定' }}
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="payableStatusInfo(p).cls">
                {{ payableStatusInfo(p).label }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <button v-if="!p.is_paid" @click="markPaid(p)"
                class="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-lg transition-colors">
                標記已匯
              </button>
              <span v-else class="text-gray-600 text-xs">{{ p.paid_at ? fmtDate(p.paid_at) : '—' }}</span>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="7" class="px-5 py-10 text-center text-gray-600">無應付帳款</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 廠商匯款資訊 -->
    <div v-if="unpaidVendors.length > 0">
      <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">廠商匯款資訊</p>
      <div class="grid grid-cols-2 gap-3">
        <div v-for="v in unpaidVendors" :key="v.id" class="bg-[#111827] rounded-lg p-4 text-sm">
          <p class="font-bold text-gray-200 mb-1">{{ v.name }}</p>
          <p class="text-gray-500 text-xs">{{ v.bank_name || '未設定銀行' }}</p>
          <p class="text-gray-300 text-xs font-mono">{{ v.bank_account || '—' }}</p>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">{{ toast }}</div>
  </div>
</template>
