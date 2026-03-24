<script setup>
import { ref, onMounted, computed, onUnmounted, toRaw } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import UserBadge from '@/components/UserBadge.vue'

const auth = useAuthStore()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ── Sub-tabs ──────────────────────────────────
const subTab = ref('order')  // 'order' | 'pending' | 'history'

// ── A1: 模式切換（叫貨/盤點，從 localStorage 恢復）──
const MODE_KEY = 'inventory:mode'
const _savedMode = (() => { try { return JSON.parse(localStorage.getItem(MODE_KEY) || '{}') } catch { return {} } })()
const modeOrder = ref(_savedMode.order !== false)
const modeStocktake = ref(_savedMode.stocktake === true)
function saveMode() { localStorage.setItem(MODE_KEY, JSON.stringify({ order: modeOrder.value, stocktake: modeStocktake.value })) }

// ── 叫貨 tab ──────────────────────────────────
const vendors = ref([])
const selectedVendor = ref(null)
const items = ref([])
const isLoading = ref(true)
const submitting = ref(false)
const submitToast = ref('')
const expectedDeliveryDate = ref('')
const adHocItems = ref([])
const showAdHocForm = ref(false)
const adHocName = ref(''); const adHocQty = ref(1); const adHocUnit = ref('個')

// Order preview sheet (legacy - kept for reference but replaced by direct submit)
const showPreviewSheet = ref(false)
const previewText = ref('')
const previewCopied = ref(false)

// ── D+N 到貨倒數 (P3-3) ──────────────────────────
const deliveryDays = computed(() => selectedVendor.value?.delivery_days_to_arrive || 2)
const estimatedDeliveryLabel = computed(() => {
  const n = deliveryDays.value
  const d = new Date(); d.setDate(d.getDate() + n)
  return `D+${n} 到貨：${d.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })}`
})

// ── 草稿自動儲存 (P3-3) ──────────────────────────
const draftBanner = ref(null)
const DRAFT_KEY = () => `draft:order:${auth.user?.id || 'anon'}`
const DRAFT_TTL = 48 * 60 * 60 * 1000

