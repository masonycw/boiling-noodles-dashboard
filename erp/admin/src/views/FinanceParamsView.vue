<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const categories = ref([])
const paymentMethods = ref([
  { id: 1, name: '現金', is_active: true },
  { id: 2, name: '信用卡', is_active: true },
  { id: 3, name: '轉帳', is_active: true },
  { id: 4, name: 'LINE Pay', is_active: false },
])
const loading = ref(true)
const toast = ref('')
const showCatModal = ref(false)
const editCat = ref(null)
const catForm = ref({ name: '', type: 'expense', is_active: true })
const saving = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: authHeaders() })
  if (res.ok) categories.value = await res.json()
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
</script>

<template>
  <div class="space-y-6">
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <!-- 科目分類管理 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
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

    <!-- 付款方式（靜態顯示，待後端 API） -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748]">
        <h3 class="text-sm font-bold text-gray-200">付款方式</h3>
        <p class="text-xs text-gray-500 mt-0.5">供應商付款條件選項</p>
      </div>
      <div class="divide-y divide-[#2d3748]">
        <div v-for="pm in paymentMethods" :key="pm.id" class="px-5 py-3 flex items-center justify-between">
          <span class="text-sm text-gray-200">{{ pm.name }}</span>
          <span class="text-xs font-bold px-2 py-0.5 rounded-full"
            :class="pm.is_active ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800 text-gray-600'">
            {{ pm.is_active ? '啟用' : '停用' }}
          </span>
        </div>
      </div>
      <div class="px-5 py-3 border-t border-[#2d3748]">
        <p class="text-xs text-gray-600">付款方式管理功能（D1 完整實作後可編輯）</p>
      </div>
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
  </div>
</template>
