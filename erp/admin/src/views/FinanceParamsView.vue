<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const categories = ref([])
const paymentMethods = ref([])
const loading = ref(true)
const toast = ref('')
const showCatModal = ref(false)
const editCat = ref(null)
const catForm = ref({ name: '', type: 'expense', is_active: true })
const saving = ref(false)

// 付款方式 modal
const showPmModal = ref(false)
const editPm = ref(null)
const pmForm = ref({ name: '', is_active: true, display_order: 999 })
const pmSaving = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

async function load() {
  loading.value = true
  const [catRes, pmRes] = await Promise.all([
    fetch(`${API_BASE}/finance/cash-flow/categories?include_inactive=true`, { headers: authHeaders() }),
    fetch(`${API_BASE}/finance/payment-methods?include_inactive=true`, { headers: authHeaders() }),
  ])
  if (catRes.ok) categories.value = await catRes.json()
  if (pmRes.ok) paymentMethods.value = await pmRes.json()
  loading.value = false
}
onMounted(load)

function openCreateCat() {
  editCat.value = null
  catForm.value = { name: '', type: 'expense', is_active: true }
  showCatModal.value = true
}
function openEditCat(c) {
  editCat.value = c
  catForm.value = { name: c.name, type: c.type, is_active: c.is_active }
  showCatModal.value = true
}
async function saveCat() {
  if (!catForm.value.name.trim()) return
  saving.value = true
  try {
    if (editCat.value) {
      await fetch(`${API_BASE}/finance/cash-flow/categories/${editCat.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(catForm.value)
      })
    } else {
      await fetch(`${API_BASE}/finance/cash-flow/categories`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify(catForm.value)
      })
    }
    showCatModal.value = false; showToast('✓ 科目已儲存'); await load()
  } catch (e) { showToast('儲存失敗') } finally { saving.value = false }
}
async function deleteCat(c) {
  if (!confirm(`刪除科目「${c.name}」？`)) return
  const res = await fetch(`${API_BASE}/finance/cash-flow/categories/${c.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) { showToast('已刪除'); await load() }
}

// 付款方式 CRUD
function openCreatePm() {
  editPm.value = null
  pmForm.value = { name: '', is_active: true, display_order: (paymentMethods.value.length + 1) }
  showPmModal.value = true
}
function openEditPm(pm) {
  editPm.value = pm
  pmForm.value = { name: pm.name, is_active: pm.is_active, display_order: pm.display_order }
  showPmModal.value = true
}
async function savePm() {
  if (!pmForm.value.name.trim()) return
  pmSaving.value = true
  try {
    let res
    if (editPm.value) {
      res = await fetch(`${API_BASE}/finance/payment-methods/${editPm.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(pmForm.value)
      })
    } else {
      res = await fetch(`${API_BASE}/finance/payment-methods`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify(pmForm.value)
      })
    }
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showPmModal.value = false; showToast('✓ 付款方式已儲存'); await load()
  } catch (e) { showToast(e.message) } finally { pmSaving.value = false }
}
async function deletePm(pm) {
  if (!confirm(`刪除付款方式「${pm.name}」？`)) return
  const res = await fetch(`${API_BASE}/finance/payment-methods/${pm.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) { showToast('已刪除'); await load() }
  else { const d = await res.json(); showToast(d.detail || '刪除失敗') }
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <!-- 科目分類管理 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div>
          <h3 class="text-sm font-bold text-gray-200">科目分類</h3>
          <p class="text-xs text-gray-500 mt-0.5">金流紀錄的科目分類管理</p>
        </div>
        <button @click="openCreateCat"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-3 py-1.5 rounded-lg text-sm transition-colors">
          + 新增科目
        </button>
      </div>
      <div v-if="loading" class="py-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-2 text-left">科目名稱</th>
            <th class="px-5 py-2 text-center">類型</th>
            <th class="px-5 py-2 text-center">狀態</th>
            <th class="px-5 py-2 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="c in categories" :key="c.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-200">{{ c.name }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold" :class="c.type === 'income' ? 'text-emerald-400' : 'text-red-400'">
                {{ c.type === 'income' ? '收入' : '支出' }}
              </span>
            </td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold" :class="c.is_active !== false ? 'text-emerald-400' : 'text-gray-600'">
                {{ c.is_active !== false ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-2.5 text-center flex gap-3 justify-center">
              <button @click="openEditCat(c)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
              <button @click="deleteCat(c)" class="text-red-400 hover:text-red-300 text-xs font-bold">刪除</button>
            </td>
          </tr>
          <tr v-if="categories.length === 0">
            <td colspan="4" class="px-5 py-8 text-center text-gray-600">尚無科目分類</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 付款方式管理 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div>
          <h3 class="text-sm font-bold text-gray-200">付款方式</h3>
          <p class="text-xs text-gray-500 mt-0.5">應付帳款付款、供應商設定等使用的付款方式選項</p>
        </div>
        <button @click="openCreatePm"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-3 py-1.5 rounded-lg text-sm transition-colors">
          + 新增付款方式
        </button>
      </div>
      <div v-if="loading" class="py-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-2 text-left">名稱</th>
            <th class="px-5 py-2 text-center">顯示順序</th>
            <th class="px-5 py-2 text-center">狀態</th>
            <th class="px-5 py-2 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="pm in paymentMethods" :key="pm.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-200 font-medium">{{ pm.name }}</td>
            <td class="px-5 py-2.5 text-center text-gray-400 text-xs">{{ pm.display_order }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="pm.is_active ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800 text-gray-600'">
                {{ pm.is_active ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-2.5 text-center flex gap-3 justify-center">
              <button @click="openEditPm(pm)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
              <button @click="deletePm(pm)" class="text-red-400 hover:text-red-300 text-xs font-bold">刪除</button>
            </td>
          </tr>
          <tr v-if="paymentMethods.length === 0">
            <td colspan="4" class="px-5 py-8 text-center text-gray-600">尚無付款方式</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 科目 Modal -->
    <div v-if="showCatModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editCat ? '編輯科目' : '新增科目' }}</h3>
          <button @click="showCatModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">科目名稱 *</label>
            <input v-model="catForm.name" type="text"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">類型</label>
            <select v-model="catForm.type"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400">
              <option value="expense">支出</option>
              <option value="income">收入</option>
            </select>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="catForm.is_active" type="checkbox" id="catActive" class="w-4 h-4 accent-blue-500" />
            <label for="catActive" class="text-gray-300">啟用</label>
          </div>
          <button @click="saveCat" :disabled="saving"
            class="w-full bg-blue-500 hover:bg-blue-400 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 付款方式 Modal -->
    <div v-if="showPmModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editPm ? '編輯付款方式' : '新增付款方式' }}</h3>
          <button @click="showPmModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">名稱 *</label>
            <input v-model="pmForm.name" type="text" placeholder="例：轉帳、現金、支票"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">顯示順序</label>
            <input v-model.number="pmForm.display_order" type="number" min="1"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div class="flex items-center gap-3">
            <input v-model="pmForm.is_active" type="checkbox" id="pmActive" class="w-4 h-4 accent-blue-500" />
            <label for="pmActive" class="text-gray-300">啟用（停用後不出現在選單）</label>
          </div>
          <button @click="savePm" :disabled="pmSaving"
            class="w-full bg-blue-500 hover:bg-blue-400 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ pmSaving ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