function saveDraft() {
  if (!selectedVendor.value || orderedCount.value === 0) return
  try {
    const draft = {
      timestamp: Date.now(),
      vendorId: selectedVendor.value.id,
      vendorName: selectedVendor.value.name,
      qtys: toRaw(items.value).filter(i => i.qty > 0).map(i => ({ id: i.id, qty: i.qty })),
      adHocItems: toRaw(adHocItems.value),
      expectedDeliveryDate: expectedDeliveryDate.value
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
  const v = vendors.value.find(v => v.id === draft.vendorId)
  if (v) {
    await selectVendor(v)
    draft.qtys.forEach(({ id, qty }) => {
      const item = items.value.find(i => i.id === id)
      if (item) item.qty = qty
    })
    adHocItems.value = draft.adHocItems || []
    if (draft.expectedDeliveryDate) expectedDeliveryDate.value = draft.expectedDeliveryDate
  }
  localStorage.removeItem(DRAFT_KEY())
}

function discardDraft() {
  localStorage.removeItem(DRAFT_KEY())
  draftBanner.value = null
}

let _draftTimer = null

const freeShippingThreshold = computed(() => parseFloat(selectedVendor.value?.free_shipping_threshold) || 0)
const orderTotal = computed(() =>
  items.value.filter(i => i.qty > 0).reduce((s, i) => s + i.qty * (parseFloat(i.price) || 0), 0)
)
const freeShippingProgress = computed(() =>
  freeShippingThreshold.value > 0 ? Math.min(100, (orderTotal.value / freeShippingThreshold.value) * 100) : 100
)
const orderedCount = computed(() => items.value.filter(i => i.qty > 0).length + adHocItems.value.length)

// stock status helpers
const isLowStock = (item) => parseFloat(item.min_stock) > 0 && parseFloat(item.current_stock) <= parseFloat(item.min_stock)
const stockBorder = (item) => isLowStock(item) ? 'border-l-4 border-l-red-400' : 'border-l-4 border-l-slate-100'

// ── 待收貨 tab ────────────────────────────────
const pendingOrders = ref([])
const pendingLoading = ref(false)
const showReceiveModal = ref(false)
const receiveTarget = ref(null)
const receiveOrderItems = ref([])
const receiveForm = ref({ total_amount: '', amount_paid: '', is_paid: true, note: '' })
const receiveSubmitting = ref(false)
const receiveError = ref('')

// ── 歷史紀錄 tab ──────────────────────────────
const historyTab = ref('orders')  // 'orders' | 'stocktake'
const historyOrders = ref([])
const historyLoading = ref(false)
const historySearch = ref('')
const expandedOrderId = ref(null)
const expandedItems = ref([])
// 盤點歷史
const historySessions = ref([])
const historyStocktakeLoading = ref(false)
const expandedSessions = ref(new Set())

const filteredHistory = computed(() => {
  if (!historySearch.value.trim()) return historyOrders.value
  const q = historySearch.value.toLowerCase()
  return historyOrders.value.filter(o =>
    (o.vendor_name || '').toLowerCase().includes(q) ||
    fmtDate(o.created_at).includes(q)
  )
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

onMounted(async () => {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  expectedDeliveryDate.value = tomorrow.toISOString().split('T')[0]
  try {
    const vRes = await fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() })
    if (vRes.ok) {
      vendors.value = await vRes.json()
      if (vendors.value.length) await selectVendor(vendors.value[0])
      else isLoading.value = false
    } else isLoading.value = false
  } catch { isLoading.value = false }
  // Draft auto-save setup (P3-3)
  loadDraftBanner()
  _draftTimer = setInterval(() => { saveDraft() }, 30000)
})

onUnmounted(() => { if (_draftTimer) clearInterval(_draftTimer) })

async function selectVendor(v) {
  selectedVendor.value = v
  isLoading.value = true
  try {
    const iRes = await fetch(`${API_BASE}/inventory/items?vendor_id=${v.id}`, { headers: authHeaders() })
    items.value = iRes.ok ? (await iRes.json()).map(i => ({ ...i, qty: 0, actual_qty: null })) : []
  } finally { isLoading.value = false }
}

function addAdHoc() {
  if (!adHocName.value.trim()) return
  adHocItems.value.push({ id: Date.now(), name: adHocName.value, qty: adHocQty.value, unit: adHocUnit.value })
  adHocName.value = ''; adHocQty.value = 1; showAdHocForm.value = false
}

// A2: 暫存草稿到後端
const draftSaving = ref(false)
const draftToast = ref('')

async function saveDraftToServer() {
  const orderItems = items.value.filter(i => i.qty > 0)
  const stocktakeItems = items.value.filter(i => i.actual_qty !== null && i.actual_qty !== '')
  if (!selectedVendor.value && !orderItems.length && !stocktakeItems.length) return

  const type = modeOrder.value && modeStocktake.value ? 'both' : modeStocktake.value ? 'stocktake' : 'order'
  const payload = {
    type,
    vendor_id: selectedVendor.value?.id || null,
    order_items: orderItems.map(i => ({ item_id: i.id, quantity: i.qty })),
    stocktake_items: stocktakeItems.map(i => ({ item_id: i.id, actual_quantity: parseFloat(i.actual_qty) || 0 })),
    created_by_name: auth.user?.full_name || auth.user?.username || ''
  }
  draftSaving.value = true
  try {
    const res = await fetch(`${API_BASE}/drafts`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('儲存失敗')
    draftToast.value = '草稿已儲存 ✓'
    setTimeout(() => { draftToast.value = '' }, 2000)
  } catch {
    draftToast.value = '⚠ 草稿儲存失敗'
    setTimeout(() => { draftToast.value = '' }, 2000)
  } finally { draftSaving.value = false }
}

// A2: 盤點歷史底部抽屜
const showStocktakeHistory = ref(false)
const stocktakeHistory = ref([])
const stocktakeHistoryLoading = ref(false)
const expandedHistoryId = ref(null)

async function loadStocktakeHistory() {
  showStocktakeHistory.value = true
  stocktakeHistoryLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/stocktake/?limit=5`, { headers: authHeaders() })
    if (res.ok) stocktakeHistory.value = await res.json()
  } finally { stocktakeHistoryLoading.value = false }
}

function toggleHistoryExpand(id) {
  expandedHistoryId.value = expandedHistoryId.value === id ? null : id
}

// A1: 送出待收貨（替換舊的複製叫貨單）
async function submitPendingReceive() {
  const orderItems = items.value.filter(i => i.qty > 0)
  const allItems = [...orderItems, ...adHocItems.value]
  if (!allItems.length && !modeStocktake.value) return

  submitting.value = true
  try {
    if (modeOrder.value && allItems.length > 0) {
      const orderDetails = [
        ...orderItems.map(i => ({ item_id: i.id, qty: i.qty })),
        ...adHocItems.value.map(i => ({ adhoc_name: i.name, qty: i.qty, adhoc_unit: i.unit }))
      ]
      const res = await fetch(`${API_BASE}/inventory/orders`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({
          vendor_id: selectedVendor.value.id,
          status: 'confirmed',
          expected_delivery_date: expectedDeliveryDate.value ? new Date(expectedDeliveryDate.value).toISOString() : null,
          items: orderDetails
        })
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '送出失敗') }
    }

    if (modeStocktake.value) {
      const stocktakeItems = items.value
        .filter(i => i.actual_qty !== null && i.actual_qty !== '')
        .map(i => ({ item_id: i.id, actual_qty: parseFloat(i.actual_qty) || 0 }))
      if (stocktakeItems.length > 0) {
        await fetch(`${API_BASE}/stocktake/records`, {
          method: 'POST', headers: authHeaders(),
          body: JSON.stringify({ items: stocktakeItems, mode: 'stocktake' })
        })
      }
    }

    // Auto-copy LINE message and switch to pending tab
    if (modeOrder.value && allItems.length > 0) {
      try {
        const lineMsg = buildLineMessage(
          selectedVendor.value?.name || '',
          items.value.filter(i => i.qty > 0),
          adHocItems.value,
          expectedDeliveryDate.value
        )
        await navigator.clipboard.writeText(lineMsg)
        submitToast.value = '已複製 LINE 訊息 ✓'
      } catch {
        submitToast.value = '✓ 已送出！訂單進入待收貨清單'
      }
    } else {
      submitToast.value = '✓ 已送出！'
    }
    // Reset form
    items.value.forEach(i => { i.qty = 0; i.actual_qty = null })
    adHocItems.value = []
    localStorage.removeItem(DRAFT_KEY())
    setTimeout(() => { submitToast.value = ''; switchTab('pending') }, 1800)
  } catch (e) {
    submitToast.value = `⚠ ${e.message || '送出失敗'}`
    setTimeout(() => { submitToast.value = '' }, 3000)
  } finally {
    submitting.value = false
  }
}

// Build LINE message for an order
function buildLineMessage(vendorName, orderItems, adHocList, date) {
  const today = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric' })
  let text = `【叫貨單】${vendorName}\n日期：${today}\n──────────\n`
  orderItems.forEach(i => { text += `${i.name} × ${i.qty} ${i.unit || ''}\n` })
  adHocList.forEach(i => { text += `${i.name} × ${i.qty} ${i.unit || ''}\n` })
  text += `──────────`
  if (date) text += `\n預計到貨：${date}`
  return text
}

// Legacy - kept for backward compat but hidden from UI
async function openPreview() { await submitPendingReceive() }
async function copyAndClose() { showPreviewSheet.value = false }

// ── 待收貨 ──────────────────────────────────
async function copyOrderLineMsg(order) {
  try {
    // Fetch order items
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    let orderItems = []
    if (res.ok) {
      const data = await res.json()
      orderItems = Array.isArray(data) ? data : (data.items || [])
    }
    const lineMsg = buildLineMessage(
      order.vendor_name || '',
      orderItems,
      [],
      order.expected_delivery_date
    )
    await navigator.clipboard.writeText(lineMsg)
    submitToast.value = '已複製 LINE 訊息 ✓'
    setTimeout(() => { submitToast.value = '' }, 2000)
  } catch {
    submitToast.value = '複製失敗'
    setTimeout(() => { submitToast.value = '' }, 2000)
  }
}

async function loadPending() {
  pendingLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?status=confirmed`, { headers: authHeaders() })
    if (res.ok) pendingOrders.value = await res.json()
  } finally { pendingLoading.value = false }
}

function orderDateBadge(order) {
  if (!order.expected_delivery_date) return null
  const d = new Date(order.expected_delivery_date)
  const today = new Date(); today.setHours(0,0,0,0)
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1)
  d.setHours(0,0,0,0)
  if (d.getTime() === today.getTime()) return { label: '今日', cls: 'bg-red-100 text-red-600' }
  if (d.getTime() === tomorrow.getTime()) return { label: '明日', cls: 'bg-blue-100 text-blue-600' }
  return null
}

