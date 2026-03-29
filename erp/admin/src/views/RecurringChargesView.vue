<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const formError = ref('')
const categories = ref([])
const payees = ref([])

const form = ref({ name: '', category: '', amount: '', day_of_month: '', vendor_id: null, note: '', is_active: true })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const [recRes, catRes, payeeRes] = await Promise.all([
    fetch(`${API_BASE}/finance/recurring?include_inactive=true`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors?vendor_type=payee`, { headers: authHeaders() }),
  ])
  if (recRes.ok) records.value = await recRes.json()
  if (catRes.ok) {
    const all = await catRes.json()
    categories.value = all.filter(c => c.type === 'expense' && c.is_active !== false).map(c => c.name)
  }
  if (payeeRes.ok) payees.value = await payeeRes.json()
  loading.value = false
}

onMounted(load)

function openAdd() {
  editTarget.value = null
  form.value = { name: '', category: categories.value[0] || '', amount: '', day_of_month: '', vendor_id: null, note: '', is_active: true }
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editTarget.value = r
  form.value = {
    name: r.name,
    category: r.category || categories.value[0] || '',
    amount: String(r.amount),
    day_of_month: String(r.day_of_month || ''),
    vendor_id: r.vendor_id || null,
    note: r.note || '',
    is_active: r.is_active,
  }
  formError.value = ''
  showModal.value = true
}

// 選擇費用對象時，若名稱尚未手動填寫，自動帶入費用對象名稱
watch(() => form.value.vendor_id, (newId) => {
  if (!newId) return
  const payee = payees.value.find(p => p.id === newId)
  if (payee && (!form.value.name || form.value.name === editTarget.value?.name)) {
    form.value.name = payee.name
  }
})

async function save() {
  if (!form.value.name.trim()) { formError.value = '請輸入名稱'; return }
  if (!form.value.amount || parseFloat(form.value.amount) <= 0) { formError.value = '請輸入金額'; return }
  saving.value = true
  formError.value = ''
  try {
    const payload = {
      name: form.value.name.trim(),
      category: form.value.category,
      amount: parseFloat(form.value.amount),
      type: 'expense',
      day_of_month: form.value.day_of_month ? parseInt(form.value.day_of_month) : null,
      vendor_id: form.value.vendor_id || null,
      note: form.value.note || null,
      is_active: form.value.is_active,
    }
    let res
    if (editTarget.value) {
      res = await fetch(`${API_BASE}/finance/recurring/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload)
      })
    } else {
      res = await fetch(`${API_BASE}/finance/recurring`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify(payload)
      })
    }
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    await load()
  } catch(e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteRecord(r) {
  if (!confirm(`確定要刪除「${r.name}」？此操作無法還原。`)) return
  const res = await fetch(`${API_BASE}/finance/recurring/${r.id}`, { method: 'DELETE', headers: authHeaders() })
  if (res.ok) await load()
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }

// B-12: 產生應付帳款
const generateModal = ref(null)  // { r }
const generateDueDate = ref('')
const generating = ref(false)
const toast = ref('')
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

function openGenerateModal(r) {
  const today = new Date()
  const d = r.day_of_month ? new Date(today.getFullYear(), today.getMonth(), r.day_of_month) : today
  generateDueDate.value = d.toISOString().split('T')[0]
  generateModal.value = { r }
}

async function confirmGenerate() {
  const r = generateModal.value.r
  generating.value = true
  try {
    const res = await fetch(`${API_BASE}/finance/recurring/${r.id}/generate-payable`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ due_date: generateDueDate.value || null })
    })
    if (res.ok) {
      showToast(`✓ 已產生「${r.name}」應付帳款`)
      generateModal.value = null
    } else {
      const d = await res.json()
      showToast(d.detail || '建立失敗')
    }
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-gray-400">重複預約費用管理</h3>
      <button @click="openAdd" class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400">
        ➕ 新增重複預約
      </button>
    </div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">費用對象 ／ 名稱</th>
            <th class="px-4 py-3 text-left">分類</th>
            <th class="px-4 py-3 text-right">金額</th>
            <th class="px-4 py-3 text-center">執行日</th>
            <th class="px-4 py-3 text-center">狀態</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in records" :key="r.id" class="hover:bg-[#1f2937] transition-colors" :class="r.is_active ? '' : 'opacity-50'">
            <td class="px-4 py-3 font-medium text-gray-200">{{ r.name }}</td>
            <td class="px-4 py-3 text-gray-400">{{ r.category || '—' }}</td>
            <td class="px-4 py-3 text-right font-mono text-gray-300">${{ fmtMoney(r.amount) }}</td>
            <td class="px-4 py-3 text-center text-gray-400">{{ r.day_of_month ? `每月 ${r.day_of_month} 號` : '—' }}</td>
            <td class="px-4 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="r.is_active ? 'bg-emerald-900/40 text-emerald-400' : 'bg-gray-700 text-gray-500'">
                {{ r.is_active ? '有效' : '已停用' }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-2 flex-wrap">
                <button v-if="r.is_active" @click="openGenerateModal(r)" class="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30" title="產生應付帳款">帳款</button>
                <button @click="openEdit(r)" class="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="deleteRecord(r)" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="records.length === 0">
            <td colspan="6" class="px-5 py-10 text-center text-gray-600">尚無重複預約費用</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- B-12: 產生應付帳款 Modal -->
    <div v-if="generateModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" @click.self="generateModal = null">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-sm mx-4 space-y-4">
        <h3 class="font-bold text-gray-200">產生應付帳款</h3>
        <div class="bg-[#0f1117] rounded-lg p-3 text-sm space-y-1">
          <p class="text-gray-400">項目：<span class="text-gray-200 font-semibold">{{ generateModal.r.name }}</span></p>
          <p class="text-gray-400">金額：<span class="text-amber-400 font-bold">NT$ {{ fmtMoney(generateModal.r.amount) }}</span></p>
        </div>
        <div>
          <label class="text-xs text-gray-500 mb-1 block">到期日</label>
          <input v-model="generateDueDate" type="date"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-emerald-400" />
        </div>
        <div class="flex gap-2">
          <button @click="generateModal = null" class="flex-1 py-2 rounded-lg text-sm text-gray-400 border border-[#2d3748] hover:bg-[#1f2937]">取消</button>
          <button @click="confirmGenerate" :disabled="generating"
            class="flex-1 py-2 rounded-lg font-bold text-sm bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-40">
            {{ generating ? '建立中…' : '確認產生' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 新增/編輯 Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-4">
          <h3 class="font-bold text-gray-200">{{ editTarget ? '編輯重複預約' : '新增重複預約' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div class="space-y-3">
          <!-- 費用對象（選後自動帶入名稱） -->
          <div v-if="payees.length > 0">
            <label class="text-xs text-gray-500 mb-1 block">費用對象</label>
            <select v-model="form.vendor_id" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
              <option :value="null">不選擇</option>
              <option v-for="p in payees" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
          </div>
          <!-- 名稱（自動帶入費用對象，可手動覆寫） -->
          <div>
            <label class="text-xs text-gray-500 mb-1 block">名稱</label>
            <input v-model="form.name" type="text" placeholder="選費用對象後自動帶入，或手動輸入" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500 mb-1 block">分類</label>
              <select v-model="form.category" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
                <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-gray-500 mb-1 block">金額</label>
              <input v-model="form.amount" type="number" min="0" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
            </div>
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">執行日（每月幾號，留空表示不固定）</label>
            <input v-model="form.day_of_month" type="number" min="1" max="31" placeholder="1-31" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">備注</label>
            <input v-model="form.note" type="text" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <!-- 停用勾選（僅編輯時顯示） -->
          <div v-if="editTarget" class="flex items-center gap-2 pt-1">
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="form.is_active" class="sr-only peer" />
              <div class="w-9 h-5 rounded-full peer bg-gray-700 peer-checked:bg-orange-500 transition-colors after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:w-4 after:h-4 after:transition-transform peer-checked:after:translate-x-4"></div>
            </label>
            <span class="text-sm" :class="form.is_active ? 'text-gray-300' : 'text-gray-500'">{{ form.is_active ? '有效（啟用中）' : '已停用' }}</span>
          </div>
          <p v-if="formError" class="text-red-400 text-xs">{{ formError }}</p>
          <div class="flex gap-2 pt-2">
            <button @click="save" :disabled="saving"
              class="flex-1 py-2 rounded-lg font-bold text-sm bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400 disabled:opacity-40">
              {{ saving ? '儲存中…' : (editTarget ? '更新' : '建立') }}
            </button>
            <button @click="showModal = false" class="flex-1 py-2 rounded-lg text-sm text-gray-400 border border-[#2d3748] hover:bg-[#1f2937]">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">{{ toast }}</div>
  </div>
</template>
