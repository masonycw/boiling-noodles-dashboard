<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---- Sub-tabs ----
const subTab = ref('order')   // 'order' | 'pending' | 'history'

// ---- Vendor + Items (叫貨) ----
const vendors = ref([])
const selectedVendor = ref(null)
const items = ref([])
const searchQuery = ref('')
const isLoading = ref(true)

// Ad-hoc
const adHocItems = ref([])
const showAdHocForm = ref(false)
const adHocItemName = ref('')
const adHocItemQty = ref(1)
const adHocItemUnit = ref('斤')
const expectedDeliveryDate = ref('')
const submitting = ref(false)

// Free shipping
const freeShippingThreshold = ref(0)
const orderTotal = computed(() =>
  items.value.filter(i => i.qty > 0).reduce((s, i) => s + (i.qty * (parseFloat(i.price) || 0)), 0)
)
const freeShippingProgress = computed(() => {
  if (!freeShippingThreshold.value) return 100
  return Math.min(100, (orderTotal.value / freeShippingThreshold.value) * 100)
})
const orderedCount = computed(() => items.value.filter(i => i.qty > 0).length + adHocItems.value.length)

// ---- Pending (待收貨) ----
const pendingOrders = ref([])
const pendingLoading = ref(false)
const showReceiveModal = ref(false)
const receiveTarget = ref(null)
const receiveOrderItems = ref([])
const receiveForm = ref({ total_amount: '', amount_paid: '', is_paid: false, note: '' })
const receiveSubmitting = ref(false)
const receiveError = ref('')

// ---- History ----
const historyOrders = ref([])
const historyLoading = ref(false)
const expandedOrderId = ref(null)
const expandedItems = ref([])

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
      if (vendors.value.length) selectVendor(vendors.value[0])
      else isLoading.value = false
    } else { isLoading.value = false }
  } catch { isLoading.value = false }
})

async function selectVendor(v) {
  selectedVendor.value = v
  freeShippingThreshold.value = parseFloat(v.free_shipping_threshold) || 0
  isLoading.value = true
  try {
    const iRes = await fetch(`${API_BASE}/inventory/items?vendor_id=${v.id}`, { headers: authHeaders() })
    if (iRes.ok) items.value = (await iRes.json()).map(item => ({ ...item, qty: 0 }))
  } finally { isLoading.value = false }
}

const filteredItems = computed(() =>
  items.value.filter(i => i.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
)

function addAdHocItem() {
  if (!adHocItemName.value.trim()) return
  adHocItems.value.push({ id: Date.now(), name: adHocItemName.value, qty: adHocItemQty.value, unit: adHocItemUnit.value })
  adHocItemName.value = ''; adHocItemQty.value = 1; showAdHocForm.value = false
}

async function generateOrderText() {
  const regularOrdered = items.value.filter(i => i.qty > 0)
  const combined = [...regularOrdered, ...adHocItems.value]
  if (!combined.length) { alert('請先輸入叫貨數量'); return }
  const orderDetails = [
    ...regularOrdered.map(i => ({ item_id: i.id, qty: i.qty })),
    ...adHocItems.value.map(i => ({ adhoc_name: i.name, qty: i.qty, adhoc_unit: i.unit }))
  ]
  try {
    submitting.value = true
    const res = await fetch(`${API_BASE}/inventory/orders`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ vendor_id: selectedVendor.value.id,
        expected_delivery_date: expectedDeliveryDate.value ? new Date(expectedDeliveryDate.value).toISOString() : null,
        items: orderDetails })
    })
    if (!res.ok) throw new Error('無法儲存叫貨紀錄')
    let text = `【滾麵 叫貨單 - ${selectedVendor.value.name}】\n日期: ${new Date().toLocaleDateString('zh-TW')}\n------------------\n`
    combined.forEach(i => { text += `${i.name} ${i.qty} ${i.unit || ''}\n` })
    text += `------------------\n請確認收單，謝謝！`
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text)
      else { const ta = document.createElement('textarea'); ta.value = text; ta.style.position='fixed'; ta.style.left='-9999px'; document.body.appendChild(ta); ta.focus(); ta.select(); document.execCommand('copy'); document.body.removeChild(ta) }
    } catch {}
    alert('叫貨紀錄已存檔，並已複製到剪貼簿！')
    items.value.forEach(i => i.qty = 0); adHocItems.value = []
  } catch (err) { alert('儲存失敗: ' + err.message) }
  finally { submitting.value = false }
}

