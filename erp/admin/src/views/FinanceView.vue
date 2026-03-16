<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const tab = ref('petty')  // 'petty' | 'cashflow' | 'payable' | 'monthly'
const loading = ref(true)

const pettyBalance = ref(0)
const pettyRecords = ref([])
const cashFlowRecords = ref([])
const categories = ref([])
const payables = ref([])
const monthlySummary = ref(null)

const monthInput = ref('')  // YYYY-MM

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function fmtMoney(n) { return Number(n).toLocaleString('zh-TW') }
function fmtDate(d) { return d ? new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—' }

async function loadAll() {
  loading.value = true
  const now = new Date()
  if (!monthInput.value) {
    monthInput.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  }
  const [y, m] = monthInput.value.split('-').map(Number)

  const [balRes, pettyRes, cfRes, payRes, catRes, sumRes] = await Promise.all([
    fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/petty-cash?days_limit=30&limit=100`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow?days_limit=90&limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/accounts-payable?limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/summary/${y}/${m}`, { headers: authHeaders() }),
  ])
  if (balRes.ok) pettyBalance.value = (await balRes.json()).balance
  if (pettyRes.ok) pettyRecords.value = await pettyRes.json()
  if (cfRes.ok) cashFlowRecords.value = await cfRes.json()
  if (payRes.ok) payables.value = await payRes.json()
  if (catRes.ok) categories.value = await catRes.json()
  if (sumRes.ok) monthlySummary.value = await sumRes.json()
  loading.value = false
}

