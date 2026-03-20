<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const pettyBalance = ref(0)
const pettyRecords = ref([])
const loading = ref(true)
const pettyType = ref('')
const now = new Date()

// ── Edit Petty Cash ──
const showEditModal = ref(false)
const editRecord = ref(null)
const editForm = ref({ type: '', amount: '', note: '', recorded_at: '' })
const editSubmitting = ref(false)
const editError = ref('')

// ── Delete Petty Cash ──
const showDeleteModal = ref(false)
const deleteRecord = ref(null)
const deleteSubmitting = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtDateTime(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function load() {
  loading.value = true
  const [balRes, pettyRes] = await Promise.all([
    fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/petty-cash?days_limit=60&limit=300`, { headers: authHeaders() }),
  ])
  if (balRes.ok) pettyBalance.value = (await balRes.json()).balance
  if (pettyRes.ok) pettyRecords.value = await pettyRes.json()
  loading.value = false
}
onMounted(load)

const filteredPetty = computed(() => {
  let list = pettyRecords.value
  if (pettyType.value) list = list.filter(r => r.type === pettyType.value)
  return list
})

const monthIncome = computed(() => pettyRecords.value.filter(r => r.type === 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0))
const monthExpense = computed(() => pettyRecords.value.filter(r => r.type === 'expense').reduce((s, r) => s + parseFloat(r.amount || 0), 0))

const pettyWithBalance = computed(() => {
  let running = parseFloat(pettyBalance.value) || 0
  return filteredPetty.value.map(r => {
    const row = { ...r, running_balance: running }
    if (r.type === 'income') running -= parseFloat(r.amount || 0)
    else running += parseFloat(r.amount || 0)
    return row
  })
})

function openEditPetty(r) {
  editRecord.value = r
  editError.value = ''
  const dt = r.created_at ? new Date(r.created_at) : new Date()
  editForm.value = {
    type: r.type,
    amount: parseFloat(r.amount) || 0,
    note: r.note || '',
    recorded_at: dt.toISOString().slice(0, 16),
  }
  showEditModal.value = true
}

async function saveEditPetty() {
  editSubmitting.value = true
  editError.value = ''
  try {
    const res = await fetch(`${API_BASE}/finance/petty-cash/${editRecord.value.id}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({
        type: editForm.value.type,
        amount: parseFloat(editForm.value.amount),
        note: editForm.value.note,
        recorded_at: editForm.value.recorded_at,
      })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showEditModal.value = false
    await load()
  } catch (e) {
    editError.value = e.message
  } finally {
    editSubmitting.value = false
  }
}

function openDeletePetty(r) {
  deleteRecord.value = r
  deleteSubmitting.value = false
  showDeleteModal.value = true
}

async function confirmDeletePetty() {
  deleteSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/finance/petty-cash/${deleteRecord.value.id}`, {
      method: 'DELETE', headers: authHeaders()
    })
    if (!res.ok) throw new Error('刪除失敗')
    showDeleteModal.value = false
    await load()
  } catch (e) { alert(e.message) }
  finally { deleteSubmitting.value = false }
}
</script>

<template>
  <div class="space-y-5">
    <!-- KPI 卡片 -->
    <div class="grid grid-cols-3 gap-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-emerald-500">
        <p class="text-gray-500 text-xs uppercase tracking-wider">目前餘額</p>
        <p class="text-2xl font-bold text-emerald-400 mt-1">NT$ {{ fmtMoney(pettyBalance) }}</p>
      </div>
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-blue-400">
        <p class="text-gray-500 text-xs uppercase tracking-wider">累積收入</p>
        <p class="text-2xl font-bold text-blue-400 mt-1">+NT$ {{ fmtMoney(monthIncome) }}</p>
      </div>
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-5 border-l-4 border-l-red-400">
        <p class="text-gray-500 text-xs uppercase tracking-wider">累積支出</p>
        <p class="text-2xl font-bold text-red-400 mt-1">-NT$ {{ fmtMoney(monthExpense) }}</p>
      </div>
    </div>

    <!-- 篩選 -->
    <div class="flex items-center gap-3">
      <select v-model="pettyType"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
        <option value="">全部類型</option>
        <option value="income">收入</option>
        <option value="expense">支出</option>
        <option value="withdrawal">提領</option>
      </select>
    </div>

    <!-- 表格 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="py-10 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-3 text-left">日期時間</th>
            <th class="px-5 py-3 text-center">類型</th>
            <th class="px-5 py-3 text-left">說明</th>
            <th class="px-5 py-3 text-right">金額</th>
            <th class="px-5 py-3 text-right">餘額</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in pettyWithBalance" :key="r.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDateTime(r.created_at) }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded"
                :class="r.type === 'income' ? 'bg-blue-900/50 text-blue-400'
                  : r.type === 'withdrawal' ? 'bg-amber-900/30 text-amber-400'
                  : 'bg-emerald-900/30 text-emerald-400'">
                {{ r.type === 'income' ? '收入' : r.type === 'withdrawal' ? '提領' : '支出' }}
              </span>
            </td>
            <td class="px-5 py-2.5 text-gray-400 text-xs">{{ r.note || r.vendor_name || '—' }}</td>
            <td class="px-5 py-2.5 text-right font-mono"
              :class="r.type === 'income' ? 'text-blue-400' : 'text-red-400'">
              {{ r.type === 'income' ? '+' : '-' }}NT$ {{ fmtMoney(r.amount) }}
            </td>
            <td class="px-5 py-2.5 text-right font-mono text-gray-200">NT$ {{ fmtMoney(r.running_balance) }}</td>
            <td class="px-5 py-2.5 text-center">
              <button @click="openEditPetty(r)"
                class="text-xs px-2 py-1 rounded bg-[#2d3748] text-[#63b3ed] hover:bg-[#3d4f63] mr-1">
                編輯
              </button>
              <button @click="openDeletePetty(r)"
                class="text-xs px-2 py-1 rounded bg-[#2d3748] text-red-400 hover:bg-red-900/30">
                刪除
              </button>
            </td>
          </tr>
          <tr v-if="pettyWithBalance.length === 0">
            <td colspan="6" class="px-5 py-10 text-center text-gray-600">無零用金紀錄</td>
          </tr>
        </tbody>
      </table>
    </div>
  <!-- Edit Petty Cash Modal -->
  <div v-if="showEditModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md">
      <div class="flex items-center justify-between px-6 py-4 border-b border-[#2d3748]">
        <h3 class="text-base font-bold text-gray-200">編輯零用金紀錄</h3>
        <button @click="showEditModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
      </div>
      <div class="px-6 py-5 space-y-4">
        <div>
          <label class="block text-xs text-gray-500 mb-1">類型</label>
          <select v-model="editForm.type"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="expense">支出</option>
            <option value="income">收入</option>
            <option value="withdrawal">提領</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">金額</label>
          <input v-model.number="editForm.amount" type="number" min="0"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">記錄時間</label>
          <input v-model="editForm.recorded_at" type="datetime-local"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">說明 / 備注</label>
          <input v-model="editForm.note" type="text" placeholder="說明…"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <p v-if="editError" class="text-red-400 text-sm text-center">{{ editError }}</p>
      </div>
      <div class="flex gap-3 px-6 pb-6">
        <button @click="showEditModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="saveEditPetty" :disabled="editSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#63b3ed] text-black hover:bg-blue-400 disabled:opacity-40">
          {{ editSubmitting ? '儲存中…' : '儲存修改' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Delete Petty Cash Dialog -->
  <div v-if="showDeleteModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
      <h3 class="text-base font-bold text-gray-200 mb-4">⚠️ 確認刪除零用金紀錄</h3>
      <div class="bg-[#0f1117] rounded-xl p-4 mb-4 space-y-1 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">類型</span>
          <span class="text-gray-300">{{ deleteRecord?.type === 'income' ? '收入' : deleteRecord?.type === 'withdrawal' ? '提領' : '支出' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">金額</span>
          <span class="text-gray-300">NT$ {{ fmtMoney(deleteRecord?.amount) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">說明</span>
          <span class="text-gray-300">{{ deleteRecord?.note || '—' }}</span>
        </div>
      </div>
      <p class="text-xs text-red-400 mb-4">刪除後無法復原</p>
      <div class="flex gap-3">
        <button @click="showDeleteModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="confirmDeletePetty" :disabled="deleteSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-40">
          {{ deleteSubmitting ? '刪除中…' : '確認刪除' }}
        </button>
      </div>
    </div>
  </div>

  </div>
</template>