async function loadPending() {
  pendingLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?status=confirmed`, { headers: authHeaders() })
    if (res.ok) pendingOrders.value = await res.json()
  } finally { pendingLoading.value = false }
}

async function openReceive(order) {
  receiveTarget.value = order
  receiveForm.value = { total_amount: order.total_amount || '', amount_paid: '', is_paid: false, note: '' }
  receiveError.value = ''; receiveOrderItems.value = []; showReceiveModal.value = true
  const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
  if (res.ok) receiveOrderItems.value = await res.json()
}

async function submitReceive() {
  receiveError.value = ''
  const amount = parseFloat(receiveForm.value.total_amount)
  if (!amount) { receiveError.value = '請輸入金額'; return }
  receiveSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${receiveTarget.value.id}/receive`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ total_amount: amount, amount_paid: parseFloat(receiveForm.value.amount_paid) || 0,
        is_paid: receiveForm.value.is_paid, note: receiveForm.value.note || null })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '收貨失敗') }
    showReceiveModal.value = false; await loadPending()
  } catch (e) { receiveError.value = e.message }
  finally { receiveSubmitting.value = false }
}

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
  if (res.ok) expandedItems.value = await res.json()
}

function switchTab(tab) {
  subTab.value = tab
  if (tab === 'pending') loadPending()
  if (tab === 'history' && !historyOrders.value.length) loadHistory()
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' }) : ''
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
const statusLabel = s => ({ pending: '待確認', confirmed: '待收貨', received: '已收貨', cancelled: '已取消' }[s] || s)
const statusColor = s => ({ pending: 'bg-gray-100 text-gray-500', confirmed: 'bg-amber-100 text-amber-600', received: 'bg-emerald-100 text-emerald-600', cancelled: 'bg-red-100 text-red-400' }[s] || 'bg-gray-100 text-gray-400')
</script>

<template>
  <div class="min-h-screen bg-slate-50 flex flex-col pb-16">
    <!-- Header + sub-tabs -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div class="px-4 pt-12 pb-2">
        <h1 class="text-xl font-extrabold text-slate-800">訂單管理</h1>
      </div>
      <div class="flex border-t border-slate-100">
        <button @click="switchTab('order')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='order' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">叫貨</button>
        <button @click="switchTab('pending')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='pending' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">
          待收貨
          <span v-if="pendingOrders.length" class="ml-1 inline-flex items-center justify-center w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full">{{ pendingOrders.length }}</span>
        </button>
        <button @click="switchTab('history')" class="flex-1 py-3 text-sm font-bold border-b-2 transition-all"
          :class="subTab==='history' ? 'text-orange-500 border-orange-500' : 'text-slate-400 border-transparent'">歷史紀錄</button>
      </div>
    </header>

    <!-- 叫貨 -->
    <div v-if="subTab==='order'" class="flex-1 pb-32">
      <div class="bg-white border-b border-slate-100 px-3 py-3">
        <div class="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          <button v-for="v in vendors" :key="v.id" @click="selectVendor(v)"
            class="shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-all"
            :class="selectedVendor?.id===v.id ? 'bg-orange-500 text-white shadow' : 'bg-slate-100 text-slate-500'">
            {{ v.name }}
          </button>
        </div>
        <div v-if="freeShippingThreshold > 0" class="mt-2">
          <div class="flex justify-between items-center mb-1">
            <span class="text-[10px] font-bold text-slate-500">免運進度</span>
            <span class="text-[10px] font-bold" :class="orderTotal>=freeShippingThreshold?'text-emerald-600':'text-orange-500'">
              ${{ fmtMoney(orderTotal) }} / ${{ fmtMoney(freeShippingThreshold) }}
            </span>
          </div>
          <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all duration-300"
              :class="orderTotal>=freeShippingThreshold?'bg-emerald-500':'bg-orange-400'"
              :style="{ width: freeShippingProgress+'%' }"></div>
          </div>
        </div>
        <div class="flex items-center justify-between mt-2 bg-orange-50 rounded-xl px-3 py-2 border border-orange-100">
          <label class="text-xs font-bold text-orange-700">📅 預計到貨日</label>
          <input v-model="expectedDeliveryDate" type="date" class="bg-transparent border-none text-xs font-bold text-slate-700 focus:outline-none" />
        </div>
      </div>

      <div class="px-4 pt-3 pb-2">
        <div class="relative">
          <input v-model="searchQuery" type="text" placeholder="搜尋品項…"
            class="w-full bg-slate-100 rounded-xl py-2.5 pl-9 pr-4 text-sm font-medium focus:ring-2 focus:ring-orange-400 focus:outline-none" />
          <svg class="w-4 h-4 text-slate-400 absolute left-3 top-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>
      </div>

      <div v-if="isLoading" class="flex flex-col items-center py-16 gap-3">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        <p class="text-slate-400 text-sm">載入品項中…</p>
      </div>
      <div v-else class="px-4 space-y-3 pb-4">
        <div v-for="item in adHocItems" :key="item.id"
          class="bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between">
          <div><span class="font-bold text-slate-900">{{ item.name }}</span><span class="text-xs text-orange-500 ml-2 font-bold">臨時</span></div>
          <div class="flex items-center gap-2">
            <span class="font-extrabold">{{ item.qty }} {{ item.unit }}</span>
            <button @click="adHocItems=adHocItems.filter(i=>i.id!==item.id)" class="text-rose-400">✕</button>
          </div>
        </div>
        <div v-for="item in filteredItems" :key="item.id"
          class="bg-white border border-slate-200 rounded-2xl p-4 flex items-center justify-between shadow-sm">
          <div class="flex flex-col min-w-0">
            <span class="font-bold text-slate-900 truncate">{{ item.name }}</span>
            <span class="text-slate-400 text-xs">{{ item.unit }}<span v-if="item.price" class="ml-1 text-orange-500">${{ fmtMoney(item.price) }}</span></span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button @click="item.qty=Math.max(0,item.qty-1)" class="w-9 h-9 bg-slate-100 rounded-full flex items-center justify-center font-bold text-slate-600 active:bg-slate-200">−</button>
            <input v-model.number="item.qty" type="number" min="0"
              class="w-14 bg-transparent border-b-2 text-center font-extrabold text-lg text-slate-900 focus:outline-none"
              :class="item.qty>0?'border-orange-500':'border-slate-200'" />
            <button @click="item.qty+=1" class="w-9 h-9 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200">+</button>
          </div>
        </div>
        <div class="flex justify-center mt-2">
          <button v-if="!showAdHocForm" @click="showAdHocForm=true"
            class="flex items-center gap-2 text-orange-500 font-bold bg-white px-5 py-2.5 rounded-2xl border-2 border-orange-100 shadow-sm text-sm active:scale-95">+ 新增臨時品項</button>
        </div>
        <div v-if="showAdHocForm" class="bg-white p-5 rounded-3xl border-2 border-orange-100 shadow-lg">
          <h3 class="font-extrabold text-slate-900 mb-4">新增臨時品項</h3>
          <div class="space-y-3">
            <input v-model="adHocItemName" type="text" placeholder="品項名稱"
              class="w-full bg-slate-50 rounded-xl py-3 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            <div class="flex gap-2">
              <input v-model.number="adHocItemQty" type="number" placeholder="數量"
                class="flex-1 bg-slate-50 rounded-xl py-3 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
              <input v-model="adHocItemUnit" type="text" placeholder="單位"
                class="w-20 bg-slate-50 rounded-xl py-3 px-4 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div class="flex gap-3">
              <button @click="showAdHocForm=false" class="flex-1 bg-slate-100 text-slate-500 font-bold py-3 rounded-xl">取消</button>
              <button @click="addAdHocItem" class="flex-1 bg-orange-500 text-white font-bold py-3 rounded-xl">加入清單</button>
            </div>
          </div>
        </div>
      </div>

      <div class="fixed bottom-16 inset-x-0 bg-white border-t border-slate-200 px-4 py-3 shadow-lg z-20 flex gap-3">
        <div class="flex-1">
          <p class="text-[10px] text-slate-400 uppercase font-bold">已選品項</p>
          <p class="text-lg font-extrabold text-slate-900">{{ orderedCount }} 項</p>
        </div>
        <button @click="generateOrderText" :disabled="submitting||orderedCount===0"
          class="flex-[2] bg-gradient-to-r from-orange-500 to-rose-600 text-white font-bold py-3.5 rounded-2xl shadow-lg active:scale-95 disabled:opacity-40 flex items-center justify-center gap-2">
          <span v-if="submitting">處理中…</span>
          <span v-else>📋 複製叫貨訊息</span>
        </button>
      </div>
    </div>

    <!-- 待收貨 -->
    <div v-else-if="subTab==='pending'" class="flex-1 pb-4">
      <div v-if="pendingLoading" class="flex justify-center py-16">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="!pendingOrders.length" class="text-center py-16">
        <p class="text-5xl mb-3">📦</p><p class="text-slate-400 font-bold">無待收貨訂單</p>
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="order in pendingOrders" :key="order.id" class="bg-white px-4 py-4 flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <p class="font-extrabold text-slate-800">{{ order.vendor_name }}</p>
            <p class="text-xs text-slate-400 mt-0.5">下單：{{ fmtDate(order.created_at) }}<span v-if="order.expected_delivery_date"> · 預計：{{ fmtDate(order.expected_delivery_date) }}</span></p>
            <p class="text-xs text-slate-500 mt-0.5">{{ order.total_items }} 項品項</p>
          </div>
          <div class="text-right shrink-0">
            <span class="block text-xs font-bold px-2 py-1 rounded-full mb-2" :class="statusColor(order.status)">{{ statusLabel(order.status) }}</span>
            <button @click="openReceive(order)" class="bg-orange-500 text-white text-xs font-bold px-3 py-1.5 rounded-xl active:scale-95">簽收</button>
          </div>
        </div>
      </div>

      <div v-if="showReceiveModal" class="fixed inset-0 bg-black/50 z-50 flex items-end">
        <div class="bg-white w-full rounded-t-3xl p-6 max-h-[85vh] overflow-y-auto">
          <div class="flex justify-between items-center mb-4">
            <h3 class="text-lg font-extrabold text-slate-800">確認收貨 — {{ receiveTarget?.vendor_name }}</h3>
            <button @click="showReceiveModal=false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
          <div v-if="receiveOrderItems.length" class="mb-4 bg-slate-50 rounded-xl p-3 space-y-1">
            <div v-for="(item,idx) in receiveOrderItems" :key="idx" class="flex justify-between text-sm">
              <span class="text-slate-700">{{ item.name||item.adhoc_name }}</span>
              <span class="text-slate-500 font-bold">{{ item.qty }} {{ item.unit||item.adhoc_unit }}</span>
            </div>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-bold text-slate-600 mb-1">訂單金額 ($)</label>
              <input v-model="receiveForm.total_amount" type="number" inputmode="decimal" placeholder="0"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-xl font-extrabold text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div>
              <label class="block text-sm font-bold text-slate-600 mb-1">已付金額 ($)</label>
              <input v-model="receiveForm.amount_paid" type="number" inputmode="decimal" placeholder="0"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div class="flex items-center gap-3">
              <input v-model="receiveForm.is_paid" type="checkbox" id="is_paid" class="w-4 h-4 accent-orange-500" />
              <label for="is_paid" class="text-sm font-bold text-slate-700">已全額付清</label>
            </div>
            <div>
              <label class="block text-sm font-bold text-slate-600 mb-1">備註（選填）</label>
              <input v-model="receiveForm.note" type="text" placeholder="如有差異請說明…"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div v-if="receiveError" class="text-rose-500 text-sm text-center">{{ receiveError }}</div>
            <button @click="submitReceive" :disabled="receiveSubmitting"
              class="w-full bg-orange-500 text-white font-bold py-4 rounded-2xl active:scale-95 disabled:opacity-40">
              {{ receiveSubmitting?'處理中…':'確認收貨' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 歷史紀錄 -->
    <div v-else-if="subTab==='history'" class="flex-1 pb-4">
      <div v-if="historyLoading" class="flex justify-center py-16">
        <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="!historyOrders.length" class="text-center py-16">
        <p class="text-5xl mb-3">📋</p><p class="text-slate-400 font-bold">近 30 天無紀錄</p>
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="order in historyOrders" :key="order.id" class="bg-white">
          <button @click="toggleExpand(order.id)" class="w-full px-4 py-4 flex items-center gap-3 active:bg-slate-50">
            <div class="flex-1 min-w-0 text-left">
              <p class="font-extrabold text-slate-800">{{ order.vendor_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">{{ fmtDate(order.created_at) }} · {{ order.total_items }} 項</p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <span v-if="order.total_amount" class="text-sm font-bold text-slate-700">${{ fmtMoney(order.total_amount) }}</span>
              <span class="text-xs font-bold px-2 py-1 rounded-full" :class="statusColor(order.status)">{{ statusLabel(order.status) }}</span>
              <svg class="w-4 h-4 text-slate-300 transition-transform" :class="expandedOrderId===order.id?'rotate-90':''"
                fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
              </svg>
            </div>
          </button>
          <div v-if="expandedOrderId===order.id" class="px-4 pb-4 bg-slate-50 border-t border-slate-100 space-y-1">
            <div v-for="(item,idx) in expandedItems" :key="idx" class="flex justify-between text-sm py-1">
              <span class="text-slate-700">{{ item.name||item.adhoc_name }}</span>
              <span class="text-slate-500 font-bold">{{ item.qty }} {{ item.unit||item.adhoc_unit }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
input[type=number] { -moz-appearance: textfield; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
</style>
