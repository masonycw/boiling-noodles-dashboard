<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const rules = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const formError = ref('')

const form = ref({ name: '', category: '平台費', calculation_basis: '訂單總額', percentage: '', settlement_period: 'monthly', note: '' })

const categoryOptions = ['平台費', '手續費', '稅金', '其他']
const basisOptions = ['訂單總額', '交易金額', '應稅銷售額', '其他']
const periodOptions = [{ value: 'monthly', label: '每月結算' }, { value: 'quarterly', label: '季度結算' }, { value: 'yearly', label: '年度結算' }]

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/finance/proportional-fees`, { headers: authHeaders() })
  if (res.ok) rules.value = await res.json()
  loading.value = false
}

onMounted(load)

function openAdd() {
  editTarget.value = null
  form.value = { name: '', category: '平台費', calculation_basis: '訂單總額', percentage: '', settlement_period: 'monthly', note: '' }
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editTarget.value = r
  form.value = { name: r.name, category: r.category || '平台費', calculation_basis: r.calculation_basis || '訂單總額', percentage: String(r.percentage), settlement_period: r.settlement_period || 'monthly', note: r.note || '' }
  formError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { formError.value = '請輸入規則名稱'; return }
  if (!form.value.percentage || parseFloat(form.value.percentage) <= 0) { formError.value = '請輸入費率 (%)'; return }
  saving.value = true
  formError.value = ''
  try {
    const payload = {
      name: form.value.name.trim(),
      category: form.value.category,
      calculation_basis: form.value.calculation_basis,
      percentage: parseFloat(form.value.percentage),
      settlement_period: form.value.settlement_period,
      note: form.value.note || null,
    }
    let res
    if (editTarget.value) {
      res = await fetch(`${API_BASE}/finance/proportional-fees/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload)
      })
    } else {
      res = await fetch(`${API_BASE}/finance/proportional-fees`, {
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

async function remove(r) {
  if (!confirm(`刪除「${r.name}」費率規則？`)) return
  const res = await fetch(`${API_BASE}/finance/proportional-fees/${r.id}`, { method: 'DELETE', headers: authHeaders() })
  if (res.ok) await load()
}

function periodLabel(p) { return periodOptions.find(o => o.value === p)?.label || p }
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-sm font-bold text-gray-400">比例費用規則管理</h3>
      <button @click="openAdd" class="px-3 py-2 rounded-lg text-sm font-bold bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400">
        ➕ 新增規則
      </button>
    </div>

    <!-- Info card -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-3 flex gap-2">
      <span>ℹ️</span>
      <p class="text-xs text-gray-400">費率設定說明：費用基於 POS 銷售資料自動計算，每月自動計入成本科目。</p>
    </div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">規則名稱</th>
            <th class="px-4 py-3 text-left">分類</th>
            <th class="px-4 py-3 text-left">計算基礎</th>
            <th class="px-4 py-3 text-center">費率</th>
            <th class="px-4 py-3 text-left">結算週期</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in rules" :key="r.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-4 py-3 font-medium text-gray-200">{{ r.name }}</td>
            <td class="px-4 py-3 text-gray-400">{{ r.category || '—' }}</td>
            <td class="px-4 py-3 text-gray-400">{{ r.calculation_basis || '—' }}</td>
            <td class="px-4 py-3 text-center font-mono font-bold text-amber-400">{{ r.percentage }}%</td>
            <td class="px-4 py-3 text-gray-400">{{ periodLabel(r.settlement_period) }}</td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-2">
                <button @click="openEdit(r)" class="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="remove(r)" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="rules.length === 0">
            <td colspan="6" class="px-5 py-10 text-center text-gray-600">尚無費率規則</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-md">
        <div class="flex justify-between items-center mb-4">
          <h3 class="font-bold text-gray-200">{{ editTarget ? '編輯費率規則' : '新增費率規則' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500 mb-1 block">規則名稱</label>
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
              <label class="text-xs text-gray-500 mb-1 block">費率 (%)</label>
              <input v-model="form.percentage" type="number" min="0" max="100" step="0.1" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-500 mb-1 block">計算基礎</label>
              <select v-model="form.calculation_basis" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
                <option v-for="b in basisOptions" :key="b" :value="b">{{ b }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-gray-500 mb-1 block">結算週期</label>
              <select v-model="form.settlement_period" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
                <option v-for="p in periodOptions" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
            </div>
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">備注</label>
            <input v-model="form.note" type="text" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <p v-if="formError" class="text-red-400 text-xs">{{ formError }}</p>
          <div class="flex gap-2 pt-2">
            <button @click="save" :disabled="saving" class="flex-1 py-2 rounded-lg font-bold text-sm bg-[#63b3ed] text-[#0f1117] hover:bg-blue-400 disabled:opacity-40">
              {{ saving ? '儲存中…' : (editTarget ? '更新' : '建立') }}
            </button>
            <button @click="showModal = false" class="flex-1 py-2 rounded-lg text-sm text-gray-400 border border-[#2d3748] hover:bg-[#1f2937]">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
