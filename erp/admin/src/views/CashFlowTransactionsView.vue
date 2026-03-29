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
const twoWeeksAgo = new Date(now); twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14)
const cfDateFrom = ref(twoWeeksAgo.toISOString().slice(0, 10))
const cfDateTo = ref(now.toISOString().slice(0, 10))

// 月份快選
function getMonthOptions() {
  const opts = []
  const d = new Date()
  for (let i = 0; i < 6; i++) {
    const y = d.getFullYear()
    const m = d.getMonth() + 1
    opts.push({
      label: `${y}/${String(m).padStart(2, '0')}`,
      from: `${y}-${String(m).padStart(2, '0')}-01`,
      to: new Date(y, m, 0).toISOString().slice(0, 10),
    })
    d.setMonth(d.getMonth() - 1)
  }
  return opts
}
const monthOptions = getMonthOptions()
function selectMonth(opt) {
  cfDateFrom.value = opt.from
  cfDateTo.value = opt.to
  load()
}
const cfType = ref('')
const cfCategory = ref('')
const cfSearch = ref('')  // 廠商/說明文字搜尋
const payees = ref([])   // 全部供應商（下拉篩選用）

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
  if (src === 'petty_cash') return { label: '💰 零用金', bg: 'bg-[#1a1a3e]', txt: 'text-violet-400' }
  if (src === 'accounts_payable') return { label: '📋 應付帳款', bg: 'bg-[#0f2a1a]', txt: 'text-emerald-400' }
  return { label: src || '—', bg: 'bg-[#1f2937]', txt: 'text-gray-400' }
}

function cfTypeLabel(r) {
  if (r.type === 'expense') return '支出'
  if (r.type === 'income') return '收入'
  if (r.type === 'withdrawal') return '提領'
  if (r.type === 'remittance') return '💸 已匯款'
  return r.type || '—'
}

// 展開應付帳款明細
const expandedCfId = ref(null)
function toggleCfExpand(r) {
  if (r.source !== 'accounts_payable' && r.source !== 'petty_cash') return
  expandedCfId.value = expandedCfId.value === r.id ? null : r.id
}

const showAddModal = ref(false)
const addForm = ref({ type: 'expense', category_id: '', amount: '', description: '', transaction_date: new Date().toISOString().slice(0, 10) })
const addSubmitting = ref(false)

const showEditModal = ref(false)
const editRecord = ref(null)
const editForm = ref({ type: '', category_id: '', amount: '', description: '', transaction_date: '' })
const editSubmitting = ref(false)

const categorySubtotals = computed(() => {
  const map = {}
  filtered.value.filter(r => r.type === 'expense').forEach(r => {
    const k = r.category_name || '⚠️ 未分類'
    if (!map[k]) map[k] = 0
    map[k] += parseFloat(r.amount || 0)
  })
  return Object.entries(map).sort((a, b) => b[1] - a[1])
})

async function submitAdd() {
  if (!addForm.value.amount) return
  addSubmitting.value = true
  await fetch(`${API_BASE}/finance/cash-flow`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({
      type: addForm.value.type,
      category_id: addForm.value.category_id ? parseInt(addForm.value.category_id) : null,
      amount: parseFloat(addForm.value.amount),
      description: addForm.value.description,
      transaction_date: addForm.value.transaction_date,
      source: 'manual'
    })
  })
  addSubmitting.value = false
  showAddModal.value = false
  addForm.value = { type: 'expense', category_id: '', amount: '', description: '', transaction_date: new Date().toISOString().slice(0, 10) }
  showToast('紀錄已新增')
  await load()
}

function openEdit(r) {
  editRecord.value = r
  editForm.value = {
    type: r.type,
    category_id: r.category_id || '',
    amount: r.amount,
    description: r.description || '',
    transaction_date: r.transaction_date ? r.transaction_date.slice(0, 10) : new Date().toISOString().slice(0, 10)
  }
  showEditModal.value = true
}

