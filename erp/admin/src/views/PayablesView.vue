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
const selectedIds = ref(new Set())
const batchPaying = ref(false)

// B-10: 月份篩選
const now = new Date()
const filterMonth = ref(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
const monthOptions = computed(() => {
  const opts = []
  for (let i = 0; i < 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    opts.push({ val, label: `${d.getFullYear()}年 ${d.getMonth() + 1}月` })
  }
  return opts
})

// B-11: 付款 modal
const payModal = ref(null)  // { p } or null
const payMethodInput = ref('轉帳')
const payMethods = ['轉帳', '現金', '支票', '其他']

// inline edit: 金額 & 付款日
const editingId = ref(null)   // payable id 正在編輯
const editAmount = ref('')
const editPaymentDate = ref('')

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
  if (p.is_paid) return { label: `✓ ${p.payment_method || '已匯款'}`, cls: 'bg-emerald-700 text-white' }
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
    fetch(`${API_BASE}/finance/accounts-payable?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (payRes.ok) payables.value = await payRes.json()
  if (vendorRes.ok) vendors.value = await vendorRes.json()
  loading.value = false
}
onMounted(load)

const filtered = computed(() => {
  let list = payables.value
  // B-10: 月份篩選（以 due_date 月份為基準，未設定到期日的也顯示）
  if (filterMonth.value) {
    list = list.filter(p => {
      if (!p.due_date) return true  // 未設到期日也顯示
      const d = new Date(p.due_date)
      const m = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      return m === filterMonth.value
    })
  }
  if (payVendor.value) list = list.filter(p => String(p.vendor_id) === payVendor.value)
  if (payStatus.value === 'paid') list = list.filter(p => p.is_paid)
  if (payStatus.value === 'unpaid') list = list.filter(p => !p.is_paid)
  return list
})

const pendingTotal = computed(() =>
  filtered.value.filter(p => !p.is_paid).reduce((s, p) => s + parseFloat(p.amount || 0), 0)
)
const unpaidVendors = computed(() => {
  const ids = [...new Set(payables.value.filter(p => !p.is_paid && p.vendor_id).map(p => p.vendor_id))]
  return vendors.value.filter(v => ids.includes(v.id))
})

// B-11: 開啟付款 modal
function openPayModal(p) {
  payMethodInput.value = '轉帳'
  payModal.value = { p }
}

async function confirmPay() {
  const p = payModal.value.p
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}/pay`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ payment_method: payMethodInput.value })
  })
  if (res.ok) { showToast('✓ 已標記付款'); payModal.value = null; await load() }
}

// B-09: 返回未付款
async function markUnpaid(p) {
  if (!confirm(`將「${p.vendor_name}」還原為未付款？`)) return
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}/unpay`, {
    method: 'PUT', headers: authHeaders()
  })
  if (res.ok) { showToast('已還原為未付款'); await load() }
}

// inline edit：開啟
function startEdit(p) {
  editingId.value = p.id
  editAmount.value = String(p.amount || '')
  editPaymentDate.value = p.payment_date
    ? new Date(p.payment_date).toISOString().split('T')[0]
    : (p.paid_at ? new Date(p.paid_at).toISOString().split('T')[0] : '')
}

async function saveEdit(p) {
  const body = {}
  const amt = parseFloat(editAmount.value)
  if (!isNaN(amt) && amt !== p.amount) body.amount = amt
  body.payment_date = editPaymentDate.value || null
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}`, {
    method: 'PATCH', headers: authHeaders(), body: JSON.stringify(body)
  })
  if (res.ok) { editingId.value = null; showToast('已更新'); await load() }
}