async function markPaid(p) {
  if (!confirm(`確認結清 ${p.vendor_name || '帳款'} $${p.amount}？`)) return
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}/pay`, {
    method: 'PUT', headers: authHeaders()
  })
  if (res.ok) await loadAll()
}

async function updateCategory(record, catId) {
  await fetch(`${API_BASE}/finance/cash-flow/${record.id}/category`, {
    method: 'PUT', headers: authHeaders(),
    body: JSON.stringify({ category_id: parseInt(catId) })
  })
  await loadAll()
}

onMounted(loadAll)

const tabDef = [
  { key: 'petty', label: '零用金' },
  { key: 'cashflow', label: '金流明細' },
  { key: 'payable', label: '應付帳款' },
  { key: 'monthly', label: '月度損益' },
]
</script>

<template>
  <div class="space-y-5">
    <!-- Tab bar -->
    <div class="flex border-b border-[#2d3748]">
      <button v-for="t in tabDef" :key="t.key" @click="tab = t.key"
        class="px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="tab === t.key ? 'text-blue-400 border-blue-400' : 'text-gray-500 border-transparent hover:text-gray-300'">
        {{ t.label }}
        <span v-if="t.key === 'payable' && payables.filter(p => !p.is_paid).length"
          class="ml-1 text-xs bg-amber-500 text-black font-bold rounded-full px-1.5">
          {{ payables.filter(p => !p.is_paid).length }}
        </span>
      </button>
    </div>

    <div v-if="loading" class="py-16 text-center text-gray-500">載入中…</div>

    <!-- ===== Petty Cash ===== -->
    <div v-else-if="tab === 'petty'" class="space-y-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 flex items-center gap-6">
        <div>
          <p class="text-xs text-gray-500 uppercase tracking-wider">零用金餘額</p>
          <p class="text-3xl font-bold text-blue-400 mt-1">${{ fmtMoney(pettyBalance) }}</p>
        </div>
      </div>

      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">時間</th>
              <th class="px-5 py-3 text-center">類型</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-left">備註</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="r in pettyRecords" :key="r.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-3 text-gray-500">{{ fmtDate(r.created_at) }}</td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold"
                  :class="r.type === 'income' ? 'text-emerald-400' : r.type === 'withdrawal' ? 'text-red-400' : 'text-blue-400'">
                  {{ r.type === 'income' ? '收入' : r.type === 'withdrawal' ? '提領' : '支出' }}
                </span>
              </td>
              <td class="px-5 py-3 text-right font-mono"
                :class="r.type === 'income' ? 'text-emerald-400' : 'text-red-400'">
                {{ r.type === 'income' ? '+' : '-' }}${{ fmtMoney(r.amount) }}
              </td>
              <td class="px-5 py-3 text-gray-500 text-xs">{{ r.note || r.vendor_name || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== Cash Flow ===== -->
    <div v-else-if="tab === 'cashflow'">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">時間</th>
              <th class="px-5 py-3 text-center">類型</th>
              <th class="px-5 py-3 text-left">科目</th>
              <th class="px-5 py-3 text-left">說明</th>
              <th class="px-5 py-3 text-right">金額</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="r in cashFlowRecords" :key="r.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-3 text-gray-500 text-xs">{{ fmtDate(r.created_at) }}</td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold" :class="r.type === 'income' ? 'text-emerald-400' : 'text-blue-400'">
                  {{ r.type === 'income' ? '收入' : '支出' }}
                </span>
              </td>
              <td class="px-5 py-3">
                <select v-if="!r.is_categorized"
                  @change="updateCategory(r, $event.target.value)"
                  class="bg-[#111827] border border-amber-500/50 text-amber-400 rounded px-2 py-1 text-xs focus:outline-none">
                  <option value="">-- 選擇科目 --</option>
                  <option v-for="c in categories.filter(c => c.type === r.type)" :key="c.id" :value="c.id">
                    {{ c.name }}
                  </option>
                </select>
                <span v-else class="text-gray-300 text-xs">{{ r.category_name || '—' }}</span>
              </td>
              <td class="px-5 py-3 text-gray-500 text-xs">{{ r.description || '—' }}</td>
              <td class="px-5 py-3 text-right font-mono"
                :class="r.type === 'income' ? 'text-emerald-400' : 'text-gray-300'">
                {{ r.type === 'income' ? '+' : '-' }}${{ fmtMoney(r.amount) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== Accounts Payable ===== -->
    <div v-else-if="tab === 'payable'">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">供應商</th>
              <th class="px-5 py-3 text-left">到期日</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-center">狀態</th>
              <th class="px-5 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="p in payables" :key="p.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-3 font-semibold text-gray-200">{{ p.vendor_name || '—' }}</td>
              <td class="px-5 py-3 text-gray-400">{{ p.due_date ? new Date(p.due_date).toLocaleDateString('zh-TW') : '未設定' }}</td>
              <td class="px-5 py-3 text-right font-mono" :class="p.is_paid ? 'text-gray-500' : 'text-amber-400'">
                ${{ fmtMoney(p.amount) }}
              </td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold" :class="p.is_paid ? 'text-emerald-400' : 'text-amber-400'">
                  {{ p.is_paid ? '已付' : '未付' }}
                </span>
              </td>
              <td class="px-5 py-3 text-center">
                <button v-if="!p.is_paid" @click="markPaid(p)"
                  class="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-lg transition-colors">
                  結清
                </button>
                <span v-else class="text-gray-600 text-xs">{{ p.paid_at ? new Date(p.paid_at).toLocaleDateString('zh-TW') : '—' }}</span>
              </td>
            </tr>
            <tr v-if="payables.length === 0">
              <td colspan="5" class="px-5 py-10 text-center text-gray-600">無應付帳款</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== Monthly P&L ===== -->
    <div v-else-if="tab === 'monthly'" class="space-y-4">
      <div class="flex items-center gap-3">
        <input v-model="monthInput" type="month"
          class="bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-blue-500" />
        <button @click="loadAll" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          查詢
        </button>
      </div>

      <div v-if="monthlySummary" class="grid grid-cols-3 gap-4">
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 uppercase tracking-wider">總收入</p>
          <p class="text-3xl font-bold text-emerald-400 mt-2">${{ fmtMoney(monthlySummary.total_income) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 uppercase tracking-wider">總支出</p>
          <p class="text-3xl font-bold text-red-400 mt-2">${{ fmtMoney(monthlySummary.total_expense) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 uppercase tracking-wider">淨收入</p>
          <p class="text-3xl font-bold mt-2" :class="monthlySummary.net >= 0 ? 'text-blue-400' : 'text-red-400'">
            ${{ fmtMoney(monthlySummary.net) }}
          </p>
        </div>
      </div>
    </div>

  </div>
</template>
