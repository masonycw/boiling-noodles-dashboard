<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const categories = ref([])
const loading = ref(true)
const toast = ref('')

const now = new Date()
const currentYM = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const cfDateFrom = ref(`${currentYM}-01`)
const cfDateTo = ref(now.toISOString().slice(0, 10))
const cfType = ref('')
const cfCategory = ref('')

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' })
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

function cfSourceInfo(r) {
  const src = r.source || ''
  if (src === 'system') return { label: '🔗 營運系統', bg: 'bg-[#1e3a5f]', txt: 'text-[#63b3ed]' }
  if (src === 'manual') return { label: '✏ 手動', bg: 'bg-[#2d1a00]', txt: 'text-[#fb923c]' }
  if (src === 'auto') return { label: '⚙ 自動', bg: 'bg-[#1a2e1a]', txt: 'text-[#4ade80]' }
  return { label: src || '—', bg: 'bg-[#1f2937]', txt: 'text-gray-400' }
}

async function load() {
  loading.value = true
  const [cfRes, catRes] = await Promise.all([
    fetch(`${API_BASE}/finance/cash-flow?days_limit=90&limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
  ])
  if (cfRes.ok) records.value = await cfRes.json()
  if (catRes.ok) categories.value = await catRes.json()
  loading.value = false
}
onMounted(load)

const filtered = computed(() => {
  let list = records.value
  if (cfDateFrom.value) list = list.filter(r => r.created_at >= cfDateFrom.value)
  if (cfDateTo.value) list = list.filter(r => r.created_at <= cfDateTo.value + 'T23:59:59')
  if (cfType.value) list = list.filter(r => r.type === cfType.value)
  if (cfCategory.value) list = list.filter(r => (r.category_name || '') === cfCategory.value)
  return list
})

const totalIncome = computed(() => filtered.value.filter(r => r.type === 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0))
const totalExpense = computed(() => filtered.value.filter(r => r.type === 'expense').reduce((s, r) => s + parseFloat(r.amount || 0), 0))

async function updateCategory(record, catId) {
  await fetch(`${API_BASE}/finance/cash-flow/${record.id}/category`, {
    method: 'PUT', headers: authHeaders(),
    body: JSON.stringify({ category_id: parseInt(catId) })
  })
  showToast('科目已更新')
  await load()
}
</script>

<template>
  <div class="space-y-4">
    <!-- 篩選列 -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex items-center gap-2 text-sm text-gray-400">
        <span>從</span>
        <input v-model="cfDateFrom" type="date"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
        <span>至</span>
        <input v-model="cfDateTo" type="date"
          class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
      </div>
      <select v-model="cfType"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部類型</option>
        <option value="income">收入</option>
        <option value="expense">支出</option>
      </select>
      <select v-model="cfCategory"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部科目</option>
        <option v-for="c in categories" :key="c.id" :value="c.name">{{ c.name }}</option>
      </select>
    </div>

    <!-- 小計 -->
    <div class="flex gap-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl px-5 py-3 flex-1">
        <p class="text-xs text-gray-500">收入合計</p>
        <p class="text-xl font-bold text-emerald-400">NT$ {{ fmtMoney(totalIncome) }}</p>
      </div>
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl px-5 py-3 flex-1">
        <p class="text-xs text-gray-500">支出合計</p>
        <p class="text-xl font-bold text-red-400">NT$ {{ fmtMoney(totalExpense) }}</p>
      </div>
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl px-5 py-3 flex-1">
        <p class="text-xs text-gray-500">淨額</p>
        <p class="text-xl font-bold" :class="totalIncome - totalExpense >= 0 ? 'text-emerald-400' : 'text-red-400'">
          NT$ {{ fmtMoney(totalIncome - totalExpense) }}
        </p>
      </div>
    </div>

    <!-- 表格 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="py-10 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-3 text-left">日期</th>
            <th class="px-5 py-3 text-center">類型</th>
            <th class="px-5 py-3 text-left">科目</th>
            <th class="px-5 py-3 text-left">說明</th>
            <th class="px-5 py-3 text-right">金額</th>
            <th class="px-5 py-3 text-center">來源</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in filtered" :key="r.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDate(r.created_at) }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold" :class="r.type === 'income' ? 'text-emerald-400' : 'text-blue-400'">
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
              :class="r.type === 'income' ? 'text-emerald-400' : 'text-red-400'">
              {{ r.type === 'income' ? '+' : '-' }}NT$ {{ fmtMoney(r.amount) }}
            </td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded" :class="[cfSourceInfo(r).bg, cfSourceInfo(r).txt]">
                {{ cfSourceInfo(r).label }}
              </span>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="6" class="px-5 py-10 text-center text-gray-600">無金流紀錄</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">
      {{ toast }}
    </div>
  </div>
</template>
