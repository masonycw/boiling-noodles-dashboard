<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const loading = ref(true)
const kpi = ref({ petty_cash: 0, pending_payables: 0, payable_amount: 0, waste_count: 0 })
const recentOrders = ref([])
const monthlySummary = ref(null)
const wasteByReason = ref([])

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

function fmtMoney(n) { return Number(n).toLocaleString('zh-TW') }
function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) : ''
}

onMounted(async () => {
  const now = new Date()
  const [y, m] = [now.getFullYear(), now.getMonth() + 1]

  const [pettyCashRes, payRes, wasteRes, ordersRes, summaryRes] = await Promise.all([
    fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/accounts-payable?is_paid=false&limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/summary?days_limit=30`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/orders?limit=10`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/summary/${y}/${m}`, { headers: authHeaders() }),
  ])

  if (pettyCashRes.ok) kpi.value.petty_cash = (await pettyCashRes.json()).balance
  if (payRes.ok) {
    const arr = await payRes.json()
    kpi.value.pending_payables = arr.length
    kpi.value.payable_amount = arr.reduce((s, p) => s + parseFloat(p.amount), 0)
  }
  if (wasteRes.ok) {
    const w = await wasteRes.json()
    kpi.value.waste_count = w.total_records ?? 0
    wasteByReason.value = w.by_reason ?? []
  }
  if (ordersRes.ok) recentOrders.value = await ordersRes.json()
  if (summaryRes.ok) monthlySummary.value = await summaryRes.json()

  loading.value = false
})

const statusLabel = (s) => ({
  confirmed: '待收貨', received: '已收貨', cancelled: '已取消'
}[s] || s)

const statusColor = (s) => ({
  confirmed: 'text-amber-400',
  received: 'text-emerald-400',
  cancelled: 'text-gray-400'
}[s] || 'text-gray-400')
</script>

<template>
  <div class="space-y-6">
    <!-- KPI row -->
    <div class="grid grid-cols-4 gap-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">零用金餘額</p>
        <p v-if="loading" class="text-3xl font-bold text-blue-400 mt-2 animate-pulse">---</p>
        <p v-else class="text-3xl font-bold text-blue-400 mt-2">${{ fmtMoney(kpi.petty_cash) }}</p>
        <p class="text-xs text-gray-600 mt-1">現金在庫</p>
      </div>

      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">本月淨收入</p>
        <p v-if="loading || !monthlySummary" class="text-3xl font-bold mt-2 animate-pulse text-gray-600">---</p>
        <p v-else class="text-3xl font-bold mt-2"
          :class="monthlySummary.net >= 0 ? 'text-emerald-400' : 'text-red-400'">
          ${{ fmtMoney(monthlySummary.net) }}
        </p>
        <p class="text-xs text-gray-600 mt-1">
          <span class="text-emerald-500">↑ ${{ fmtMoney(monthlySummary?.total_income ?? 0) }}</span>
          &nbsp;
          <span class="text-red-500">↓ ${{ fmtMoney(monthlySummary?.total_expense ?? 0) }}</span>
        </p>
      </div>

      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">待付帳款</p>
        <p v-if="loading" class="text-3xl font-bold mt-2 animate-pulse text-gray-600">---</p>
        <p v-else class="text-3xl font-bold text-amber-400 mt-2">{{ kpi.pending_payables }} 筆</p>
        <p class="text-xs text-gray-600 mt-1">合計 ${{ fmtMoney(kpi.payable_amount) }}</p>
      </div>

      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">本月損耗</p>
        <p v-if="loading" class="text-3xl font-bold mt-2 animate-pulse text-gray-600">---</p>
        <p v-else class="text-3xl font-bold text-red-400 mt-2">{{ kpi.waste_count }} 筆</p>
        <p class="text-xs text-gray-600 mt-1">近 30 天</p>
      </div>
    </div>

    <!-- Content row -->
    <div class="grid grid-cols-3 gap-4">

      <!-- Recent orders -->
      <div class="col-span-2 bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <div class="px-5 py-4 border-b border-[#2d3748]">
          <h3 class="font-semibold text-gray-200">最近叫貨紀錄</h3>
        </div>
        <div v-if="loading" class="p-8 text-center text-gray-600">載入中…</div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">日期</th>
              <th class="px-5 py-3 text-left">供應商</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-center">狀態</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="o in recentOrders" :key="o.id" class="hover:bg-[#1f2937] transition-colors">
              <td class="px-5 py-3 text-gray-400">{{ fmtDate(o.created_at) }}</td>
              <td class="px-5 py-3 font-medium text-gray-200">{{ o.vendor_name }}</td>
              <td class="px-5 py-3 text-right font-mono text-gray-300">${{ fmtMoney(o.total_amount) }}</td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold" :class="statusColor(o.status)">
                  {{ statusLabel(o.status) }}
                </span>
              </td>
            </tr>
            <tr v-if="recentOrders.length === 0">
              <td colspan="4" class="px-5 py-8 text-center text-gray-600">無資料</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Waste by reason -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <div class="px-5 py-4 border-b border-[#2d3748]">
          <h3 class="font-semibold text-gray-200">本月損耗分類</h3>
        </div>
        <div v-if="loading" class="p-8 text-center text-gray-600">載入中…</div>
        <div v-else-if="wasteByReason.length === 0" class="p-8 text-center text-gray-600">無損耗紀錄</div>
        <div v-else class="px-5 py-4 space-y-3">
          <div v-for="r in wasteByReason" :key="r.reason" class="flex items-center justify-between">
            <span class="text-sm text-gray-400">{{ r.reason }}</span>
            <span class="text-sm font-bold text-gray-200">{{ r.count }} 筆</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
