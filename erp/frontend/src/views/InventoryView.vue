<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ── Sub-tabs ──────────────────────────────────
const subTab = ref('order')  // 'order' | 'pending' | 'history'

// ── 叫貨 tab ──────────────────────────────────
const vendors = ref([])
const selectedVendor = ref(null)
const items = ref([])
const isLoading = ref(true)
const submitting = ref(false)
const expectedDeliveryDate = ref('')
const adHocItems = ref([])
const showAdHocForm = ref(false)
const adHocName = ref(''); const adHocQty = ref(1); const adHocUnit = ref('個')

// Order preview sheet
const showPreviewSheet = ref(false)
const previewText = ref('')
const previewCopied = ref(false)

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
const historyOrders = ref([])
const historyLoading = ref(false)
const historySearch = ref('')
const expandedOrderId = ref(null)
const expandedItems = ref([])

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
})

async function selectVendor(v) {
  selectedVendor.value = v
  isLoading.value = true
  try {
    const iRes = await fetch(`${API_BASE}/inventory/items?vendor_id=${v.id}`, { headers: authHeaders() })
    items.value = iRes.ok ? (await iRes.json()).map(i => ({ ...i, qty: 0 })) : []
  } finally { isLoading.value = false }
}

function addAdHoc() {
  if (!adHocName.value.trim()) return
  adHocItems.value.push({ id: Date.now(), name: adHocName.value, qty: adHocQty.value, unit: adHocUnit.value })
  adHocName.value = ''; adHocQty.value = 1; showAdHocForm.value = false
}

async function openPreview() {
  const regularOrdered = items.value.filter(i => i.qty > 0)
  const combined = [...regularOrdered, ...adHocItems.value]
  if (!combined.length) return

  // Save order to backend
  submitting.value = true
  try {
    const orderDetails = [
      ...regularOrdered.map(i => ({ item_id: i.id, qty: i.qty })),
      ...adHocItems.value.map(i => ({ adhoc_name: i.name, qty: i.qty, adhoc_unit: i.unit }))
    ]
    await fetch(`${API_BASE}/inventory/orders`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({
        vendor_id: selectedVendor.value.id,
        expected_delivery_date: expectedDeliveryDate.value ? new Date(expectedDeliveryDate.value).toISOString() : null,
        items: orderDetails
      })
    })
  } finally { submitting.value = false }

  const today = new Date().toLocaleDateString('zh-TW', { year: 'numeric', month: 'numeric', day: 'numeric' })
  let text = `【叫貨單】${selectedVendor.value.name}\n日期：${today}\n──────────\n`
  regularOrdered.forEach(i => { text += `${i.name} × ${i.qty} ${i.unit || ''}\n` })
  adHocItems.value.forEach(i => { text += `${i.name} × ${i.qty} ${i.unit}\n` })
  text += `──────────\n請於${expectedDeliveryDate.value ? new Date(expectedDeliveryDate.value).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) : '預計日期'}配送，謝謝！`
  previewText.value = text
  previewCopied.value = false
  showPreviewSheet.value = true
}

async function copyAndClose() {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(previewText.value)
    else { const ta = document.createElement('textarea'); ta.value = previewText.value; ta.style.cssText = 'position:fixed;left:-9999px'; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta) }
    previewCopied.value = true
    setTimeout(() => { showPreviewSheet.value = false; items.value.forEach(i => i.qty = 0); adHocItems.value = [] }, 1500)
  } catch (e) { alert('複製失敗，請手動複製') }
}

// ── 待收貨 ──────────────────────────────────
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
    const res = await fetch(`${API_BASE}/inventory/orders?days_limit=30`, { headers: authHeaders() })
    if (res.ok) historyOrders.value = await res.json()
  } finally { historyLoading.value = false }
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
  if (tab === 'history' && !historyOrders.value.length) loadHistory()
}

