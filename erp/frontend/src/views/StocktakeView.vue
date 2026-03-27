<script setup>
import { ref, computed, onMounted, onUnmounted, toRaw } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ── State ──────────────────────────────────────
const groups = ref([])
const vendors = ref([])
const selectedGroup = ref(null)   // null = 全部品項
const items = ref([])
const loading = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const showOrderSheets = ref(false)
const vendorSheets = ref([])       // [{ vendor_id, vendor_name, items: [], total, text }]
const vendorDeliveryDates = ref({})  // { vendor_id: 'YYYY-MM-DD' }

// Mode toggles (independent, both can be on)
const modeStocktake = ref(true)   // 📋 盤點
const modeOrder = ref(true)       // 📦 叫貨

// counts: { item_id: { actual: number|null, order: number|null } }
const counts = ref({})

// ── D+X 到貨日計算（含廠商休息日遞延）──────────────────
// closed_days DB 格式：1=週一 … 7=週日；JS getDay()：0=週日, 1=週一 … 6=週六
function calcDeliveryDate(vendor) {
  if (!vendor) return ''
  const daysToAdd = vendor.delivery_days_to_arrive || 1
  const closedSet = new Set((vendor.closed_days || []).map(d => d === 7 ? 0 : d))
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + daysToAdd)
  let safety = 0
  while (closedSet.has(date.getDay()) && safety++ < 7) {
    date.setDate(date.getDate() + 1)
  }
  // 用本地時區格式化，避免 toISOString() 的 UTC 偏移問題
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