async function openReceive(order) {
  receiveTarget.value = order
  receiveForm.value = { total_amount: order.total_amount || '', amount_paid: '', is_paid: true, note: '' }
  receiveError.value = ''; receiveOrderItems.value = []; showReceiveModal.value = true
  const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
  if (res.ok) {
    const data = await res.json()
    receiveOrderItems.value = Array.isArray(data) ? data : (data.items || [])
  }
}

async function submitReceive() {
  receiveError.value = ''
  const amount = parseFloat(receiveForm.value.total_amount)
  if (!amount) { receiveError.value = '請輸入訂單金額'; return }
  receiveSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${receiveTarget.value.id}/receive`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ total_amount: amount, amount_paid: parseFloat(receiveForm.value.amount_paid) || 0, is_paid: receiveForm.value.is_paid, note: receiveForm.value.note || null })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '收貨失敗') }
    showReceiveModal.value = false
    await loadPending()
  } catch (e) { receiveError.value = e.message }
  finally { receiveSubmitting.value = false }
}

async function cancelOrder(order) {
  if (!confirm(`確認取消 ${order.vendor_name} 的訂單？`)) return
  await fetch(`${API_BASE}/inventory/orders/${order.id}`, { method: 'DELETE', headers: authHeaders() })
  await loadPending()
}

// ── 歷史紀錄 ──────────────────────────────────
async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?status=received,cancelled&days_limit=60`, { headers: authHeaders() })
    if (res.ok) historyOrders.value = await res.json()
  } finally { historyLoading.value = false }
}