async function deletePayable(p) {
  if (!confirm(`確認刪除「${p.vendor_name}」的帳款 NT$${fmtMoney(p.amount)}？`)) return
  const res = await fetch(`${API_BASE}/finance/accounts-payable/${p.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) { showToast('已刪除'); await load() }
}

function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function toggleSelectAll() {
  const unpaid = filtered.value.filter(p => !p.is_paid)
  if (selectedIds.value.size === unpaid.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(unpaid.map(p => p.id))
  }
}

const selectedTotal = computed(() => {
  return payables.value
    .filter(p => selectedIds.value.has(p.id))
    .reduce((s, p) => s + parseFloat(p.amount || 0), 0)
})

const allUnpaidSelected = computed(() => {
  const unpaid = filtered.value.filter(p => !p.is_paid)
  return unpaid.length > 0 && unpaid.every(p => selectedIds.value.has(p.id))
})

// B-10+B-11: 批次付款 modal
const batchPayModal = ref(false)
const batchPayMethod = ref('轉帳')

function openBatchPayModal() {
  if (!selectedIds.value.size) return
  batchPayMethod.value = '轉帳'
  batchPayModal.value = true
}

async function confirmBatchPay() {
  const ids = [...selectedIds.value]
  batchPaying.value = true
  batchPayModal.value = false
  try {
    await Promise.all(ids.map(id =>
      fetch(`${API_BASE}/finance/accounts-payable/${id}/pay`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ payment_method: batchPayMethod.value })
      })
    ))
    selectedIds.value = new Set()
    showToast(`✓ 已結清 ${ids.length} 筆帳款`)
    await load()
  } catch {
    showToast('部分結清失敗，請重試')
  } finally {
    batchPaying.value = false
  }
}
</script>

<template>
  <div class="space-y-5">
    <!-- 篩選列 -->
    <div class="flex flex-wrap items-center gap-3">
      <!-- B-10: 月份篩選 -->
      <select v-model="filterMonth"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option v-for="m in monthOptions" :key="m.val" :value="m.val">{{ m.label }}</option>
      </select>
      <select v-model="payVendor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部廠商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <select v-model="payStatus"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部狀態</option>
        <option value="unpaid">待付款</option>
        <option value="paid">已付款</option>
      </select>
      <div v-if="pendingTotal > 0"
        class="ml-auto px-4 py-2 rounded-lg text-sm font-bold bg-purple-900/40 border border-purple-500/50 text-purple-300">
        ⚠ 待付合計 NT$ {{ fmtMoney(pendingTotal) }}
      </div>
    </div>

    <!-- 批次付款 toolbar -->
    <div v-if="selectedIds.size > 0"
      class="flex items-center gap-4 px-4 py-3 bg-emerald-900/30 border border-emerald-500/40 rounded-xl">
      <span class="text-sm font-bold text-emerald-300">已選 {{ selectedIds.size }} 筆 · NT$ {{ fmtMoney(selectedTotal) }}</span>
      <button @click="selectedIds = new Set()" class="text-xs text-gray-400 hover:text-gray-200">取消選取</button>
      <button @click="openBatchPayModal" :disabled="batchPaying"
        class="ml-auto bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50">
        {{ batchPaying ? '處理中…' : `✓ 批次結清 (${selectedIds.size})` }}
      </button>
    </div>

    <!-- 表格 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="py-10 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-3 py-3 text-center w-8">
              <input type="checkbox" :checked="allUnpaidSelected" @change="toggleSelectAll"
                class="w-3.5 h-3.5 accent-emerald-500 cursor-pointer" />
            </th>
            <th class="px-5 py-3 text-left">廠商</th>
            <th class="px-5 py-3 text-left">建立日</th>
            <th class="px-5 py-3 text-left">付款條件</th>
            <th class="px-5 py-3 text-right">應付金額</th>
            <th class="px-5 py-3 text-left">到期日</th>
            <th class="px-5 py-3 text-left">付款日</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="p in filtered" :key="p.id" class="hover:bg-[#1f2937]"
            :class="selectedIds.has(p.id) ? 'bg-emerald-900/20' : ''">
            <td class="px-3 py-3 text-center">
              <input v-if="!p.is_paid" type="checkbox" :checked="selectedIds.has(p.id)" @change="toggleSelect(p.id)"
                class="w-3.5 h-3.5 accent-emerald-500 cursor-pointer" />
            </td>
            <td class="px-5 py-3 font-semibold text-gray-200">{{ p.vendor_name || '—' }}</td>
            <td class="px-5 py-3 text-gray-400 text-xs">{{ fmtDate(p.created_at) }}</td>
            <td class="px-5 py-3 text-gray-400 text-xs">{{ p.payment_terms || '—' }}</td>
            <!-- 金額（可 inline edit） -->
            <td class="px-5 py-3 text-right font-mono">
              <template v-if="editingId === p.id">
                <input v-model="editAmount" type="number" min="0"
                  class="w-24 bg-[#0f1117] border border-amber-400 text-amber-300 rounded px-1 py-0.5 text-xs text-right focus:outline-none" />
              </template>
              <span v-else :class="p.is_paid ? 'text-gray-500' : 'text-amber-400'">
                NT$ {{ fmtMoney(p.amount) }}
              </span>
            </td>
            <!-- 到期日（唯讀，自動計算）-->
            <td class="px-5 py-3 text-xs text-gray-400">
              {{ p.due_date ? new Date(p.due_date).toLocaleDateString('zh-TW') : '—' }}
              <span v-if="p.payment_terms" class="block text-[10px] text-gray-600">{{ p.payment_terms }}</span>
            </td>
            <!-- 付款日（可編輯）-->
            <td class="px-5 py-3 text-xs">
              <template v-if="editingId === p.id">
                <input v-model="editPaymentDate" type="date"
                  class="bg-[#0f1117] border border-blue-400 text-gray-200 rounded px-1 py-0.5 text-xs focus:outline-none" />
              </template>
              <span v-else class="text-gray-400">
                {{ p.payment_date ? new Date(p.payment_date).toLocaleDateString('zh-TW') : (p.paid_at ? new Date(p.paid_at).toLocaleDateString('zh-TW') : '—') }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="payableStatusInfo(p).cls">
                {{ payableStatusInfo(p).label }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <!-- 編輯中：儲存/取消 -->
              <template v-if="editingId === p.id">
                <div class="flex gap-1 justify-center">
                  <button @click="saveEdit(p)" class="text-blue-400 hover:text-blue-300 font-bold text-xs">儲存</button>
                  <button @click="editingId = null" class="text-gray-500 hover:text-gray-300 text-xs">取消</button>
                </div>
              </template>
              <template v-else>
                <div class="flex flex-col items-center gap-1">
                  <div v-if="!p.is_paid" class="flex gap-1">
                    <button @click="openPayModal(p)"
                      class="bg-emerald-700 hover:bg-emerald-600 text-white text-xs font-bold px-2 py-1 rounded-lg transition-colors">
                      付款
                    </button>
                    <button @click="startEdit(p)"
                      class="bg-[#2d3748] hover:bg-[#374151] text-gray-300 text-xs font-bold px-2 py-1 rounded-lg transition-colors">
                      編輯
                    </button>
                    <button @click="deletePayable(p)"
                      class="text-red-500 hover:text-red-400 text-xs font-bold px-2 py-1 rounded-lg border border-red-800 hover:border-red-600 transition-colors">
                      刪
                    </button>
                  </div>
                  <div v-else class="flex flex-col items-center gap-1">
                    <div class="flex gap-1">
                      <button @click="startEdit(p)"
                        class="bg-[#2d3748] hover:bg-[#374151] text-gray-300 text-xs px-2 py-0.5 rounded transition-colors">
                        編輯日期
                      </button>
                      <button @click="deletePayable(p)"
                        class="text-red-500 hover:text-red-400 text-xs px-1 py-0.5 rounded transition-colors">
                        刪
                      </button>
                    </div>
                    <button @click="markUnpaid(p)"
                      class="text-red-500 hover:text-red-400 text-[10px] underline">
                      返回未付款
                    </button>
                  </div>
                </div>
              </template>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="9" class="px-5 py-10 text-center text-gray-600">無應付帳款</td>
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

    <!-- B-11: 付款 Modal -->
    <div v-if="payModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" @click.self="payModal = null">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl p-6 w-full max-w-sm mx-4 space-y-4">
        <h3 class="text-lg font-bold text-gray-100">確認付款</h3>
        <div class="bg-[#0f1117] rounded-lg p-4 text-sm space-y-1">
          <p class="text-gray-400">廠商：<span class="text-gray-200 font-semibold">{{ payModal.p.vendor_name }}</span></p>
          <p class="text-gray-400">金額：<span class="text-amber-400 font-bold font-mono">NT$ {{ fmtMoney(payModal.p.amount) }}</span></p>
          <p class="text-gray-400">到期日：<span class="text-gray-200">{{ payModal.p.due_date ? new Date(payModal.p.due_date).toLocaleDateString('zh-TW') : '未設定' }}</span></p>
        </div>
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-2">付款方式</label>
          <div class="flex gap-2 flex-wrap">
            <button v-for="m in payMethods" :key="m" @click="payMethodInput = m"
              class="px-3 py-1.5 rounded-lg text-sm font-bold transition-colors border"
              :class="payMethodInput === m
                ? 'bg-emerald-700 border-emerald-500 text-white'
                : 'bg-[#0f1117] border-[#2d3748] text-gray-400 hover:border-gray-500'">
              {{ m }}
            </button>
          </div>
        </div>
        <div class="flex gap-3 pt-2">
          <button @click="payModal = null"
            class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-400 font-bold py-2 rounded-xl text-sm hover:bg-[#1f2937]">
            取消
          </button>
          <button @click="confirmPay"
            class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2 rounded-xl text-sm">
            確認付款
          </button>
        </div>
      </div>
    </div>

    <!-- B-10+B-11: 批次付款 Modal -->
    <div v-if="batchPayModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" @click.self="batchPayModal = false">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl p-6 w-full max-w-sm mx-4 space-y-4">
        <h3 class="text-lg font-bold text-gray-100">批次結清</h3>
        <p class="text-gray-400 text-sm">共 <span class="text-white font-bold">{{ selectedIds.size }}</span> 筆，合計 <span class="text-amber-400 font-bold font-mono">NT$ {{ fmtMoney(selectedTotal) }}</span></p>
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-2">付款方式</label>
          <div class="flex gap-2 flex-wrap">
            <button v-for="m in payMethods" :key="m" @click="batchPayMethod = m"
              class="px-3 py-1.5 rounded-lg text-sm font-bold transition-colors border"
              :class="batchPayMethod === m
                ? 'bg-emerald-700 border-emerald-500 text-white'
                : 'bg-[#0f1117] border-[#2d3748] text-gray-400 hover:border-gray-500'">
              {{ m }}
            </button>
          </div>
        </div>
        <div class="flex gap-3 pt-2">
          <button @click="batchPayModal = false"
            class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-400 font-bold py-2 rounded-xl text-sm hover:bg-[#1f2937]">
            取消
          </button>
          <button @click="confirmBatchPay"
            class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-2 rounded-xl text-sm">
            確認結清
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">{{ toast }}</div>
  </div>
</template>