// 品項依廠商分組
const itemsByVendor = computed(() => {
  const map = {}
  for (const item of items.value) {
    const vid = item.vendor_id || 0
    if (!map[vid]) {
      // 優先從已載入的 vendors ref 查廠商名稱
      const vendorObj = vendors.value.find(v => v.id === vid)
      map[vid] = { vendor_id: vid, vendor_name: vendorObj?.name || item.vendor_name || '其他', items: [] }
    }
    map[vid].items.push(item)
  }
  return Object.values(map)
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

// ── Load groups ──────────────────────────────────
onMounted(async () => {
  try {
    const [gRes, vRes] = await Promise.all([
      fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
    ])
    if (gRes.ok) groups.value = await gRes.json()
    if (vRes.ok) {
      vendors.value = await vRes.json()
      vendors.value.forEach(v => { vendorDeliveryDates.value[v.id] = calcDeliveryDate(v) })
    }
  } catch {}

  // O5: 讀取 route.query.group 自動選取群組
  const queryGroupId = parseInt(route.query.group)
  if (queryGroupId && groups.value.length) {
    const g = groups.value.find(g => g.id === queryGroupId)
    if (g) {
      await loadItems(g)
    } else {
      await loadItems(null)
    }
  } else {
    await loadItems(null)
  }

  // Draft auto-save (P3-3)
  loadDraftBanner()
  _draftTimer = setInterval(() => { saveDraft() }, 30000)
})

onUnmounted(() => { if (_draftTimer) clearInterval(_draftTimer) })

async function loadItems(group) {
  selectedGroup.value = group
  counts.value = {}
  loading.value = true
  try {
    const url = group
      ? `${API_BASE}/inventory/items?stocktake_group_id=${group.id}&limit=200`
      : `${API_BASE}/inventory/items?limit=200`
    const res = await fetch(url, { headers: authHeaders() })
    items.value = res.ok ? await res.json() : []
  } finally { loading.value = false }
}

// ── Count helpers ──────────────────────────────────
function getActual(id) { return counts.value[id]?.actual ?? null }
function getOrder(id) { return counts.value[id]?.order ?? null }
function setActual(id, val) {
  if (!counts.value[id]) counts.value[id] = { actual: null, order: null }
  const n = val === '' ? null : parseFloat(val)
  counts.value[id].actual = isNaN(n) ? null : n
  // auto-suggest order qty
  if (!counts.value[id].orderManual) autoSuggestOrder(id)
}
function setOrder(id, val) {
  if (!counts.value[id]) counts.value[id] = { actual: null, order: null, orderManual: true }
  counts.value[id].orderManual = true
  const n = val === '' ? null : parseFloat(val)
  counts.value[id].order = isNaN(n) ? null : n
}
function incrementActual(id) { setActual(id, (getActual(id) ?? 0) + 1) }
function decrementActual(id) { setActual(id, Math.max(0, (getActual(id) ?? 0) - 1)) }
function incrementOrder(id) { setOrder(id, (getOrder(id) ?? 0) + 1) }
function decrementOrder(id) { setOrder(id, Math.max(0, (getOrder(id) ?? 0) - 1)) }

function autoSuggestOrder(id) {
  const item = items.value.find(i => i.id === id)
  if (!item) return
  const min = parseFloat(item.min_stock) || 0
  if (min <= 0) return
  const actual = counts.value[id]?.actual ?? parseFloat(item.current_stock) ?? 0
  const suggested = Math.max(0, Math.ceil(min - actual))
  counts.value[id].order = suggested
}

// ── Diff indicators ──────────────────────────────────
function actualDiff(item) {
  const actual = getActual(item.id)
  if (actual === null) return null
  const sys = parseFloat(item.current_stock) || 0
  return actual - sys
}
function actualStatus(item) {
  const diff = actualDiff(item)
  if (diff === null) return null
  if (diff === 0) return { text: '相符 ✓', cls: 'text-emerald-500' }
  return { text: `差 ${diff > 0 ? '+' : ''}${diff} ⚠️`, cls: 'text-red-500' }
}
function orderStatus(item) {
  const qty = getOrder(item.id)
  if (qty === null) return null
  if (qty === 0) return { text: '不需叫貨', cls: 'text-slate-400' }
  const min = parseFloat(item.min_stock) || 0
  return { text: `建議 ${qty} ✓`, cls: 'text-emerald-600' }
}

// ── Progress ──────────────────────────────────
const filledCount = computed(() =>
  items.value.filter(i => getActual(i.id) !== null).length
)
const diffCount = computed(() =>
  items.value.filter(i => { const d = actualDiff(i); return d !== null && d !== 0 }).length
)
const pendingOrderCount = computed(() =>
  items.value.filter(i => (getOrder(i.id) ?? 0) > 0).length
)
const singleMode = computed(() => modeStocktake.value !== modeOrder.value)
const progressPct = computed(() =>
  items.value.length > 0 ? Math.round((filledCount.value / items.value.length) * 100) : 0
)

// ── Vendor grouping for order sheets ──────────────────
function buildSheetText(v) {
  const delivDate = vendorDeliveryDates.value[v.vendor_id]
  const today = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric' })
  let text = `【叫貨單】${v.vendor_name}\n日期：${today}\n──────────\n`
  v.items.forEach(i => { text += `${i.name} × ${i.orderQty} ${i.unit || ''}\n` })
  text += `──────────`
  if (v.total > 0) text += `\n合計金額 $${v.total.toLocaleString('zh-TW')}`
  if (delivDate) {
    const d = new Date(delivDate + 'T00:00:00')
    text += `\n預計到貨：${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`
  }
  return text
}

function buildVendorSheets() {
  const map = {}
  items.value.forEach(item => {
    const qty = getOrder(item.id) ?? 0
    if (qty <= 0) return
    const vid = item.vendor_id || 0
    const vname = item.vendor_name || '未分類廠商'
    if (!map[vid]) map[vid] = { vendor_id: vid, vendor_name: vname, items: [], total: 0 }
    map[vid].items.push({ ...item, orderQty: qty })
    map[vid].total += qty * (parseFloat(item.price) || 0)
  })
  vendorSheets.value = Object.values(map).map(v => ({
    ...v,
    text: buildSheetText(v),
    copied: false
  }))
}

function onSheetDateChange(sheet) {
  sheet.text = buildSheetText(sheet)
  sheet.copied = false
}

async function copySheet(sheet) {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(sheet.text)
    else { const ta = document.createElement('textarea'); ta.value = sheet.text; ta.style.cssText = 'position:fixed;left:-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta) }
    sheet.copied = true
    setTimeout(() => { sheet.copied = false }, 2000)
  } catch {}
}

// ── Submit ──────────────────────────────────────
async function submit() {
  submitting.value = true
  try {
    const createRes = await fetch(`${API_BASE}/stocktake/`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ group_id: selectedGroup.value?.id || null, mode: modeStocktake.value && modeOrder.value ? 'both' : modeStocktake.value ? 'stocktake' : 'order' })
    })
    if (!createRes.ok) throw new Error('建立盤點失敗')
    const session = await createRes.json()

    const itemPayloads = items.value
      .filter(i => getActual(i.id) !== null)
      .map(i => ({ item_id: i.id, counted_qty: getActual(i.id) }))

    if (itemPayloads.length > 0) {
      await fetch(`${API_BASE}/stocktake/${session.id}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ items: itemPayloads })
      })
    }
    await fetch(`${API_BASE}/stocktake/${session.id}/submit`, { method: 'PUT', headers: authHeaders() })

    // O5: 是否需要顯示下次盤點日 dialog
    _pendingNextDue = shouldShowNextDue()
    if (_pendingNextDue) computeNextDue()

    if (modeOrder.value && pendingOrderCount.value > 0) {
      buildVendorSheets()
      showOrderSheets.value = true
    } else if (_pendingNextDue) {
      _pendingNextDue = false
      showNextDueModal.value = true
    } else {
      submitted.value = true
    }
  } catch (e) {
    alert('提交失敗：' + (e.message || '請稍後再試'))
  } finally { submitting.value = false }
}

function closeOrderSheets() {
  showOrderSheets.value = false
  if (_pendingNextDue) {
    _pendingNextDue = false
    showNextDueModal.value = true
  } else {
    submitted.value = true
  }
}

function reset() {
  submitted.value = false; showOrderSheets.value = false
  showNextDueModal.value = false; editingNextDue.value = false
  counts.value = {}
  loadItems(selectedGroup.value)
}

function isLowStock(item) {
  return parseFloat(item.min_stock) > 0 && parseFloat(item.current_stock) <= parseFloat(item.min_stock)
}

// ── 草稿自動儲存 (P3-3) ──────────────────────────
const draftBanner = ref(null)
const DRAFT_KEY = () => `draft:stocktake:${auth.user?.id || 'anon'}`
const DRAFT_TTL = 48 * 60 * 60 * 1000

function saveDraft() {
  if (Object.keys(counts.value).length === 0) return
  try {
    const rawCounts = toRaw(counts.value)
    const draft = {
      timestamp: Date.now(),
      groupId: selectedGroup.value?.id || null,
      groupName: selectedGroup.value?.name || '全部品項',
      counts: rawCounts,
      modeStocktake: modeStocktake.value,
      modeOrder: modeOrder.value
    }
    localStorage.setItem(DRAFT_KEY(), JSON.stringify(draft))
  } catch (e) {
    console.error('Draft save failed:', e)
  }
}

function loadDraftBanner() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY())
    if (!raw) return
    const draft = JSON.parse(raw)
    if (Date.now() - draft.timestamp > DRAFT_TTL) { localStorage.removeItem(DRAFT_KEY()); return }
    draftBanner.value = draft
  } catch { localStorage.removeItem(DRAFT_KEY()) }
}

async function resumeDraft() {
  const draft = draftBanner.value
  if (!draft) return
  draftBanner.value = null
  modeStocktake.value = draft.modeStocktake ?? true
  modeOrder.value = draft.modeOrder ?? true
  const g = groups.value.find(g => g.id === draft.groupId) || null
  await loadItems(g)
  counts.value = draft.counts
  localStorage.removeItem(DRAFT_KEY())
}

function discardDraft() {
  localStorage.removeItem(DRAFT_KEY())
  draftBanner.value = null
}

let _draftTimer = null

// ── O5: 下次盤點日 Dialog ──────────────────────────
const showNextDueModal = ref(false)
const nextDueDate = ref('')
const editingNextDue = ref(false)
const nextDueSaving = ref(false)
const nextDueGroupId = ref(null)
let _pendingNextDue = false

function shouldShowNextDue() {
  return modeStocktake.value && selectedGroup.value?.stocktake_cycle_days
}

function computeNextDue() {
  const group = selectedGroup.value
  if (!group?.stocktake_cycle_days) return
  const base = group.next_stocktake_due
    ? new Date(group.next_stocktake_due + 'T00:00:00')
    : new Date()
  base.setDate(base.getDate() + group.stocktake_cycle_days)
  nextDueDate.value = base.toISOString().split('T')[0]
  nextDueGroupId.value = group.id
}

async function confirmNextDue() {
  if (editingNextDue.value && nextDueGroupId.value) {
    nextDueSaving.value = true
    try {
      await fetch(`${API_BASE}/stocktake/groups/${nextDueGroupId.value}/next-due`, {
        method: 'PATCH', headers: authHeaders(),
        body: JSON.stringify({ next_due: nextDueDate.value })
      })
    } catch {}
    nextDueSaving.value = false
  }
  showNextDueModal.value = false
  editingNextDue.value = false
  submitted.value = true
}

function fmtNextDueDisplay(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric', weekday: 'short' })
}

// ── 差異分析 Sheet (P3-3) ──────────────────────────
const showDiscrepancy = ref(false)
const discrepancyItem = ref(null)
const discrepancyData = ref(null)
const discrepancyLoading = ref(false)

async function openDiscrepancy(item) {
  discrepancyItem.value = item
  discrepancyData.value = null
  showDiscrepancy.value = true
  discrepancyLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/items/${item.id}/discrepancy-analysis?days=7`, { headers: authHeaders() })
    if (res.ok) discrepancyData.value = await res.json()
  } catch {}
  finally { discrepancyLoading.value = false }
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-32">

    <!-- Header -->
    <div class="bg-white border-b border-slate-100 sticky top-0 z-10">
      <div class="px-4 pt-12 pb-2 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button @click="router.push({ name: 'order' })" class="text-orange-500 font-bold text-lg">‹</button>
          <h1 class="text-lg font-extrabold text-slate-800">盤點叫貨</h1>
        </div>
        <p class="text-xs text-slate-400">
          {{ new Date().toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) }}
        </p>
      </div>

      <!-- Group chips -->
      <div class="px-3 pb-3 space-y-2">
        <div class="flex items-center justify-between">
          <p class="text-[10px] font-bold text-slate-400 uppercase">盤點群組</p>
        </div>
        <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          <button @click="loadItems(null)"
            class="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all"
            :class="!selectedGroup ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-500'">
            全部品項
          </button>
          <button v-for="g in groups" :key="g.id" @click="loadItems(g)"
            class="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all"
            :class="selectedGroup?.id===g.id ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-500'">
            {{ g.name }}
          </button>
        </div>

        <!-- Dual mode toggles -->
        <div class="flex gap-2">
          <button @click="modeStocktake = !modeStocktake"
            class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all"
            :class="modeStocktake ? 'text-white border-orange-500' : 'bg-white border-slate-200 text-slate-400'"
            :style="modeStocktake ? 'background:#e85d04' : ''">
            📋 盤點{{ modeStocktake ? ' ✓' : '' }}
          </button>
          <button @click="modeOrder = !modeOrder"
            class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all"
            :class="modeOrder ? 'text-white border-emerald-500 bg-emerald-500' : 'bg-white border-slate-200 text-slate-400'">
            📦 叫貨{{ modeOrder ? ' ✓' : '' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 草稿恢復 banner (P3-3) -->
    <div v-if="draftBanner && !submitted && !showOrderSheets" class="mx-3 mt-3 rounded-xl px-3 py-2.5 bg-amber-50 border border-amber-200">
      <p class="text-xs font-bold text-amber-800">📌 發現未完成的盤點草稿（{{ draftBanner.groupName }}）</p>
      <div class="flex gap-2 mt-1.5">
        <button @click="resumeDraft" class="flex-1 bg-orange-500 text-white text-xs font-bold py-1.5 rounded-lg">繼續編輯</button>
        <button @click="discardDraft" class="flex-1 bg-slate-200 text-slate-600 text-xs font-bold py-1.5 rounded-lg">丟棄草稿</button>
      </div>
    </div>

    <!-- Success screen -->
    <div v-if="submitted" class="flex flex-col items-center justify-center px-6 py-20 text-center">
      <div class="text-6xl mb-4">✅</div>
      <h2 class="text-xl font-extrabold text-slate-800">盤點已提交</h2>
      <p class="text-slate-400 text-sm mt-2">庫存數量已更新</p>
      <button @click="reset" class="mt-8 bg-orange-500 text-white font-bold px-8 py-3 rounded-2xl">繼續盤點</button>
    </div>

    <!-- Vendor order sheets -->
    <div v-else-if="showOrderSheets" class="pb-24">
      <div class="px-4 py-4 text-center">
        <p class="text-2xl mb-1">✅</p>
        <p class="text-base font-extrabold text-slate-800">盤點已提交！</p>
        <p class="text-xs text-slate-400 mt-1">以下為各廠商叫貨單，請複製後傳送</p>
      </div>
      <div class="px-4 space-y-4">
        <div v-for="sheet in vendorSheets" :key="sheet.vendor_id"
          class="bg-white rounded-xl shadow-sm p-4">
          <div class="flex items-center justify-between mb-2">
            <p class="font-extrabold text-slate-800">{{ sheet.vendor_name }}</p>
            <span class="text-xs font-bold bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
              {{ sheet.items.length }} 項
            </span>
          </div>
          <!-- 到貨日期（可調整） -->
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs text-slate-500 font-bold">預計到貨</span>
            <input
              v-model="vendorDeliveryDates[sheet.vendor_id]"
              type="date"
              @change="onSheetDateChange(sheet)"
              class="flex-1 text-sm border border-slate-200 rounded-xl px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-orange-300" />
          </div>
          <pre class="bg-slate-50 border border-slate-200 rounded-xl p-3 text-xs text-slate-700 whitespace-pre-wrap font-mono">{{ sheet.text }}</pre>
          <button @click="copySheet(sheet)"
            class="mt-3 w-full text-white font-bold py-3 rounded-xl active:scale-95"
            :class="sheet.copied ? 'bg-emerald-500' : ''"
            :style="sheet.copied ? '' : 'background:#e85d04'">
            {{ sheet.copied ? '✓ 已複製' : '📋 複製 LINE 訊息' }}
          </button>
        </div>
        <button @click="closeOrderSheets" class="w-full py-3 bg-slate-100 text-slate-600 font-bold rounded-xl">
          完成，返回
        </button>
      </div>
    </div>

    <!-- Main content -->
    <div v-else-if="!loading">

      <!-- Progress card -->
      <div class="mx-4 mt-4 bg-white rounded-xl shadow-sm p-4">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-bold text-slate-500">進度</p>
          <div class="flex gap-3">
            <span class="text-xs font-bold text-red-500" v-if="diffCount > 0">差異 {{ diffCount }}</span>
            <span class="text-xs font-bold text-emerald-600" v-if="pendingOrderCount > 0">待叫 {{ pendingOrderCount }}</span>
          </div>
        </div>
        <div class="h-2.5 bg-slate-100 rounded-full overflow-hidden mb-2">
          <div class="h-full rounded-full transition-all duration-300 bg-orange-500"
            :style="{ width: progressPct + '%' }"></div>
        </div>
        <p class="text-xs text-slate-400">
          已盤 {{ filledCount }} / {{ items.length }} 品項
          <span v-if="selectedGroup"> · {{ selectedGroup.name }}</span>
          <span v-else> · 全部品項</span>
        </p>
      </div>

      <!-- Column headers -->
      <div v-if="modeStocktake || modeOrder" class="px-4 mt-3 mb-1">
        <div class="flex gap-2 text-[10px] font-bold text-slate-400 uppercase">
          <span class="flex-[2]">品項</span>
          <span v-if="modeStocktake" class="flex-1 text-center">實盤</span>
          <span v-if="modeOrder" class="flex-1 text-center" style="color:#16a34a">叫貨</span>
        </div>
      </div>

      <!-- Items（依廠商分組，群組盤點時加分隔線） -->
      <div class="px-4 space-y-2 pb-4">
        <template v-for="group in itemsByVendor" :key="group.vendor_id">
          <!-- 廠商分隔線（群組盤點 + 叫貨模式 + 多廠商時顯示） -->
          <div v-if="selectedGroup && itemsByVendor.length > 1 && modeOrder"
            class="flex items-center gap-2 pt-2 pb-1">
            <span class="text-xs font-extrabold text-slate-500">🏪 {{ group.vendor_name }}</span>
            <div class="flex-1 h-px bg-slate-200"></div>
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] text-slate-400">到貨日</span>
              <input
                v-model="vendorDeliveryDates[group.vendor_id]"
                type="date"
                class="text-[11px] border border-slate-200 rounded-lg px-2 py-0.5 text-slate-600 focus:outline-none focus:ring-1 focus:ring-orange-300" />
            </div>
          </div>

        <div v-for="item in group.items" :key="item.id"
          class="bg-white rounded-xl shadow-sm overflow-hidden"
          :class="isLowStock(item) ? 'border-l-4 border-l-red-400' : 'border-l-4 border-l-slate-100'">
          <div class="p-3">
            <!-- Item header -->
            <div class="flex items-start gap-2 mb-2">
              <div class="flex-[2] min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <p class="font-bold text-slate-800" style="font-size:12px">{{ item.name }}</p>
                  <span v-if="item.vendor_name" class="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-bold">
                    {{ item.vendor_name }}
                  </span>
                </div>
                <p class="text-[10px] text-slate-400 mt-0.5">
                  系統 {{ item.current_stock || 0 }} {{ item.unit }} · 安全庫存 {{ item.min_stock || 0 }} {{ item.unit }}
                </p>
              </div>
              <!-- 🔍 差異分析按鈕 (P3-3) -->
              <button @click="openDiscrepancy(item)"
                class="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg bg-slate-100 text-slate-500 active:bg-slate-200 text-sm">
                🔍
              </button>
            </div>

            <!-- Single mode: compact 1-row layout -->
            <template v-if="singleMode">
              <!-- 實盤 compact -->
              <div v-if="modeStocktake" class="flex items-center gap-2 mt-1">
                <button @click="decrementActual(item.id)"
                  class="w-8 h-8 bg-slate-200 rounded-full flex items-center justify-center font-bold text-slate-600 text-lg active:bg-slate-300 shrink-0">−</button>
                <input
                  :value="getActual(item.id) ?? ''"
                  @input="setActual(item.id, $event.target.value)"
                  type="number" min="0" inputmode="decimal"
                  :placeholder="item.unit"
                  class="flex-1 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none py-1"
                  :class="getActual(item.id) !== null ? 'border-orange-400 text-orange-600' : 'border-slate-300 text-slate-700'" />
                <span class="text-xs text-slate-400 shrink-0">{{ item.unit }}</span>
                <button @click="incrementActual(item.id)"
                  class="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 text-lg active:bg-orange-200 shrink-0">+</button>
              </div>
              <!-- 叫貨 compact -->
              <div v-if="modeOrder" class="flex items-center gap-2 mt-1">
                <button @click="decrementOrder(item.id)"
                  class="w-8 h-8 bg-emerald-100 rounded-full flex items-center justify-center font-bold text-emerald-600 text-lg active:bg-emerald-200 shrink-0">−</button>
                <input
                  :value="getOrder(item.id) ?? ''"
                  @input="setOrder(item.id, $event.target.value)"
                  type="number" min="0" inputmode="decimal"
                  :placeholder="item.unit"
                  class="flex-1 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none py-1"
                  :class="getOrder(item.id) !== null && getOrder(item.id) > 0 ? 'border-emerald-400 text-emerald-700' : 'border-emerald-200 text-slate-700'" />
                <span class="text-xs text-slate-400 shrink-0">{{ item.unit }}</span>
                <button @click="incrementOrder(item.id)"
                  class="w-8 h-8 bg-emerald-100 rounded-full flex items-center justify-center font-bold text-emerald-600 text-lg active:bg-emerald-200 shrink-0">+</button>
              </div>
            </template>

            <!-- Dual mode: two columns -->
            <div v-else class="flex gap-2">
              <!-- 實盤 column -->
              <div v-if="modeStocktake" class="flex-1 rounded-xl p-2" style="background:#f8fafc">
                <p class="text-[9px] font-bold text-slate-400 text-center mb-1.5">實盤</p>
                <div class="flex items-center justify-center gap-1">
                  <button @click="decrementActual(item.id)"
                    class="w-7 h-7 bg-slate-200 rounded-full flex items-center justify-center font-bold text-slate-600 text-base leading-none active:bg-slate-300">−</button>
                  <input
                    :value="getActual(item.id) ?? ''"
                    @input="setActual(item.id, $event.target.value)"
                    type="number" min="0" inputmode="decimal"
                    :placeholder="item.unit"
                    class="w-12 text-center border-b-2 font-extrabold text-sm bg-transparent focus:outline-none"
                    :class="getActual(item.id) !== null ? 'border-orange-400 text-orange-600' : 'border-slate-300 text-slate-700'" />
                  <button @click="incrementActual(item.id)"
                    class="w-7 h-7 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 text-base leading-none active:bg-orange-200">+</button>
                </div>
                <p v-if="actualStatus(item)" class="text-center mt-1" style="font-size:10px"
                  :class="actualStatus(item).cls">
                  {{ actualStatus(item).text }}
                </p>
              </div>

              <!-- 叫貨 column -->
              <div v-if="modeOrder" class="flex-1 rounded-xl p-2"
                style="background:#f0fdf4;border:1px solid #bbf7d0">
                <p class="text-[9px] font-bold text-center mb-1.5" style="color:#16a34a">叫貨</p>
                <div class="flex items-center justify-center gap-1">
                  <button @click="decrementOrder(item.id)"
                    class="w-7 h-7 bg-emerald-100 rounded-full flex items-center justify-center font-bold text-emerald-600 text-base leading-none active:bg-emerald-200">−</button>
                  <input
                    :value="getOrder(item.id) ?? ''"
                    @input="setOrder(item.id, $event.target.value)"
                    type="number" min="0" inputmode="decimal"
                    :placeholder="item.unit"
                    class="w-12 text-center border-b-2 font-extrabold text-sm bg-transparent focus:outline-none"
                    :class="getOrder(item.id) !== null && getOrder(item.id) > 0 ? 'border-emerald-400 text-emerald-700' : 'border-emerald-200 text-slate-700'" />
                  <button @click="incrementOrder(item.id)"
                    class="w-7 h-7 bg-emerald-100 rounded-full flex items-center justify-center font-bold text-emerald-600 text-base leading-none active:bg-emerald-200">+</button>
                </div>
                <p v-if="orderStatus(item)" class="text-center mt-1" style="font-size:10px"
                  :class="orderStatus(item).cls">
                  {{ orderStatus(item).text }}
                </p>
              </div>
            </div>
          </div>
        </div>
        </template>

        <div v-if="!items.length && !loading" class="text-center py-12 text-slate-400">
          此分組暫無品項
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-else class="flex justify-center py-16">
      <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full"></div>
    </div>

    <!-- Submit bar -->
    <div v-if="!submitted && !showOrderSheets && !showNextDueModal && !loading"
      class="fixed bottom-16 inset-x-0 px-4 py-3 bg-white border-t border-slate-100 shadow-lg z-20 flex gap-3">
      <div class="flex-1 flex flex-col justify-center">
        <p class="text-[10px] text-slate-400 font-bold">已盤點</p>
        <p class="text-base font-extrabold text-slate-900">{{ filledCount }} / {{ items.length }}</p>
      </div>
      <button @click="submit" :disabled="submitting || filledCount === 0"
        class="flex-[2] text-white font-bold py-3 rounded-2xl shadow active:scale-95 disabled:opacity-40 text-sm"
        style="background:#e85d04">
        <span v-if="submitting">提交中…</span>
        <span v-else-if="modeStocktake && modeOrder">✅ 提交盤點 + 叫貨</span>
        <span v-else-if="modeStocktake">💾 提交盤點</span>
        <span v-else>📦 提交叫貨</span>
      </button>
    </div>

    <!-- ═══ O5: 下次盤點日確認 Modal ═══ -->
    <div v-if="showNextDueModal" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="text-center">
            <div class="text-4xl mb-2">✅</div>
            <h3 class="text-lg font-extrabold text-slate-800">盤點完成！</h3>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2">
          <div class="bg-slate-50 rounded-xl p-4">
            <p class="text-xs font-bold text-slate-500 mb-2">下次預定盤點</p>
            <div v-if="!editingNextDue" class="flex items-center justify-between">
              <p class="text-base font-extrabold text-slate-800">{{ fmtNextDueDisplay(nextDueDate) }}</p>
              <button @click="editingNextDue = true"
                class="text-orange-500 font-bold text-sm px-3 py-1.5 rounded-lg bg-orange-50 active:bg-orange-100">
                修改 ✎
              </button>
            </div>
            <div v-else class="space-y-2">
              <input v-model="nextDueDate" type="date"
                class="w-full border-2 border-orange-400 rounded-xl px-3 py-2.5 text-slate-800 font-bold text-sm focus:outline-none" />
              <p class="text-xs text-slate-400 text-center">調整後，下下次將從此日期 + 週期天數計算</p>
            </div>
          </div>
        </div>

        <!-- Fixed bottom button -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
          <button @click="confirmNextDue" :disabled="nextDueSaving"
            class="w-full text-white font-bold py-3.5 rounded-2xl active:scale-95 disabled:opacity-50"
            style="background:#e85d04">
            {{ nextDueSaving ? '儲存中…' : '確認' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ═══ 差異分析 Sheet (P3-3) ═══ -->
    <div v-if="showDiscrepancy" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="flex justify-between items-center">
            <h3 class="text-base font-extrabold text-slate-800">
              🔍 {{ discrepancyItem?.name }} — 近 7 天紀錄
            </h3>
            <button @click="showDiscrepancy=false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4">
          <div v-if="discrepancyLoading" class="flex justify-center py-10">
            <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
          </div>

          <template v-else-if="discrepancyData">
            <!-- 到貨紀錄 -->
            <div>
              <p class="text-xs font-bold text-slate-500 uppercase mb-2">近 7 天到貨</p>
              <div v-if="discrepancyData.deliveries.length" class="space-y-1">
                <div v-for="(d,i) in discrepancyData.deliveries" :key="i"
                  class="flex justify-between text-sm bg-emerald-50 rounded-lg px-3 py-2">
                  <span class="text-slate-700">{{ d.date }} 到貨</span>
                  <span class="font-bold text-emerald-700">+{{ d.qty }} {{ d.unit }}</span>
                </div>
              </div>
              <p v-else class="text-xs text-slate-400 text-center py-2">近 7 天無到貨紀錄</p>
            </div>

            <!-- 損耗紀錄 -->
            <div>
              <p class="text-xs font-bold text-slate-500 uppercase mb-2">損耗紀錄</p>
              <div v-if="discrepancyData.wastes.length" class="space-y-1">
                <div v-for="(w,i) in discrepancyData.wastes" :key="i"
                  class="flex justify-between text-sm bg-red-50 rounded-lg px-3 py-2">
                  <span class="text-slate-700">{{ w.date }} {{ w.reason }}</span>
                  <span class="font-bold text-red-600">−{{ w.qty }} {{ w.unit }}</span>
                </div>
              </div>
              <p v-else class="text-xs text-slate-400 text-center py-2">近 7 天無損耗紀錄</p>
            </div>

            <!-- 分析摘要 -->
            <div class="bg-blue-50 rounded-xl p-3 border border-blue-100">
              <p class="text-xs font-bold text-blue-700 mb-1">💡 分析摘要</p>
              <p class="text-xs text-blue-800">{{ discrepancyData.analysis_summary }}</p>
              <p class="text-xs text-slate-400 mt-2">
                系統庫存：{{ discrepancyData.current_stock }} {{ discrepancyData.unit }}
                <span v-if="discrepancyData.total_received > 0"> · 近期到貨：+{{ discrepancyData.total_received }}</span>
                <span v-if="discrepancyData.total_waste > 0"> · 損耗：−{{ discrepancyData.total_waste }}</span>
              </p>
            </div>
          </template>

          <div v-else class="text-center py-10 text-slate-400">
            <p>無法載入分析資料</p>
          </div>
        </div>

        <!-- Fixed bottom button -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
          <button @click="showDiscrepancy=false"
            class="w-full py-3.5 bg-slate-100 text-slate-600 font-bold rounded-xl">
            關閉
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; }
input[type=number] { -moz-appearance: textfield; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