async function saveEdit() {
  editSubmitting.value = true
  await fetch(`${API_BASE}/finance/cash-flow/${editRecord.value.id}`, {
    method: 'PUT', headers: authHeaders(),
    body: JSON.stringify({
      type: editForm.value.type,
      category_id: editForm.value.category_id ? parseInt(editForm.value.category_id) : null,
      amount: parseFloat(editForm.value.amount),
      description: editForm.value.description,
      transaction_date: editForm.value.transaction_date
    })
  })
  editSubmitting.value = false
  showEditModal.value = false
  showToast('已更新')
  await load()
}

async function deleteRecord_fn(r) {
  if (!confirm(`確認刪除 NT$${r.amount} 的${r.type === 'income' ? '收入' : '支出'}紀錄？`)) return
  const res = await fetch(`${API_BASE}/finance/cash-flow/${r.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) { showToast('已刪除'); await load() }
}

async function load() {
  loading.value = true
  const params = new URLSearchParams({ limit: 500 })
  if (cfDateFrom.value) params.set('date_from', cfDateFrom.value)
  if (cfDateTo.value) params.set('date_to', cfDateTo.value)
  const [cfRes, catRes, vendorRes] = await Promise.all([
    fetch(`${API_BASE}/finance/cash-flow?${params}`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (cfRes.ok) records.value = await cfRes.json()
  if (catRes.ok) categories.value = await catRes.json()
  if (vendorRes.ok) payees.value = await vendorRes.json()
  loading.value = false
}
onMounted(load)

const filtered = computed(() => {
  let list = records.value
  if (cfDateFrom.value) list = list.filter(r => r.created_at >= cfDateFrom.value)
  if (cfDateTo.value) list = list.filter(r => r.created_at <= cfDateTo.value + 'T23:59:59')
  if (cfType.value) list = list.filter(r => r.type === cfType.value)
  if (cfCategory.value) list = list.filter(r => (r.category_name || '') === cfCategory.value)
  if (cfSearch.value) {
    const q = cfSearch.value.toLowerCase()
    list = list.filter(r =>
      (r.vendor_name || '').toLowerCase().includes(q) ||
      (r.description || '').toLowerCase().includes(q)
    )
  }
  return list
})

// CSV 下載
function downloadCSV() {
  const rows = [['日期', '類型', '科目', '廠商', '說明', '金額', '付款方式', '來源']]
  filtered.value.forEach(r => {
    rows.push([
      r.transaction_date ? r.transaction_date.slice(0, 10) : (r.created_at || '').slice(0, 10),
      r.type === 'income' ? '收入' : r.type === 'expense' ? '支出' : '提領',
      r.category_name || '',
      r.vendor_name || '',
      r.description || '',
      r.amount,
      r.payment_method || '',
      r.source || '',
    ])
  })
  const csv = rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n')
  const bom = '\uFEFF'
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `金流紀錄_${cfDateFrom.value}_${cfDateTo.value}.csv`
  a.click()
}

const totalIncome = computed(() => filtered.value.filter(r => r.type === 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0))
const totalExpense = computed(() => filtered.value.filter(r => r.type === 'expense' || r.type === 'remittance').reduce((s, r) => s + parseFloat(r.amount || 0), 0))

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
    <div class="space-y-2">
      <!-- 月份快選 -->
      <div class="flex flex-wrap gap-1.5">
        <button v-for="opt in monthOptions" :key="opt.from"
          @click="selectMonth(opt)"
          :class="cfDateFrom === opt.from && cfDateTo === opt.to
            ? 'bg-blue-600 text-white border-blue-500'
            : 'bg-[#1a202c] text-gray-400 border-[#2d3748] hover:border-blue-400 hover:text-gray-200'"
          class="border text-xs font-medium px-3 py-1 rounded-lg transition-colors">
          {{ opt.label }}
        </button>
      </div>
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
      <input v-model="cfSearch" type="text" placeholder="搜尋廠商 / 說明…"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400 w-48" />
      </div>
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
      <button @click="downloadCSV"
        class="px-4 py-2 bg-[#2d3748] hover:bg-[#374151] text-gray-300 text-sm font-bold rounded-xl transition-colors whitespace-nowrap">
        ↓ CSV
      </button>
      <button @click="showAddModal = true"
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl transition-colors whitespace-nowrap">
        + 新增紀錄
      </button>
    </div>

    <!-- 科目小計 -->
    <div v-if="categorySubtotals.length" class="flex flex-wrap gap-2">
      <span v-for="[cat, amt] in categorySubtotals" :key="cat"
        class="text-xs px-3 py-1 rounded-full border"
        :class="cat === '⚠️ 未分類' ? 'border-amber-500/50 text-amber-400 bg-amber-500/10' : 'border-[#2d3748] text-gray-400 bg-[#1a202c]'">
        {{ cat }}  −NT${{ fmtMoney(amt) }}
      </span>
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
            <th class="px-5 py-3 text-left">廠商</th>
            <th class="px-5 py-3 text-left">說明</th>
            <th class="px-5 py-3 text-right">金額</th>
            <th class="px-5 py-3 text-center">付款方式</th>
            <th class="px-5 py-3 text-center">來源</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <template v-for="r in filtered" :key="r.id">
            <tr class="hover:bg-[#1f2937]"
              :class="(r.source === 'accounts_payable' || r.source === 'petty_cash') ? 'cursor-pointer' : ''"
              @click="toggleCfExpand(r)">
              <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDate(r.transaction_date || r.created_at) }}</td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold"
                  :class="r.type === 'income' ? 'text-emerald-400' : r.type === 'remittance' ? 'text-violet-400' : 'text-blue-400'">
                  {{ cfTypeLabel(r) }}
                </span>
              </td>
              <td class="px-5 py-2.5 text-xs">
                <select v-if="!r.is_categorized"
                  @change="updateCategory(r, $event.target.value)"
                  @click.stop
                  class="bg-[#0f1117] border border-amber-500/50 text-amber-400 rounded px-2 py-1 text-xs focus:outline-none">
                  <option value="">-- 選擇科目 --</option>
                  <option v-for="c in categories.filter(c => c.type === r.type)" :key="c.id" :value="c.id">
                    {{ c.name }}
                  </option>
                </select>
                <span v-else class="text-gray-300">{{ r.category_name || '—' }}</span>
              </td>
              <td class="px-5 py-2.5 text-xs">
                <span v-if="r.vendor_name" class="text-gray-300">{{ r.vendor_name }}</span>
                <span v-else class="text-gray-600">—</span>
              </td>
              <td class="px-5 py-2.5 text-gray-400 text-xs">
                {{ r.description || '—' }}
                <span v-if="r.source === 'accounts_payable' && r.ref_payable_ids?.length"
                  class="ml-1 text-[10px] text-emerald-600">▼ 展開明細</span>
              </td>
              <td class="px-5 py-2.5 text-right font-mono"
                :class="r.type === 'income' ? 'text-emerald-400' : r.type === 'remittance' ? 'text-violet-400' : 'text-red-400'">
                {{ r.type === 'income' ? '+' : '-' }}NT$ {{ fmtMoney(r.amount) }}
              </td>
              <td class="px-5 py-2.5 text-center">
                <span v-if="r.payment_method" class="text-xs px-2 py-0.5 rounded bg-[#1f2937] text-gray-300 border border-[#2d3748]">
                  {{ r.payment_method }}
                </span>
                <span v-else class="text-gray-600 text-xs">—</span>
              </td>
              <td class="px-5 py-2.5 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded" :class="[cfSourceInfo(r).bg, cfSourceInfo(r).txt]">
                  {{ cfSourceInfo(r).label }}
                </span>
              </td>
              <td class="px-5 py-2.5 text-center" @click.stop>
                <button @click="openEdit(r)" class="text-xs px-2 py-1 rounded bg-[#2d3748] text-blue-400 hover:bg-[#3d4f63] mr-1">編輯</button>
                <button @click="deleteRecord_fn(r)" class="text-xs px-2 py-1 rounded bg-[#2d3748] text-red-400 hover:bg-red-900/30">刪除</button>
              </td>
            </tr>
            <!-- 展開：應付帳款明細 -->
            <tr v-if="expandedCfId === r.id && r.source === 'accounts_payable'" class="bg-[#0a1a0f]">
              <td colspan="9" class="px-8 py-3">
                <p class="text-xs font-bold text-emerald-400 mb-2">📋 應付帳款明細</p>
                <div class="text-xs text-gray-300 space-y-1">
                  <p>{{ r.description }}</p>
                  <p v-if="r.payment_method" class="text-gray-500">付款方式：{{ r.payment_method }}</p>
                  <p class="text-gray-500">付款日期：{{ fmtDate(r.transaction_date || r.created_at) }}</p>
                  <p v-if="r.ref_payable_ids?.length" class="text-gray-500">
                    包含帳款 ID：{{ r.ref_payable_ids.join(', ') }}
                  </p>
                </div>
              </td>
            </tr>
            <!-- 展開：零用金結帳明細 -->
            <tr v-if="expandedCfId === r.id && r.source === 'petty_cash'" class="bg-[#0a0a1f]">
              <td colspan="9" class="px-8 py-3">
                <p class="text-xs font-bold text-violet-400 mb-2">💰 零用金支出明細</p>
                <div class="text-xs text-gray-300 space-y-1">
                  <p>{{ r.description }}</p>
                  <p class="text-gray-500">日期：{{ fmtDate(r.transaction_date || r.created_at) }}</p>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="filtered.length === 0">
            <td colspan="9" class="px-5 py-10 text-center text-gray-600">無金流紀錄</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Add Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6 space-y-4">
        <div class="flex justify-between items-center">
          <h3 class="text-lg font-bold text-gray-100">新增金流紀錄</h3>
          <button @click="showAddModal = false" class="text-gray-500 hover:text-white text-xl">✕</button>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">類型</label>
          <select v-model="addForm.type" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="expense">支出</option>
            <option value="income">收入</option>
          </select>
        </div>
        <div v-if="addForm.type === 'expense'">
          <label class="text-xs text-gray-500 block mb-1">科目（必選）</label>
          <select v-model="addForm.category_id" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">-- 選擇科目 --</option>
            <option v-for="c in categories.filter(c => c.type === 'expense')" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">金額</label>
          <input v-model="addForm.amount" type="number" min="0" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="0" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">說明</label>
          <input v-model="addForm.description" type="text" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="說明用途…" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">日期</label>
          <input v-model="addForm.transaction_date" type="date" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div class="flex gap-3 pt-2">
          <button @click="showAddModal = false" class="flex-1 py-2 bg-[#2d3748] text-gray-300 rounded-lg text-sm font-bold hover:bg-[#374151]">取消</button>
          <button @click="submitAdd" :disabled="addSubmitting" class="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-bold disabled:opacity-50">
            {{ addSubmitting ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Edit Modal -->
    <div v-if="showEditModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6 space-y-4">
        <div class="flex justify-between items-center">
          <h3 class="text-lg font-bold text-gray-100">編輯金流紀錄</h3>
          <button @click="showEditModal = false" class="text-gray-500 hover:text-white text-xl">✕</button>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">類型</label>
          <select v-model="editForm.type" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="expense">支出</option>
            <option value="income">收入</option>
            <option value="withdrawal">提領</option>
          </select>
        </div>
        <div v-if="editForm.type === 'expense'">
          <label class="text-xs text-gray-500 block mb-1">科目</label>
          <select v-model="editForm.category_id" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">-- 選擇科目 --</option>
            <option v-for="c in categories.filter(c => c.type === 'expense')" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">金額</label>
          <input v-model="editForm.amount" type="number" min="0" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="0" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">說明</label>
          <input v-model="editForm.description" type="text" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" placeholder="說明用途…" />
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">日期</label>
          <input v-model="editForm.transaction_date" type="date" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div class="flex gap-3 pt-2">
          <button @click="showEditModal = false" class="flex-1 py-2 bg-[#2d3748] text-gray-300 rounded-lg text-sm font-bold hover:bg-[#374151]">取消</button>
          <button @click="saveEdit" :disabled="editSubmitting" class="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-bold disabled:opacity-50">
            {{ editSubmitting ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">
      {{ toast }}
    </div>
  </div>
</template>
