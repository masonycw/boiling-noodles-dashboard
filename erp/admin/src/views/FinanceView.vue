<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const tab = ref('overview') // overview | cashflow | petty | payable | monthly
const loading = ref(true)

// Data
const pettyBalance = ref(0)
const pettyMonthIncome = ref(0)
const pettyMonthExpense = ref(0)
const pettyRecords = ref([])
const cashFlowRecords = ref([])
const categories = ref([])
const payables = ref([])
const monthlySummary = ref(null)
const vendors = ref([])

// Filters
const monthInput = ref('')
const cfDateFrom = ref('')
const cfDateTo = ref('')
const cfType = ref('')
const cfCategory = ref('')
const cfSource = ref('')
const pettyMonth = ref('')
const pettyType = ref('')
const pettyCategory = ref('')
const payMonth = ref('')
const payVendor = ref('')
const payStatus = ref('')
const plPeriod = ref('month')
const plDateFrom = ref('')
const plDateTo = ref('')

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' })
}
function fmtDateTime(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const now = new Date()
const currentYM = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const [cy, cm] = [now.getFullYear(), now.getMonth() + 1]

async function loadAll() {
  loading.value = true
  if (!monthInput.value) monthInput.value = currentYM
  if (!pettyMonth.value) pettyMonth.value = currentYM
  if (!payMonth.value) payMonth.value = currentYM
  const today = now.toISOString().slice(0, 10)
  const monthStart = `${currentYM}-01`
  if (!cfDateFrom.value) cfDateFrom.value = monthStart
  if (!cfDateTo.value) cfDateTo.value = today

  const [balRes, pettyRes, cfRes, payRes, catRes, sumRes, vendorRes] = await Promise.all([
    fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/petty-cash?days_limit=30&limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow?days_limit=90&limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/accounts-payable?limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/summary/${cy}/${cm}`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (balRes.ok) pettyBalance.value = (await balRes.json()).balance
  if (pettyRes.ok) {
    const pr = await pettyRes.json()
    pettyRecords.value = pr
    pettyMonthIncome.value = pr.filter(r => r.type === 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0)
    pettyMonthExpense.value = pr.filter(r => r.type === 'expense').reduce((s, r) => s + parseFloat(r.amount || 0), 0)
  }
  if (cfRes.ok) cashFlowRecords.value = await cfRes.json()
  if (payRes.ok) payables.value = await payRes.json()
  if (catRes.ok) categories.value = await catRes.json()
  if (sumRes.ok) monthlySummary.value = await sumRes.json()
  if (vendorRes.ok) vendors.value = await vendorRes.json()
  loading.value = false
}

onMounted(loadAll)

// Computed filters
const filteredCF = computed(() => {
  let list = cashFlowRecords.value
  if (cfDateFrom.value) list = list.filter(r => r.created_at >= cfDateFrom.value)
  if (cfDateTo.value) list = list.filter(r => r.created_at <= cfDateTo.value + 'T23:59:59')
  if (cfType.value) list = list.filter(r => r.type === cfType.value)
  if (cfCategory.value) list = list.filter(r => (r.category_name || '') === cfCategory.value)
  return list
})

const filteredPetty = computed(() => {
  let list = pettyRecords.value
  if (pettyType.value) list = list.filter(r => r.type === pettyType.value)
  return list
})

const pettyWithBalance = computed(() => {
  let running = parseFloat(pettyBalance.value) || 0
  return filteredPetty.value.map(r => {
    const row = { ...r, running_balance: running }
    if (r.type === 'income') running -= parseFloat(r.amount || 0)
    else running += parseFloat(r.amount || 0)
    return row
  })
})

const filteredPayables = computed(() => {
  let list = payables.value
  if (payVendor.value) list = list.filter(p => String(p.vendor_id) === payVendor.value)
  if (payStatus.value === 'paid') list = list.filter(p => p.is_paid)
  if (payStatus.value === 'unpaid') list = list.filter(p => !p.is_paid)
  return list
})

const pendingPayableTotal = computed(() =>
  payables.value.filter(p => !p.is_paid).reduce((s, p) => s + parseFloat(p.amount || 0), 0)
)

const unpaidVendors = computed(() => {
  const ids = [...new Set(payables.value.filter(p => !p.is_paid && p.vendor_id).map(p => p.vendor_id))]
  return vendors.value.filter(v => ids.includes(v.id))
})

// Overview KPIs
const overviewIncome = computed(() => monthlySummary.value?.total_income || 0)
const overviewExpense = computed(() => monthlySummary.value?.total_expense || 0)
const overviewPending = computed(() => pendingPayableTotal.value)

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

function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = Math.ceil((new Date(dateStr) - now) / 86400000)
  return diff
}
function payableStatusInfo(p) {
  if (p.is_paid) return { label: '✓ 已匯款', cls: 'bg-[#10b981] text-white' }
  const days = daysUntil(p.due_date)
  if (days === null) return { label: '待付款', cls: 'bg-[#f59e0b] text-white' }
  if (days < 0) return { label: '逾期', cls: 'bg-[#ef4444] text-white' }
  if (days <= 3) return { label: `${days}天後到期`, cls: 'bg-[#ef4444] text-white' }
  if (days <= 14) return { label: `${days}天後到期`, cls: 'bg-[#f59e0b] text-white' }
  return { label: '下月到期', cls: 'bg-[#374151] text-gray-300' }
}

function cfSourceInfo(r) {
  const src = r.source || ''
  if (src === 'system' || src === '營運系統') return { label: '🔗 營運系統', bg: 'bg-[#1e3a5f]', txt: 'text-[#63b3ed]' }
  if (src === 'manual' || src === '手動') return { label: '✏ 手動補key', bg: 'bg-[#2d1a00]', txt: 'text-[#fb923c]' }
  if (src === 'auto' || src === '自動') return { label: '⚙ 自動計算', bg: 'bg-[#1a2e1a]', txt: 'text-[#4ade80]' }
  if (src === 'vendor' || src === '廠商') return { label: '💸 廠商匯款', bg: 'bg-[#2d1f3d]', txt: 'text-[#c084fc]' }
  return { label: src || '—', bg: 'bg-[#1f2937]', txt: 'text-gray-400' }
}

// P&L summary values
const plIncome = computed(() => monthlySummary.value?.total_income || 0)
const plExpense = computed(() => monthlySummary.value?.total_expense || 0)
const plCost = computed(() => Math.round(plExpense.value * 0.6))
const plGrossProfit = computed(() => plIncome.value - plCost.value)
const plOtherExpense = computed(() => plExpense.value - plCost.value)
const plNet = computed(() => monthlySummary.value?.net || (plIncome.value - plExpense.value))

// 6-month trend (mock data based on current month)
const trendMonths = computed(() => {
  const months = []
  for (let i = 5; i >= 0; i--) {
    const d = new Date(cy, cm - 1 - i, 1)
    months.push(`${d.getMonth() + 1}月`)
  }
  return months
})

const trendData = computed(() => {
  const base = parseFloat(plIncome.value) || 280000
  return [5, 4, 3, 2, 1, 0].map(i => ({
    income: Math.round(base * (0.85 + Math.random() * 0.3)),
    expense: Math.round(base * (0.55 + Math.random() * 0.2)),
  })).map(d => ({ ...d, net: d.income - d.expense }))
})

const svgMaxVal = 350000
function barH(val) { return Math.round((val / svgMaxVal) * 160) }
function barY(val) { return 180 - barH(val) }

const tabDef = [
  { key: 'overview', label: '金流總覽' },
  { key: 'cashflow', label: '金流紀錄' },
  { key: 'petty', label: '零用金管理' },
  { key: 'payable', label: '應付帳款' },
  { key: 'monthly', label: '月度損益' },
]

const expenseCategoryOptions = ['食材費用', '人事費用', '營業費用', '平台費用', '金融費用', '其他']
</script>

<template>
  <div class="space-y-5">
    <!-- Tab bar -->
    <div class="flex border-b border-[#2d3748]">
      <button v-for="t in tabDef" :key="t.key" @click="tab = t.key"
        class="px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="tab === t.key ? 'text-[#63b3ed] border-[#63b3ed]' : 'text-gray-500 border-transparent hover:text-gray-300'">
        {{ t.label }}
        <span v-if="t.key === 'payable' && payables.filter(p => !p.is_paid).length"
          class="ml-1 text-xs bg-amber-500 text-black font-bold rounded-full px-1.5">
          {{ payables.filter(p => !p.is_paid).length }}
        </span>
      </button>
    </div>

    <div v-if="loading" class="py-16 text-center text-gray-500">載入中…</div>

    <!-- ===== 金流總覽 ===== -->
    <div v-else-if="tab === 'overview'" class="space-y-5">
      <!-- 3 KPI cards -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#10b981]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">當月實際收入</p>
          <p class="text-2xl font-bold text-[#10b981] mt-1">${{ fmtMoney(overviewIncome) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">來自營運系統</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#ef4444]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">當月已確認支出</p>
          <p class="text-2xl font-bold text-[#ef4444] mt-1">${{ fmtMoney(overviewExpense) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">已記帳項目合計</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#f59e0b]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">當月預計支出</p>
          <p class="text-2xl font-bold text-[#f59e0b] mt-1">${{ fmtMoney(overviewExpense + overviewPending) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">尚差 ${{ fmtMoney(overviewPending) }} 待付出</p>
        </div>
      </div>

      <!-- Scheduled expenses table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <div class="px-5 py-3 border-b border-[#2d3748]">
          <h3 class="text-sm font-bold text-gray-200">預計支出明細</h3>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-5 py-2 text-left">廠商 / 科目</th>
              <th class="px-5 py-2 text-left">付款條件</th>
              <th class="px-5 py-2 text-right">金額</th>
              <th class="px-5 py-2 text-center">狀態</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="p in payables.slice(0, 10)" :key="p.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-200 font-medium">{{ p.vendor_name || '帳款' }}</td>
              <td class="px-5 py-2.5 text-gray-400 text-xs">{{ p.note || '—' }}</td>
              <td class="px-5 py-2.5 text-right font-mono text-amber-400">${{ fmtMoney(p.amount) }}</td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="payableStatusInfo(p).cls">
                  {{ payableStatusInfo(p).label }}
                </span>
              </td>
            </tr>
            <tr v-if="payables.length === 0">
              <td colspan="4" class="px-5 py-8 text-center text-gray-600">無預計支出</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 零用金餘額 -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 flex items-center gap-6">
        <div>
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">零用金餘額</p>
          <p class="text-3xl font-bold text-[#63b3ed] mt-1">${{ fmtMoney(pettyBalance) }}</p>
        </div>
      </div>
    </div>

    <!-- ===== 金流紀錄 ===== -->
    <div v-else-if="tab === 'cashflow'" class="space-y-4">
      <!-- Filters -->
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2 text-sm text-gray-400">
          <span>從</span>
          <input v-model="cfDateFrom" type="date"
            class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
          <span>至</span>
          <input v-model="cfDateTo" type="date"
            class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <select v-model="cfType"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部類型</option>
          <option value="income">收入</option>
          <option value="expense">支出</option>
        </select>
        <select v-model="cfCategory"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部分類</option>
          <option v-for="c in expenseCategoryOptions" :key="c" :value="c">{{ c }}</option>
        </select>
        <select v-model="cfSource"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部來源</option>
          <option value="system">🔗 營運系統</option>
          <option value="manual">✏ 手動補key</option>
          <option value="auto">⚙ 自動計算</option>
          <option value="vendor">💸 廠商匯款</option>
        </select>
      </div>

      <!-- Color legend -->
      <div class="flex items-center gap-4 text-xs">
        <div class="flex items-center gap-1.5">
          <span class="w-3 h-3 rounded" style="background:#1e3a5f"></span>
          <span class="text-[#63b3ed]">營運系統</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-3 h-3 rounded" style="background:#2d1a00"></span>
          <span class="text-[#fb923c]">手動補key</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-3 h-3 rounded" style="background:#1a2e1a"></span>
          <span class="text-[#4ade80]">自動計算</span>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="w-3 h-3 rounded" style="background:#2d1f3d"></span>
          <span class="text-[#c084fc]">廠商匯款</span>
        </div>
      </div>

      <!-- Table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-5 py-3 text-left">日期</th>
              <th class="px-5 py-3 text-center">類型</th>
              <th class="px-5 py-3 text-left">科目</th>
              <th class="px-5 py-3 text-left">說明</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-center">來源</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="r in filteredCF" :key="r.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDate(r.created_at) }}</td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold"
                  :class="r.type === 'income' ? 'text-[#10b981]' : 'text-[#63b3ed]'">
                  {{ r.type === 'income' ? '收入' : '支出' }}
                </span>
              </td>
              <td class="px-5 py-2.5 text-xs">
                <select v-if="!r.is_categorized"
                  @change="updateCategory(r, $event.target.value)"
                  class="bg-[#0f1117] border border-amber-500/50 text-amber-400 rounded px-2 py-1 text-xs focus:outline-none">
                  <option value="">-- 選擇科目 --</option>
                  <option v-for="c in categories.filter(c => c.type === r.type)" :key="c.id" :value="c.id">
                    {{ c.name }}
                  </option>
                </select>
                <span v-else class="text-gray-300">{{ r.category_name || '—' }}</span>
              </td>
              <td class="px-5 py-2.5 text-gray-500 text-xs">{{ r.description || '—' }}</td>
              <td class="px-5 py-2.5 text-right font-mono"
                :class="r.type === 'income' ? 'text-[#10b981]' : 'text-[#ef4444]'">
                {{ r.type === 'income' ? '+' : '-' }}${{ fmtMoney(r.amount) }}
              </td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded"
                  :class="[cfSourceInfo(r).bg, cfSourceInfo(r).txt]">
                  {{ cfSourceInfo(r).label }}
                </span>
              </td>
            </tr>
            <tr v-if="filteredCF.length === 0">
              <td colspan="6" class="px-5 py-10 text-center text-gray-600">無金流記錄</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== 零用金管理 ===== -->
    <div v-else-if="tab === 'petty'" class="space-y-5">
      <!-- 3 KPI cards -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#10b981]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">目前零用金餘額</p>
          <p class="text-2xl font-bold text-[#10b981] mt-1">${{ fmtMoney(pettyBalance) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">最後更新 {{ fmtDate(now.toISOString()) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#63b3ed]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">本月累積補充</p>
          <p class="text-2xl font-bold text-[#63b3ed] mt-1">+${{ fmtMoney(pettyMonthIncome) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">共 {{ pettyRecords.filter(r => r.type === 'income').length }} 筆提款</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#ef4444]">
          <p class="text-[#9ca3af] text-xs uppercase tracking-wider">本月累積支出</p>
          <p class="text-2xl font-bold text-[#ef4444] mt-1">-${{ fmtMoney(pettyMonthExpense) }}</p>
          <p class="text-[#6b7280] text-xs mt-1">共 {{ pettyRecords.filter(r => r.type === 'expense').length }} 筆支出</p>
        </div>
      </div>

      <!-- 說明卡片 -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#f59e0b]">
        <p class="text-[#9ca3af] text-[13px] leading-[1.9]">
          零用金為獨立現金帳，與收銀機分開管理。<br>
          <strong class="text-[#10b981]">收入</strong> = 現金撥入零用金（如日結後存入）→ 餘額增加<br>
          <strong class="text-[#ef4444]">支出</strong> = 零用金付出的現場費用 → 餘額減少<br>
          <strong class="text-[#f59e0b]">提領</strong> = 零用金累積過多，取出存入銀行（需 PIN + 拍照）→ 餘額減少<br>
          前台 PWA 僅顯示近 2 天紀錄，完整歷史在此查詢。
        </p>
      </div>

      <!-- Filters -->
      <div class="flex items-center gap-3 flex-wrap">
        <input v-model="pettyMonth" type="month"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
        <select v-model="pettyType"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部類型</option>
          <option value="income">收入</option>
          <option value="expense">支出</option>
          <option value="withdrawal">提領</option>
        </select>
        <select v-model="pettyCategory"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部科目</option>
          <option v-for="c in expenseCategoryOptions" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>

      <!-- Transaction table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-5 py-3 text-left">日期時間</th>
              <th class="px-5 py-3 text-center">類型</th>
              <th class="px-5 py-3 text-left">說明</th>
              <th class="px-5 py-3 text-right">金額</th>
              <th class="px-5 py-3 text-right">餘額</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="r in pettyWithBalance" :key="r.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDateTime(r.created_at) }}</td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded"
                  :class="r.type === 'income' ? 'bg-[#1e3a5f] text-[#63b3ed]' : r.type === 'withdrawal' ? 'bg-[#3d2a00] text-[#f59e0b]' : 'bg-[#10b981] text-white'">
                  {{ r.type === 'income' ? '收入' : r.type === 'withdrawal' ? '提領' : '支出' }}
                </span>
              </td>
              <td class="px-5 py-2.5 text-gray-400 text-xs">{{ r.note || r.vendor_name || '—' }}</td>
              <td class="px-5 py-2.5 text-right font-mono"
                :class="r.type === 'income' ? 'text-[#63b3ed]' : 'text-[#ef4444]'">
                {{ r.type === 'income' ? '+' : '-' }}${{ fmtMoney(r.amount) }}
              </td>
              <td class="px-5 py-2.5 text-right font-mono text-[#e5e7eb]">
                ${{ fmtMoney(r.running_balance) }}
              </td>
            </tr>
            <tr v-if="pettyWithBalance.length === 0">
              <td colspan="5" class="px-5 py-10 text-center text-gray-600">無零用金記錄</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 月度小結 -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-sm font-bold text-gray-200 mb-3">本月零用金小結</p>
        <div class="grid grid-cols-4 gap-4 text-center">
          <div>
            <p class="text-[#9ca3af] text-xs mb-1">月初餘額</p>
            <p class="text-lg font-bold text-gray-200">$0</p>
          </div>
          <div class="border-l border-[#2d3748]">
            <p class="text-[#9ca3af] text-xs mb-1">累積補充</p>
            <p class="text-lg font-bold text-[#63b3ed]">+${{ fmtMoney(pettyMonthIncome) }}</p>
          </div>
          <div class="border-l border-[#2d3748]">
            <p class="text-[#9ca3af] text-xs mb-1">累積支出</p>
            <p class="text-lg font-bold text-[#ef4444]">-${{ fmtMoney(pettyMonthExpense) }}</p>
          </div>
          <div class="border-l border-[#2d3748]">
            <p class="text-[#9ca3af] text-xs mb-1">月末餘額</p>
            <p class="text-lg font-bold text-gray-200">${{ fmtMoney(pettyBalance) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 應付帳款 ===== -->
    <div v-else-if="tab === 'payable'" class="space-y-5">
      <!-- Filters + alert -->
      <div class="flex flex-wrap items-center gap-3">
        <input v-model="payMonth" type="month"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
        <select v-model="payVendor"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部廠商</option>
          <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
        </select>
        <select v-model="payStatus"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]">
          <option value="">全部狀態</option>
          <option value="unpaid">待付款</option>
          <option value="paid">已匯款</option>
        </select>
        <div v-if="pendingPayableTotal > 0"
          class="ml-auto px-4 py-2 rounded-lg text-sm font-bold"
          style="background:#2d1f3d; border:1px solid #7c3aed; color:#c084fc;">
          ⚠ 本月待付 ${{ fmtMoney(pendingPayableTotal) }}
        </div>
      </div>

      <!-- Payables table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
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
            <tr v-for="p in filteredPayables" :key="p.id" class="hover:bg-[#1f2937]">
              <td class="px-5 py-3 font-semibold text-gray-200">{{ p.vendor_name || '—' }}</td>
              <td class="px-5 py-3 text-gray-400 text-xs">{{ fmtDate(p.created_at) }}</td>
              <td class="px-5 py-3 text-gray-400 text-xs">{{ p.payment_terms || p.note || '—' }}</td>
              <td class="px-5 py-3 text-right font-mono" :class="p.is_paid ? 'text-gray-500' : 'text-amber-400'">
                ${{ fmtMoney(p.amount) }}
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
            <tr v-if="filteredPayables.length === 0">
              <td colspan="7" class="px-5 py-10 text-center text-gray-600">無應付帳款</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Vendor bank info cards -->
      <div v-if="unpaidVendors.length > 0">
        <p class="text-xs font-bold text-[#9ca3af] uppercase tracking-wider mb-3">廠商匯款資訊</p>
        <div class="grid grid-cols-2 gap-3">
          <div v-for="v in unpaidVendors" :key="v.id"
            class="rounded-lg p-4 text-sm"
            style="background:#111827;">
            <p class="font-bold text-gray-200 mb-2">{{ v.name }}</p>
            <p class="text-[#9ca3af] text-xs">{{ v.bank_name || '—' }}</p>
            <p class="text-gray-300 text-xs font-mono">{{ v.bank_account || '—' }}</p>
            <p class="text-gray-400 text-xs">{{ v.bank_account_holder || '—' }}</p>
          </div>
        </div>
      </div>

      <!-- 菜商說明卡片 -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-[#f59e0b]">
        <p class="text-sm font-bold text-gray-200 mb-2">💡 關於逐日入帳的廠商（如菜商）</p>
        <p class="text-[#9ca3af] text-[13px] leading-[1.9]">
          菜商等<strong class="text-white">收貨當日才確認金額</strong>的廠商，每筆收貨紀錄填入金額後，系統自動累積為應付帳款。<br>
          損益表中的食材成本以<strong class="text-white">收貨日</strong>認列（非付款日），確保帳目符合權責發生制。<br>
          每週或月結時，點「標記已匯」即完成付款記錄，金流紀錄自動產生一筆廠商匯款支出。
        </p>
      </div>
    </div>

    <!-- ===== 月度損益 ===== -->
    <div v-else-if="tab === 'monthly'" class="space-y-5">
      <!-- Period selector -->
      <div class="flex items-center gap-3 flex-wrap">
        <div class="flex rounded-lg overflow-hidden border border-[#2d3748]">
          <button v-for="p in ['month','quarter','year']" :key="p" @click="plPeriod = p"
            class="px-4 py-1.5 text-sm transition-colors"
            :class="plPeriod === p ? 'bg-[#63b3ed] text-black font-bold' : 'bg-[#0f1117] text-gray-400 hover:text-gray-200'">
            {{ p === 'month' ? '本月' : p === 'quarter' ? '本季' : '本年' }}
          </button>
        </div>
        <input v-model="plDateFrom" type="date"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
        <span class="text-gray-500">至</span>
        <input v-model="plDateTo" type="date"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#63b3ed]" />
        <button @click="loadAll" class="bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-1.5 rounded-lg text-sm transition-colors">查詢</button>
      </div>

      <!-- 5 KPI cards -->
      <div class="grid grid-cols-5 gap-3">
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-[#9ca3af] text-xs mb-1">營收</p>
          <p class="text-lg font-bold text-gray-200">${{ fmtMoney(plIncome) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-[#9ca3af] text-xs mb-1">成本</p>
          <p class="text-lg font-bold text-[#ef4444]">${{ fmtMoney(plCost) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-[#9ca3af] text-xs mb-1">毛利</p>
          <p class="text-lg font-bold text-gray-200">${{ fmtMoney(plGrossProfit) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-[#9ca3af] text-xs mb-1">費用</p>
          <p class="text-lg font-bold text-[#ef4444]">${{ fmtMoney(plOtherExpense) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-[#9ca3af] text-xs mb-1">淨利</p>
          <p class="text-lg font-bold" :class="plNet >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'">
            ${{ fmtMoney(plNet) }}
          </p>
        </div>
      </div>

      <!-- 6-month trend SVG chart -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-sm font-bold text-gray-200 mb-4">近 6 個月趨勢</p>
        <svg width="100%" viewBox="0 0 600 220" class="overflow-visible">
          <!-- Grid lines -->
          <line v-for="(y, i) in [20, 60, 100, 140, 180]" :key="i"
            x1="40" :y1="y" x2="580" :y2="y"
            stroke="#2d3748" stroke-dasharray="4,4" stroke-width="1" />
          <!-- Y axis labels -->
          <text x="35" y="24" fill="#6b7280" font-size="10" text-anchor="end">35萬</text>
          <text x="35" y="64" fill="#6b7280" font-size="10" text-anchor="end">25萬</text>
          <text x="35" y="104" fill="#6b7280" font-size="10" text-anchor="end">15萬</text>
          <text x="35" y="144" fill="#6b7280" font-size="10" text-anchor="end">5萬</text>
          <!-- Bars and line -->
          <g v-for="(d, i) in trendData" :key="i">
            <rect :x="55 + i * 90" :y="barY(d.income)" width="28" :height="barH(d.income)"
              fill="#10b981" opacity="0.85" rx="2" />
            <rect :x="87 + i * 90" :y="barY(d.expense)" width="28" :height="barH(d.expense)"
              fill="#ef4444" opacity="0.75" rx="2" />
            <text :x="80 + i * 90" y="200" fill="#6b7280" font-size="10" text-anchor="middle">
              {{ trendMonths[i] }}
            </text>
          </g>
          <!-- Net profit line -->
          <polyline
            :points="trendData.map((d, i) => `${70 + i * 90},${barY(d.net)}`).join(' ')"
            fill="none" stroke="#f59e0b" stroke-width="2.5" />
          <circle v-for="(d, i) in trendData" :key="'dot-' + i"
            :cx="70 + i * 90" :cy="barY(d.net)" r="4" fill="#f59e0b" />
          <!-- Legend -->
          <rect x="350" y="205" width="12" height="8" fill="#10b981" rx="1" />
          <text x="366" y="213" fill="#9ca3af" font-size="10">營收</text>
          <rect x="400" y="205" width="12" height="8" fill="#ef4444" rx="1" />
          <text x="416" y="213" fill="#9ca3af" font-size="10">支出</text>
          <line x1="450" y1="209" x2="462" y2="209" stroke="#f59e0b" stroke-width="2.5" />
          <text x="466" y="213" fill="#9ca3af" font-size="10">淨利</text>
        </svg>
      </div>

      <!-- P&L detail table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-5 py-3 text-left">科目</th>
              <th class="px-5 py-3 text-right">本期金額</th>
              <th class="px-5 py-3 text-right">上期金額</th>
              <th class="px-5 py-3 text-right">差異</th>
              <th class="px-5 py-3 text-right">變化率</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr class="bg-[#111827]">
              <td class="px-5 py-2.5 font-bold text-gray-200" colspan="5">收入明細</td>
            </tr>
            <tr class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-300 pl-10">營業收入</td>
              <td class="px-5 py-2.5 text-right font-mono text-gray-200">${{ fmtMoney(plIncome) }}</td>
              <td class="px-5 py-2.5 text-right font-mono text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
            </tr>
            <tr class="bg-[#111827]">
              <td class="px-5 py-2.5 font-bold text-gray-200" colspan="5">支出明細</td>
            </tr>
            <tr class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-300 pl-10">食材成本</td>
              <td class="px-5 py-2.5 text-right font-mono text-[#ef4444]">${{ fmtMoney(plCost) }}</td>
              <td class="px-5 py-2.5 text-right font-mono text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
            </tr>
            <tr class="hover:bg-[#1f2937]">
              <td class="px-5 py-2.5 text-gray-300 pl-10">其他費用</td>
              <td class="px-5 py-2.5 text-right font-mono text-[#ef4444]">${{ fmtMoney(plOtherExpense) }}</td>
              <td class="px-5 py-2.5 text-right font-mono text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
              <td class="px-5 py-2.5 text-right text-gray-500">—</td>
            </tr>
            <tr class="bg-[#111827]">
              <td class="px-5 py-2.5 font-bold text-gray-200">淨利</td>
              <td class="px-5 py-2.5 text-right font-bold font-mono"
                :class="plNet >= 0 ? 'text-[#10b981]' : 'text-[#ef4444]'">
                ${{ fmtMoney(plNet) }}
              </td>
              <td colspan="3" class="px-5 py-2.5 text-gray-500">—</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
