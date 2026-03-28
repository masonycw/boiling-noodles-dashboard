<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as XLSX from 'xlsx'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const cashflowCategories = ref([])

const vendors = ref([])
const loading = ref(true)
const search = ref('')
const selectedId = ref(null)
const isNew = ref(false)
const saving = ref(false)
const saveError = ref('')
const toast = ref('')

const filterCategoryId = ref('')

const emptyForm = () => ({
  name: '', contact_person: '', phone: '', line_id: '',
  payment_method: '現金',
  payment_terms: '現付',
  default_category_id: null,
  bank_account: '', bank_account_holder: '',
  reminder_days: 5,
  order_cycle: '',
  show_in_ordering: false,
  is_fixed_order: false,
  order_days: [],
  order_time: '',
  delivery_days_to_arrive: 1,
  closed_days: [],
  closed_on_holidays: false,
  free_shipping_threshold: '',
  note: '',
})

const form = ref(emptyForm())

const paymentMethodOptions = ref(['現金', '轉帳', '支票'])
const expenseCategoryOptions = ['食材費用', '人事費用', '營業費用', '平台費用', '金融費用', '其他']
const paymentTermsOptions = ['先收款', '現付', '後收款', '週結', '月結']
const reminderDaysOptions = [1, 2, 3, 4, 5]

// LINE 群組配對
const linePendingGroups = ref([])
const selectedPendingGroupId = ref(null)

const unmatchedGroups = computed(() => linePendingGroups.value.filter(g => !g.matched))
const unmatchedCount = computed(() => unmatchedGroups.value.length)

async function loadLinePendingGroups() {
  try {
    const res = await fetch(`${API_BASE}/admin/settings/line-pending-groups`, { headers: authHeaders() })
    if (res.ok) linePendingGroups.value = await res.json()
  } catch (e) { /* 靜默失敗 */ }
}

function formatGroupId(groupId) {
  if (!groupId) return ''
  if (groupId.length > 12) return groupId.slice(0, 8) + '…' + groupId.slice(-4)
  return groupId
}

function formatGroupDate(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function clearLineGroup() {
  form.value.line_id = ''
  selectedPendingGroupId.value = null
}

async function copyGroupId(groupId) {
  try {
    await navigator.clipboard.writeText(groupId)
  } catch {
    // fallback
    const el = document.createElement('textarea')
    el.value = groupId
    el.style.position = 'fixed'; el.style.opacity = '0'
    document.body.appendChild(el); el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  copiedGroupId.value = groupId
  setTimeout(() => { copiedGroupId.value = '' }, 2000)
}
const copiedGroupId = ref('')

// CSV 匯入
const importFileInput = ref(null)
const importModal = ref(false)
const importRows = ref([])
const importError = ref('')
const importing = ref(false)
const importResult = ref(null)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() })
  if (res.ok) vendors.value = await res.json()
  loading.value = false
}

async function loadCashflowCategories() {
  const res = await fetch(`${API_BASE}/finance/cash-flow/categories`, { headers: { Authorization: `Bearer ${auth.token}` } })
  if (res.ok) cashflowCategories.value = await res.json()
}

async function loadPaymentMethods() {
  const res = await fetch(`${API_BASE}/finance/payment-methods`, { headers: authHeaders() })
  if (res.ok) {
    const methods = await res.json()
    if (methods.length > 0) paymentMethodOptions.value = methods.map(m => m.name)
  }
}

onMounted(() => { load(); loadCashflowCategories(); loadPaymentMethods(); loadLinePendingGroups() })

// CSV 匯入功能
function openImport() {
  importRows.value = []
  importError.value = ''
  importResult.value = null
  importModal.value = true
}

function parseBool(val) {
  return ['y', '是', '1', 'true', 'yes'].includes(String(val ?? '').toLowerCase().trim())
}

