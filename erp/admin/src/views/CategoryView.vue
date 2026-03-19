<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const categories = ref([])
const loading = ref(true)
const showForm = ref(false)
const editTarget = ref(null)
const formName = ref('')
const formError = ref('')
const saving = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/inventory/categories`, { headers: authHeaders() })
  if (res.ok) categories.value = await res.json()
  loading.value = false
}

onMounted(load)

function openAdd() {
  editTarget.value = null
  formName.value = ''
  formError.value = ''
  showForm.value = true
}

function openEdit(cat) {
  editTarget.value = cat
  formName.value = cat.name
  formError.value = ''
  showForm.value = true
}

function cancelForm() {
  showForm.value = false
  editTarget.value = null
  formName.value = ''
  formError.value = ''
}

async function save() {
  if (!formName.value.trim()) { formError.value = '請輸入分類名稱'; return }
  saving.value = true
  formError.value = ''
  try {
    let res
    if (editTarget.value) {
      res = await fetch(`${API_BASE}/inventory/categories/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ name: formName.value.trim(), display_order: 0 })
      })
    } else {
      res = await fetch(`${API_BASE}/inventory/categories`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ name: formName.value.trim(), display_order: 0 })
      })
    }
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '儲存失敗')
    }
    cancelForm()
    await load()
  } catch(e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function remove(cat) {
  if (!confirm(`確定要刪除「${cat.name}」分類？`)) return
  const res = await fetch(`${API_BASE}/inventory/categories/${cat.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (!res.ok) {
    const d = await res.json()
    alert(d.detail || '刪除失敗')
    return
  }
  await load()
}
</script>

<template>
  <div class="space-y-4">
    <!-- Add button -->
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-gray-400">品項分類管理</h3>
      <button @click="openAdd" class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400 transition-colors">
        ➕ 新增分類
      </button>
    </div>

    <!-- Inline form -->
    <div v-if="showForm" class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 space-y-3">
      <p class="text-sm font-bold text-gray-300">{{ editTarget ? '編輯分類' : '新增分類' }}</p>
      <input v-model="formName" type="text" placeholder="分類名稱"
        class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <p v-if="formError" class="text-red-400 text-xs">{{ formError }}</p>
      <div class="flex gap-2">
        <button @click="save" :disabled="saving"
          class="px-4 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400 disabled:opacity-40">
          {{ saving ? '儲存中…' : (editTarget ? '更新' : '建立') }}
        </button>
        <button @click="cancelForm" class="px-4 py-2 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937]">取消</button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">分類名稱</th>
            <th class="px-4 py-3 text-center">品項數</th>
            <th class="px-4 py-3 text-left">範例品項</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="cat in categories" :key="cat.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-4 py-3 font-bold text-gray-200">{{ cat.name }}</td>
            <td class="px-4 py-3 text-center text-gray-400">{{ cat.item_count }}</td>
            <td class="px-4 py-3 text-gray-400 text-xs">{{ cat.example_items?.join('、') || '—' }}</td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-2">
                <button @click="openEdit(cat)" class="text-xs px-2 py-1 rounded-lg bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="remove(cat)" class="text-xs px-2 py-1 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="categories.length === 0">
            <td colspan="4" class="px-5 py-10 text-center text-gray-600">尚無分類</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
