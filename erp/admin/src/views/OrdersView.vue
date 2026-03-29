<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import UserBadge from '@/components/UserBadge.vue'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const orders = ref([])
const vendors = ref([])
const allItems = ref([])
const loading = ref(true)
const expandedId = ref(null)
const orderDetails = ref({})

// ── Edit Order ──
const showEditModal = ref(false)
const editOrderId = ref(null)
const editOrderVendorName = ref('')
const editOrderForm = ref({ status: '', ordered_at: '', note: '', items: [] })
const editOrderSubmitting = ref(false)
const editOrderError = ref('')
const editToast = ref('')

// ── Delete Order ──
const showDeleteModal = ref(false)
const deleteOrderRecord = ref(null)
const deleteOrderSubmitting = ref(false)

// ── Lightbox ──
const showLightbox = ref(false)
const lightboxImages = ref([])
const lightboxIndex = ref(0)

// Tabs
const orderTab = ref('received')  // 'pending' | 'received'

// Filters
const filterDateFrom = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10))
const filterDateTo = ref(new Date().toISOString().slice(0, 10))
const filterVendor = ref('')
const filterStatus = ref('')

// Pagination
const page = ref(1)
const PAGE_SIZE = 10

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

function resolveUrl(url) {
  if (!url) return null
  if (url.startsWith('http')) return url
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')
  return base + url
}

