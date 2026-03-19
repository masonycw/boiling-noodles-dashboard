<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const formError = ref('')

const form = ref({ name: '', category: '固定費用', amount: '', day_of_month: '', note: '' })

const categoryOptions = ['平台費', '固定費用', '權利金', '手續費', '其他']

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/finance/recurring`, { headers: authHeaders() })
  if (res.ok) records.value = await res.json()
  loading.value = false
}

onMounted(load)

function openAdd() {
  editTarget.value = null
  form.value = { name: '', category: '固定費用', amount: '', day_of_month: '', note: '' }
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editTarget.value = r
  form.value = { name: r.name, category: r.category || '固定費用', amount: String(r.amount), day_of_month: String(r.day_of_month || ''), note: r.note || '' }
  formError.value = ''
  showModal.value = true
}

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
      note: form.value.note || null,
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

async function deactivate(r) {
  if (!confirm(`停用「${r.name}」？`)) return
  const res = await fetch(`${API_BASE}/finance/recurring/${r.id}`, { method: 'DELETE', headers: authHeaders() })
  if (res.ok) await load()
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-gray-400">重複預約費用管理</h3>
      <button @click="openAdd" class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400">
        ➕ 新增重複預約
      </button>
    </div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">名稱</th>
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
              <div v-if="r.is_active" class="flex items-center justify-center gap-2">
                <button @click="openEdit(r)" class="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="deactivate(r)" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">停用</button>
              </div>
              <span v-else class="text-gray-600 text-xs">—</span>
            </td>
          </tr>
          <tr v-if="records.length === 0">
            <td colspan="6" class="px-5 py-10 text-center text-gray-600">尚無重複預約費用</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-md">
        <div class="flex justify-between items-center mb-4">
          <h3 class="font-bold text-gray-200">{{ editTarget ? '編輯重複預約' : '新增重複預約' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500 mb-1 block">名稱</label>
            <input v-model="form.name" type="text" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500 mb-1 block">分類</label>
              <select v-model="form.category" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
                <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
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
  </div>
</template>
