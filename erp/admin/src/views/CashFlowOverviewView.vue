<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const overview = ref(null)
const loading = ref(true)

function authHeaders() { return { Authorization: `Bearer ${auth.token}` } }

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/finance/overview`, { headers: authHeaders() })
  if (res.ok) overview.value = await res.json()
  loading.value = false
}

onMounted(load)

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
</script>

<template>
  <div class="space-y-5">
    <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
    <template v-else-if="overview">

      <!-- KPI Cards -->
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-xs text-[#9ca3af] uppercase tracking-wider mb-1">本月收入</p>
          <p class="text-3xl font-black text-emerald-400">${{ fmtMoney(overview.month_income) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-xs text-[#9ca3af] uppercase tracking-wider mb-1">本月支出</p>
          <p class="text-3xl font-black text-red-400">${{ fmtMoney(overview.month_expense) }}</p>
        </div>
        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
          <p class="text-xs text-[#9ca3af] uppercase tracking-wider mb-1">預估淨額</p>
          <p class="text-3xl font-black" :class="overview.projected_net >= 0 ? 'text-emerald-400' : 'text-red-400'">
            {{ overview.projected_net >= 0 ? '+' : '' }}${{ fmtMoney(overview.projected_net) }}
          </p>
        </div>
      </div>

      <!-- Petty Cash Card -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 flex items-center gap-4">
        <span class="text-2xl">💰</span>
        <div>
          <p class="text-xs text-[#9ca3af] uppercase">零用金餘額</p>
          <p class="text-2xl font-black text-[#63b3ed]">${{ fmtMoney(overview.petty_cash_balance) }}</p>
        </div>
      </div>

      <!-- Projected Expenses Table -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <div class="px-4 py-3 border-b border-[#2d3748]">
          <p class="text-xs font-bold text-[#9ca3af] uppercase tracking-wider">本月預估費用</p>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-4 py-3 text-left">項目</th>
              <th class="px-4 py-3 text-right">次數</th>
              <th class="px-4 py-3 text-right">金額</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr class="hover:bg-[#1f2937]">
              <td class="px-4 py-3 text-gray-300">重複預約費用</td>
              <td class="px-4 py-3 text-right text-gray-400">{{ overview.recurring_expense_count }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-300">${{ fmtMoney(overview.recurring_expense_total) }}</td>
            </tr>
            <tr class="hover:bg-[#1f2937]">
              <td class="px-4 py-3 text-gray-300">匯款應付帳款</td>
              <td class="px-4 py-3 text-right text-gray-400">{{ overview.payable_count }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-300">${{ fmtMoney(overview.payable_amount) }}</td>
            </tr>
            <tr class="hover:bg-[#1f2937]">
              <td class="px-4 py-3 text-gray-300">本月實際支出</td>
              <td class="px-4 py-3 text-right text-gray-400">—</td>
              <td class="px-4 py-3 text-right font-mono text-red-400">${{ fmtMoney(overview.month_expense) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