async function loadHistoryStocktake() {
  historyStocktakeLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/stocktake/?days_limit=60&limit=50`, { headers: authHeaders() })
    if (res.ok) historySessions.value = await res.json()
  } finally { historyStocktakeLoading.value = false }
}

function toggleSession(id) {
  const s = new Set(expandedSessions.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedSessions.value = s
}

function switchHistoryTab(tab) {
  historyTab.value = tab
  if (tab === 'orders' && !historyOrders.value.length) loadHistory()
  if (tab === 'stocktake' && !historySessions.value.length) loadHistoryStocktake()
}

async function toggleExpand(orderId) {
  if (expandedOrderId.value === orderId) { expandedOrderId.value = null; return }
  expandedOrderId.value = orderId
  const res = await fetch(`${API_BASE}/inventory/orders/${orderId}`, { headers: authHeaders() })
  if (res.ok) {
    const data = await res.json()
    expandedItems.value = Array.isArray(data) ? data : (data.items || [])
  }
}

function switchTab(tab) {
  subTab.value = tab
  if (tab === 'pending') loadPending()
  if (tab === 'history') {
    historyTab.value = 'orders'
    if (!historyOrders.value.length) loadHistory()
  }
}

function fmtDate(d) { return d ? new Date(d).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) : '' }
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
const statusLabel = s => ({ confirmed: '待收貨', received: '已收貨', cancelled: '已取消' }[s] || s)
const statusColor = s => ({ confirmed: 'bg-amber-100 text-amber-600', received: 'bg-emerald-100 text-emerald-600', cancelled: 'bg-red-100 text-red-400' }[s] || 'bg-gray-100 text-gray-400')
const payBadge = (o) => {
  if (o.status !== 'received') return null
  if (o.is_paid) return { label: '已付', cls: 'bg-emerald-100 text-emerald-600' }
  if (o.payment_terms === 'monthly') return { label: '月結', cls: 'bg-orange-100 text-orange-600' }
  return { label: '待付', cls: 'bg-red-100 text-red-500' }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col pb-24">

    <!-- Header + sub-tabs -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div class="px-4 pt-12 pb-2 flex items-center justify-between">
        <h1 class="text-xl font-extrabold text-slate-800">訂單管理</h1>
      </div>
      <div class="flex border-t border-slate-100">
        <button @click="switchTab('order')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='order' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">
          叫貨
        </button>
        <button @click="switchTab('pending')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='pending' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">
          待收貨
          <span v-if="pendingOrders.length" class="ml-1 inline-flex items-center justify-center w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full">{{ pendingOrders.length }}</span>
        </button>
        <button @click="switchTab('history')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='history' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">
          歷史紀錄
        </button>
      </div>
    </header>

    <!-- ═══ 叫貨 Tab ═══ -->
    <div v-if="subTab==='order'" class="flex-1 pb-32">

      <!-- 草稿恢復 banner (P3-3) -->
      <div v-if="draftBanner" class="mx-3 mt-3 rounded-xl px-3 py-2.5 bg-amber-50 border border-amber-200">
        <p class="text-xs font-bold text-amber-800">📌 發現未完成的叫貨草稿（{{ draftBanner.vendorName }}）</p>
        <div class="flex gap-2 mt-1.5">
          <button @click="resumeDraft" class="flex-1 bg-orange-500 text-white text-xs font-bold py-1.5 rounded-lg">繼續編輯</button>
          <button @click="discardDraft" class="flex-1 bg-slate-200 text-slate-600 text-xs font-bold py-1.5 rounded-lg">丟棄草稿</button>
        </div>
      </div>

      <!-- Control bar -->
      <div class="bg-white border-b border-slate-100 px-3 py-3 space-y-3">

        <!-- A1: 模式切換（可同時勾選） -->
        <div class="flex gap-2">
          <button @click="modeOrder=!modeOrder; saveMode()"
            class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all"
            :class="modeOrder ? 'text-white border-orange-500' : 'bg-white border-slate-200 text-slate-400'"
            :style="modeOrder ? 'background:#e85d04' : ''">
            📦 叫貨{{ modeOrder ? ' ✓' : '' }}
          </button>
          <button @click="modeStocktake=!modeStocktake; saveMode()"
            class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all"
            :class="modeStocktake ? 'bg-blue-500 text-white border-blue-500' : 'bg-white border-slate-200 text-slate-400'">
            📋 盤點{{ modeStocktake ? ' ✓' : '' }}
          </button>
        </div>

        <!-- Vendor chips -->
        <div class="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          <button v-for="v in vendors" :key="v.id" @click="selectVendor(v)"
            class="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all"
            :class="selectedVendor?.id===v.id ? 'bg-orange-500 text-white shadow' : 'bg-slate-100 text-slate-500'">
            {{ v.name }}
          </button>
        </div>

        <!-- Free shipping progress -->
        <div v-if="freeShippingThreshold > 0">
          <div class="flex justify-between items-center mb-1">
            <span class="text-[10px] font-bold text-slate-500">{{ selectedVendor?.name }} 免運門檻</span>
            <span class="text-[10px] font-bold" :class="orderTotal>=freeShippingThreshold?'text-emerald-600':'text-orange-500'">
              本單 ${{ fmtMoney(orderTotal) }}
              <span v-if="orderTotal < freeShippingThreshold" class="text-slate-400"> | 差 ${{ fmtMoney(freeShippingThreshold - orderTotal) }}</span>
              <span v-else> ✓ 已達免運</span>
            </span>
          </div>
          <div class="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all duration-300"
              :class="orderTotal>=freeShippingThreshold?'bg-emerald-500':'bg-orange-400'"
              :style="{ width: freeShippingProgress+'%' }"></div>
          </div>
        </div>

        <!-- D+N 到貨倒數 + 日期選擇器 (P3-3) -->
        <div class="bg-orange-50 rounded-xl px-3 py-2 border border-orange-100 space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-bold text-orange-600">⚡ {{ estimatedDeliveryLabel }}</span>
          </div>
          <div class="flex items-center justify-between">
            <label class="text-xs font-bold text-orange-700">📅 預計到貨日</label>
            <input v-model="expectedDeliveryDate" type="date"
              class="bg-transparent border-none text-xs font-bold text-slate-700 focus:outline-none" />
          </div>
        </div>
      </div>

      <!-- Item list -->
      <div v-if="isLoading" class="flex flex-col items-center py-16 gap-3">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        <p class="text-slate-400 text-sm">載入品項中…</p>
      </div>

      <div v-else class="px-4 pt-3 space-y-2 pb-4">
        <!-- Ad-hoc items -->
        <div v-for="item in adHocItems" :key="item.id"
          class="bg-orange-50 border border-orange-200 rounded-xl p-3 flex items-center justify-between">
          <div>
            <span class="font-bold text-slate-900 text-sm">{{ item.name }}</span>
            <span class="text-[10px] text-orange-500 ml-2 font-bold bg-orange-100 px-1.5 py-0.5 rounded">臨時</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="font-extrabold text-sm">{{ item.qty }} {{ item.unit }}</span>
            <button @click="adHocItems=adHocItems.filter(i=>i.id!==item.id)" class="text-red-400 text-lg leading-none">✕</button>
          </div>
        </div>

        <!-- A1: Regular items（支援雙模式） -->
        <div v-for="item in items" :key="item.id"
          class="bg-white rounded-xl p-3 shadow-sm transition-all duration-300"
          :class="stockBorder(item)"
          style="overflow:hidden">
          <!-- 品項資訊 -->
          <div class="flex items-center gap-2 mb-1.5">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-bold text-slate-900 text-sm">{{ item.name }}</span>
                <span v-if="isLowStock(item)" class="text-[9px] font-extrabold bg-red-100 text-red-500 px-1.5 py-0.5 rounded-full">低庫存</span>
              </div>
              <p class="text-[10px] text-slate-400 mt-0.5">
                庫存 <span :class="isLowStock(item) ? 'text-red-500 font-bold' : 'text-slate-500'">{{ item.current_stock || 0 }}</span>
                {{ item.unit }}<span v-if="item.price" class="ml-1 text-orange-500"> ${{ fmtMoney(item.price) }}</span>
              </p>
            </div>
          </div>
          <!-- 模式欄位 -->
          <div class="flex gap-3" :class="modeOrder && modeStocktake ? 'items-start' : 'items-center justify-end'">
            <!-- 叫貨數量 (+/-) -->
            <div v-if="modeOrder" class="flex items-center gap-1.5 shrink-0" :class="modeStocktake ? 'flex-1 flex-col items-center' : ''">
              <span v-if="modeStocktake" class="text-[10px] font-bold text-orange-500 mb-1">叫貨</span>
              <div class="flex items-center gap-1">
                <button @click="item.qty=Math.max(0,item.qty-1)"
                  class="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center font-bold text-slate-600 active:bg-slate-200 text-lg leading-none">−</button>
                <input v-model.number="item.qty" type="number" min="0"
                  class="w-12 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none"
                  :class="item.qty>0?'border-orange-500 text-orange-600':'border-slate-200 text-slate-800'" />
                <button @click="item.qty+=1"
                  class="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200 text-lg leading-none">+</button>
              </div>
            </div>
            <!-- 實盤數量（直接輸入）-->
            <div v-if="modeStocktake" class="flex-1 flex flex-col items-center">
              <span class="text-[10px] font-bold text-blue-500 mb-1">實盤</span>
              <div class="flex items-center gap-1">
                <input v-model.number="item.actual_qty" type="number" min="0" :placeholder="`原 ${item.current_stock || 0}`"
                  class="w-20 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none"
                  :class="item.actual_qty != null && item.actual_qty !== '' ? 'border-blue-500 text-blue-700' : 'border-slate-200 text-slate-400'" />
                <span class="text-xs text-slate-400">{{ item.unit }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Add ad-hoc -->
        <div class="flex justify-center pt-1">
          <button v-if="!showAdHocForm" @click="showAdHocForm=true"
            class="text-orange-500 font-bold bg-white px-5 py-2.5 rounded-xl border-2 border-orange-100 shadow-sm text-sm">
            + 新增臨時品項
          </button>
        </div>
        <div v-if="showAdHocForm" class="bg-white p-4 rounded-xl border border-orange-100 shadow">
          <h3 class="font-extrabold text-slate-900 mb-3 text-sm">新增臨時品項</h3>
          <div class="space-y-2">
            <input v-model="adHocName" type="text" placeholder="品項名稱"
              class="w-full bg-slate-50 rounded-xl py-2.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            <div class="flex gap-2">
              <input v-model.number="adHocQty" type="number" placeholder="數量"
                class="flex-1 bg-slate-50 rounded-xl py-2.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
              <input v-model="adHocUnit" type="text" placeholder="單位"
                class="w-20 bg-slate-50 rounded-xl py-2.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div class="flex gap-2">
              <button @click="showAdHocForm=false" class="flex-1 bg-slate-100 text-slate-500 font-bold py-2.5 rounded-xl text-sm">取消</button>
              <button @click="addAdHoc" class="flex-1 bg-orange-500 text-white font-bold py-2.5 rounded-xl text-sm">加入清單</button>
            </div>
          </div>
        </div>
      </div>

      <!-- A1: Submit toast -->
      <div v-if="submitToast"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-sm font-bold shadow-lg text-white"
        :style="submitToast.startsWith('⚠') ? 'background:#ef4444' : 'background:#10b981'">
        {{ submitToast }}
      </div>

      <!-- A2: Draft toast -->
      <div v-if="draftToast"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-sm font-bold shadow-lg text-white"
        :style="draftToast.startsWith('⚠') ? 'background:#ef4444' : 'background:#64748b'">
        {{ draftToast }}
      </div>

      <!-- Bottom action bar -->
      <div class="fixed bottom-16 inset-x-0 bg-white border-t border-slate-200 px-4 py-3 shadow-lg z-20">
        <div class="flex gap-2 mb-2" v-if="modeStocktake">
          <button @click="loadStocktakeHistory"
            class="flex-1 py-2 bg-blue-50 text-blue-600 text-xs font-bold rounded-xl border border-blue-200">
            📋 查看歷史盤點
          </button>
          <button @click="saveDraftToServer" :disabled="draftSaving"
            class="flex-1 py-2 bg-slate-100 text-slate-600 text-xs font-bold rounded-xl border border-slate-200 disabled:opacity-40">
            💾 {{ draftSaving ? '儲存中…' : '暫存草稿' }}
          </button>
        </div>
        <div class="flex gap-3" :class="!modeStocktake ? 'items-center' : ''">
          <div v-if="!modeStocktake" class="flex-1 flex flex-col justify-center">
            <p class="text-[10px] text-slate-400 font-bold">已選品項</p>
            <p class="text-lg font-extrabold text-slate-900">{{ orderedCount }} 項</p>
          </div>
          <button v-if="!modeStocktake" @click="saveDraftToServer" :disabled="draftSaving"
            class="py-3 px-3 bg-slate-100 text-slate-600 text-xs font-bold rounded-2xl border border-slate-200 disabled:opacity-40">
            💾{{ draftSaving ? '…' : '' }}
          </button>
          <button @click="submitPendingReceive" :disabled="submitting || (orderedCount === 0 && !modeStocktake)"
            class="flex-[2] text-white font-bold py-3 rounded-2xl shadow active:scale-95 disabled:opacity-40 flex items-center justify-center gap-2 text-sm"
            style="background:#e85d04">
            <span v-if="submitting">處理中…</span>
            <span v-else-if="modeOrder && modeStocktake">📤 送出叫貨+盤點</span>
            <span v-else-if="modeStocktake">📋 送出盤點</span>
            <span v-else>📤 送出待收貨</span>
          </button>
        </div>
      </div>

      <!-- A2: 盤點歷史底部抽屜 -->
      <div v-if="showStocktakeHistory" class="fixed inset-0 bg-black/50 z-50 flex items-end" @click.self="showStocktakeHistory=false">
        <div class="bg-white w-full rounded-t-3xl max-h-[80vh] overflow-y-auto">
          <div class="flex items-center justify-center w-10 h-1 bg-slate-200 rounded-full mx-auto mt-4 mb-3"></div>
          <div class="px-5 pb-2 flex items-center justify-between">
            <h3 class="text-base font-extrabold text-slate-800">最近盤點紀錄</h3>
            <button @click="showStocktakeHistory=false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
          <div v-if="stocktakeHistoryLoading" class="flex justify-center py-10">
            <div class="animate-spin h-6 w-6 border-4 border-blue-500 border-t-transparent rounded-full"></div>
          </div>
          <div v-else-if="!stocktakeHistory.length" class="text-center py-10 text-slate-400">無歷史盤點紀錄</div>
          <div v-else class="px-5 pb-8 space-y-3">
            <div v-for="record in stocktakeHistory" :key="record.id" class="bg-slate-50 rounded-xl p-3">
              <div class="flex items-start justify-between">
                <div>
                  <p class="font-bold text-slate-800 text-sm">
                    {{ new Date(record.stocktake_date || record.created_at).toLocaleDateString('zh-TW', { month:'numeric',day:'numeric',weekday:'short' }) }}
                  </p>
                  <div class="flex items-center gap-1 text-xs text-slate-400 mt-0.5">
                    <UserBadge :user="record.performed_by" size="sm" />
                    · {{ record.item_count || (record.items?.length) || '?' }} 品項
                  </div>
                </div>
                <div class="text-right">
                  <span v-if="(record.diff_count || 0) > 0" class="text-xs font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">
                    差異 {{ record.diff_count }} 項
                  </span>
                  <span v-else class="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">完全吻合</span>
                </div>
              </div>
              <button @click="toggleHistoryExpand(record.id)"
                class="mt-2 text-xs font-bold text-blue-500 flex items-center gap-1">
                查看明細 {{ expandedHistoryId===record.id ? '▲' : '▼' }}
              </button>
              <div v-if="expandedHistoryId===record.id && record.items?.length" class="mt-2 border-t border-slate-200 pt-2 space-y-1">
                <div v-for="it in record.items" :key="it.item_id" class="flex items-center justify-between text-xs">
                  <span class="text-slate-700">{{ it.item_name }}</span>
                  <span class="text-slate-400">系統 {{ it.system_stock }} → 實盤 {{ it.actual_qty }}</span>
                  <span :class="(it.diff||0) < 0 ? 'text-red-500 font-bold' : (it.diff||0) > 0 ? 'text-orange-500 font-bold' : 'text-emerald-600'">
                    {{ (it.diff||0) > 0 ? '+' : '' }}{{ it.diff || 0 }}
                    {{ (it.diff||0) === 0 ? '✅' : '⚠️' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 待收貨 Tab ═══ -->
    <div v-else-if="subTab==='pending'" class="flex-1 pb-4">

      <!-- Info banner -->
      <div class="mx-4 mt-3 rounded-xl px-3 py-2.5" style="background:#fffbeb;border:1px solid #fde68a">
        <p class="text-xs font-semibold" style="color:#92400e">
          💡 提前到貨可直接簽收；未到貨訂單可刪除
        </p>
      </div>

      <div v-if="pendingLoading" class="flex justify-center py-16">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="!pendingOrders.length" class="text-center py-16">
        <p class="text-5xl mb-3">📦</p>
        <p class="text-slate-400 font-bold">無待收貨訂單</p>
      </div>
      <div v-else class="px-4 mt-3 space-y-2">
        <p class="text-xs font-bold text-slate-500 uppercase">未簽收訂單 ({{ pendingOrders.length }})</p>
        <div v-for="order in pendingOrders" :key="order.id"
          class="bg-white rounded-xl shadow-sm p-4">
          <div class="flex items-start gap-3">
            <span class="text-2xl mt-0.5">🚚</span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <p class="font-extrabold text-slate-800 text-sm">{{ order.vendor_name }}</p>
                <span v-if="orderDateBadge(order)"
                  class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  :class="orderDateBadge(order).cls">
                  {{ orderDateBadge(order).label }}
                </span>
              </div>
              <p class="text-xs text-slate-400 mt-0.5">
                預計 {{ order.expected_delivery_date ? fmtDate(order.expected_delivery_date) : '待定' }}
                · {{ order.total_items || '?' }} 項品項
                <span v-if="order.total_amount"> · ${{ fmtMoney(order.total_amount) }}</span>
              </p>
              <UserBadge v-if="order.created_by" :user="order.created_by" size="sm" class="mt-0.5" />
            </div>
          </div>
          <!-- Actions row（已收貨不顯示編輯/刪除按鈕） -->
          <div class="flex gap-2 mt-3 pt-3 border-t border-slate-100">
            <template v-if="order.status !== 'received' && order.status !== 'cancelled'">
              <button @click="cancelOrder(order)"
                class="flex-1 py-2 bg-slate-100 text-slate-600 text-xs font-bold rounded-xl active:bg-slate-200">
                🗑 刪除
              </button>
              <button @click="copyOrderLineMsg(order)"
                class="flex-1 py-2 bg-blue-50 text-blue-600 text-xs font-bold rounded-xl active:scale-95 border border-blue-100">
                📋 複製訊息
              </button>
              <button @click="openReceive(order)"
                class="flex-[2] py-2 text-white text-xs font-bold rounded-xl active:scale-95"
                style="background:#e85d04">
                ✅ 簽收
              </button>
            </template>
            <div v-else class="flex-1 text-center text-xs text-slate-400 py-2">
              {{ order.status === 'received' ? '✓ 已簽收' : '已取消' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Receive bottom sheet -->
      <div v-if="showReceiveModal" class="fixed inset-0 bg-black/50 z-50 flex items-end">
        <div class="bg-white w-full rounded-t-3xl p-5 max-h-[88vh] overflow-y-auto">
          <div class="flex items-center justify-center w-10 h-1 bg-slate-200 rounded-full mx-auto mb-4"></div>
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-base font-extrabold text-slate-800">{{ receiveTarget?.vendor_name }} — 簽收確認</h3>
            <button @click="showReceiveModal=false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>

          <!-- Order items preview -->
          <div v-if="receiveOrderItems.length" class="mb-4">
            <p class="text-xs font-bold text-slate-500 uppercase mb-2">到貨品項確認</p>
            <div class="bg-slate-50 rounded-xl p-3 space-y-1.5">
              <div v-for="(item,idx) in receiveOrderItems" :key="idx"
                class="flex justify-between text-sm">
                <span class="text-slate-700">{{ item.name || item.adhoc_name }}</span>
                <span class="text-slate-500 font-bold">叫貨：{{ item.qty }} {{ item.unit || item.adhoc_unit }}</span>
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <!-- Amount -->
            <div>
              <p class="text-xs font-bold text-slate-500 mb-1">本次訂單金額</p>
              <p class="text-[10px] text-slate-400 mb-1">菜商等現場議價廠商請直接輸入今日金額</p>
              <input v-model="receiveForm.total_amount" type="number" inputmode="decimal" placeholder="0"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-2xl font-extrabold text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>

            <!-- Payment status -->
            <div>
              <p class="text-xs font-bold text-slate-500 mb-2">付款狀態</p>
              <div class="flex gap-2">
                <button @click="receiveForm.is_paid = true"
                  class="flex-1 py-3 rounded-xl text-sm font-bold border transition-all text-left px-3"
                  :class="receiveForm.is_paid ? 'border-emerald-400 bg-emerald-50 text-emerald-700' : 'border-slate-200 text-slate-400'">
                  <p class="font-extrabold text-sm">✓ 現場已付</p>
                  <p class="text-[10px] mt-0.5 opacity-70">現金當場結清</p>
                </button>
                <button @click="receiveForm.is_paid = false"
                  class="flex-1 py-3 rounded-xl text-sm font-bold border transition-all text-left px-3"
                  :class="!receiveForm.is_paid ? 'border-slate-500 bg-slate-100 text-slate-700' : 'border-slate-200 text-slate-400'">
                  <p class="font-extrabold text-sm">未付款</p>
                  <p class="text-[10px] mt-0.5 opacity-70">月結/後續結帳</p>
                </button>
              </div>
            </div>

            <!-- Note -->
            <div>
              <label class="block text-xs font-bold text-slate-500 mb-1">備註（選填）</label>
              <input v-model="receiveForm.note" type="text" placeholder="如有差異請說明…"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>

            <div v-if="receiveError" class="text-red-500 text-sm text-center">{{ receiveError }}</div>
            <button @click="submitReceive" :disabled="receiveSubmitting"
              class="w-full text-white font-bold py-4 rounded-2xl active:scale-95 disabled:opacity-40"
              style="background:#e85d04">
              {{ receiveSubmitting ? '處理中…' : '✓ 確認簽收' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 歷史紀錄 Tab ═══ -->
    <div v-else-if="subTab==='history'" class="flex-1 pb-4">

      <!-- 內 tab：已收貨 / 盤點歷史 -->
      <div class="bg-white border-b border-slate-100 sticky top-[120px] z-10">
        <div class="flex">
          <button @click="switchHistoryTab('orders')"
            class="flex-1 py-2.5 text-sm font-bold transition-colors"
            :style="historyTab==='orders' ? 'color:#e85d04;border-bottom:2px solid #e85d04' : 'color:#94a3b8'">
            已收貨
          </button>
          <button @click="switchHistoryTab('stocktake')"
            class="flex-1 py-2.5 text-sm font-bold transition-colors"
            :style="historyTab==='stocktake' ? 'color:#e85d04;border-bottom:2px solid #e85d04' : 'color:#94a3b8'">
            盤點歷史
          </button>
        </div>
      </div>

      <!-- ── 已收貨 ── -->
      <div v-if="historyTab==='orders'" class="px-4 py-3">
        <div class="mb-3">
          <input v-model="historySearch" type="text" placeholder="🔍 搜尋廠商 / 日期…"
            class="w-full bg-slate-100 rounded-xl py-2.5 pl-4 pr-4 text-sm font-medium focus:ring-2 focus:ring-orange-400 focus:outline-none" />
        </div>
        <div v-if="historyLoading" class="flex justify-center py-16">
          <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        </div>
        <div v-else-if="!filteredHistory.length" class="text-center py-16">
          <p class="text-5xl mb-3">📋</p>
          <p class="text-slate-400 font-bold">{{ historySearch ? '查無符合紀錄' : '近 60 天無收貨紀錄' }}</p>
        </div>
        <div v-else class="space-y-2">
          <div v-for="order in filteredHistory" :key="order.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div @click="toggleExpand(order.id)" class="px-4 py-3 cursor-pointer active:bg-slate-50">
              <div class="flex items-center justify-between mb-1">
                <p class="font-extrabold text-slate-800">{{ order.vendor_name }}</p>
                <p class="text-xs text-slate-400">{{ fmtDate(order.created_at) }}</p>
              </div>
              <div class="flex items-center justify-between text-xs text-slate-500">
                <span>
                  <span v-if="order.ordered_by">叫貨：{{ order.ordered_by.name }}</span>
                  <span v-if="order.received_by"> · 簽收：{{ order.received_by.name }}</span>
                </span>
                <span class="font-bold" style="color:#e85d04">
                  {{ order.total_items }} 品項 · ${{ fmtMoney(order.total_amount) }}
                </span>
              </div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-[10px] px-2 py-0.5 rounded-full font-bold"
                  :style="order.is_paid ? 'background:#f0fdf4;color:#16a34a' : 'background:#fef9c3;color:#92400e'">
                  {{ order.is_paid ? '已付款 ✓' : '未付款' }}
                </span>
                <span class="text-slate-400 text-xs">{{ expandedOrderId===order.id ? '▲' : '▼' }}</span>
              </div>
            </div>
            <div v-if="expandedOrderId===order.id" class="border-t border-slate-100 px-4 py-3 space-y-1">
              <div v-for="(item,idx) in expandedItems" :key="idx" class="flex justify-between text-sm py-0.5">
                <span class="text-slate-700">{{ item.name || item.adhoc_name }}</span>
                <span class="text-slate-500 text-xs">{{ item.qty }} {{ item.unit || item.adhoc_unit }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 盤點歷史 ── -->
      <div v-else class="px-4 py-3">
        <div v-if="historyStocktakeLoading" class="flex justify-center py-16">
          <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        </div>
        <div v-else-if="historySessions.length === 0" class="text-center py-16">
          <p class="text-5xl mb-3">📋</p>
          <p class="text-slate-400 font-bold">近 60 天無盤點紀錄</p>
        </div>
        <div v-else class="space-y-2">
          <div v-for="s in historySessions" :key="s.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div @click="toggleSession(s.id)" class="px-4 py-3 cursor-pointer active:bg-slate-50">
              <div class="flex items-center justify-between mb-1">
                <p class="font-extrabold text-slate-800">{{ s.group_name || '全部品項' }}</p>
                <p class="text-xs text-slate-400">{{ fmtDate(s.created_at) }}</p>
              </div>
              <div class="flex items-center justify-between text-xs text-slate-500">
                <span v-if="s.performed_by">執行人：{{ s.performed_by.name || s.performed_by }}</span>
                <span>{{ s.total_items || 0 }} 品項</span>
              </div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-[10px] font-bold"
                  :class="(s.discrepancy_count || 0) > 0 ? 'text-red-500' : 'text-emerald-600'">
                  {{ (s.discrepancy_count || 0) > 0 ? `差異 ${s.discrepancy_count} 項` : '無差異 ✓' }}
                </span>
                <span class="text-slate-400 text-xs">{{ expandedSessions.has(s.id) ? '▲' : '▼' }}</span>
              </div>
            </div>
            <div v-if="expandedSessions.has(s.id) && s.discrepancies?.length" class="border-t border-slate-100 px-4 py-3 space-y-1">
              <div v-for="d in s.discrepancies" :key="d.item_id" class="flex items-center justify-between text-sm">
                <span class="text-slate-700">{{ d.item_name }}</span>
                <span class="text-red-500 text-xs font-bold">系統 {{ d.system_qty }} / 實盤 {{ d.counted_qty }} {{ d.unit }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ═══ Order Preview Bottom Sheet ═══ -->
    <div v-if="showPreviewSheet" class="fixed inset-0 bg-black/50 z-50 flex items-end">
      <div class="bg-white w-full rounded-t-3xl p-5 max-h-[80vh] overflow-y-auto">
        <div class="flex items-center justify-center w-10 h-1 bg-slate-200 rounded-full mx-auto mb-4"></div>
        <div class="flex justify-between items-center mb-3">
          <h3 class="text-base font-extrabold text-slate-800">叫貨單預覽</h3>
          <button @click="showPreviewSheet=false" class="text-slate-400 text-xl font-bold">✕</button>
        </div>

        <!-- Copy success alert -->
        <div v-if="previewCopied"
          class="mb-3 rounded-xl px-3 py-2.5 text-center text-sm font-bold text-emerald-700"
          style="background:#f0fdf4;border:1px solid #bbf7d0">
          ✓ 已複製至剪貼簿，可直接貼到 LINE
        </div>

        <!-- Formatted text preview -->
        <pre class="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-700 whitespace-pre-wrap font-mono overflow-x-auto">{{ previewText }}</pre>

        <button @click="copyAndClose"
          class="mt-4 w-full text-white font-bold py-4 rounded-2xl active:scale-95"
          style="background:#e85d04">
          📋 複製 LINE 訊息
        </button>
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
