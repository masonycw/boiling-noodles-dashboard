<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---- State ----
const tab = ref('petty')          // 'petty' | 'cashflow' | 'payable'
const pettyBalance = ref(0)
const pettyRecords = ref([])
const cashFlowRecords = ref([])
const payables = ref([])
const categories = ref([])
const isLoading = ref(false)

// ---- Add petty cash form ----
const showAddModal = ref(false)
const form = ref({ type: 'expense', amount: '', note: '' })
const formError = ref('')
const formSubmitting = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

// ---- Load data ----
async function loadAll() {
  isLoading.value = true
  try {
    const [balRes, pettRes, cfRes, payRes, catRes] = await Promise.all([
      fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/petty-cash?days_limit=30&limit=50`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/cash-flow?days_limit=30&limit=100`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/accounts-payable?is_paid=false&limit=100`, { headers: authHeaders() }),
      fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
    ])
    if (balRes.ok) pettyBalance.value = (await balRes.json()).balance
    if (pettRes.ok) pettyRecords.value = await pettRes.json()
    if (cfRes.ok) cashFlowRecords.value = await cfRes.json()
    if (payRes.ok) payables.value = await payRes.json()
    if (catRes.ok) categories.value = await catRes.json()
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAll)

// ---- Petty cash type options ----
const typeOptions = computed(() => {
  const opts = [
    { value: 'income', label: '收入', color: 'text-emerald-600' },
    { value: 'expense', label: '支出', color: 'text-slate-800' },
  ]
  if (auth.user?.petty_cash_permission) {
    opts.push({ value: 'withdrawal', label: '提領', color: 'text-rose-500' })
  }
  return opts
})

// ---- Submit petty cash ----
async function submitForm() {
  formError.value = ''
  const amount = parseFloat(form.value.amount)
  if (!amount || amount <= 0) { formError.value = '請輸入金額'; return }
  formSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/finance/petty-cash`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ type: form.value.type, amount, note: form.value.note || null })
    })
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '儲存失敗')
    }
    showAddModal.value = false
    form.value = { type: 'expense', amount: '', note: '' }
    await loadAll()
  } catch (e) {
    formError.value = e.message
  } finally {
    formSubmitting.value = false
  }
}