function onImportFile(e) {
  const file = e.target.files[0]
  if (!file) return
  importError.value = ''
  const reader = new FileReader()
  reader.onload = (ev) => {
    try {
      const wb = XLSX.read(new Uint8Array(ev.target.result), { type: 'array' })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' })
      if (data.length < 2) { importError.value = '需至少有標題列和一筆資料'; return }
      // 欄位順序（對應 Excel 範本）：
      // 0:名稱 1:聯絡人 2:電話 3:LINE ID 4:付款方式 5:付款條件 6:金流科目
      // 7:到期提醒天數 8:匯款帳號 9:戶名 10:到貨天數 11:免運門檻 12:出現叫貨系統 13:固定排程 14:備注
      const rows = data.slice(1)
        .filter(row => String(row[0] ?? '').trim())
        .map(row => {
          const catName = String(row[6] ?? '').trim()
          const catId = cashflowCategories.value.find(c => c.name === catName)?.id || null
          return {
            name: String(row[0] ?? '').trim(),
            contact_person: String(row[1] ?? '').trim(),
            phone: String(row[2] ?? '').trim(),
            line_id: String(row[3] ?? '').trim(),
            payment_method: String(row[4] ?? '').trim() || '現金',
            payment_terms: String(row[5] ?? '').trim() || '現付',
            default_category_id: catId,
            reminder_days: parseInt(row[7]) || 5,
            bank_account: String(row[8] ?? '').trim(),
            bank_account_holder: String(row[9] ?? '').trim(),
            delivery_days_to_arrive: parseInt(row[10]) || 1,
            free_shipping_threshold: row[11] !== '' ? parseFloat(row[11]) : null,
            show_in_ordering: parseBool(row[12]),
            is_fixed_order: parseBool(row[13]),
            note: String(row[14] ?? '').trim(),
          }
        })
      if (rows.length === 0) { importError.value = '找不到有效資料（名稱欄位不可空白）'; return }
      importRows.value = rows
    } catch {
      importError.value = '解析檔案失敗，請確認格式'
    }
  }
  reader.readAsArrayBuffer(file)
  e.target.value = ''
}

async function downloadTemplate() {
  const res = await fetch(`${API_BASE}/inventory/vendors/import-template`, { headers: authHeaders() })
  if (!res.ok) { showToast('⚠ 無法下載範本'); return }
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '供應商匯入範本.xlsx'
  a.click()
  URL.revokeObjectURL(a.href)
}

async function confirmImport() {
  importing.value = true
  importResult.value = null
  let success = 0, failed = 0, errors = []
  for (const row of importRows.value) {
    const res = await fetch(`${API_BASE}/inventory/vendors`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(row)
    })
    if (res.ok) { success++ }
    else { failed++; const d = await res.json(); errors.push(`${row.name}: ${d.detail || '失敗'}`) }
  }
  importResult.value = { success, failed, errors }
  importing.value = false
  if (success > 0) await load()
}

const filtered = computed(() => {
  let list = vendors.value
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    list = list.filter(v =>
      v.name.toLowerCase().includes(q) ||
      (v.contact_person || '').toLowerCase().includes(q) ||
      (v.phone || '').includes(q)
    )
  }
  if (filterCategoryId.value) {
    list = list.filter(v => String(v.default_category_id) === filterCategoryId.value)
  }
  return list
})

function selectVendor(v) {
  isNew.value = false
  selectedId.value = v.id
  saveError.value = ''
  selectedPendingGroupId.value = v.line_id
    ? (linePendingGroups.value.find(g => g.group_id === v.line_id)?.id ?? null)
    : null
  form.value = {
    name: v.name || '',
    contact_person: v.contact_person || '',
    phone: v.phone || '',
    line_id: v.line_id || '',
    payment_method: v.payment_method || '現金',
    payment_terms: v.payment_terms || '現付',
    default_category_id: v.default_category_id || null,
    bank_account: v.bank_account || '',
    bank_account_holder: v.bank_account_holder || '',
    reminder_days: v.reminder_days || 5,
    order_cycle: v.order_cycle || '',
    show_in_ordering: v.show_in_ordering || false,
    is_fixed_order: v.is_fixed_order || false,
    order_days: v.order_days || [],
    order_time: v.order_time || '',
    delivery_days_to_arrive: v.delivery_days_to_arrive ?? 1,
    closed_days: v.closed_days || [],
    closed_on_holidays: v.closed_on_holidays || false,
    free_shipping_threshold: v.free_shipping_threshold || '',
    note: v.note || '',
  }
}

// B1: 兩步驟新增供應商
const showNewModal = ref(false)
const newStep = ref(1)
const newVendorId = ref(null)
const newVendorName = ref('')

// B1: Step 2 — 品項關聯
const allItems = ref([])
const itemSearch = ref('')
const selectedItemIds = ref(new Set())
const itemPrices = ref({})  // item_id → unit_price

