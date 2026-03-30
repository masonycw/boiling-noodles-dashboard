<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as XLSX from 'xlsx'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const items = ref([])
const vendors = ref([])
const groups = ref([])
const loading = ref(true)
const search = ref('')
const filterVendor = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const toast = ref('')

// 批次刪除
const selectedIds = ref(new Set())
const deleting = ref(false)

// CSV 匯入
const importFileInput = ref(null)
const importModal = ref(false)
const importRows = ref([])
const importError = ref('')
const importing = ref(false)
const importResult = ref(null)

const parseMode = (val) => {
  const v = String(val ?? '').trim()
  if (v === '僅基準單位') return 'base'
  if (v === '僅第二單位') return 'secondary'
  return 'both'
}

const emptyForm = () => ({
  name: '', unit: '', vendor_id: null,
  stocktake_group_id: null, min_stock: 10, current_stock: 0,
  price: null, display_order: 999, is_active: true,
  secondary_unit: '', secondary_unit_ratio: null,
  order_unit_mode: 'both', stocktake_unit_mode: 'both'
})

const form = ref(emptyForm())

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

async function load() {
  loading.value = true
  const [itemsRes, vendorsRes, groupsRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
  ])
  if (itemsRes.ok) items.value = await itemsRes.json()
  if (vendorsRes.ok) vendors.value = await vendorsRes.json()
  if (groupsRes.ok) groups.value = await groupsRes.json()
  selectedIds.value = new Set()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  let list = items.value
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    list = list.filter(i =>
      i.name.toLowerCase().includes(q) ||
      (vendorName(i.vendor_id)).toLowerCase().includes(q)
    )
  }
  if (filterVendor.value) {
    list = list.filter(i => String(i.vendor_id) === filterVendor.value)
  }
  return list
})

const allSelected = computed(() =>
  filtered.value.length > 0 && filtered.value.every(i => selectedIds.value.has(i.id))
)

const vendorName = (id) => vendors.value.find(v => v.id === id)?.name || '—'
const groupName = (id) => groups.value.find(g => g.id === id)?.name || null

function stockStatus(item) {
  const stock = parseFloat(item.current_stock) || 0
  const min = parseFloat(item.min_stock) || 0
  if (min === 0) return { label: '正常', cls: 'bg-[#10b981] text-white' }
  if (stock <= 0) return { label: '缺貨', cls: 'bg-[#ef4444] text-white' }
  if (stock <= min) return { label: '預警', cls: 'bg-[#f59e0b] text-white' }
  return { label: '正常', cls: 'bg-[#10b981] text-white' }
}

function openCreate() {
  editTarget.value = null
  form.value = emptyForm()
  saveError.value = ''
  showModal.value = true
}

function openEdit(item) {
  editTarget.value = item
  form.value = {
    name: item.name || '',
    unit: item.unit || '',
    vendor_id: item.vendor_id,
    stocktake_group_id: item.stocktake_group_id,
    min_stock: item.min_stock ?? 10,
    current_stock: item.current_stock ?? 0,
    price: item.price ?? null,
    display_order: item.display_order ?? 999,
    is_active: item.is_active !== false,
    secondary_unit: item.secondary_unit || '',
    secondary_unit_ratio: item.secondary_unit_ratio ?? null,
    order_unit_mode: item.order_unit_mode || 'both',
    stocktake_unit_mode: item.stocktake_unit_mode || 'both'
  }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入品項名稱'; return }
  if (!form.value.unit.trim()) { saveError.value = '請填入單位'; return }
  saving.value = true
  saveError.value = ''
  try {
    const url = editTarget.value
      ? `${API_BASE}/inventory/items/${editTarget.value.id}`
      : `${API_BASE}/inventory/items`
    const method = editTarget.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(form.value) })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    showToast('✓ 品項已儲存')
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

// 批次刪除
function toggleSelect(id) {
  const s = new Set(selectedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  selectedIds.value = s
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(filtered.value.map(i => i.id))
  }
}

