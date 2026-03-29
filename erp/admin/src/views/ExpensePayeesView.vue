<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const payees = ref([])
const categories = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const formError = ref('')
const toast = ref('')

function emptyForm() {
  return {
    name: '',
    default_category_id: null,
    payment_method: '轉帳',
    bank_name: '',
    bank_account: '',
    bank_account_holder: '',
    note: '',
    vendor_type: 'payee',
  }
}
const form = ref(emptyForm())

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }
function fmtCat(id) {
  const c = categories.value.find(c => c.id === id)
  return c ? c.name : '—'
}

async function load() {
  loading.value = true
  const [payRes, catRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/vendors?vendor_type=payee`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() }),
  ])
  if (payRes.ok) payees.value = await payRes.json()
  if (catRes.ok) {
    const all = await catRes.json()
    categories.value = all.filter(c => c.is_active !== false)
  }
  loading.value = false
}
onMounted(load)

function openAdd() {
  editTarget.value = null
  form.value = emptyForm()
  formError.value = ''
  showModal.value = true
}

function openEdit(p) {
  editTarget.value = p
  form.value = {
    name: p.name || '',
    default_category_id: p.default_category_id || null,
    payment_method: p.payment_method || '轉帳',
    bank_name: p.bank_name || '',
    bank_account: p.bank_account || '',
    bank_account_holder: p.bank_account_holder || '',
    note: p.note || '',
    vendor_type: 'payee',
  }
  formError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { formError.value = '請輸入名稱'; return }
  saving.value = true
  formError.value = ''
  try {
    const payload = { ...form.value, is_active: true }
    let res
    if (editTarget.value) {
      res = await fetch(`${API_BASE}/inventory/vendors/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload)
      })
    } else {
      res = await fetch(`${API_BASE}/inventory/vendors`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify(payload)
      })
    }
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    showToast(editTarget.value ? '✓ 已更新' : '✓ 已新增')
    await load()
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function remove(p) {
  if (!confirm(`刪除「${p.name}」費用對象？`)) return
  const res = await fetch(`${API_BASE}/inventory/vendors/${p.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) { showToast('已刪除'); await load() }
}
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-bold text-gray-300">費用對象管理</h3>
        <p class="text-xs text-gray-600 mt-0.5">記錄非叫貨支出對象（POS 費用、租金、訂閱服務等），可在金流記帳時選擇</p>
      </div>
      <button @click="openAdd"
        class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400">
        ➕ 新增費用對象
      </button>
    </div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">名稱</th>
            <th class="px-4 py-3 text-left">預設科目</th>
            <th class="px-4 py-3 text-left">付款方式</th>
            <th class="px-4 py-3 text-left">銀行資訊</th>
            <th class="px-4 py-3 text-left">備注</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="p in payees" :key="p.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-4 py-3 font-semibold text-gray-200">{{ p.name }}</td>
            <td class="px-4 py-3">
              <span v-if="p.default_category_id"
                class="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-300">
                {{ fmtCat(p.default_category_id) }}
              </span>
              <span v-else class="text-gray-600 text-xs">—</span>
            </td>
            <td class="px-4 py-3 text-gray-400 text-xs">{{ p.payment_method || '—' }}</td>
            <td class="px-4 py-3 text-gray-500 text-xs">
              <div v-if="p.bank_account">
                <p>{{ p.bank_name || '' }} {{ p.bank_account }}</p>
                <p v-if="p.bank_account_holder" class="text-gray-600">{{ p.bank_account_holder }}</p>
              </div>
              <span v-else>—</span>
            </td>
            <td class="px-4 py-3 text-gray-500 text-xs">{{ p.note || '—' }}</td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-2">
                <button @click="openEdit(p)" class="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="remove(p)" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="payees.length === 0">
            <td colspan="6" class="px-5 py-12 text-center text-gray-600">
              <p class="text-2xl mb-2">🏷️</p>
              <p>尚無費用對象</p>
              <p class="text-xs mt-1">點擊右上角「新增費用對象」開始建立</p>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" @click.self="showModal = false">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-md mx-4">
        <div class="flex justify-between items-center mb-5">
          <h3 class="font-bold text-gray-200">{{ editTarget ? '編輯費用對象' : '新增費用對象' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div class="space-y-4">
          <div>
            <label class="text-xs text-gray-500 mb-1 block">名稱 <span class="text-red-400">*</span></label>
            <input v-model="form.name" type="text" placeholder="例：iCHEF、電費、房租"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">預設科目（選金流科目，記帳時自動帶入）</label>
            <select v-model="form.default_category_id"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
              <option :value="null">不設定</option>
              <optgroup label="支出">
                <option v-for="c in categories.filter(c => c.type === 'expense')" :key="c.id" :value="c.id">{{ c.name }}</option>
              </optgroup>
              <optgroup label="收入">
                <option v-for="c in categories.filter(c => c.type === 'income')" :key="c.id" :value="c.id">{{ c.name }}</option>
              </optgroup>
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">付款方式</label>
            <div class="flex gap-2">
              <button v-for="m in ['轉帳','現金','支票','其他']" :key="m" @click="form.payment_method = m"
                class="flex-1 py-1.5 rounded-lg text-xs font-bold border transition-colors"
                :class="form.payment_method === m
                  ? 'bg-blue-700 border-blue-500 text-white'
                  : 'bg-[#0f1117] border-[#2d3748] text-gray-400 hover:border-gray-500'">
                {{ m }}
              </button>
            </div>
          </div>
          <!-- 銀行資訊（收摺） -->
          <details class="group">
            <summary class="text-xs text-gray-500 cursor-pointer hover:text-gray-300 select-none list-none flex items-center gap-1">
              <span class="text-gray-600 group-open:rotate-90 transition-transform inline-block">▶</span>
              銀行資訊（選填）
            </summary>
            <div class="mt-3 space-y-2 pl-2">
              <input v-model="form.bank_name" type="text" placeholder="銀行名稱"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
              <input v-model="form.bank_account" type="text" placeholder="帳號"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
              <input v-model="form.bank_account_holder" type="text" placeholder="戶名"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
            </div>
          </details>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">備注</label>
            <input v-model="form.note" type="text" placeholder="例：每月 5 號扣款"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <p v-if="formError" class="text-red-400 text-xs">{{ formError }}</p>
          <div class="flex gap-2 pt-2">
            <button @click="save" :disabled="saving"
              class="flex-1 py-2 rounded-lg font-bold text-sm bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400 disabled:opacity-40">
              {{ saving ? '儲存中…' : (editTarget ? '更新' : '建立') }}
            </button>
            <button @click="showModal = false"
              class="flex-1 py-2 rounded-lg text-sm text-gray-400 border border-[#2d3748] hover:bg-[#1f2937]">
              取消
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast" class="fixed bottom-6 right-6 bg-green-600 text-white px-4 py-2 rounded-lg text-sm shadow-xl z-50">{{ toast }}</div>
  </div>
</template>
