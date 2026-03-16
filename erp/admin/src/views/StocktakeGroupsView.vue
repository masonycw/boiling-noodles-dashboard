<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const groups = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')

const form = ref({ name: '', display_order: 0, is_active: true })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() })
  if (res.ok) groups.value = await res.json()
  loading.value = false
}

onMounted(load)

function openCreate() {
  editTarget.value = null
  form.value = { name: '', display_order: 0, is_active: true }
  saveError.value = ''
  showModal.value = true
}

function openEdit(g) {
  editTarget.value = g
  form.value = { ...g }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入群組名稱'; return }
  saving.value = true
  saveError.value = ''
  try {
    const url = editTarget.value
      ? `${API_BASE}/stocktake/groups/${editTarget.value.id}`
      : `${API_BASE}/stocktake/groups`
    const method = editTarget.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(form.value) })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteGroup(g) {
  if (!confirm(`確定要刪除群組「${g.name}」？`)) return
  const res = await fetch(`${API_BASE}/stocktake/groups/${g.id}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) await load()
  else {
    const d = await res.json()
    alert(d.detail || '刪除失敗')
  }
}
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-5">
      <h2 class="text-gray-200 font-semibold">盤點群組管理</h2>
      <button @click="openCreate"
        class="ml-auto bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增群組
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">群組名稱</th>
            <th class="px-5 py-3 text-right">顯示排序</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="g in groups" :key="g.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-semibold text-gray-200">{{ g.name }}</td>
            <td class="px-5 py-3 text-right text-gray-400">{{ g.display_order }}</td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="g.is_active !== false ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800 text-gray-500'">
                {{ g.is_active !== false ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center flex items-center justify-center gap-3">
              <button @click="openEdit(g)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
              <button @click="deleteGroup(g)" class="text-red-400 hover:text-red-300 text-xs font-bold">刪除</button>
            </td>
          </tr>
          <tr v-if="groups.length === 0">
            <td colspan="4" class="px-5 py-10 text-center text-gray-600">無群組資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯群組' : '新增群組' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-4 text-sm">
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">群組名稱 *</label>
            <input v-model="form.name" type="text"
              class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">顯示排序</label>
            <input v-model.number="form.display_order" type="number"
              class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div v-if="editTarget" class="flex items-center gap-3">
            <input v-model="form.is_active" type="checkbox" id="grp_active" class="w-4 h-4 accent-blue-500" />
            <label for="grp_active" class="text-gray-300 text-sm">啟用此群組</label>
          </div>
          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>
          <button @click="save" :disabled="saving"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