async function deleteSelected() {
  if (selectedIds.value.size === 0) return
  if (!confirm(`確定要刪除選取的 ${selectedIds.value.size} 個品項？此操作無法復原。`)) return
  deleting.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/items/bulk-delete`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ ids: [...selectedIds.value] })
    })
    if (res.ok) {
      const d = await res.json()
      showToast(`✓ 已刪除 ${d.deleted} 個品項`)
      await load()
    }
  } finally {
    deleting.value = false
  }
}

// B1: Drag & Drop 排序
const isDragging = computed(() => !!search.value.trim() || !!filterVendor.value)
const dragFromIdx = ref(null)
const dragOverIdx = ref(null)

function onDragStart(idx) {
  if (isDragging.value) return
  dragFromIdx.value = idx
}

function onDragOver(idx) {
  if (isDragging.value) return
  dragOverIdx.value = idx
}

function onDragEnd() {
  if (isDragging.value || dragFromIdx.value === null || dragOverIdx.value === null || dragFromIdx.value === dragOverIdx.value) {
    dragFromIdx.value = null; dragOverIdx.value = null; return
  }
  const arr = [...items.value]
  const [moved] = arr.splice(dragFromIdx.value, 1)
  arr.splice(dragOverIdx.value, 0, moved)
  items.value = arr.map((it, i) => ({ ...it, sort_order: i + 1 }))
  dragFromIdx.value = null; dragOverIdx.value = null
  saveReorder()
}

async function saveReorder() {
  const payload = { items: items.value.map((it, i) => ({ id: it.id, sort_order: i + 1 })) }
  await fetch(`${API_BASE}/inventory/items/reorder`, {
    method: 'PATCH', headers: authHeaders(), body: JSON.stringify(payload)
  }).catch(() => {})
}

// CSV 匯入
function openImport() {
  importRows.value = []
  importError.value = ''
  importResult.value = null
  importModal.value = true
}

async function downloadTemplate() {
  const res = await fetch(`${API_BASE}/inventory/items/import-template`, { headers: authHeaders() })
  if (!res.ok) { showToast('⚠ 無法下載範本'); return }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '品項匯入範本.xlsx'
  a.click()
  URL.revokeObjectURL(a.href)
}

function onImportFile(e) {
  const file = e.target.files[0]
  if (!file) return
  importError.value = ''
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      const wb = XLSX.read(new Uint8Array(ev.target.result), { type: 'array' })
      const sheetName = wb.SheetNames.find(n => n === '品項匯入')
        || wb.SheetNames.find(n => !n.startsWith('_'))
        || wb.SheetNames[0]
      const ws = wb.Sheets[sheetName]
      const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
        .filter(row => row.some(cell => String(cell ?? '').trim()))  // 跳過完全空白列
      if (data.length < 2) { importError.value = '需至少有標題列和一筆資料'; return }
      const rows = data.slice(1)
        .filter(row => String(row[0] ?? '').trim())
        .map(row => {
          const vendorId = vendors.value.find(v => v.name === String(row[2] ?? '').trim())?.id || null
          const groupId  = groups.value.find(g => g.name === String(row[3] ?? '').trim())?.id || null
          return {
            name: String(row[0] ?? '').trim(),
            unit: String(row[1] ?? '').trim(),
            vendor_id: vendorId,
            stocktake_group_id: groupId,
            min_stock: parseFloat(row[4]) || 0,
            price: row[5] !== '' ? parseFloat(row[5]) : null,
            secondary_unit: String(row[6] ?? '').trim() || null,
            secondary_unit_ratio: row[7] !== '' && !isNaN(parseFloat(row[7])) ? parseFloat(row[7]) : null,
            order_unit_mode: parseMode(row[8]),
            stocktake_unit_mode: parseMode(row[9]),
            current_stock: 0, display_order: 999, is_active: true,
          }
        })
        .filter(r => r.name && r.unit)
      if (rows.length === 0) { importError.value = '找不到有效資料（名稱和單位不可空白）'; return }
      importRows.value = rows
    } catch {
      importError.value = '解析檔案失敗，請確認格式'
    }
  }
  reader.readAsArrayBuffer(file)
  e.target.value = ''
}

async function confirmImport() {
  importing.value = true
  importResult.value = null
  let success = 0, failed = 0, errors = []
  for (const row of importRows.value) {
    const res = await fetch(`${API_BASE}/inventory/items`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(row)
    })
    if (res.ok) { success++ }
    else { failed++; const d = await res.json(); errors.push(`${row.name}: ${d.detail || '失敗'}`) }
  }
  importResult.value = { success, failed, errors }
  importing.value = false
  if (success > 0) await load()
}
</script>

<template>
  <div>
    <!-- Toast -->
    <div v-if="toast"
      class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">
      {{ toast }}
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <input v-model="search" type="text" placeholder="搜尋品項、供應商…"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-4 py-2 text-sm w-56 focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterVendor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部供應商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <div class="ml-auto flex gap-2">
        <button v-if="selectedIds.size > 0" @click="deleteSelected" :disabled="deleting"
          class="bg-red-600 hover:bg-red-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50">
          {{ deleting ? '刪除中…' : `🗑 刪除 ${selectedIds.size} 項` }}
        </button>
        <button @click="openImport"
          class="bg-[#2d3748] hover:bg-[#374151] text-gray-300 font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          ↑ 批次匯入
        </button>
        <button @click="openCreate"
          class="bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          + 新增品項
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-3 py-3 text-center" style="width:36px">
              <input type="checkbox" :checked="allSelected" @change="toggleSelectAll"
                class="w-4 h-4 accent-blue-500 cursor-pointer" />
            </th>
            <th class="px-2 py-3 text-center" style="width:30px"></th>
            <th class="px-4 py-3 text-left" style="width:150px">品項名稱</th>
            <th class="px-4 py-3 text-left" style="width:100px">主要供應商</th>
            <th class="px-4 py-3 text-left" style="width:100px">盤點群組</th>
            <th class="px-4 py-3 text-center" style="width:50px">單位</th>
            <th class="px-4 py-3 text-right" style="width:70px">安全庫存</th>
            <th class="px-4 py-3 text-right" style="width:70px">目前庫存</th>
            <th class="px-4 py-3 text-right" style="width:70px">參考價格</th>
            <th class="px-4 py-3 text-center" style="width:80px">狀態</th>
            <th class="px-4 py-3 text-center" style="width:120px">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="(item, idx) in filtered" :key="item.id"
            class="hover:bg-[#1f2937] transition-colors"
            :class="[dragOverIdx === idx ? 'bg-[#1e3a5f]' : '', selectedIds.has(item.id) ? 'bg-blue-900/20' : '']"
            :draggable="!isDragging"
            @dragstart="onDragStart(idx)"
            @dragover.prevent="onDragOver(idx)"
            @dragend="onDragEnd">
            <td class="px-3 py-3 text-center" @click.stop>
              <input type="checkbox" :checked="selectedIds.has(item.id)" @change="toggleSelect(item.id)"
                class="w-4 h-4 accent-blue-500 cursor-pointer" />
            </td>
            <td class="px-2 py-3 text-center">
              <span :class="isDragging ? 'text-gray-700 cursor-not-allowed' : 'text-gray-500 cursor-grab'"
                title="拖曳排序（搜尋/篩選狀態下不可拖曳）">⠿</span>
            </td>
            <td class="px-4 py-3 font-semibold text-gray-200">{{ item.name }}</td>
            <td class="px-4 py-3 text-gray-400">{{ vendorName(item.vendor_id) }}</td>
            <td class="px-4 py-3">
              <span v-if="groupName(item.stocktake_group_id)"
                class="text-[11px] px-1.5 py-0.5 rounded"
                style="background:#1f2937; color:#9ca3af; border:1px solid #2d3748;">
                {{ groupName(item.stocktake_group_id) }}
              </span>
              <span v-else class="text-gray-600">—</span>
            </td>
            <td class="px-4 py-3 text-center text-gray-400">{{ item.unit }}</td>
            <td class="px-4 py-3 text-right font-mono text-gray-300">{{ item.min_stock ?? 0 }}</td>
            <td class="px-4 py-3 text-right font-mono"
              :class="parseFloat(item.min_stock) > 0 && parseFloat(item.current_stock) <= parseFloat(item.min_stock) ? 'text-amber-400 font-bold' : 'text-gray-300'">
              {{ item.current_stock ?? 0 }}
            </td>
            <td class="px-4 py-3 text-right font-mono text-gray-400">
              {{ item.price != null ? '$' + Number(item.price).toLocaleString('zh-TW') : '—' }}
            </td>
            <td class="px-4 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="stockStatus(item).cls">
                {{ stockStatus(item).label }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <button @click="openEdit(item)" class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="11" class="px-4 py-10 text-center text-gray-600">無品項資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- CSV 匯入 Modal -->
    <div v-if="importModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" @click.self="importModal=false">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg p-6">
        <div class="flex justify-between items-center mb-4">
          <div>
            <h3 class="font-bold text-gray-200">批次匯入品項</h3>
            <p class="text-xs text-gray-500 mt-0.5">下載 Excel 範本，填好後上傳（供應商/群組為下拉選單）</p>
          </div>
          <button @click="importModal=false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div v-if="!importResult">
          <div class="flex gap-2 mb-4">
            <input ref="importFileInput" type="file" accept=".xlsx,.csv" class="hidden" @change="onImportFile" />
            <button @click="importFileInput.click()"
              class="flex-1 border-2 border-dashed border-[#2d3748] hover:border-[#63b3ed] text-gray-400 hover:text-gray-200 rounded-lg py-3 text-sm font-bold transition-colors">
              📁 選擇 Excel 檔案
            </button>
            <button @click="downloadTemplate"
              class="px-4 py-3 bg-[#0f1117] border border-[#2d3748] hover:border-[#63b3ed] text-gray-400 hover:text-gray-200 rounded-lg text-xs font-bold transition-colors whitespace-nowrap">
              ↓ 下載範本
            </button>
          </div>
          <p v-if="importError" class="text-red-400 text-xs mb-3">{{ importError }}</p>
          <div v-if="importRows.length > 0" class="mb-4">
            <p class="text-xs text-gray-400 mb-2">預覽（共 {{ importRows.length }} 筆）：</p>
            <div class="bg-[#0f1117] rounded-lg p-3 max-h-40 overflow-y-auto space-y-1">
              <div v-for="(r, i) in importRows" :key="i" class="text-xs text-gray-300 flex gap-2">
                <span class="text-gray-600 w-5">{{ i+1 }}.</span>
                <span class="font-semibold">{{ r.name }}</span>
                <span class="text-gray-500">{{ r.unit }}</span>
                <span class="text-gray-500">安全:{{ r.min_stock }}</span>
              </div>
            </div>
            <button @click="confirmImport" :disabled="importing"
              class="mt-3 w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg text-sm disabled:opacity-50">
              {{ importing ? `匯入中…` : `確認匯入 ${importRows.length} 筆` }}
            </button>
          </div>
          <div class="bg-[#0f1117] rounded-lg p-3">
            <p class="text-xs text-gray-500 font-semibold mb-1">Excel 欄位說明</p>
            <p class="text-xs text-gray-600">名稱* / 單位* / 供應商（下拉）/ 盤點群組（下拉）/ 安全庫存 / 參考價格</p>
            <p class="text-xs text-gray-600 mt-1">※ 下載範本後，下拉選單自動帶入目前系統的供應商與群組</p>
          </div>
        </div>
        <div v-else class="text-center py-4">
          <p class="text-emerald-400 font-bold mb-2">✓ 匯入完成</p>
          <p class="text-gray-300 text-sm">成功 {{ importResult.success }} 筆 / 失敗 {{ importResult.failed }} 筆</p>
          <div v-if="importResult.errors.length > 0" class="mt-2 text-xs text-red-400 text-left bg-[#0f1117] rounded p-2 max-h-24 overflow-y-auto">
            <div v-for="e in importResult.errors" :key="e">{{ e }}</div>
          </div>
          <button @click="importModal=false" class="mt-4 px-6 py-2 bg-[#2d3748] text-gray-300 rounded-lg text-sm font-bold">關閉</button>
        </div>
      </div>
    </div>

    <!-- 新增/編輯 Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯品項' : '新增品項' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="space-y-3 text-sm">
          <div class="grid grid-cols-2 gap-3">
            <div class="col-span-2">
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                品項名稱 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.name" type="text" maxlength="50"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                單位 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.unit" type="text" placeholder="包 / 把 / 瓶 / 箱"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">主要供應商 <span class="text-red-400">*</span></label>
              <select v-model.number="form.vendor_id"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option :value="null">—</option>
                <option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">盤點群組 <span class="text-red-400">*</span></label>
              <select v-model.number="form.stocktake_group_id"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option :value="null">—</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                安全庫存量 <span class="text-red-400">*</span>
              </label>
              <input v-model.number="form.min_stock" type="number" min="0"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">參考價格</label>
              <input v-model.number="form.price" type="number" min="0" step="0.01"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">陳列順序</label>
              <input v-model.number="form.display_order" type="number"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                第二單位 (例如: 箱)
              </label>
              <input v-model="form.secondary_unit" type="text" placeholder="留白表示不啟用第二單位"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                換算比例 (1 個第二單位 = ? 基準單位)
              </label>
              <input v-model.number="form.secondary_unit_ratio" type="number" min="0" step="0.01"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">叫貨單位模式</label>
              <select v-model="form.order_unit_mode"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option value="both">雙單位並存</option>
                <option value="base">僅基準單位</option>
                <option value="secondary">僅第二單位</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">盤點單位模式</label>
              <select v-model="form.stocktake_unit_mode"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option value="both">雙單位並存</option>
                <option value="base">僅基準單位</option>
                <option value="secondary">僅第二單位</option>
              </select>
            </div>

            <div class="col-span-2 flex items-center gap-3 pt-1 border-t border-[#2d3748] mt-2">
              <input v-model="form.is_active" type="checkbox" id="is_active" class="w-4 h-4 accent-blue-500" />
              <label for="is_active" class="text-gray-300 text-sm">啟用此品項</label>
            </div>
          </div>

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <button @click="save" :disabled="saving"
            class="w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