function fmtDate(d) { return d ? new Date(d).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) : '' }
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
const statusLabel = s => ({ pending: '待確認', confirmed: '待收貨', received: '已收貨', cancelled: '已取消' }[s] || s)
const statusColor = s => ({ pending: 'bg-gray-100 text-gray-500', confirmed: 'bg-amber-100 text-amber-600', received: 'bg-emerald-100 text-emerald-600', cancelled: 'bg-red-100 text-red-400' }[s] || 'bg-gray-100 text-gray-400')
const payBadge = (o) => {
  if (o.status !== 'received') return null
  if (o.is_paid) return { label: '已付', cls: 'bg-emerald-100 text-emerald-600' }
  if (o.payment_terms === 'monthly') return { label: '月結', cls: 'bg-orange-100 text-orange-600' }
  return { label: '待付', cls: 'bg-red-100 text-red-500' }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col pb-16">

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

      <!-- Control bar -->
      <div class="bg-white border-b border-slate-100 px-3 py-3 space-y-3">

        <!-- Mode toggle: 盤點 / 叫貨 -->
        <div class="flex gap-2">
          <button @click="router.push({ name: 'stocktake' })"
            class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all bg-white border-slate-200 text-slate-500">
            📋 盤點
          </button>
          <button class="flex-1 py-2 rounded-xl text-xs font-bold border transition-all text-white"
            style="background:#e85d04;border-color:#e85d04">
            📦 叫貨
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

        <!-- Delivery date -->
        <div class="flex items-center justify-between bg-orange-50 rounded-xl px-3 py-2 border border-orange-100">
          <label class="text-xs font-bold text-orange-700">📅 預計到貨日</label>
          <input v-model="expectedDeliveryDate" type="date"
            class="bg-transparent border-none text-xs font-bold text-slate-700 focus:outline-none" />
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

        <!-- Regular items -->
        <div v-for="item in items" :key="item.id"
          class="bg-white rounded-xl p-3 shadow-sm flex items-center gap-3"
          :class="stockBorder(item)">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="font-bold text-slate-900 text-sm">{{ item.name }}</span>
              <span v-if="isLowStock(item)"
                class="text-[9px] font-extrabold bg-red-100 text-red-500 px-1.5 py-0.5 rounded-full">低庫存</span>
            </div>
            <p class="text-[10px] text-slate-400 mt-0.5">
              安全庫存 {{ item.min_stock || 0 }} · 庫存 
              <span :class="isLowStock(item) ? 'text-red-500 font-bold' : 'text-slate-500'">
                {{ item.current_stock || 0 }}
              </span>
              {{ item.unit }}
              <span v-if="item.price" class="ml-1 text-orange-500">${{ fmtMoney(item.price) }}</span>
            </p>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <button @click="item.qty=Math.max(0,item.qty-1)"
              class="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center font-bold text-slate-600 active:bg-slate-200 text-lg leading-none">−</button>
            <input v-model.number="item.qty" type="number" min="0"
              class="w-12 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none"
              :class="item.qty>0?'border-orange-500 text-orange-600':'border-slate-200 text-slate-800'" />
            <button @click="item.qty+=1"
              class="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200 text-lg leading-none">+</button>
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

      <!-- Bottom action bar -->
      <div class="fixed bottom-16 inset-x-0 bg-white border-t border-slate-200 px-4 py-3 shadow-lg z-20 flex gap-3">
        <div class="flex-1 flex flex-col justify-center">
          <p class="text-[10px] text-slate-400 font-bold">已選品項</p>
          <p class="text-lg font-extrabold text-slate-900">{{ orderedCount }} 項</p>
        </div>
        <button @click="openPreview" :disabled="submitting || orderedCount === 0"
          class="flex-[2] text-white font-bold py-3 rounded-2xl shadow active:scale-95 disabled:opacity-40 flex items-center justify-center gap-2 text-sm"
          style="background:#e85d04">
          <span v-if="submitting">處理中…</span>
          <span v-else>📋 複製叫貨單</span>
        </button>
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
            </div>
          </div>
          <!-- Actions row -->
          <div class="flex gap-2 mt-3 pt-3 border-t border-slate-100">
            <button @click="cancelOrder(order)"
              class="flex-1 py-2 bg-slate-100 text-slate-600 text-xs font-bold rounded-xl active:bg-slate-200">
              🗑 刪除
            </button>
            <button @click="openReceive(order)"
              class="flex-[2] py-2 text-white text-xs font-bold rounded-xl active:scale-95"
              style="background:#e85d04">
              ✅ 簽收
            </button>
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

      <!-- Search bar -->
      <div class="px-4 py-3 bg-white border-b border-slate-100 sticky top-[120px] z-10">
        <div class="relative">
          <input v-model="historySearch" type="text" placeholder="🔍 搜尋廠商 / 日期…"
            class="w-full bg-slate-100 rounded-xl py-2.5 pl-4 pr-4 text-sm font-medium focus:ring-2 focus:ring-orange-400 focus:outline-none" />
        </div>
      </div>

      <div v-if="historyLoading" class="flex justify-center py-16">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="!filteredHistory.length" class="text-center py-16">
        <p class="text-5xl mb-3">📋</p>
        <p class="text-slate-400 font-bold">{{ historySearch ? '查無符合紀錄' : '近 30 天無紀錄' }}</p>
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="order in filteredHistory" :key="order.id" class="bg-white">
          <button @click="toggleExpand(order.id)" class="w-full px-4 py-4 flex items-center gap-3 active:bg-slate-50">
            <span class="text-xl shrink-0">📦</span>
            <div class="flex-1 min-w-0 text-left">
              <p class="font-extrabold text-slate-800 text-sm">{{ order.vendor_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">
                {{ fmtDate(order.created_at) }} · 實付 ${{ fmtMoney(order.total_amount) }}
              </p>
            </div>
            <div class="flex items-center gap-1.5 shrink-0">
              <span v-if="payBadge(order)"
                class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                :class="payBadge(order).cls">
                {{ payBadge(order).label }}
              </span>
              <span v-else class="text-xs font-bold px-2 py-1 rounded-full" :class="statusColor(order.status)">
                {{ statusLabel(order.status) }}
              </span>
              <svg class="w-4 h-4 text-slate-300 transition-transform"
                :class="expandedOrderId===order.id?'rotate-90':''"
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
            </div>
          </button>
          <div v-if="expandedOrderId===order.id" class="px-4 pb-3 bg-slate-50 border-t border-slate-100 space-y-1">
            <div v-for="(item,idx) in expandedItems" :key="idx" class="flex justify-between text-sm py-1">
              <span class="text-slate-700">{{ item.name || item.adhoc_name }}</span>
              <span class="text-slate-500 font-bold">{{ item.qty }} {{ item.unit || item.adhoc_unit }}</span>
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