async function load() {
  loading.value = true
  const [ordRes, vendRes, itemsRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/orders?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
  ])
  if (ordRes.ok) orders.value = await ordRes.json()
  if (vendRes.ok) vendors.value = await vendRes.json()
  if (itemsRes.ok) allItems.value = await itemsRes.json()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  let list = orders.value
  // tab 篩選
  if (orderTab.value === 'pending') {
    list = list.filter(o => o.status === 'confirmed')
    // 待收貨：依叫貨日期倒序
    list = [...list].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  } else {
    list = list.filter(o => o.status === 'received')
    // 已收貨：依收貨日期（updated_at）倒序
    list = [...list].sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
  }
  if (filterDateFrom.value) {
    const dateField = orderTab.value === 'received' ? 'updated_at' : 'created_at'
    list = list.filter(o => (o[dateField] || o.created_at) >= filterDateFrom.value)
  }
  if (filterDateTo.value) {
    const to = filterDateTo.value + 'T23:59:59'
    const dateField = orderTab.value === 'received' ? 'updated_at' : 'created_at'
    list = list.filter(o => (o[dateField] || o.created_at) <= to)
  }
  if (filterVendor.value) {
    list = list.filter(o => String(o.vendor_id) === filterVendor.value)
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paginated = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

function changePage(p) {
  page.value = Math.max(1, Math.min(p, totalPages.value))
}

function applyFilters() {
  page.value = 1
}

function switchOrderTab(tab) {
  orderTab.value = tab
  page.value = 1
  expandedId.value = null
}

async function toggleExpand(order) {
  if (expandedId.value === order.id) { expandedId.value = null; return }
  expandedId.value = order.id
  if (!orderDetails.value[order.id]) {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    if (res.ok) {
      const d = await res.json()
      orderDetails.value[order.id] = Array.isArray(d) ? d : (d.items || [])
    }
  }
}

async function openEditOrder(order, e) {
  e.stopPropagation()
  editOrderId.value = order.id
  editOrderVendorName.value = order.vendor_name
  editOrderError.value = ''
  editOrderForm.value = {
    status: order.status,
    ordered_at: order.created_at?.slice(0, 10) || '',
    note: order.note || '',
    items: []
  }
  if (!orderDetails.value[order.id]) {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    if (res.ok) {
      const d = await res.json()
      orderDetails.value[order.id] = Array.isArray(d) ? d : (d.items || [])
    }
  }
  editOrderForm.value.items = (orderDetails.value[order.id] || []).map(i => ({
    item_id: i.item_id || null,
    adhoc_name: i.adhoc_name || null,
    name: i.name || i.adhoc_name,
    qty: parseFloat(i.qty) || 0,
    unit: i.unit || i.adhoc_unit || ''
  }))
  showEditModal.value = true
}

function addEditItem() {
  if (allItems.value.length === 0) return
  const item = allItems.value[0]
  editOrderForm.value.items.push({ item_id: item.id, adhoc_name: null, name: item.name, qty: 1, unit: item.unit || '' })
}

function removeEditItem(idx) {
  editOrderForm.value.items.splice(idx, 1)
}

function onEditItemSelect(idx, itemId) {
  const item = allItems.value.find(i => i.id === parseInt(itemId))
  if (item) {
    editOrderForm.value.items[idx].item_id = item.id
    editOrderForm.value.items[idx].name = item.name
    editOrderForm.value.items[idx].unit = item.unit || ''
    editOrderForm.value.items[idx].adhoc_name = null
  }
}

async function saveEditOrder() {
  editOrderSubmitting.value = true
  editOrderError.value = ''
  // 記錄修改前的品項（用於比對是否有改動）
  const originalItemSnapshot = JSON.stringify(
    editOrderForm.value.items.map(i => ({ id: i.item_id, qty: parseFloat(i.qty) || 0 })).sort((a,b) => a.id - b.id)
  )
  try {
    const newItems = editOrderForm.value.items.map(i => ({
      item_id: i.item_id,
      adhoc_name: i.adhoc_name,
      adhoc_unit: null,
      qty: parseFloat(i.qty) || 0
    }))
    const res = await fetch(`${API_BASE}/inventory/orders/${editOrderId.value}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: editOrderForm.value.status,
        note: editOrderForm.value.note,
        ordered_at: editOrderForm.value.ordered_at,
        items: newItems
      })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showEditModal.value = false
    delete orderDetails.value[editOrderId.value]
    await load()
    // 品項有異動 → 提醒聯繫廠商
    const newSnapshot = JSON.stringify(
      newItems.map(i => ({ id: i.item_id, qty: i.qty })).sort((a,b) => a.id - b.id)
    )
    if (newSnapshot !== originalItemSnapshot) {
      editToast.value = '⚠ 品項已修改，記得聯繫廠商確認更改'
      setTimeout(() => { editToast.value = '' }, 5000)
    }
  } catch (e) {
    editOrderError.value = e.message
  } finally {
    editOrderSubmitting.value = false
  }
}

async function openDeleteOrder(order, e) {
  e.stopPropagation()
  deleteOrderRecord.value = order
  deleteOrderSubmitting.value = false
  showDeleteModal.value = true
}

async function confirmDeleteOrder() {
  deleteOrderSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${deleteOrderRecord.value.id}`, {
      method: 'DELETE', headers: authHeaders()
    })
    if (!res.ok) throw new Error('刪除失敗')
    showDeleteModal.value = false
    if (expandedId.value === deleteOrderRecord.value.id) expandedId.value = null
    delete orderDetails.value[deleteOrderRecord.value.id]
    await load()
  } catch (e) { alert(e.message) }
  finally { deleteOrderSubmitting.value = false }
}

function openLightbox(imgs, idx = 0) {
  lightboxImages.value = imgs
  lightboxIndex.value = idx
  showLightbox.value = true
}

const statusLabel = (s) => ({ confirmed: '待收貨', received: '已收貨', cancelled: '已取消' }[s] || s)
const statusBadge = (s) => ({
  confirmed: 'bg-[#f59e0b] text-white',
  received: 'bg-[#10b981] text-white',
  cancelled: 'bg-gray-700 text-gray-300',
}[s] || 'bg-gray-700 text-gray-300')

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '—'
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
</script>

<template>
  <div>
    <!-- Tabs -->
    <div class="flex gap-1 mb-5 bg-[#0f1117] rounded-xl p-1 w-fit">
      <button @click="switchOrderTab('received')"
        class="px-5 py-2 rounded-lg text-sm font-bold transition-colors"
        :class="orderTab === 'received' ? 'bg-emerald-600 text-white' : 'text-gray-400 hover:text-gray-200'">
        ✅ 已收貨
      </button>
      <button @click="switchOrderTab('pending')"
        class="px-5 py-2 rounded-lg text-sm font-bold transition-colors"
        :class="orderTab === 'pending' ? 'bg-amber-500 text-black' : 'text-gray-400 hover:text-gray-200'">
        ⏳ 待收貨
        <span v-if="orders.filter(o=>o.status==='confirmed').length" class="ml-1.5 bg-amber-900/60 text-amber-300 text-xs px-1.5 py-0.5 rounded-full">
          {{ orders.filter(o=>o.status==='confirmed').length }}
        </span>
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <input v-model="filterDateFrom" @change="applyFilters" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <span class="text-gray-500 text-sm">至</span>
      <input v-model="filterDateTo" @change="applyFilters" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterVendor" @change="applyFilters"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部供應商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <template v-else>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
              <th class="px-4 py-3 text-left">單號</th>
              <th class="px-4 py-3 text-left">{{ orderTab === 'received' ? '收貨日期' : '叫貨日期' }}</th>
              <th class="px-4 py-3 text-left">供應商</th>
              <th class="px-4 py-3 text-left">送出人</th>
              <th class="px-4 py-3 text-center">品項數</th>
              <th class="px-4 py-3 text-right">參考金額</th>
              <th class="px-4 py-3 text-right">實際金額</th>
              <th class="px-4 py-3 text-center">狀態</th>
              <th class="px-4 py-3 text-center">付款</th>
              <th class="px-4 py-3 text-center">查看</th>
              <th class="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="o in paginated" :key="o.id">
              <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] transition-colors cursor-pointer"
                @click="toggleExpand(o)">
                <td class="px-4 py-3 text-[#63b3ed] text-xs font-mono font-bold">#{{ o.id }}</td>
                <td class="px-4 py-3 text-gray-400 text-xs">{{ orderTab === 'received' ? fmtDate(o.updated_at || o.created_at) : fmtDate(o.created_at) }}</td>
                <td class="px-4 py-3 font-semibold text-gray-200">{{ o.vendor_name }}</td>
                <td class="px-4 py-3"><UserBadge :user="o.created_by" size="sm" /></td>
                <td class="px-4 py-3 text-center text-gray-400">{{ o.total_items }}</td>
                <td class="px-4 py-3 text-right font-mono text-gray-500">
                  {{ o.reference_amount > 0 ? '$' + fmtMoney(o.reference_amount) : '—' }}
                </td>
                <td class="px-4 py-3 text-right font-mono text-gray-300">
                  {{ o.total_amount ? '$' + fmtMoney(o.total_amount) : '—' }}
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="statusBadge(o.status)">
                    {{ statusLabel(o.status) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold px-2 py-0.5 rounded"
                    :class="o.is_paid ? 'bg-emerald-900/40 text-emerald-400' : 'bg-orange-900/40 text-orange-400'">
                    {{ o.is_paid ? '已付' : '待付' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center text-[#63b3ed] text-xs font-bold">
                  {{ expandedId === o.id ? '▲' : '查看' }}
                </td>
                <td class="px-4 py-3 text-center" @click.stop>
                  <button @click="openEditOrder(o, $event)"
                    class="text-xs px-2 py-1 rounded bg-[#2d3748] text-[#63b3ed] hover:bg-[#3d4f63] mr-1">
                    編輯
                  </button>
                  <button @click="openDeleteOrder(o, $event)"
                    class="text-xs px-2 py-1 rounded bg-[#2d3748] text-red-400 hover:bg-red-900/30">
                    刪除
                  </button>
                </td>
              </tr>
              <!-- Expanded detail -->
              <tr v-if="expandedId === o.id" class="border-b border-[#2d3748] bg-[#0f1117]">
                <td colspan="10" class="px-6 py-4">
                  <div class="flex flex-wrap items-center gap-6 mb-3 text-xs">
                    <div class="flex items-center gap-2">
                      <span class="text-gray-500">叫貨人：</span>
                      <UserBadge :user="o.ordered_by || o.created_by" size="md" />
                    </div>
                    <div v-if="o.received_by" class="flex items-center gap-2">
                      <span class="text-gray-500">收貨人：</span>
                      <UserBadge :user="o.received_by" size="md" />
                    </div>
                    <div v-else-if="o.status === 'received'" class="flex items-center gap-2">
                      <span class="text-gray-500">收貨人：</span>
                      <span class="text-gray-500">未紀錄</span>
                    </div>
                  </div>
                  <div v-if="!orderDetails[o.id]" class="text-gray-500 text-sm">載入中…</div>
                  <table v-else class="w-full text-xs">
                    <thead>
                      <tr class="text-[#9ca3af] border-b border-[#2d3748]">
                        <th class="pb-2 text-left">品項</th>
                        <th class="pb-2 text-right">叫貨量</th>
                        <th class="pb-2 text-right">收貨量</th>
                        <th class="pb-2 text-right">差異</th>
                        <th class="pb-2 text-right">小計</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="d in orderDetails[o.id]" :key="d.id || d.name"
                        class="text-gray-400 border-b border-[#1a202c]"
                        :class="d.discrepancy ? 'bg-red-900/10' : ''">
                        <td class="py-1.5">{{ d.name || d.adhoc_name }}</td>
                        <td class="py-1.5 text-right">{{ d.qty }}</td>
                        <td class="py-1.5 text-right">{{ d.actual_qty ?? '—' }}</td>
                        <td class="py-1.5 text-right" :class="d.discrepancy ? 'text-amber-400' : ''">
                          {{ d.discrepancy ? d.discrepancy : '—' }}
                        </td>
                        <td class="py-1.5 text-right text-gray-300">${{ fmtMoney(d.subtotal ?? 0) }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="o.note" class="text-gray-500 text-xs mt-3">備註：{{ o.note }}</p>
                  <div v-if="o.receipt_url" class="mt-3">
                    <p class="text-gray-500 text-xs mb-1">收據憑證</p>
                    <a :href="resolveUrl(o.receipt_url)" target="_blank" rel="noopener">
                      <img :src="resolveUrl(o.receipt_url)" class="max-h-40 object-cover rounded-lg hover:opacity-80 cursor-pointer" />
                    </a>
                  </div>
                </td>
              </tr>
            </template>
            <tr v-if="filtered.length === 0">
              <td colspan="10" class="px-5 py-10 text-center text-gray-600">
                {{ orderTab === 'pending' ? '目前沒有待收貨訂單' : '此期間沒有已收貨紀錄' }}
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 px-5 py-4 border-t border-[#2d3748]">
          <button @click="changePage(page - 1)" :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30 transition-colors">
            上一頁
          </button>
          <button v-for="p in totalPages" :key="p" @click="changePage(p)"
            class="w-8 h-8 rounded-lg text-sm font-bold transition-colors"
            :class="p === page ? 'bg-[#63b3ed] text-black' : 'text-gray-400 hover:bg-[#1f2937]'">
            {{ p }}
          </button>
          <button @click="changePage(page + 1)" :disabled="page === totalPages"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30 transition-colors">
            下一頁
          </button>
        </div>
        <div class="px-5 py-2 text-xs text-gray-600 text-right">
          共 {{ filtered.length }} 筆
        </div>
      </template>
    </div>
  <!-- Toast 提醒 -->
  <div v-if="editToast" class="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] bg-amber-600 text-white text-sm font-semibold px-5 py-3 rounded-xl shadow-lg">
    {{ editToast }}
  </div>
  <!-- Edit Order Modal -->
  <div v-if="showEditModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between px-6 py-4 border-b border-[#2d3748]">
        <h3 class="text-base font-bold text-gray-200">編輯叫貨單</h3>
        <button @click="showEditModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
      </div>
      <div class="px-6 py-5 space-y-4">
        <!-- 廠商（唯讀） -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">供應商（不可更改）</label>
          <p class="text-gray-400 text-sm px-3 py-2 bg-[#0f1117] rounded-lg">{{ editOrderVendorName }}</p>
          <p class="text-xs text-yellow-600 mt-1">若需更換廠商，請刪除此單後重新建立</p>
        </div>
        <!-- 狀態 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">狀態</label>
          <select v-model="editOrderForm.status"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
            <option value="pending">待送出</option>
            <option value="shipped">已送出</option>
            <option value="received">已收貨</option>
            <option value="cancelled">已取消</option>
            <option value="draft">草稿</option>
          </select>
        </div>
        <!-- 叫貨日期 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">叫貨日期</label>
          <input v-model="editOrderForm.ordered_at" type="date"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <!-- 品項 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs text-gray-500">品項明細</label>
            <button @click="addEditItem" class="text-xs text-[#63b3ed] hover:text-blue-300">＋ 新增品項</button>
          </div>
          <div class="space-y-2">
            <div v-for="(item, idx) in editOrderForm.items" :key="idx"
              class="flex items-center gap-2 bg-[#0f1117] rounded-lg px-3 py-2">
              <select @change="onEditItemSelect(idx, $event.target.value)"
                class="flex-1 bg-[#1a202c] border border-[#2d3748] text-gray-300 rounded px-2 py-1 text-xs focus:outline-none">
                <option v-for="ai in allItems" :key="ai.id" :value="ai.id" :selected="ai.id === item.item_id">
                  {{ ai.name }}
                </option>
              </select>
              <input v-model.number="item.qty" type="number" min="0" step="0.5" placeholder="數量"
                class="w-20 bg-[#1a202c] border border-[#2d3748] text-gray-300 rounded px-2 py-1 text-xs text-center focus:outline-none" />
              <span class="text-xs text-gray-500 w-8">{{ item.unit }}</span>
              <button @click="removeEditItem(idx)" class="text-red-400 hover:text-red-300 text-sm">✕</button>
            </div>
          </div>
        </div>
        <!-- 備注 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">備注</label>
          <input v-model="editOrderForm.note" type="text" placeholder="備注說明…"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <p v-if="editOrderError" class="text-red-400 text-sm text-center">{{ editOrderError }}</p>
      </div>
      <div class="flex gap-3 px-6 pb-6">
        <button @click="showEditModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="saveEditOrder" :disabled="editOrderSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#63b3ed] text-black hover:bg-blue-400 disabled:opacity-40">
          {{ editOrderSubmitting ? '儲存中…' : '儲存修改' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Delete Order Dialog -->
  <div v-if="showDeleteModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
      <h3 class="text-base font-bold text-gray-200 mb-4">⚠️ 確認刪除叫貨單</h3>
      <div class="bg-[#0f1117] rounded-xl p-4 mb-4 space-y-1 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">供應商</span>
          <span class="text-gray-300">{{ deleteOrderRecord?.vendor_name }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">日期</span>
          <span class="text-gray-300">{{ fmtDate(deleteOrderRecord?.created_at) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">品項數</span>
          <span class="text-gray-300">{{ deleteOrderRecord?.total_items }} 項</span>
        </div>
      </div>
      <p class="text-xs text-red-400 mb-1">• 刪除後無法復原</p>
      <p v-if="deleteOrderRecord?.status === 'received'" class="text-xs text-amber-400 mb-4">
        ⚠️ 此叫貨單已收貨，相關收貨紀錄亦將一併刪除
      </p>
      <div class="flex gap-3 mt-4">
        <button @click="showDeleteModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="confirmDeleteOrder" :disabled="deleteOrderSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-40">
          {{ deleteOrderSubmitting ? '刪除中…' : '確認刪除' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Lightbox -->
  <div v-if="showLightbox" class="fixed inset-0 bg-black/90 z-[60] flex items-center justify-center"
    @click.self="showLightbox=false">
    <button @click="showLightbox=false" class="absolute top-4 right-4 text-white text-2xl">✕</button>
    <button v-if="lightboxIndex > 0" @click="lightboxIndex--" class="absolute left-4 text-white text-3xl">‹</button>
    <img :src="lightboxImages[lightboxIndex]" class="max-w-full max-h-full rounded-xl object-contain" />
    <button v-if="lightboxIndex < lightboxImages.length-1" @click="lightboxIndex++"
      class="absolute right-4 text-white text-3xl">›</button>
    <p class="absolute bottom-4 text-white text-sm">{{ lightboxIndex+1 }} / {{ lightboxImages.length }}</p>
  </div>

  </div>
</template>