const filteredItems = computed(() => {
  if (!itemSearch.value.trim()) return allItems.value
  const q = itemSearch.value.toLowerCase()
  return allItems.value.filter(i => i.name.toLowerCase().includes(q))
})

function openNew() {
  showNewModal.value = true
  newStep.value = 1
  newVendorId.value = null
  newVendorName.value = ''
  selectedItemIds.value = new Set()
  itemPrices.value = {}
  itemSearch.value = ''
  saveError.value = ''
  selectedPendingGroupId.value = null
  form.value = emptyForm()
}

async function saveStep1() {
  if (!form.value.name.trim()) { saveError.value = '請填入供應商名稱'; return }
  saving.value = true
  saveError.value = ''
  try {
    const res = await fetch(`${API_BASE}/inventory/vendors`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(form.value)
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    const saved = await res.json()
    newVendorId.value = saved.id
    newVendorName.value = saved.name
    // load items for step 2
    const itemsRes = await fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() })
    if (itemsRes.ok) allItems.value = await itemsRes.json()
    newStep.value = 2
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

async function saveStep2() {
  saving.value = true
  try {
    const vendorItems = [...selectedItemIds.value].map(id => ({
      item_id: id,
      unit_price: parseFloat(itemPrices.value[id]) || null
    }))
    if (vendorItems.length > 0) {
      await fetch(`${API_BASE}/inventory/vendors/${newVendorId.value}/items`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ items: vendorItems })
      })
    }
    showNewModal.value = false
    showToast('✓ 供應商已建立')
    await load()
    selectedId.value = newVendorId.value
    isNew.value = false
    const v = vendors.value.find(v => v.id === newVendorId.value)
    if (v) selectVendor(v)
  } catch (e) {
    showToast('⚠ 品項關聯儲存失敗')
    showNewModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function toggleItem(id) {
  if (selectedItemIds.value.has(id)) selectedItemIds.value.delete(id)
  else selectedItemIds.value.add(id)
  selectedItemIds.value = new Set(selectedItemIds.value)
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入供應商名稱'; return }
  saving.value = true
  saveError.value = ''
  try {
    const res = await fetch(`${API_BASE}/inventory/vendors/${selectedId.value}`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(form.value)
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }

    // 若選擇了待配對群組，標記為已配對
    if (selectedPendingGroupId.value && form.value.line_id) {
      try {
        await fetch(`${API_BASE}/admin/settings/line-pending-groups/${selectedPendingGroupId.value}/match`, {
          method: 'PATCH', headers: authHeaders(), body: JSON.stringify({ matched: true })
        })
        const pg = linePendingGroups.value.find(g => g.id === selectedPendingGroupId.value)
        if (pg) pg.matched = true
      } catch (e) { /* 非關鍵錯誤 */ }
    }

    showToast('✓ 供應商已儲存')
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteVendor() {
  if (!selectedId.value) return
  const v = vendors.value.find(v => v.id === selectedId.value)
  if (!confirm(`確定要刪除「${v?.name}」？`)) return
  const res = await fetch(`${API_BASE}/inventory/vendors/${selectedId.value}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) {
    selectedId.value = null
    isNew.value = false
    await load()
    showToast('✓ 已刪除')
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

    <div class="grid gap-5" style="grid-template-columns: 1fr 1fr; max-width: 1400px;">
      <!-- Left: List -->
      <div>
        <div class="flex items-center gap-3 mb-4 flex-wrap">
          <input v-model="search" type="text" placeholder="搜尋供應商..."
            class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-4 py-2 text-sm flex-1 focus:outline-none focus:border-[#63b3ed]" />
          <select v-model="filterCategoryId"
            class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
            <option value="">全部科目</option>
            <option v-for="c in cashflowCategories.filter(c => c.type === 'expense')" :key="c.id" :value="String(c.id)">{{ c.name }}</option>
          </select>
          <span v-if="unmatchedCount > 0"
            class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-amber-900/30 border border-amber-700/40 text-amber-400 text-xs font-bold whitespace-nowrap">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0"></span>
            {{ unmatchedCount }} 個群組待配對
          </span>
          <button @click="openImport"
            class="bg-[#2d3748] hover:bg-[#374151] text-gray-300 font-bold px-4 py-2 rounded-lg text-sm transition-colors whitespace-nowrap">
            ↑ 批次匯入
          </button>
          <button @click="openNew"
            class="bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors whitespace-nowrap">
            + 新增供應商
          </button>

          <!-- CSV 匯入 Modal -->
          <div v-if="importModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" @click.self="importModal=false">
            <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg p-6">
              <div class="flex justify-between items-center mb-4">
                <div>
                  <h3 class="font-bold text-gray-200">批次匯入供應商</h3>
                  <p class="text-xs text-gray-500 mt-0.5">下載 Excel 範本，付款方式/科目等均為下拉選單</p>
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
                    <div v-for="(r, i) in importRows" :key="i" class="text-xs text-gray-300 flex gap-2 flex-wrap">
                      <span class="text-gray-600 w-5">{{ i+1 }}.</span>
                      <span class="font-semibold">{{ r.name }}</span>
                      <span class="text-gray-500">{{ r.phone || '—' }}</span>
                      <span class="text-gray-500">{{ r.payment_method }}</span>
                      <span class="text-gray-500">{{ r.payment_terms }}</span>
                    </div>
                  </div>
                  <button @click="confirmImport" :disabled="importing"
                    class="mt-3 w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg text-sm disabled:opacity-50">
                    {{ importing ? `匯入中…` : `確認匯入 ${importRows.length} 筆` }}
                  </button>
                </div>
                <div class="bg-[#0f1117] rounded-lg p-3">
                  <p class="text-xs text-gray-500 font-semibold mb-1">Excel 欄位說明</p>
                  <p class="text-xs text-gray-600 leading-relaxed">名稱* / 聯絡人 / 電話 / LINE ID / 付款方式（下拉）/ 付款條件（下拉）/ 金流科目（下拉）/ 到期提醒天數（下拉）/ 匯款帳號 / 戶名 / 到貨天數 / 免運門檻 / 出現叫貨系統（是/否）/ 固定排程（是/否）/ 備注</p>
                  <p class="text-xs text-gray-600 mt-1">※ 下載範本後，下拉選單會顯示目前系統設定的選項</p>
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

          <!-- B1: 兩步驟新增 Modal -->
          <div v-if="showNewModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" @click.self="showNewModal=false">
            <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-xl max-h-[85vh] overflow-y-auto">
              <div class="px-6 py-4 border-b border-[#2d3748] flex items-center justify-between">
                <div>
                  <h3 class="text-base font-bold text-gray-100">新增供應商</h3>
                  <p class="text-xs text-gray-500 mt-0.5">步驟 {{ newStep }} / 2</p>
                </div>
                <div class="flex gap-2">
                  <span class="w-6 h-6 rounded-full text-xs flex items-center justify-center font-bold"
                    :class="newStep >= 1 ? 'bg-[#63b3ed] text-black' : 'bg-[#2d3748] text-gray-500'">1</span>
                  <span class="w-6 h-6 rounded-full text-xs flex items-center justify-center font-bold"
                    :class="newStep >= 2 ? 'bg-[#63b3ed] text-black' : 'bg-[#2d3748] text-gray-500'">2</span>
                </div>
              </div>

              <!-- Step 1: 基本資料（與編輯卡片欄位完全一致） -->
              <div v-if="newStep === 1" class="p-6 space-y-4 text-sm">
                <!-- 基本資訊 -->
                <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748]">基本資訊</div>
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">供應商名稱 <span class="text-red-400">*</span></label>
                  <input v-model="form.name" type="text" maxlength="50"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                </div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">聯絡人</label>
                    <input v-model="form.contact_person" type="text" maxlength="30"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">電話</label>
                    <input v-model="form.phone" type="text"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                  </div>
                </div>
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">LINE 群組</label>
                  <!-- 手動輸入 Group ID -->
                  <div class="flex items-center gap-2">
                    <input v-model="form.line_id" type="text" placeholder="貼上 Group ID（C...）"
                      class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 font-mono text-xs focus:outline-none focus:border-[#63b3ed]" />
                    <button v-if="form.line_id" @click="clearLineGroup"
                      class="text-gray-500 hover:text-red-400 text-sm transition-colors shrink-0" title="清除">✕</button>
                  </div>
                  <!-- 偵測到的群組清單 -->
                  <div v-if="linePendingGroups.length > 0" class="mt-2 space-y-1">
                    <p class="text-[11px] text-gray-600">偵測到的群組（點複製後貼入上方）：</p>
                    <div v-for="g in linePendingGroups" :key="g.id"
                      class="flex items-center gap-2 bg-[#0f1117] border border-[#2d3748] rounded-lg px-2.5 py-1.5">
                      <span class="flex-1 font-mono text-[11px] text-gray-300 break-all">{{ g.group_id }}</span>
                      <span class="text-[10px] text-gray-600 shrink-0">{{ formatGroupDate(g.first_seen) }}</span>
                      <button @click="copyGroupId(g.group_id)"
                        class="shrink-0 text-[11px] px-2 py-0.5 rounded transition-colors"
                        :class="copiedGroupId === g.group_id ? 'bg-emerald-700/50 text-emerald-400' : 'text-blue-400 hover:text-blue-300'">
                        {{ copiedGroupId === g.group_id ? '已複製 ✓' : '複製' }}
                      </button>
                    </div>
                  </div>
                  <p v-else class="mt-1 text-[11px] text-gray-600">尚無偵測到群組，請先將 Bot 加入廠商 LINE 群組</p>
                </div>

                <!-- 叫貨系統 -->
                <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748] pt-2">叫貨系統</div>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" v-model="form.show_in_ordering" class="w-4 h-4 rounded accent-orange-500" />
                  <span class="text-[#9ca3af] text-[13px] font-semibold">出現在前台叫貨/盤點系統</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" v-model="form.is_fixed_order" class="w-4 h-4 rounded accent-orange-500" />
                  <span class="text-[#9ca3af] text-[13px] font-semibold">固定叫貨排程</span>
                </label>
                <div v-if="form.is_fixed_order" class="p-3 rounded-lg space-y-3" style="background:#0f1117;border:1px solid #2d3748">
                  <div>
                    <label class="block text-[#9ca3af] text-[12px] font-semibold mb-2">需叫貨星期</label>
                    <div class="flex gap-2 flex-wrap">
                      <label v-for="(day, idx) in ['一','二','三','四','五','六','日']" :key="idx+1"
                        class="flex flex-col items-center gap-1 cursor-pointer">
                        <input type="checkbox" :value="idx+1" v-model="form.order_days" class="w-4 h-4 accent-orange-500" />
                        <span class="text-[11px]" :class="form.order_days.includes(idx+1) ? 'text-orange-400 font-bold' : 'text-gray-500'">{{ day }}</span>
                      </label>
                    </div>
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[12px] font-semibold mb-1">應下單截止時間</label>
                    <input v-model="form.order_time" type="time"
                      class="bg-[#1a202c] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-400" />
                  </div>
                </div>

                <!-- 財務與付款 -->
                <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748] pt-2">財務與付款</div>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">付款方式</label>
                    <select v-model="form.payment_method"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                      <option v-for="o in paymentMethodOptions" :key="o" :value="o">{{ o }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">金流科目</label>
                    <select v-model="form.default_category_id"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                      <option :value="null">（不設定）</option>
                      <option v-for="c in cashflowCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">付款條件</label>
                    <select v-model="form.payment_terms"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                      <option v-for="o in paymentTermsOptions" :key="o" :value="o">{{ o }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">到期前提醒天數</label>
                    <select v-model.number="form.reminder_days"
                      class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                      <option v-for="d in reminderDaysOptions" :key="d" :value="d">{{ d }} 天前</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">匯款帳號</label>
                  <input v-model="form.bank_account" type="text" placeholder="004-012-345-678901"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                </div>
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">戶名</label>
                  <input v-model="form.bank_account_holder" type="text"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                </div>

                <!-- 到貨設定 -->
                <div class="p-3 rounded-lg space-y-3" style="background:#0f1117;border:1px solid #2d3748">
                  <p class="text-[#9ca3af] text-[12px] font-bold uppercase tracking-wide">到貨設定</p>
                  <div class="flex items-center gap-3">
                    <label class="text-[#9ca3af] text-[13px] font-semibold shrink-0">到貨日</label>
                    <span class="text-gray-400 text-sm">D+</span>
                    <input v-model.number="form.delivery_days_to_arrive" type="number" min="0" max="30"
                      class="w-20 bg-[#1a202c] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-400" />
                    <span class="text-gray-500 text-xs">天後到貨</span>
                  </div>
                  <div>
                    <label class="block text-[#9ca3af] text-[12px] font-semibold mb-2">休息日星期</label>
                    <div class="flex gap-2 flex-wrap">
                      <label v-for="(day, idx) in ['一','二','三','四','五','六','日']" :key="idx+1"
                        class="flex flex-col items-center gap-1 cursor-pointer">
                        <input type="checkbox" :value="idx+1" v-model="form.closed_days" class="w-4 h-4 accent-red-500" />
                        <span class="text-[11px]" :class="form.closed_days.includes(idx+1) ? 'text-red-400 font-bold' : 'text-gray-500'">{{ day }}</span>
                      </label>
                    </div>
                  </div>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" v-model="form.closed_on_holidays" class="w-4 h-4 rounded accent-red-500" />
                    <span class="text-[#9ca3af] text-[13px] font-semibold">國定假日休息</span>
                  </label>
                </div>

                <!-- 免運門檻 + 備注 -->
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">免運門檻（元）</label>
                  <input v-model.number="form.free_shipping_threshold" type="number" min="0" placeholder="0 = 不設定"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                </div>
                <div>
                  <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">備注</label>
                  <textarea v-model="form.note" rows="2" placeholder="廠商備注、注意事項…"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed] text-sm resize-none"></textarea>
                </div>

                <div v-if="saveError" class="text-red-400 text-xs">{{ saveError }}</div>
                <div class="flex gap-3 pt-2">
                  <button @click="showNewModal=false" class="flex-1 py-2.5 rounded-xl border border-[#2d3748] text-gray-400 font-bold text-sm">取消</button>
                  <button @click="saveStep1" :disabled="saving"
                    class="flex-[2] py-2.5 rounded-xl bg-[#63b3ed] text-black font-bold text-sm disabled:opacity-40">
                    {{ saving ? '儲存中…' : '下一步：設定供應品項 →' }}
                  </button>
                </div>
              </div>

              <!-- Step 2: 供應品項 -->
              <div v-else-if="newStep === 2" class="p-6 space-y-4 text-sm">
                <p class="text-gray-400">供應商：<span class="text-gray-200 font-bold">{{ newVendorName }}</span></p>
                <p class="text-gray-500 text-xs">從品項庫勾選此供應商的供應品項，並輸入採購單價（選填）</p>
                <input v-model="itemSearch" type="text" placeholder="搜尋品項名稱..."
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
                <div class="max-h-64 overflow-y-auto space-y-1 border border-[#2d3748] rounded-xl p-2">
                  <div v-if="!allItems.length" class="text-center py-4 text-gray-600">無品項資料</div>
                  <div v-for="item in filteredItems" :key="item.id"
                    class="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-[#0f1117] cursor-pointer"
                    @click="toggleItem(item.id)">
                    <input type="checkbox" :checked="selectedItemIds.has(item.id)"
                      class="w-4 h-4 accent-[#63b3ed]" @click.stop="toggleItem(item.id)" />
                    <span class="flex-1 text-gray-200">{{ item.name }}</span>
                    <span class="text-gray-500 text-xs">{{ item.unit }}</span>
                    <input v-if="selectedItemIds.has(item.id)"
                      v-model.number="itemPrices[item.id]"
                      type="number" placeholder="採購價" min="0" @click.stop
                      class="w-20 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-[#63b3ed]" />
                  </div>
                </div>
                <div class="text-xs text-gray-500">已勾選 {{ selectedItemIds.size }} 項</div>
                <div class="flex gap-3 pt-2">
                  <button @click="saveStep2" :disabled="saving"
                    class="flex-[2] py-2.5 rounded-xl bg-[#63b3ed] text-black font-bold text-sm disabled:opacity-40">
                    {{ saving ? '儲存中…' : '完成建立供應商' }}
                  </button>
                  <button @click="saveStep2" :disabled="saving"
                    class="flex-1 py-2.5 rounded-xl border border-[#2d3748] text-gray-400 font-bold text-sm disabled:opacity-40">
                    略過，直接完成
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
          <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
                <th class="px-4 py-3 text-left">供應商名稱</th>
                <th class="px-4 py-3 text-left">科目</th>
                <th class="px-4 py-3 text-left">付款方式</th>
                <th class="px-4 py-3 text-left">到貨日</th>
                <th class="px-4 py-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#2d3748]">
              <tr v-for="v in filtered" :key="v.id"
                class="cursor-pointer transition-colors"
                :class="selectedId === v.id ? 'bg-[#1e3a5f]' : 'hover:bg-[#1f2937]'"
                @click="selectVendor(v)">
                <td class="px-4 py-3 font-semibold text-gray-200">{{ v.name }}</td>
                <td class="px-4 py-3 text-gray-400 text-xs">
                  <span v-if="v.default_category_id"
                    class="px-2 py-0.5 rounded bg-[#2d3748] text-[#9ca3af]">
                    {{ cashflowCategories.find(c => c.id === v.default_category_id)?.name || '—' }}
                  </span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <td class="px-4 py-3 text-gray-400">{{ v.payment_method || '—' }}</td>
                <td class="px-4 py-3 text-gray-400 text-xs">{{ v.delivery_days_to_arrive ? 'D+' + v.delivery_days_to_arrive : '—' }}</td>
                <td class="px-4 py-3 text-center">
                  <button @click.stop="selectVendor(v)"
                    class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
                </td>
              </tr>
              <tr v-if="filtered.length === 0">
                <td colspan="5" class="px-4 py-10 text-center text-gray-600">無供應商資料</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right: Form -->
      <div>
        <div v-if="!isNew && !selectedId"
          class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-8 text-center text-gray-600 mt-12">
          <p class="text-3xl mb-3">🏪</p>
          <p>點擊左側供應商進行編輯<br>或點擊「新增供應商」建立新記錄</p>
        </div>

        <div v-else class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 max-h-[800px] overflow-y-auto">
          <div class="flex justify-between items-center mb-5">
            <h3 class="text-base font-bold text-gray-100">{{ isNew ? '新增供應商' : '編輯供應商' }}</h3>
            <button v-if="!isNew" @click="deleteVendor"
              class="text-xs text-red-400 hover:text-red-300 font-bold border border-red-800 hover:border-red-600 px-2 py-1 rounded transition-colors">
              刪除
            </button>
          </div>

          <div class="space-y-4 text-sm">
            <!-- 基本資訊 -->
            <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748]">
              基本資訊
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                供應商名稱 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.name" type="text" maxlength="50"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  聯絡人 <span class="text-red-400">*</span>
                </label>
                <input v-model="form.contact_person" type="text" maxlength="30"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  電話 <span class="text-red-400">*</span>
                </label>
                <input v-model="form.phone" type="text"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
              </div>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">LINE 群組</label>
              <!-- 手動輸入 Group ID -->
              <div class="flex items-center gap-2">
                <input v-model="form.line_id" type="text" placeholder="貼上 Group ID（C...）"
                  class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 font-mono text-xs focus:outline-none focus:border-[#63b3ed]" />
                <button v-if="form.line_id" @click="clearLineGroup"
                  class="text-gray-500 hover:text-red-400 text-sm transition-colors shrink-0" title="清除">✕</button>
              </div>
              <!-- 偵測到的群組清單 -->
              <div v-if="linePendingGroups.length > 0" class="mt-2 space-y-1">
                <p class="text-[11px] text-gray-600">偵測到的群組（點複製後貼入上方）：</p>
                <div v-for="g in linePendingGroups" :key="g.id"
                  class="flex items-center gap-2 bg-[#0f1117] border border-[#2d3748] rounded-lg px-2.5 py-1.5">
                  <span class="flex-1 font-mono text-[11px] text-gray-300 break-all">{{ g.group_id }}</span>
                  <span class="text-[10px] text-gray-600 shrink-0">{{ formatGroupDate(g.first_seen) }}</span>
                  <button @click="copyGroupId(g.group_id)"
                    class="shrink-0 text-[11px] px-2 py-0.5 rounded transition-colors"
                    :class="copiedGroupId === g.group_id ? 'bg-emerald-700/50 text-emerald-400' : 'text-blue-400 hover:text-blue-300'">
                    {{ copiedGroupId === g.group_id ? '已複製 ✓' : '複製' }}
                  </button>
                </div>
              </div>
              <p v-else class="mt-1 text-[11px] text-gray-600">尚無偵測到群組，請先將 Bot 加入廠商 LINE 群組</p>
            </div>

            <!-- 叫貨系統設定 -->
            <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748] pt-2">
              叫貨系統
            </div>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="form.show_in_ordering"
                class="w-4 h-4 rounded accent-orange-500" />
              <span class="text-[#9ca3af] text-[13px] font-semibold">出現在前台叫貨/盤點系統</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer mt-1">
              <input type="checkbox" v-model="form.is_fixed_order"
                class="w-4 h-4 rounded accent-orange-500" />
              <span class="text-[#9ca3af] text-[13px] font-semibold">固定叫貨排程</span>
            </label>
            <div v-if="form.is_fixed_order" class="mt-2 p-3 rounded-lg space-y-3" style="background:#0f1117;border:1px solid #2d3748">
              <!-- 需叫貨星期 -->
              <div>
                <label class="block text-[#9ca3af] text-[12px] font-semibold mb-2">需叫貨星期 <span class="text-gray-600 font-normal">（排程參考，不限制叫貨）</span></label>
                <div class="flex gap-2 flex-wrap">
                  <label v-for="(day, idx) in ['一','二','三','四','五','六','日']" :key="idx+1"
                    class="flex flex-col items-center gap-1 cursor-pointer">
                    <input type="checkbox" :value="idx+1" v-model="form.order_days"
                      class="w-4 h-4 accent-orange-500" />
                    <span class="text-[11px]" :class="form.order_days.includes(idx+1) ? 'text-orange-400 font-bold' : 'text-gray-500'">
                      {{ day }}
                    </span>
                  </label>
                </div>
              </div>
              <!-- 截單時間 -->
              <div>
                <label class="block text-[#9ca3af] text-[12px] font-semibold mb-1">應下單截止時間</label>
                <input v-model="form.order_time" type="time"
                  class="bg-[#1a202c] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-400" />
                <span class="text-[11px] text-gray-600 ml-2">當天此時間前需下單</span>
              </div>
            </div>

            <!-- 財務與付款 -->
            <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748] pt-2">
              財務與付款
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  付款方式 <span class="text-red-400">*</span>
                </label>
                <select v-model="form.payment_method"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="o in paymentMethodOptions" :key="o" :value="o">{{ o }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">金流科目</label>
                <select v-model="form.default_category_id"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option :value="null">（不設定）</option>
                  <option v-for="c in cashflowCategories" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  付款條件 <span class="text-red-400">*</span>
                </label>
                <select v-model="form.payment_terms"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="o in paymentTermsOptions" :key="o" :value="o">{{ o }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">到期前提醒天數</label>
                <select v-model.number="form.reminder_days"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="d in reminderDaysOptions" :key="d" :value="d">{{ d }} 天前</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">匯款帳號</label>
              <input v-model="form.bank_account" type="text" placeholder="004-012-345-678901"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">戶名</label>
              <input v-model="form.bank_account_holder" type="text"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <!-- 到貨日 + 休息日設定 -->
            <div class="p-3 rounded-lg space-y-3" style="background:#0f1117;border:1px solid #2d3748">
              <p class="text-[#9ca3af] text-[12px] font-bold uppercase tracking-wide">到貨設定</p>
              <div class="flex items-center gap-3">
                <label class="text-[#9ca3af] text-[13px] font-semibold shrink-0">到貨日</label>
                <span class="text-gray-400 text-sm">D+</span>
                <input v-model.number="form.delivery_days_to_arrive" type="number" min="0" max="30"
                  class="w-20 bg-[#1a202c] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-orange-400" />
                <span class="text-gray-500 text-xs">天後到貨</span>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[12px] font-semibold mb-2">休息日星期</label>
                <div class="flex gap-2 flex-wrap">
                  <label v-for="(day, idx) in ['一','二','三','四','五','六','日']" :key="idx+1"
                    class="flex flex-col items-center gap-1 cursor-pointer">
                    <input type="checkbox" :value="idx+1" v-model="form.closed_days" class="w-4 h-4 accent-red-500" />
                    <span class="text-[11px]" :class="form.closed_days.includes(idx+1) ? 'text-red-400 font-bold' : 'text-gray-500'">
                      {{ day }}
                    </span>
                  </label>
                </div>
              </div>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" v-model="form.closed_on_holidays" class="w-4 h-4 rounded accent-red-500" />
                <span class="text-[#9ca3af] text-[13px] font-semibold">國定假日休息</span>
              </label>
            </div>

            <!-- 免運門檻 + 備注 -->
            <div class="flex gap-3 items-end">
              <div class="flex-1">
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">免運門檻（元）</label>
                <input v-model.number="form.free_shipping_threshold" type="number" min="0" placeholder="0 = 不設定"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
              </div>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">備注</label>
              <textarea v-model="form.note" rows="2" placeholder="廠商備注、注意事項…"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed] text-sm resize-none"></textarea>
            </div>

            <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

            <button @click="save" :disabled="saving"
              class="w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50 text-sm"
              style="height:44px;">
              {{ saving ? '儲存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