// ---- Mark payable paid ----
async function markPaid(p) {
  if (!confirm(`確認結清 ${p.vendor_name || '此帳款'} $${p.amount}？`)) return
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}/pay`, {
    method: 'PUT',
    headers: authHeaders()
  })
  if (res.ok) await loadAll()
}

// ---- Helpers ----
function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
}
function fmtMoney(n) {
  return Number(n).toLocaleString('zh-TW')
}

const tabDef = [
  { key: 'petty', label: '零用金' },
  { key: 'cashflow', label: '金流' },
  { key: 'payable', label: '應付帳款' },
]
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-24">

    <!-- Header -->
    <div class="bg-white border-b border-slate-100 sticky top-0 z-10">
      <div class="flex items-center justify-between px-4 pt-12 pb-3">
        <h1 class="text-xl font-extrabold text-slate-800">金流管理</h1>
        <button
          v-if="tab === 'petty'"
          @click="showAddModal = true"
          class="bg-orange-500 text-white px-4 py-2 rounded-xl text-sm font-bold shadow active:scale-95 transition-transform"
        >
          + 新增
        </button>
      </div>

      <!-- Tab bar -->
      <div class="flex border-t border-slate-100">
        <button
          v-for="t in tabDef" :key="t.key"
          @click="tab = t.key"
          class="flex-1 py-3 text-sm font-bold transition-all border-b-2"
          :class="tab === t.key ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'"
        >
          {{ t.label }}
          <span v-if="t.key === 'payable' && payables.length" class="ml-1 text-xs bg-rose-500 text-white rounded-full px-1.5">{{ payables.length }}</span>
        </button>
      </div>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>

    <!-- ======== Petty Cash Tab ======== -->
    <div v-else-if="tab === 'petty'">
      <!-- Balance card -->
      <div class="mx-4 mt-4 bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-5 text-white">
        <p class="text-xs text-slate-400 font-bold uppercase tracking-wider">零用金餘額</p>
        <p class="text-4xl font-extrabold mt-1">$&nbsp;{{ fmtMoney(pettyBalance) }}</p>
        <p class="text-xs text-slate-400 mt-2">近 30 天記錄</p>
      </div>

      <div class="mt-3 divide-y divide-slate-100">
        <div v-if="pettyRecords.length === 0" class="text-center py-12 text-slate-400">無紀錄</div>
        <div
          v-for="r in pettyRecords" :key="r.id"
          class="bg-white px-4 py-3 flex items-center gap-3"
        >
          <div
            class="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-sm font-bold"
            :class="r.type === 'income' ? 'bg-emerald-100 text-emerald-600' :
                    r.type === 'withdrawal' ? 'bg-rose-100 text-rose-500' :
                    'bg-blue-100 text-blue-600'"
          >
            {{ r.type === 'income' ? '收' : r.type === 'withdrawal' ? '提' : '支' }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-bold text-slate-800 truncate">{{ r.note || r.vendor_name || '零用金' }}</p>
            <p class="text-xs text-slate-400">{{ fmtDate(r.created_at) }}</p>
          </div>
          <p class="font-bold text-sm shrink-0"
            :class="r.type === 'income' ? 'text-emerald-600' : 'text-rose-500'">
            {{ r.type === 'income' ? '+' : '-' }} ${{ fmtMoney(r.amount) }}
          </p>
        </div>
      </div>
    </div>

    <!-- ======== Cash Flow Tab ======== -->
    <div v-else-if="tab === 'cashflow'">
      <div class="mt-3 divide-y divide-slate-100">
        <div v-if="cashFlowRecords.length === 0" class="text-center py-12 text-slate-400">無紀錄</div>
        <div
          v-for="r in cashFlowRecords" :key="r.id"
          class="bg-white px-4 py-3 flex items-center gap-3"
        >
          <div
            class="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-sm font-bold"
            :class="r.type === 'income' ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-600'"
          >
            {{ r.type === 'income' ? '收' : '支' }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-bold text-slate-800 truncate">
              {{ r.category_name || r.description || '未分類' }}
            </p>
            <p class="text-xs text-slate-400">{{ r.source }} · {{ fmtDate(r.created_at) }}</p>
          </div>
          <p class="font-bold text-sm shrink-0"
            :class="r.type === 'income' ? 'text-emerald-600' : 'text-rose-500'">
            {{ r.type === 'income' ? '+' : '-' }} ${{ fmtMoney(r.amount) }}
          </p>
        </div>
      </div>
    </div>

    <!-- ======== Accounts Payable Tab ======== -->
    <div v-else-if="tab === 'payable'">
      <div class="mt-3 divide-y divide-slate-100">
        <div v-if="payables.length === 0" class="text-center py-12 text-emerald-600 font-bold">
          🎉 無待付帳款
        </div>
        <div
          v-for="p in payables" :key="p.id"
          class="bg-white px-4 py-4 flex items-center gap-3"
        >
          <div class="flex-1 min-w-0">
            <p class="font-bold text-slate-800 text-sm">{{ p.vendor_name || '廠商' }}</p>
            <p class="text-xs text-slate-400 mt-0.5">
              到期：{{ p.due_date ? new Date(p.due_date).toLocaleDateString('zh-TW') : '未設定' }}
            </p>
          </div>
          <div class="text-right shrink-0">
            <p class="font-extrabold text-rose-500 text-lg">${{ fmtMoney(p.amount) }}</p>
            <button
              @click="markPaid(p)"
              class="mt-1 bg-slate-800 text-white text-xs font-bold px-3 py-1.5 rounded-xl active:scale-95 transition-transform"
            >
              結清
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ======== Add Petty Cash Modal ======== -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/50 z-50 flex items-end justify-center">
      <div class="bg-white w-full max-w-md rounded-t-3xl p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-extrabold text-slate-800">新增零用金紀錄</h3>
          <button @click="showAddModal = false; formError = ''" class="text-slate-400 font-bold text-lg">✕</button>
        </div>

        <div class="space-y-4">
          <!-- Type -->
          <div class="flex gap-2">
            <button
              v-for="opt in typeOptions" :key="opt.value"
              @click="form.type = opt.value"
              class="flex-1 py-2 rounded-xl text-sm font-bold border transition-all"
              :class="form.type === opt.value ? 'bg-orange-500 text-white border-orange-500' : 'bg-white border-slate-200 text-slate-500'"
            >
              {{ opt.label }}
            </button>
          </div>

          <!-- Amount -->
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-1">金額</label>
            <input
              v-model="form.amount"
              type="number" inputmode="decimal" min="0" placeholder="0"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-2xl font-extrabold text-center focus:outline-none focus:ring-2 focus:ring-orange-400"
            />
          </div>

          <!-- Note -->
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-1">備註（選填）</label>
            <input
              v-model="form.note"
              type="text" placeholder="說明用途…"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
            />
          </div>

          <div v-if="formError" class="text-rose-500 text-sm text-center">{{ formError }}</div>

          <button
            @click="submitForm"
            :disabled="formSubmitting"
            class="w-full bg-orange-500 text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40"
          >
            {{ formSubmitting ? '儲存中…' : '儲存紀錄' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>
