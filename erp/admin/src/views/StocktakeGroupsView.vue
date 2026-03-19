<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const groups = ref([])
const items = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const toast = ref('')

const frequencyOptions = [
  '每日', '每週一', '每週二', '每週三', '每週四', '每週五', '每週六',
  '每月一次（月初）', '每月中旬', '自訂'
]

const form = ref({ name: '', description: '', suggested_frequency: '每日', display_order: 0, is_active: true })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

function itemCount(groupId) {
  return items.value.filter(i => i.stocktake_group_id === groupId).length
}

async function load() {
  loading.value = true
  const [grpRes, itemRes] = await Promise.all([
    fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
  ])
  if (grpRes.ok) groups.value = await grpRes.json()
  if (itemRes.ok) items.value = await itemRes.json()
  loading.value = false
}

onMounted(load)

function openCreate() {
  editTarget.value = null
  form.value = { name: '', description: '', suggested_frequency: '每日', display_order: 0, is_active: true }
  saveError.value = ''
  showModal.value = true
}

function openEdit(g) {
  editTarget.value = g
  form.value = {
    name: g.name || '',
    description: g.description || '',
    suggested_frequency: g.suggested_frequency || '每日',
    display_order: g.display_order || 0,
    is_active: g.is_active !== false,
  }
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
    showToast('✓ 群組已儲存')
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
  if (res.ok) {
    showToast('✓ 已刪除')
    await load()
  } else {
    const d = await res.json()
    alert(d.detail || '刪除失敗')
  }
}
</script>

<template>
  <div>
    <!-- Toast -->
    <div v-if="toast"
      class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">
      {{ toast }}
    </div>

    <!-- Description -->
    <p class="text-[#9ca3af] text-sm mb-4">
      盤點群組是庫存分類的邏輯單位，用於安排定期盤點排程。例如：冷藏品每週一盤點，乾貨每月一次。
    </p>

    <!-- Toolbar -->
    <div class="flex items-center mb-4">
      <button @click="openCreate"
        class="ml-auto bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增群組
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-5 py-3 text-left">群組名稱</th>
            <th class="px-5 py-3 text-center">項目數量</th>
            <th class="px-5 py-3 text-left">建議頻率</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="g in groups" :key="g.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-semibold text-gray-200">
              {{ g.name }}
              <p v-if="g.description" class="text-xs text-gray-500 font-normal mt-0.5">{{ g.description }}</p>
            </td>
            <td class="px-5 py-3 text-center text-[#9ca3af]">{{ itemCount(g.id) }} 項</td>
            <td class="px-5 py-3 text-gray-400">{{ g.suggested_frequency || '—' }}</td>
            <td class="px-5 py-3 text-center flex items-center justify-center gap-3">
              <button @click="openEdit(g)" class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
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
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
              群組名稱 <span class="text-red-400">*</span>
            </label>
            <input v-model="form.name" type="text" maxlength="30"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">描述</label>
            <textarea v-model="form.description" rows="2" maxlength="200"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed] resize-none"></textarea>
          </div>
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
              建議盤點頻率 <span class="text-red-400">*</span>
            </label>
            <select v-model="form.suggested_frequency"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
              <option v-for="f in frequencyOptions" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>

          <!-- Item assignment info -->
          <div v-if="editTarget" class="bg-[#0f1117] border border-[#2d3748] rounded-lg p-3">
            <p class="text-[#9ca3af] text-xs">
              已分配 <strong class="text-gray-200">{{ itemCount(editTarget.id) }}</strong> 項 /
              共 {{ items.length }} 項可用品項
            </p>
            <p class="text-[#9ca3af] text-xs mt-1">
              如需分配品項，請至「品項管理」編輯各品項的盤點群組。
            </p>
          </div>

          <div v-if="editTarget" class="flex items-center gap-3">
            <input v-model="form.is_active" type="checkbox" id="grp_active" class="w-4 h-4 accent-blue-500" />
            <label for="grp_active" class="text-gray-300 text-sm">啟用此群組</label>
          </div>

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <div class="flex gap-3">
            <button @click="save" :disabled="saving"
              class="flex-1 bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
              {{ saving ? '儲存中…' : '保存' }}
            </button>
            <button v-if="editTarget" @click="deleteGroup(editTarget); showModal = false"
              class="px-4 bg-red-900 hover:bg-red-800 text-white font-bold py-2.5 rounded-lg transition-colors text-sm">
              刪除群組
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
