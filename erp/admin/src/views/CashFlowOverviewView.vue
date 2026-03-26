<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// 月份狀態
const today = new Date()
const currentYear = ref(today.getFullYear())
const currentMonth = ref(today.getMonth() + 1)

const monthStr = computed(() => {
  const m = String(currentMonth.value).padStart(2, '0')
  return `${currentYear.value}-${m}`
})
const monthLabel = computed(() => `${currentYear.value} 年 ${currentMonth.value} 月`)

function prevMonth() {
  if (currentMonth.value === 1) { currentMonth.value = 12; currentYear.value-- }
  else currentMonth.value--
  load()
}
function nextMonth() {
  if (currentMonth.value === 12) { currentMonth.value = 1; currentYear.value++ }
  else currentMonth.value++
  load()
}
function goToday() {
  currentYear.value = today.getFullYear()
  currentMonth.value = today.getMonth() + 1
  load()
}

const overview = ref(null)
const loading = ref(true)
const error = ref('')

function authHeaders() { return { Authorization: `Bearer ${auth.token}` } }
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function pctLabel(n) {
  if (n == null) return '—'
  const sign = n >= 0 ? '+' : ''
  return `${sign}${Number(n).toFixed(1)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${API_BASE}/cashflow/overview?month=${monthStr.value}`, { headers: authHeaders() })
    if (res.ok) {
      overview.value = await res.json()
    } else {
      // fallback to old endpoint
      const res2 = await fetch(`${API_BASE}/finance/overview`, { headers: authHeaders() })
      if (res2.ok) {
        const old = await res2.json()
        overview.value = {
          kpi: {
            total_income: old.month_income || 0,
            total_expense: old.month_expense || 0,
            net: (old.month_income || 0) - (old.month_expense || 0),
            income_vs_last_month_pct: null,
            expense_vs_last_month_pct: null,
            net_vs_last_month_pct: null,
            petty_cash_income: old.petty_cash_income || 0,
            petty_cash_withdrawal: old.petty_cash_withdrawal || 0,
          },
          trend: [],
          category_breakdown: [],
          summary: {
            settlement_count: old.settlement_count || 0,
            unsettled_count: old.unsettled_count || 0,
            accounts_payable: old.payable_amount || 0,
            petty_cash_balance: old.petty_cash_balance || 0,
          }
        }
      }
    }
  } catch (e) {
    error.value = '載入失敗'
  }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">

    <!-- 月份選擇器 -->
    <div class="flex items-center gap-3">
      <button @click="prevMonth" class="p-2 rounded-lg bg-[#1a202c] border border-[#2d3748] text-gray-400 hover:text-white hover:border-blue-400 transition-colors">←</button>
      <span class="text-lg font-bold text-gray-100 min-w-[140px] text-center">{{ monthLabel }}</span>
      <button @click="nextMonth" class="p-2 rounded-lg bg-[#1a202c] border border-[#2d3748] text-gray-400 hover:text-white hover:border-blue-400 transition-colors">→</button>
      <button @click="goToday" class="ml-2 px-3 py-1.5 text-xs rounded-lg bg-blue-500/20 text-blue-400 border border-blue-400/30 hover:bg-blue-500/30 transition-colors">本月</button>
    </div>

    <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
    <div v-else-if="error" class="p-4 text-center text-red-400">{{ error }}</div>

    <template v-else-if="overview">

      <!-- KPI 卡片列 -->
      <div class="grid grid-cols-3 gap-4">
        <!-- 收入 -->
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 mb-1">本月收入</p>
          <p class="text-2xl font-black text-emerald-400">NT$ {{ fmtMoney(overview.kpi?.total_income) }}</p>
          <p v-if="overview.kpi?.income_vs_last_month_pct != null" class="text-xs mt-1"
            :class="overview.kpi.income_vs_last_month_pct >= 0 ? 'text-emerald-500' : 'text-red-400'">
            較上月 {{ pctLabel(overview.kpi.income_vs_last_month_pct) }}
          </p>
        </div>
        <!-- 支出 -->
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 mb-1">本月支出</p>
          <p class="text-2xl font-black text-red-400">NT$ {{ fmtMoney(overview.kpi?.total_expense) }}</p>
          <p v-if="overview.kpi?.expense_vs_last_month_pct != null" class="text-xs mt-1"
            :class="overview.kpi.expense_vs_last_month_pct <= 0 ? 'text-emerald-500' : 'text-red-400'">
            較上月 {{ pctLabel(overview.kpi.expense_vs_last_month_pct) }}
          </p>
        </div>
        <!-- 淨額 -->
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
          <p class="text-xs text-gray-500 mb-1">當月淨額</p>
          <p class="text-2xl font-black" :class="(overview.kpi?.net || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ (overview.kpi?.net || 0) >= 0 ? '+' : '' }}NT$ {{ fmtMoney(overview.kpi?.net) }}
          </p>
          <p v-if="overview.kpi?.net_vs_last_month_pct != null" class="text-xs mt-1"
            :class="overview.kpi.net_vs_last_month_pct >= 0 ? 'text-emerald-500' : 'text-red-400'">
            較上月 {{ pctLabel(overview.kpi.net_vs_last_month_pct) }}
          </p>
        </div>
      </div>

      <!-- 收支趨勢圖（近 6 個月簡易長條） -->
      <div v-if="overview.trend?.length" class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">收支趨勢（近 6 個月）</p>
        <div class="flex items-end gap-3 h-32">
          <div v-for="t in overview.trend" :key="t.month" class="flex-1 flex flex-col items-center gap-1">
            <div class="w-full flex gap-0.5 items-end h-24">
              <div class="flex-1 bg-emerald-500/60 rounded-t"
                :style="{ height: Math.max(4, (t.income / Math.max(...overview.trend.map(x=>x.income||1))) * 96) + 'px' }"
                :title="`收入: NT$${fmtMoney(t.income)}`"></div>
              <div class="flex-1 bg-red-500/60 rounded-t"
                :style="{ height: Math.max(4, (t.expense / Math.max(...overview.trend.map(x=>x.expense||1))) * 96) + 'px' }"
                :title="`支出: NT$${fmtMoney(t.expense)}`"></div>
            </div>
            <span class="text-[10px] text-gray-500">{{ t.month?.slice(5) }}</span>
          </div>
        </div>
        <div class="flex gap-4 mt-3">
          <span class="text-xs flex items-center gap-1"><span class="w-3 h-3 rounded bg-emerald-500/60 inline-block"></span>收入</span>
          <span class="text-xs flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-500/60 inline-block"></span>支出</span>
        </div>
      </div>

      <!-- 科目支出分佈 -->
      <div v-if="overview.category_breakdown?.length" class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">本月科目支出分佈</p>
        <div class="space-y-2">
          <div v-for="cat in overview.category_breakdown" :key="cat.category" class="flex items-center gap-3">
            <span class="text-sm text-gray-300 w-24 truncate">{{ cat.category }}</span>
            <div class="flex-1 bg-[#0f1117] rounded-full h-2">
              <div class="bg-blue-400 h-2 rounded-full" :style="{ width: (cat.pct || 0) + '%' }"></div>
            </div>
            <span class="text-xs text-gray-400 w-12 text-right">{{ cat.pct?.toFixed(1) }}%</span>
            <span class="text-xs text-gray-400 w-20 text-right font-mono">NT$ {{ fmtMoney(cat.amount) }}</span>
          </div>
        </div>
      </div>

      <!-- 本月金流摘要 -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5">
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">本月金流摘要</p>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-400">日結次數</span>
            <span class="text-gray-200 font-bold">{{ overview.summary?.settlement_count || 0 }} 次</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">未日結紀錄</span>
            <span class="font-bold" :class="(overview.summary?.unsettled_count || 0) > 0 ? 'text-amber-400' : 'text-gray-200'">
              {{ overview.summary?.unsettled_count || 0 }} 筆
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">應付帳款</span>
            <span class="text-gray-200 font-mono">NT$ {{ fmtMoney(overview.summary?.accounts_payable) }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">零用金餘額</span>
            <span class="text-blue-400 font-mono font-bold">NT$ {{ fmtMoney(overview.summary?.petty_cash_balance) }}</span>
          </div>
        </div>
        <!-- 帳戶間轉移（不計入業務損益） -->
        <div v-if="overview.kpi?.petty_cash_income || overview.kpi?.petty_cash_withdrawal"
          class="mt-3 pt-3 border-t border-[#2d3748] space-y-2 text-sm">
          <p class="text-xs text-gray-600 uppercase tracking-wider">帳戶間轉移（不計入業務損益）</p>
          <div v-if="overview.kpi?.petty_cash_income" class="flex justify-between text-gray-500">
            <span>零用金收入（補充）</span>
            <span class="font-mono">NT$ {{ fmtMoney(overview.kpi.petty_cash_income) }}</span>
          </div>
          <div v-if="overview.kpi?.petty_cash_withdrawal" class="flex justify-between text-gray-500">
            <span>零用金提領</span>
            <span class="font-mono">NT$ {{ fmtMoney(overview.kpi.petty_cash_withdrawal) }}</span>
          </div>
        </div>
      </div>

    </template>
  </div>
</template>
