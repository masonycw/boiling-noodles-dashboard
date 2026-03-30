<script setup>
import { ref, onMounted, computed, onUnmounted, toRaw, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import UserBadge from '@/components/UserBadge.vue'
import { formatDualUnit } from '@/utils/formatters'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
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
const stocktakeGroups = ref([])
const vendorDeliveryDates = ref({})  // { vendor_id: 'YYYY-MM-DD' }，群組模式各廠商獨立到貨日
const vendorMeta = ref({})           // { vendor_id: vendorObject }，含 free_shipping_threshold 等
const selectedVendor = ref(null)

// Merged list: vendors first, then active stocktake groups (marked with _isGroup)
const vendorAndGroupList = computed(() => [
  ...vendors.value,
  ...stocktakeGroups.value.filter(g => g.is_active).map(g => ({ ...g, _isGroup: true })),
])

// 下拉選單 key helper
const selectedVendorKey = ref('')
const vendorSearch = ref('')
const showVendorDropdown = ref(false)
// 所有品項（供搜尋廠商用）
const allItemsForSearch = ref([])  // { id, name, vendor_id }
const filteredVendorList = computed(() => {
  const q = vendorSearch.value.trim().toLowerCase()
  if (!q) return vendorAndGroupList.value

  // 廠商名稱匹配
  const byVendor = vendorAndGroupList.value.filter(v => v.name.toLowerCase().includes(q))
  const byVendorIds = new Set(byVendor.map(v => v.id))

  // 品項名稱匹配 → 找出對應廠商（去重，排除已出現的廠商）
  const matchedItemsByVendor = {}
  for (const i of allItemsForSearch.value) {
    if (i.name.toLowerCase().includes(q) && i.vendor_id && !byVendorIds.has(i.vendor_id)) {
      if (!matchedItemsByVendor[i.vendor_id]) matchedItemsByVendor[i.vendor_id] = []
      matchedItemsByVendor[i.vendor_id].push(i.name)
    }
  }
  const byItem = vendorAndGroupList.value
    .filter(v => !v._isGroup && matchedItemsByVendor[v.id])
    .map(v => ({ ...v, _matchedItems: matchedItemsByVendor[v.id] }))

  return [...byVendor, ...byItem]
})
function vendorKey(v) { return (v._isGroup ? 'g' : 'v') + v.id }
watch(selectedVendorKey, async (key) => {
  const v = vendorAndGroupList.value.find(v => vendorKey(v) === key)
  if (v) await selectVendor(v)
})
function handleVendorFocus() {
  vendorSearch.value = ''
  showVendorDropdown.value = true
}
function handleVendorBlur() {
  setTimeout(() => {
    showVendorDropdown.value = false
    // 恢復顯示已選廠商名稱
    if (selectedVendor.value) {
      vendorSearch.value = (selectedVendor.value._isGroup ? '📦 ' : '🏪 ') + selectedVendor.value.name
    }
  }, 150)
}
async function pickVendor(v) {
  vendorSearch.value = (v._isGroup ? '📦 ' : '🏪 ') + v.name
  showVendorDropdown.value = false
  await selectVendor(v)
}
const items = ref([])
const isLoading = ref(true)
const submitting = ref(false)
const submitToast = ref('')
const noLineWarning = ref(false)   // 廠商未串接 LINE 時的跳出提醒
const expectedDeliveryDate = ref('')
const adHocItems = ref([])
const showAdHocForm = ref(false)
const adHocName = ref(''); const adHocQty = ref(1); const adHocUnit = ref('個')

// Order preview sheet (legacy - kept for reference but replaced by direct submit)
const showPreviewSheet = ref(false)
const previewText = ref('')
const previewCopied = ref(false)

// ── 品項依廠商分組（群組叫貨模式用）──────────────────
const itemsByVendor = computed(() => {
  const map = {}
  for (const item of items.value) {
    const vid = item.vendor_id || 0
    if (!map[vid]) {
      const meta = vendorMeta.value[vid] || vendors.value.find(v => v.id === vid) || {}
      map[vid] = {
        vendor_id: vid,
        vendor_name: meta.name || '其他',
        free_shipping_threshold: parseFloat(meta.free_shipping_threshold) || 0,
        note: meta.note || '',
        items: []
      }
    }
    map[vid].items.push(item)
  }
  return Object.values(map)
})

// 各廠商目前叫貨金額小計
const vendorOrderTotals = computed(() => {
  const totals = {}
  for (const group of itemsByVendor.value) {
    totals[group.vendor_id] = group.items.reduce(
      (sum, i) => sum + (i.qty || 0) * (parseFloat(i.price) || 0), 0
    )
  }
  return totals
})

// ── D+N 到貨倒數 (P3-3) ──────────────────────────
const deliveryDays = computed(() => selectedVendor.value?.delivery_days_to_arrive || 2)
const estimatedDeliveryLabel = computed(() => {
  const n = deliveryDays.value
  const d = new Date(); d.setDate(d.getDate() + n)
  return `D+${n} 到貨：${d.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })}`
})

// ── 草稿自動儲存 (P3-3) ──────────────────────────
const draftBanner = ref(null)
const DRAFT_PREFIX = () => `draft:order:${auth.user?.id || 'anon'}:`
const DRAFT_KEY = (vkey) => `${DRAFT_PREFIX()}${vkey || 'none'}`
const DRAFT_TTL = 48 * 60 * 60 * 1000

// 草稿選單
const showDraftSheet = ref(false)
const draftsList = ref([])

function saveDraft() {
  if (!selectedVendor.value) return
  const hasOrder = orderedCount.value > 0 || adHocItems.value.length > 0
  const hasStocktake = modeStocktake.value && items.value.some(i => i.actual_qty != null && i.actual_qty !== '')
  if (!hasOrder && !hasStocktake) return
  try {
    const vkey = vendorKey(selectedVendor.value)  // 'v2' = 廠商, 'g2' = 群組
    const draft = {
      timestamp: Date.now(),
      vendorKey: vkey,
      vendorId: selectedVendor.value.id,
      isGroup: selectedVendor.value._isGroup || false,
      vendorName: selectedVendor.value.name,
      modeOrder: modeOrder.value,
      modeStocktake: modeStocktake.value,
      qtys: toRaw(items.value).filter(i => i.qty > 0).map(i => ({ id: i.id, qty: i.qty })),
      stocktakeQtys: toRaw(items.value)
        .filter(i => i.actual_qty != null && i.actual_qty !== '')
        .map(i => ({ id: i.id, actual_qty: i.actual_qty })),
      adHocItems: toRaw(adHocItems.value),
      expectedDeliveryDate: expectedDeliveryDate.value
    }
    localStorage.setItem(DRAFT_KEY(vkey), JSON.stringify(draft))
  } catch (e) {
    console.error('Draft save failed:', e)
  }
}

function getAllDrafts() {
  const prefix = DRAFT_PREFIX()
  const drafts = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (!key?.startsWith(prefix)) continue
    try {
      const d = JSON.parse(localStorage.getItem(key))
      if (Date.now() - d.timestamp <= DRAFT_TTL) {
        drafts.push({ ...d, _key: key })
      } else {
        localStorage.removeItem(key)
      }
    } catch { localStorage.removeItem(key) }
  }
  return drafts.sort((a, b) => b.timestamp - a.timestamp)
}

function openDraftSheet() {
  draftsList.value = getAllDrafts()
  showDraftSheet.value = true
}

function loadDraftBanner() {
  // 向後相容：掃描是否有任一草稿，有就顯示 banner（onMounted 用）
  const drafts = getAllDrafts()
  if (drafts.length) draftBanner.value = drafts[0]
}

async function resumeDraft(draft) {
  showDraftSheet.value = false
  draftBanner.value = null
  let v
  if (draft.vendorKey) {
    // 新格式：直接用 vendorKey（'g2'/'v2'）比對
    v = vendorAndGroupList.value.find(x => vendorKey(x) === draft.vendorKey)
  } else if (draft.isGroup) {
    // 新格式有 isGroup 但無 vendorKey
    v = vendorAndGroupList.value.find(x => x._isGroup && x.id === draft.vendorId)
  } else {
    // 舊格式（只有 vendorId 數字）：先嘗試比名稱找群組，避免 id 碰撞（如群組2 ≠ 廠商2）
    v = vendorAndGroupList.value.find(x => x._isGroup && x.name === draft.vendorName)
      || vendors.value.find(x => x.id === draft.vendorId)
  }
  // 自動遷移舊草稿：re-save 成新格式並刪除舊 key
  if (v && !draft.vendorKey) {
    const newVkey = vendorKey(v)
    const migrated = { ...draft, vendorKey: newVkey, isGroup: v._isGroup || false }
    localStorage.setItem(DRAFT_KEY(newVkey), JSON.stringify(migrated))
    if (draft._key) localStorage.removeItem(draft._key)
  }
  if (v) {
    await selectVendor(v)
    // 恢復叫貨數量
    if (draft.qtys) {
      draft.qtys.forEach(({ id, qty }) => {
        const item = items.value.find(i => i.id === id)
        if (item) item.qty = qty
      })
    }
    // 恢復盤點數量
    if (draft.stocktakeQtys) {
      draft.stocktakeQtys.forEach(({ id, actual_qty }) => {
        const item = items.value.find(i => i.id === id)
        if (item) item.actual_qty = actual_qty
      })
    }
    // 恢復模式
    if (draft.modeOrder !== undefined) { modeOrder.value = draft.modeOrder; saveMode() }
    if (draft.modeStocktake !== undefined) { modeStocktake.value = draft.modeStocktake; saveMode() }
    adHocItems.value = draft.adHocItems || []
    if (draft.expectedDeliveryDate) expectedDeliveryDate.value = draft.expectedDeliveryDate
  }
  // 不在這裡刪草稿——草稿在送出或手動丟棄才清除
  draftsList.value = getAllDrafts()
}

function discardDraft(draft) {
  localStorage.removeItem(draft?._key || DRAFT_KEY(draft?.vendorId))
  draftBanner.value = null
  draftsList.value = getAllDrafts()
  if (!draftsList.value.length) showDraftSheet.value = false
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
const showEditOrderModal = ref(false)
const editOrderTarget = ref(null)
const editOrderForm = ref({ expected_delivery_date: '', note: '' })
const editOrderSubmitting = ref(false)
const editOrderItems = ref([])
const editOrderItemsLoading = ref(false)
const editOrderNewItem = ref({ name: '', unit: '', qty: 1 })
const copyMsgSheet = ref({ show: false, text: '' })
const showReceiveModal = ref(false)
const receiveTarget = ref(null)
const receiveOrderItems = ref([])
const receiveForm = ref({ total_amount: '', amount_paid: '', payment_mode: 'cash', note: '' })
const receiveSubmitting = ref(false)
const receiveError = ref('')
const receivePhoto = ref(null)
const receivePhotoPreview = ref('')
const photoInput = ref(null)

// ── 補拍單據 ──────────────────────────────────
const rephotaOrderId = ref(null)
const rephotaUploading = ref(false)
const rephotaInput = ref(null)

async function handleRephotaSelect(e, order) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  rephotaOrderId.value = order.id
  rephotaUploading.value = true
  try {
    const { compressImage } = await import('@/composables/useImageCompress')
    const compressed = await compressImage(file)
    const fd = new FormData()
    fd.append('file', compressed)
    const upRes = await fetch(`${API_BASE}/uploads/image`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: fd
    })
    if (!upRes.ok) throw new Error('上傳失敗')
    const upData = await upRes.json()
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')
    const photoUrl = base + upData.url
    const patchRes = await fetch(`${API_BASE}/inventory/orders/${order.id}/receipt-photo`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ receipt_url: photoUrl })
    })
    if (!patchRes.ok) throw new Error('儲存失敗')
    // 更新本地紀錄
    const idx = historyOrders.value.findIndex(o => o.id === order.id)
    if (idx >= 0) historyOrders.value[idx] = { ...historyOrders.value[idx], receipt_url: photoUrl }
    order.receipt_url = photoUrl
    submitToast.value = '✅ 單據已更新'
    setTimeout(() => { submitToast.value = '' }, 2500)
  } catch (err) {
    submitToast.value = '⚠ ' + err.message
    setTimeout(() => { submitToast.value = '' }, 2500)
  } finally {
    rephotaUploading.value = false
    rephotaOrderId.value = null
  }
}

// F-07: 依到貨日排序 + 今日/未來分切線
const pendingSortedWithDivider = computed(() => {
  const today = new Date(); today.setHours(0,0,0,0)
  const tomorrow = new Date(today); tomorrow.setDate(tomorrow.getDate() + 1)

  const todayList = [...pendingOrders.value]
    .filter(o => {
      if (!o.expected_delivery_date) return true
      const d = new Date(o.expected_delivery_date); d.setHours(0,0,0,0)
      return d.getTime() < tomorrow.getTime()
    })
    .sort((a, b) => {
      if (!a.expected_delivery_date) return 1
      if (!b.expected_delivery_date) return -1
      return new Date(a.expected_delivery_date) - new Date(b.expected_delivery_date)
    })

  const futureList = [...pendingOrders.value]
    .filter(o => {
      if (!o.expected_delivery_date) return false
      const d = new Date(o.expected_delivery_date); d.setHours(0,0,0,0)
      return d.getTime() >= tomorrow.getTime()
    })
    .sort((a, b) => new Date(a.expected_delivery_date) - new Date(b.expected_delivery_date))

  const result = todayList.map(o => ({ ...o, _type: 'order' }))
  if (todayList.length > 0 && futureList.length > 0) {
    result.push({ _type: 'divider', _futureCount: futureList.length })
  }
  futureList.forEach(o => result.push({ ...o, _type: 'future' }))
  return result
})

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
const stocktakeSearch = ref('')
const editingSessionId = ref(null)
const editingItems = ref([])
const editingSubmitting = ref(false)

const filteredHistory = computed(() => {
  if (!historySearch.value.trim()) return historyOrders.value
  const q = historySearch.value.toLowerCase()
  return historyOrders.value.filter(o =>
    (o.vendor_name || '').toLowerCase().includes(q) ||
    fmtDate(o.created_at).includes(q)
  )
})

const filteredSessions = computed(() => {
  if (!stocktakeSearch.value.trim()) return historySessions.value
  const q = stocktakeSearch.value.toLowerCase()
  return historySessions.value.filter(s =>
    (s.group_name || '全部品項').toLowerCase().includes(q) ||
    fmtDate(s.created_at).includes(q)
  )
})

// 底部抽屜：只顯示目前廠商的品項（依 item_id 過濾）
const vendorItemIds = computed(() => new Set(items.value.map(i => i.id)))
const vendorFilteredHistory = computed(() => {
  if (!selectedVendor.value || !stocktakeHistory.value.length) return stocktakeHistory.value
  const ids = vendorItemIds.value
  return stocktakeHistory.value.filter(record =>
    !record.items?.length || record.items.some(it => ids.has(it.item_id))
  )
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

onMounted(async () => {
  try {
    const [vRes, gRes] = await Promise.all([
      fetch(`${API_BASE}/inventory/vendors?show_in_ordering=true`, { headers: authHeaders() }),
      fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
    ])
    if (vRes.ok) {
      vendors.value = await vRes.json()
      vendors.value.forEach(v => {
        vendorDeliveryDates.value[v.id] = calcDeliveryDate(v)
        vendorMeta.value[v.id] = v
      })
    }
    if (gRes.ok) stocktakeGroups.value = await gRes.json()
    // 背景載入所有品項，供廠商搜尋使用
    fetch(`${API_BASE}/inventory/items`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(all => { allItemsForSearch.value = all.map(i => ({ id: i.id, name: i.name, vendor_id: i.vendor_id })) })
      .catch(() => {})

    // 再載入所有廠商（不過濾 show_in_ordering），補充群組內廠商的 meta
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(all => all.forEach(v => {
        if (!vendorMeta.value[v.id]) {
          vendorDeliveryDates.value[v.id] = calcDeliveryDate(v)
          vendorMeta.value[v.id] = v
        }
      }))

    // F-04: auto-select vendor from query param
    const qVendorId = route.query.vendorId ? parseInt(route.query.vendorId) : null
    const initVendor = qVendorId
      ? (vendors.value.find(v => v.id === qVendorId) || vendors.value[0])
      : vendors.value[0]
    if (initVendor) await selectVendor(initVendor)
    else isLoading.value = false
  } catch { isLoading.value = false }
  // F-05: auto-open receive modal from query param
  const qOrderId = route.query.orderId ? parseInt(route.query.orderId) : null
  if (qOrderId) {
    subTab.value = 'pending'
    await loadPending()
    const target = pendingOrders.value.find(o => o.id === qOrderId)
    if (target) await openReceive(target)
  }
  // Draft auto-save setup (P3-3)
  loadDraftBanner()
  _draftTimer = setInterval(() => { saveDraft() }, 30000)
})

onUnmounted(() => { if (_draftTimer) clearInterval(_draftTimer) })

// D+X 到貨日計算（含廠商休息日遞延）
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
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

async function selectVendor(v) {
  selectedVendor.value = v
  selectedVendorKey.value = vendorKey(v)
  vendorSearch.value = (v._isGroup ? '📦 ' : '🏪 ') + v.name
  isLoading.value = true
  try {
    const param = v._isGroup ? `stocktake_group_id=${v.id}` : `vendor_id=${v.id}`
    const iRes = await fetch(`${API_BASE}/inventory/items?${param}`, { headers: authHeaders() })
    items.value = iRes.ok ? (await iRes.json()).map(i => ({ ...i, qty: 0, actual_qty: null })) : []
    if (!v._isGroup) {
      // 單一廠商模式：自動設定預計到貨日
      expectedDeliveryDate.value = calcDeliveryDate(v)
    } else {
      // 群組模式：確保每個廠商的 delivery date 和 meta 都有值
      const uniqueVids = [...new Set(items.value.map(i => i.vendor_id).filter(Boolean))]
      const missingVids = uniqueVids.filter(vid => !vendorMeta.value[vid])
      if (missingVids.length > 0) {
        // 補載入缺少的廠商資訊
        const allVRes = await fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() })
        if (allVRes.ok) {
          const allVendors = await allVRes.json()
          allVendors.forEach(vendor => {
            vendorMeta.value[vendor.id] = vendor
            if (!vendorDeliveryDates.value[vendor.id]) {
              vendorDeliveryDates.value[vendor.id] = calcDeliveryDate(vendor)
            }
          })
        }
      }
      // 確保每個 vid 都有 delivery date
      uniqueVids.forEach(vid => {
        if (!vendorDeliveryDates.value[vid]) {
          const meta = vendorMeta.value[vid]
          vendorDeliveryDates.value[vid] = meta ? calcDeliveryDate(meta) : ''
        }
      })
    }
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

function saveDraftToServer() {
  saveDraft()
  loadDraftBanner()  // 重新讀入 localStorage，讓 banner 可再次出現
  draftToast.value = '草稿已儲存 ✓'
  setTimeout(() => { draftToast.value = '' }, 2000)
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

function isToday(d) {
  if (!d) return false
  const dt = new Date(d)
  const now = new Date()
  return dt.getFullYear() === now.getFullYear() &&
    dt.getMonth() === now.getMonth() &&
    dt.getDate() === now.getDate()
}

async function startEditSession(s) {
  editingSessionId.value = s.id
  // 展開該 session
  const set = new Set(expandedSessions.value)
  set.add(s.id)
  expandedSessions.value = set

  // 取得已盤點品項（以 item_id 建立 map）
  const existingMap = {}
  for (const it of (s.items || [])) {
    existingMap[it.item_id] = it
  }

  // 若有群組，載入群組所有品項（含未盤點的）
  let allItems = []
  if (s.stocktake_group_id) {
    const res = await fetch(`${API_BASE}/inventory/items?stocktake_group_id=${s.stocktake_group_id}`, { headers: authHeaders() })
    if (res.ok) allItems = await res.json()
  }

  // 合併：已盤點的保留 counted_qty，未盤點的預設 edit_qty=0
  const mergedMap = {}
  // 先放已盤點的
  for (const it of (s.items || [])) {
    mergedMap[it.item_id] = { ...it, edit_qty: parseFloat(it.counted_qty ?? 0) }
  }
  // 再補未盤點的群組品項
  for (const item of allItems) {
    if (!mergedMap[item.id]) {
      mergedMap[item.id] = {
        item_id: item.id,
        item_name: item.name,
        unit: item.unit,
        counted_qty: null,
        expected_qty: item.current_stock ?? 0,
        edit_qty: 0,
      }
    }
  }

  editingItems.value = Object.values(mergedMap)
}

function cancelEditSession() {
  editingSessionId.value = null
  editingItems.value = []
}

async function saveEditSession() {
  editingSubmitting.value = true
  try {
    const patch = {
      // 原本已有計數的品項：全部更新；新加入品項：只有輸入 > 0 才送出
      items: editingItems.value
        .filter(it => it.counted_qty !== null || (parseFloat(it.edit_qty) || 0) > 0)
        .map(it => ({
          item_id: it.item_id,
          counted_qty: parseFloat(it.edit_qty) || 0
        }))
    }
    await fetch(`${API_BASE}/stocktake/${editingSessionId.value}`, {
      method: 'PATCH', headers: authHeaders(),
      body: JSON.stringify(patch)
    })
    await fetch(`${API_BASE}/stocktake/${editingSessionId.value}/submit`, {
      method: 'PUT', headers: authHeaders()
    })
    editingSessionId.value = null
    editingItems.value = []
    await loadHistoryStocktake()
  } catch (e) {
    console.error('Edit session failed:', e)
  } finally {
    editingSubmitting.value = false
  }
}

// A1: 送出待收貨（替換舊的複製叫貨單）
async function submitPendingReceive() {
  const orderItems = items.value.filter(i => i.qty > 0)
  const allItems = [...orderItems, ...adHocItems.value]
  if (!allItems.length && !modeStocktake.value) return

  submitting.value = true
  try {
    if (modeOrder.value && allItems.length > 0) {
      if (selectedVendor.value._isGroup) {
        // 盤點群組模式：按品項的實際 vendor_id 分組，各廠商獨立建立訂單
        const byVendor = {}
        for (const i of orderItems) {
          const vid = i.vendor_id
          if (!vid) continue
          if (!byVendor[vid]) byVendor[vid] = []
          byVendor[vid].push({ item_id: i.id, qty: i.qty })
        }
        for (const [vid, vendorItems] of Object.entries(byVendor)) {
          // 優先用使用者在分隔線調整過的到貨日，否則用 D+X 計算
          const delivDate = vendorDeliveryDates.value[parseInt(vid)] || expectedDeliveryDate.value
          const res = await fetch(`${API_BASE}/inventory/orders`, {
            method: 'POST', headers: authHeaders(),
            body: JSON.stringify({
              vendor_id: parseInt(vid),
              status: 'confirmed',
              expected_delivery_date: delivDate ? new Date(delivDate).toISOString() : null,
              items: vendorItems
            })
          })
          if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '送出失敗') }
        }
      } else {
        // 單一廠商模式
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
    }

    if (modeStocktake.value) {
      const stocktakeItems = items.value
        .filter(i => i.actual_qty !== null && i.actual_qty !== '')
        .map(i => ({ item_id: i.id, counted_qty: parseFloat(i.actual_qty) || 0 }))
      if (stocktakeItems.length > 0) {
        const createRes = await fetch(`${API_BASE}/stocktake/`, {
          method: 'POST', headers: authHeaders(),
          body: JSON.stringify({ items: stocktakeItems, mode: 'stocktake' })
        })
        if (createRes.ok) {
          const created = await createRes.json()
          const submitRes = await fetch(`${API_BASE}/stocktake/${created.id}/submit`, {
            method: 'PUT', headers: authHeaders()
          })
          // 送出後立即更新前端庫存數值
          if (submitRes.ok) {
            const submitted = await submitRes.json()
            if (submitted.items) {
              submitted.items.forEach(si => {
                if (si.item_id && si.counted_qty != null) {
                  const item = items.value.find(i => i.id === si.item_id)
                  if (item) item.current_stock = si.counted_qty
                }
              })
            }
          }
        }
      }
    }

    // 送出後提示
    if (modeOrder.value && allItems.length > 0) {
      const hasLineGroup = !selectedVendor.value?._isGroup && !!selectedVendor.value?.line_id
      if (hasLineGroup) {
        // 廠商已配對 LINE 群組 → 後端自動推播
        submitToast.value = '✓ 已送出！LINE 訊息已自動推播'
      } else if (!selectedVendor.value?._isGroup) {
        // 單一廠商但未串接 LINE → 顯示跳出提醒
        submitToast.value = '✓ 已送出！'
        noLineWarning.value = true
      } else {
        // 群組模式未配對 LINE → 複製訊息至剪貼簿備用
        try {
          const lineMsg = buildLineMessage(
            selectedVendor.value?.name || '',
            items.value.filter(i => i.qty > 0),
            adHocItems.value,
            expectedDeliveryDate.value
          )
          await navigator.clipboard.writeText(lineMsg)
          submitToast.value = '✓ 已送出！已複製 LINE 訊息'
        } catch {
          submitToast.value = '✓ 已送出！'
        }
      }
    } else {
      submitToast.value = '✓ 已送出！'
    }
    // Reset form + 清除草稿
    const vendorId = selectedVendor.value?.id
    const wasStocktake = modeStocktake.value
    items.value.forEach(i => { i.qty = 0; i.actual_qty = null })
    adHocItems.value = []
    if (vendorId) localStorage.removeItem(DRAFT_KEY(vendorId))
    draftsList.value = getAllDrafts()
    setTimeout(() => {
      submitToast.value = ''
      if (wasStocktake) {
        // 盤點送出後，直接跳到歷史紀錄 > 盤點歷史 tab
        subTab.value = 'history'
        historyTab.value = 'stocktake'
        historySessions.value = []
        loadHistoryStocktake()
      } else {
        switchTab('pending')
      }
    }, 1800)
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
  orderItems.forEach(i => { text += `${i.name} × ${formatDualUnit(i.qty, i)}\n` })
  adHocList.forEach(i => { text += `${i.name} × ${i.qty} ${i.unit || ''}\n` })
  text += `──────────`
  if (date) {
    const d = new Date(date)
    const fmted = `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`
    text += `\n預計到貨：${fmted}`
  }
  return text
}

// Legacy - kept for backward compat but hidden from UI
async function openPreview() { await submitPendingReceive() }
async function copyAndClose() { showPreviewSheet.value = false }

// ── 待收貨 ──────────────────────────────────
async function copyOrderLineMsg(order) {
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
    let orderItems = []
    if (res.ok) {
      const data = await res.json()
      orderItems = Array.isArray(data) ? data : (data.items || [])
    }
    const lineMsg = buildLineMessage(order.vendor_name || '', orderItems, [], order.expected_delivery_date)
    // 顯示 sheet 供使用者點按複製（navigator.clipboard 需 HTTPS，execCommand 需 user gesture）
    copyMsgSheet.value = { show: true, text: lineMsg }
  } catch {
    submitToast.value = '載入失敗'
    setTimeout(() => { submitToast.value = '' }, 2000)
  }
}

async function doCopyMsgText() {
  try {
    await navigator.clipboard.writeText(copyMsgSheet.value.text)
  } catch {
    const el = document.createElement('textarea')
    el.value = copyMsgSheet.value.text
    el.style.position = 'fixed'; el.style.opacity = '0'
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
  copyMsgSheet.value.show = false
  submitToast.value = '已複製 LINE 訊息 ✓'
  setTimeout(() => { submitToast.value = '' }, 2000)
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
  receiveForm.value = { total_amount: order.total_amount || '', amount_paid: '', payment_mode: order.is_prepaid ? 'pre_paid' : 'cash', note: '' }
  receiveError.value = ''; receiveOrderItems.value = []; receivePhoto.value = null; receivePhotoPreview.value = ''; showReceiveModal.value = true
  const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() })
  if (res.ok) {
    const data = await res.json()
    receiveOrderItems.value = Array.isArray(data) ? data : (data.items || [])
  }
}

function handlePhotoSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  receivePhoto.value = file
  const reader = new FileReader()
  reader.onload = (evt) => { receivePhotoPreview.value = evt.target.result }
  reader.readAsDataURL(file)
}

async function submitReceive() {
  receiveError.value = ''
  const amount = parseFloat(receiveForm.value.total_amount) || 0
  if (!amount && !receiveForm.value.note?.trim()) {
    receiveError.value = '未填金額時，請在備註欄填寫說明（例：金額待確認）'
    return
  }
  if (!receivePhoto.value) {
    receiveError.value = '請拍攝單據照片（必填）'
    return
  }
  receiveSubmitting.value = true
  try {
    // 先上傳照片，取得 URL 後一起帶入簽收請求（才能同步到零用金紀錄）
    let receivePhotoUrl = null
    if (receivePhoto.value) {
      const formData = new FormData()
      formData.append('file', receivePhoto.value)
      const upRes = await fetch(`${API_BASE}/uploads/image`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${auth.token}` },
        body: formData
      })
      if (upRes.ok) {
        const upData = await upRes.json()
        const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')
        receivePhotoUrl = base + upData.url
      }
    }
    const res = await fetch(`${API_BASE}/inventory/orders/${receiveTarget.value.id}/receive`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({
        total_amount: amount,
        amount_paid: parseFloat(receiveForm.value.amount_paid) || 0,
        payment_mode: receiveForm.value.payment_mode,
        note: receiveForm.value.note || null,
        receive_photo_url: receivePhotoUrl
      })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '收貨失敗') }
    showReceiveModal.value = false
    historyOrders.value = []  // 清空快取，下次進歷史 tab 時強制重載
    await loadPending()
  } catch (e) { receiveError.value = e.message }
  finally { receiveSubmitting.value = false }
}

async function cancelOrder(order) {
  if (!confirm(`確認取消 ${order.vendor_name} 的訂單？`)) return
  await fetch(`${API_BASE}/inventory/orders/${order.id}`, { method: 'DELETE', headers: authHeaders() })
  await loadPending()
}

async function openEditOrder(order) {
  editOrderTarget.value = order
  editOrderForm.value = {
    expected_delivery_date: order.expected_delivery_date
      ? (() => { const d = new Date(order.expected_delivery_date); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}` })()
      : '',
    total_amount: order.total_amount || '',
    note: order.note || '',
    is_prepaid: order.is_prepaid || false
  }
  editOrderItems.value = []
  editOrderItemsLoading.value = true
  showEditOrderModal.value = true
  try {
    const [orderRes, vendorRes] = await Promise.all([
      fetch(`${API_BASE}/inventory/orders/${order.id}`, { headers: authHeaders() }),
      fetch(`${API_BASE}/inventory/items?vendor_id=${order.vendor_id}`, { headers: authHeaders() })
    ])
    const currentItems = orderRes.ok ? await orderRes.json() : []
    const vendorItems = vendorRes.ok ? await vendorRes.json() : []
    const currentQtyMap = {}
    currentItems.forEach(i => { if (i.item_id) currentQtyMap[i.item_id] = Number(i.qty) })
    const merged = vendorItems.map(vi => ({
      item_id: vi.id,
      name: vi.name,
      unit: vi.unit || '',
      qty: currentQtyMap[vi.id] || 0,
      isAdhoc: false
    }))
    // 加入 ad-hoc 品項（非系統品項）
    currentItems.forEach(i => {
      if (!i.item_id && i.adhoc_name) {
        merged.push({ item_id: null, name: i.adhoc_name, unit: i.adhoc_unit || '', qty: Number(i.qty), isAdhoc: true })
      }
    })
    editOrderItems.value = merged
  } finally {
    editOrderItemsLoading.value = false
  }
}

function addNewEditItem() {
  const name = editOrderNewItem.value.name.trim()
  if (!name) return
  editOrderItems.value.push({
    item_id: null,
    name,
    unit: editOrderNewItem.value.unit.trim(),
    qty: Math.max(1, editOrderNewItem.value.qty || 1),
    isAdhoc: true
  })
  editOrderNewItem.value = { name: '', unit: '', qty: 1 }
}

async function submitEditOrder() {
  if (!editOrderTarget.value) return
  editOrderSubmitting.value = true
  try {
    const body = {}
    if (editOrderForm.value.expected_delivery_date)
      body.expected_delivery_date = new Date(editOrderForm.value.expected_delivery_date).toISOString()
    if (editOrderForm.value.total_amount !== '' && editOrderForm.value.total_amount != null)
      body.total_amount = parseFloat(editOrderForm.value.total_amount)
    if (editOrderForm.value.note !== undefined)
      body.note = editOrderForm.value.note
    body.is_prepaid = editOrderForm.value.is_prepaid
    // 品項更新：只送出 qty > 0 的
    const itemsToSave = editOrderItems.value.filter(i => i.qty > 0)
    if (itemsToSave.length > 0) {
      body.items = itemsToSave.map(i => ({
        item_id: i.isAdhoc ? null : i.item_id,
        adhoc_name: i.isAdhoc ? i.name : null,
        adhoc_unit: i.isAdhoc ? i.unit : null,
        qty: i.qty
      }))
    }
    const itemsChanged = !!body.items
    const res = await fetch(`${API_BASE}/inventory/orders/${editOrderTarget.value.id}`, {
      method: 'PATCH', headers: authHeaders(),
      body: JSON.stringify(body)
    })
    if (res.ok) {
      showEditOrderModal.value = false
      await loadPending()
      if (itemsChanged) {
        submitToast.value = '⚠ 品項已修改，記得聯繫廠商確認更改'
        setTimeout(() => { submitToast.value = '' }, 4000)
      }
    }
  } catch (e) { console.error(e) }
  finally { editOrderSubmitting.value = false }
}

// ── 歷史紀錄 ──────────────────────────────────
async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?status=received&limit=100`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      // 按收貨日期（updated_at）倒序排列
      historyOrders.value = data.sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))
    }
  } finally { historyLoading.value = false }
}

async function loadHistoryStocktake() {
  historyStocktakeLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/stocktake/?limit=50`, { headers: authHeaders() })
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

function getRenderUnits(item, op) {
  const mode = item[`${op}_unit_mode`] || 'both'
  const units = []
  if (['both', 'secondary'].includes(mode) && item.secondary_unit) {
    units.push({ type: 'sec', label: item.secondary_unit, isSec: true })
  }
  if (['both', 'base'].includes(mode)) {
    units.push({ type: 'base', label: item.unit || '個', isSec: false })
  }
  return units
}

function initCount(item, op) {
  // InventoryView directly mutates item.qty and item.actual_qty
  // To support dual units without rewriting state, we keep base in item.qty and sec in item[`${op}Sec`]
  // But wait, it's easier to just use `item.qtyBase` and `item.qtySec`
}

function getActual(item, type) { return item[type==='sec'?'actualSec':'actualBase'] ?? item.actual_qty ?? null }
function setActual(item, val, type) { 
  const n = val==='' ? null : parseFloat(val);
  item[type==='sec'?'actualSec':'actualBase'] = isNaN(n) ? null : n;
  const b = item.actualBase ?? 0, s = item.actualSec ?? 0;
  item.actual_qty = (item.actualBase===null && item.actualSec===null) ? null : b + s * (parseFloat(item.secondary_unit_ratio)||1);
}

function getOrder(item, type) { return item[type==='sec'?'orderSec':'orderBase'] ?? item.qty ?? (type==='base'?0:null) }
function setOrder(item, val, type) {
  const n = val==='' ? 0 : parseFloat(val);
  item[type==='sec'?'orderSec':'orderBase'] = isNaN(n) ? 0 : n;
  const b = item.orderBase ?? 0, s = item.orderSec ?? 0;
  item.qty = b + s * (parseFloat(item.secondary_unit_ratio)||1);
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
          叫貨/盤點
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

        <!-- 草稿選單按鈕 -->
        <button @click="openDraftSheet"
          class="w-full py-2 rounded-xl text-xs font-bold border transition-all flex items-center justify-center gap-1.5"
          :class="getAllDrafts().length ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-slate-50 border-slate-200 text-slate-400'">
          📌 草稿{{ getAllDrafts().length ? `（${getAllDrafts().length}）` : '（無）' }}
        </button>

        <!-- Vendor / group 可搜尋下拉選單 -->
        <div v-if="vendorAndGroupList.length === 0" class="text-xs text-slate-400 text-center py-2">
          尚無叫貨廠商，請至後台供應商管理勾選「出現在叫貨/盤點系統」
        </div>
        <div v-else class="relative">
          <input
            v-model="vendorSearch"
            @focus="handleVendorFocus"
            @blur="handleVendorBlur"
            type="text"
            placeholder="搜尋廠商或群組…"
            class="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-orange-400 bg-white"
          />
          <div v-if="showVendorDropdown"
            class="absolute z-50 w-full bg-white border border-slate-200 rounded-xl shadow-lg mt-1 max-h-48 overflow-y-auto">
            <div v-if="filteredVendorList.length === 0" class="px-3 py-2 text-xs text-slate-400">無符合結果</div>
            <button
              v-for="v in filteredVendorList" :key="vendorKey(v)"
              @mousedown.prevent="pickVendor(v)"
              class="w-full text-left px-3 py-2.5 text-sm font-bold hover:bg-orange-50 flex items-center gap-2"
              :class="vendorKey(v) === selectedVendorKey ? 'text-orange-600 bg-orange-50' : 'text-slate-700'">
              <span>{{ v._isGroup ? '📦' : '🏪' }}</span>
              <div class="flex-1 min-w-0">
                <div>{{ v.name }}</div>
                <div v-if="v._matchedItems?.length" class="text-[10px] text-orange-400 font-normal truncate">
                  含：{{ v._matchedItems.slice(0, 3).join('、') }}{{ v._matchedItems.length > 3 ? '…' : '' }}
                </div>
              </div>
              <span v-if="v._isGroup" class="ml-auto text-[10px] text-slate-400 shrink-0">盤點群組</span>
            </button>
          </div>
        </div>

        <!-- Free shipping progress -->
        <div v-if="freeShippingThreshold > 0 && !selectedVendor?.value?._isGroup">
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

        <!-- D+N 到貨倒數 + 日期選擇器（群組模式改由各廠商分隔線顯示，此處隱藏） -->
        <div v-if="!selectedVendor?._isGroup" class="bg-orange-50 rounded-xl px-3 py-2 border border-orange-100 space-y-1">
          <div class="flex items-center justify-between">
            <span class="text-[10px] font-bold text-orange-600">⚡ {{ estimatedDeliveryLabel }}</span>
          </div>
          <div class="flex items-center justify-between">
            <label class="text-xs font-bold text-orange-700">📅 預計到貨日</label>
            <input v-model="expectedDeliveryDate" type="date"
              class="bg-transparent border-none text-xs font-bold text-slate-700 focus:outline-none" />
          </div>
        </div>

        <!-- 廠商備注 -->
        <div v-if="selectedVendor?.note"
          class="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
          <span class="text-amber-500 text-sm shrink-0">📌</span>
          <p class="text-xs font-bold text-amber-800 leading-relaxed">{{ selectedVendor.note }}</p>
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

        <!-- A1: Regular items（支援雙模式，群組時依廠商分組） -->
        <template v-for="group in itemsByVendor" :key="group.vendor_id">
          <!-- 廠商分隔線（選了群組 + 多廠商時顯示） -->
          <div v-if="selectedVendor?._isGroup && itemsByVendor.length > 1"
            class="pt-2 pb-0.5 space-y-1">
            <div class="flex items-center gap-2">
              <span class="text-xs font-extrabold text-slate-600">🏪 {{ group.vendor_name }}</span>
              <span v-if="vendorMeta[group.vendor_id]?.delivery_days_to_arrive"
                class="text-[10px] font-bold text-orange-500 shrink-0">
                D+{{ vendorMeta[group.vendor_id].delivery_days_to_arrive }}
              </span>
              <div class="flex-1 h-px bg-slate-200"></div>
              <!-- 到貨日（永遠顯示，供叫貨時手動調整） -->
              <div class="flex items-center gap-1 shrink-0">
                <span class="text-[10px] text-slate-400">到貨日</span>
                <input
                  :value="vendorDeliveryDates[group.vendor_id] || ''"
                  @change="vendorDeliveryDates[group.vendor_id] = $event.target.value"
                  type="date"
                  class="text-[11px] border border-slate-200 rounded-lg px-1.5 py-0.5 text-slate-600 bg-white focus:outline-none focus:ring-1 focus:ring-orange-300" />
              </div>
            </div>
            <!-- 免運門檻進度（有設定時顯示） -->
            <div v-if="group.free_shipping_threshold > 0"
              class="flex items-center gap-2 pl-1">
              <span class="text-[10px]"
                :class="vendorOrderTotals[group.vendor_id] >= group.free_shipping_threshold ? 'text-emerald-600 font-bold' : 'text-slate-400'">
                滿${{ fmtMoney(group.free_shipping_threshold) }}免運
              </span>
              <span class="text-[10px]"
                :class="vendorOrderTotals[group.vendor_id] >= group.free_shipping_threshold ? 'text-emerald-600 font-bold' : 'text-orange-500'">
                目前 ${{ fmtMoney(vendorOrderTotals[group.vendor_id] || 0) }}
                <span v-if="vendorOrderTotals[group.vendor_id] < group.free_shipping_threshold">
                  （差 ${{ fmtMoney(group.free_shipping_threshold - (vendorOrderTotals[group.vendor_id] || 0)) }}）
                </span>
                <span v-else>✓</span>
              </span>
            </div>
          </div>
        <div v-for="item in group.items" :key="item.id"
          class="bg-white rounded-xl p-3 shadow-sm transition-all duration-300"
          :class="stockBorder(item)"
          style="overflow:hidden">

          <!-- ── 單一模式：名稱＋控制項同一行 ── -->
          <template v-if="!(modeOrder && modeStocktake)">
            <div class="flex items-center gap-2">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="font-bold text-slate-900 text-sm">{{ item.name }}</span>
                  <span v-if="isLowStock(item)" class="text-[9px] font-extrabold bg-red-100 text-red-500 px-1.5 py-0.5 rounded-full">低庫存</span>
                </div>
                <p class="text-[10px] text-slate-400 mt-0.5">
                  <span v-if="item.secondary_unit" class="text-orange-500 font-bold mr-1">[{{ item.secondary_unit_ratio || 1 }}{{ item.unit }}/{{ item.secondary_unit }}]</span>                  庫存 <span :class="isLowStock(item) ? 'text-red-500 font-bold' : 'text-slate-500'">{{ item.secondary_unit ? formatDualUnit(item.current_stock || 0, item) : (item.current_stock || 0) }}</span>                  <span v-if="!item.secondary_unit">{{ item.unit }}</span><span v-if="item.price" class="ml-1 text-orange-500"> ${{ fmtMoney(item.price) }}</span>                </p>
              </div>
              <!-- 叫貨控制 -->
              <div v-if="modeOrder" class="flex flex-col gap-1 shrink-0">
                <div v-for="u in getRenderUnits(item, 'order')" :key="'o'+u.type" class="flex items-center gap-1">
                  <button @click="setOrder(item, Math.max(0, getOrder(item, u.type)-1), u.type)"
                  class="w-8 h-8 bg-slate-100 rounded-full flex items-center justify-center font-bold text-slate-600 active:bg-slate-200 text-lg leading-none">−</button>
                  <input
                    :value="getOrder(item, u.type) || ''"
                    @input="setOrder(item, $event.target.value, u.type)"
                    type="number" min="0" :placeholder="u.label"
  
                  class="w-12 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none"
                  :class="item.qty>0?'border-orange-500 text-orange-600':'border-slate-200 text-slate-800'" />
                  <button @click="setOrder(item, getOrder(item, u.type)+1, u.type)"
                  class="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200 text-lg leading-none">+</button>
                </div>
              </div>
              <!-- 實盤控制 -->
              <div v-if="modeStocktake" class="flex flex-col gap-1 shrink-0">
                <div v-for="u in getRenderUnits(item, 'stocktake')" :key="'s'+u.type" class="flex items-center gap-1">
                  <button @click="setActual(item, Math.max(0, (getActual(item, u.type)||0)-1), u.type)"
                  class="w-8 h-8 bg-blue-50 rounded-full flex items-center justify-center font-bold text-blue-600 active:bg-blue-100 text-lg leading-none">−</button>
                  <input
                    :value="getActual(item, u.type) ?? ''"
                    @input="setActual(item, $event.target.value, u.type)"
                    type="number" min="0" :placeholder="u.isSec ? item.secondary_unit : `${item.current_stock || 0}`"
                  class="w-14 text-center border-b-2 font-extrabold text-base bg-transparent focus:outline-none"
                  :class="getActual(item, u.type) !== null && getActual(item, u.type) !== '' ? 'border-blue-500 text-blue-700' : 'border-slate-200 text-slate-400'" />
                  <button @click="setActual(item, (getActual(item, u.type)||0)+1, u.type)"
                  class="w-8 h-8 bg-blue-50 rounded-full flex items-center justify-center font-bold text-blue-600 active:bg-blue-100 text-lg leading-none">+</button>
                </div>
                <!-- 雙單位合計顯示（有 secondary_unit 時才顯示） -->
                <div v-if="item.secondary_unit && item.actual_qty != null"
                  class="text-[10px] font-bold text-blue-500 text-right mt-0.5">
                  = {{ formatDualUnit(item.actual_qty, item) }}
                </div>
              </div>
            </div>
          </template>

          <!-- ── 雙模式：名稱上方，兩欄控制項在下方 ── -->
          <template v-else>
            <div class="flex items-center gap-2 mb-2">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="font-bold text-slate-900 text-sm">{{ item.name }}</span>
                  <span v-if="isLowStock(item)" class="text-[9px] font-extrabold bg-red-100 text-red-500 px-1.5 py-0.5 rounded-full">低庫存</span>
                </div>
                <p class="text-[10px] text-slate-400 mt-0.5">
                  <span v-if="item.secondary_unit" class="text-orange-500 font-bold mr-1">[{{ item.secondary_unit_ratio || 1 }}{{ item.unit }}/{{ item.secondary_unit }}]</span>                  庫存 <span :class="isLowStock(item) ? 'text-red-500 font-bold' : 'text-slate-500'">{{ item.secondary_unit ? formatDualUnit(item.current_stock || 0, item) : (item.current_stock || 0) }}</span>                  <span v-if="!item.secondary_unit">{{ item.unit }}</span><span v-if="item.price" class="ml-1 text-orange-500"> ${{ fmtMoney(item.price) }}</span>                </p>
              </div>
            </div>
            <div class="flex gap-2">
              <!-- 叫貨欄：使用 getRenderUnits 支援雙單位 -->
              <div class="flex-1 rounded-xl p-2" style="background:#fff7ed">
                <p class="text-[9px] font-bold text-orange-400 text-center mb-1.5">叫貨</p>
                <div v-for="u in getRenderUnits(item, 'order')" :key="'bo'+u.type"
                  class="flex items-center justify-center gap-1 mb-1">
                  <span class="text-[10px] font-bold text-orange-300 w-4 text-right shrink-0">{{ u.label }}</span>
                  <button @click="setOrder(item, Math.max(0, getOrder(item, u.type)-1), u.type)"
                    class="w-7 h-7 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200 text-base leading-none">−</button>
                  <input
                    :value="getOrder(item, u.type) || ''"
                    @input="setOrder(item, $event.target.value, u.type)"
                    type="number" min="0" :placeholder="u.label"
                    class="w-10 text-center border-b-2 font-extrabold text-sm bg-transparent focus:outline-none"
                    :class="item.qty>0?'border-orange-500 text-orange-600':'border-slate-200 text-slate-800'" />
                  <button @click="setOrder(item, getOrder(item, u.type)+1, u.type)"
                    class="w-7 h-7 bg-orange-100 rounded-full flex items-center justify-center font-bold text-orange-600 active:bg-orange-200 text-base leading-none">+</button>
                </div>
              </div>
              <!-- 實盤欄：使用 getRenderUnits 支援雙單位 -->
              <div class="flex-1 rounded-xl p-2" style="background:#eff6ff">
                <p class="text-[9px] font-bold text-blue-400 text-center mb-1.5">實盤</p>
                <div v-for="u in getRenderUnits(item, 'stocktake')" :key="'bs'+u.type"
                  class="flex items-center justify-center gap-1 mb-1">
                  <span class="text-[10px] font-bold text-blue-300 w-4 text-right shrink-0">{{ u.label }}</span>
                  <button @click="setActual(item, Math.max(0, (getActual(item, u.type)||0)-1), u.type)"
                    class="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center font-bold text-blue-600 active:bg-blue-200 text-base leading-none">−</button>
                  <input
                    :value="getActual(item, u.type) ?? ''"
                    @input="setActual(item, $event.target.value, u.type)"
                    type="number" min="0" :placeholder="u.isSec ? u.label : `${item.current_stock || 0}`"
                    class="w-10 text-center border-b-2 font-extrabold text-sm bg-transparent focus:outline-none"
                    :class="getActual(item, u.type) !== null && getActual(item, u.type) !== '' ? 'border-blue-500 text-blue-700' : 'border-slate-200 text-slate-400'" />
                  <button @click="setActual(item, (getActual(item, u.type)||0)+1, u.type)"
                    class="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center font-bold text-blue-600 active:bg-blue-200 text-base leading-none">+</button>
                </div>
              </div>
            </div>
          </template>
        </div>
        </template>

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

      <!-- 無 LINE 廠商提醒 Modal -->
      <div v-if="noLineWarning" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center px-6" @click.self="noLineWarning = false">
        <div class="bg-white rounded-2xl p-6 w-full max-w-sm text-center shadow-2xl">
          <div class="text-4xl mb-3">📵</div>
          <h3 class="text-lg font-bold text-red-600 mb-2">請記得聯繫廠商確認！</h3>
          <p class="text-sm text-gray-500 mb-5">
            此廠商尚未串接 LINE，訂單已送出，<br>
            <span class="font-bold text-red-500">需手動聯繫廠商</span>確認叫貨內容。
          </p>
          <button @click="noLineWarning = false"
            class="w-full bg-red-500 text-white font-bold py-3 rounded-xl active:scale-95">
            我知道了
          </button>
        </div>
      </div>

      <!-- A2: Draft toast -->
      <div v-if="draftToast"
        class="fixed top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-sm font-bold shadow-lg text-white"
        :style="draftToast.startsWith('⚠') ? 'background:#ef4444' : 'background:#64748b'">
        {{ draftToast }}
      </div>

      <!-- Bottom action bar -->
      <div class="fixed inset-x-0 bg-white border-t border-slate-200 px-4 py-3 shadow-lg z-20"
           style="bottom: calc(4rem + max(16px, env(safe-area-inset-bottom))); will-change: transform;">
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

      <!-- A2: 盤點歷史底部抽屜（依目前廠商品項過濾） -->
      <div v-if="showStocktakeHistory" class="fixed inset-0 bg-black/50 z-[60] flex items-end" @click.self="showStocktakeHistory=false">
        <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
          <!-- Fixed header -->
          <div class="flex-shrink-0 px-5 pt-4 pb-3">
            <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-extrabold text-slate-800">{{ selectedVendor?.name || '最近' }}盤點紀錄</h3>
              <button @click="showStocktakeHistory=false" class="text-slate-400 text-xl font-bold">✕</button>
            </div>
          </div>
          <!-- Scrollable content -->
          <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-3">
            <div v-if="stocktakeHistoryLoading" class="flex justify-center py-10">
              <div class="animate-spin h-6 w-6 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
            <div v-else-if="!vendorFilteredHistory.length" class="text-center py-10 text-slate-400">無相關盤點紀錄</div>
            <template v-else>
              <div v-for="record in vendorFilteredHistory" :key="record.id" class="bg-slate-50 rounded-xl p-3">
                <div class="flex items-start justify-between">
                  <div>
                    <p class="font-bold text-slate-800 text-sm">
                      {{ new Date(record.stocktake_date || record.created_at).toLocaleDateString('zh-TW', { month:'numeric',day:'numeric',weekday:'short' }) }}
                    </p>
                    <div class="flex items-center gap-1 text-xs text-slate-400 mt-0.5">
                      <UserBadge :user="record.performed_by" size="sm" />
                      · {{ record.items?.filter(it => vendorItemIds.has(it.item_id)).length || record.items?.length || '?' }} 品項
                    </div>
                  </div>
                  <span class="text-xs text-slate-400">
                    {{ record.items?.filter(it => vendorItemIds.has(it.item_id)).length || 0 }} 項已盤
                  </span>
                </div>
                <button @click="toggleHistoryExpand(record.id)"
                  class="mt-2 text-xs font-bold text-blue-500 flex items-center gap-1">
                  查看明細 {{ expandedHistoryId===record.id ? '▲' : '▼' }}
                </button>
                <!-- 展開只顯示本廠商品項，呈現實際盤點數，不強調差異 -->
                <div v-if="expandedHistoryId===record.id" class="mt-2 border-t border-slate-200 pt-2 space-y-1.5">
                  <template v-for="it in (record.items || [])" :key="it.item_id">
                    <div v-if="vendorItemIds.has(it.item_id)" class="flex items-center justify-between text-xs">
                      <span class="text-slate-700">{{ it.item_name }}</span>
                      <span class="font-bold text-slate-700">
                        實盤 {{ formatDualUnit(it.counted_qty ?? it.actual_qty, it) || '–' }}
                      </span>
                    </div>
                  </template>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
      <!-- 草稿選單底部抽屜 -->
      <div v-if="showDraftSheet" class="fixed inset-0 bg-black/50 z-[60] flex items-end" @click.self="showDraftSheet=false">
        <div class="bg-white w-full rounded-t-3xl max-h-[70vh] flex flex-col">
          <div class="flex-shrink-0 px-5 pt-4 pb-3">
            <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
            <div class="flex items-center justify-between">
              <h3 class="text-base font-extrabold text-slate-800">已存草稿</h3>
              <button @click="showDraftSheet=false" class="text-slate-400 text-xl font-bold">✕</button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto px-5 pb-6 space-y-3">
            <div v-if="!draftsList.length" class="text-center py-10 text-slate-400 text-sm">無已存草稿</div>
            <div v-for="d in draftsList" :key="d._key"
              class="bg-slate-50 rounded-xl p-4 flex items-center justify-between gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="font-bold text-slate-800 text-sm">{{ d.vendorName }}</p>
                  <span class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                    :style="d.modeOrder && d.modeStocktake ? 'background:#fef3c7;color:#92400e' : d.modeOrder ? 'background:#dcfce7;color:#166534' : 'background:#dbeafe;color:#1e40af'">
                    {{ d.modeOrder && d.modeStocktake ? '叫貨＋盤點' : d.modeOrder ? '叫貨' : '盤點' }}
                  </span>
                </div>
                <p class="text-xs text-slate-400 mt-0.5">
                  {{ (d.qtys?.length || 0) + (d.adHocItems?.length || 0) + (d.stocktakeQtys?.length || 0) }} 筆
                  · {{ new Date(d.timestamp).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}
                </p>
              </div>
              <div class="flex gap-2 shrink-0">
                <button @click="discardDraft(d)"
                  class="px-3 py-1.5 bg-slate-200 text-slate-500 text-xs font-bold rounded-lg">刪除</button>
                <button @click="resumeDraft(d)"
                  class="px-3 py-1.5 text-white text-xs font-bold rounded-lg" style="background:#e85d04">載入</button>
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
        <template v-for="item in pendingSortedWithDivider" :key="item._type === 'divider' ? 'divider' : item.id">
          <!-- 分切線 -->
          <div v-if="item._type === 'divider'" class="flex items-center gap-2 py-1">
            <div class="flex-1 h-px bg-slate-200"></div>
            <span class="text-[10px] font-bold text-slate-400 uppercase shrink-0 px-2">預計未來到貨 ({{ item._futureCount }})</span>
            <div class="flex-1 h-px bg-slate-200"></div>
          </div>
          <!-- 訂單卡片 -->
          <div v-else class="bg-white rounded-xl shadow-sm p-4" :class="item._type === 'future' ? 'opacity-75' : ''">
            <div class="flex items-start gap-3">
              <span class="text-2xl mt-0.5">🚚</span>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="font-extrabold text-slate-800 text-sm">{{ item.vendor_name }}</p>
                  <span class="text-[10px] font-mono text-slate-400">#{{ item.id }}</span>
                  <span v-if="orderDateBadge(item)"
                    class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    :class="orderDateBadge(item).cls">
                    {{ orderDateBadge(item).label }}
                  </span>
                  <span v-if="item.is_prepaid"
                    class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-50 text-green-600">
                    ✓ 已收款
                  </span>
                </div>
                <p class="text-xs text-slate-400 mt-0.5">
                  預計 {{ item.expected_delivery_date ? fmtDate(item.expected_delivery_date) : '待定' }}
                  · {{ item.total_items || '?' }} 項品項
                  <span v-if="item.reference_amount > 0"> · 參考 ${{ fmtMoney(item.reference_amount) }}</span>
                  <span v-if="item.total_amount"> · 實際 ${{ fmtMoney(item.total_amount) }}</span>
                </p>
                <UserBadge v-if="item.created_by" :user="item.created_by" size="sm" class="mt-0.5" />
              </div>
            </div>
            <!-- Actions row（已收貨不顯示編輯/刪除按鈕） -->
            <div class="flex gap-2 mt-3 pt-3 border-t border-slate-100">
              <template v-if="item.status !== 'received' && item.status !== 'cancelled'">
                <button @click="cancelOrder(item)"
                  class="flex-1 py-2 bg-slate-100 text-slate-600 text-xs font-bold rounded-xl active:bg-slate-200">
                  🗑 刪除
                </button>
                <button @click="openEditOrder(item)"
                  class="flex-1 py-2 bg-blue-50 text-blue-600 text-xs font-bold rounded-xl active:scale-95 border border-blue-100">
                  ✎ 編輯
                </button>
                <button @click="copyOrderLineMsg(item)"
                  class="flex-1 py-2 bg-blue-50 text-blue-600 text-xs font-bold rounded-xl active:scale-95 border border-blue-100">
                  📋 訊息
                </button>
                <button @click="openReceive(item)"
                  class="flex-[2] py-2 text-white text-xs font-bold rounded-xl active:scale-95"
                  style="background:#e85d04">
                  ✅ 簽收
                </button>
              </template>
              <div v-else class="flex-1 text-center text-xs text-slate-400 py-2">
                {{ item.status === 'received' ? '✓ 已簽收' : '已取消' }}
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Copy LINE Message Sheet -->
      <div v-if="copyMsgSheet.show" class="fixed inset-0 bg-black/50 z-[60] flex items-end" @click.self="copyMsgSheet.show=false">
        <div class="bg-white w-full rounded-t-3xl max-h-[70vh] flex flex-col">
          <div class="flex-shrink-0 px-5 pt-4 pb-3 border-b border-slate-100">
            <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
            <div class="flex justify-between items-center">
              <h3 class="text-base font-extrabold text-slate-800">📋 LINE 叫貨訊息</h3>
              <button @click="copyMsgSheet.show=false" class="text-slate-400 text-xl font-bold">✕</button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto px-5 py-4">
            <textarea readonly :value="copyMsgSheet.text" @click="$event.target.select()"
              class="w-full min-h-[180px] bg-slate-50 rounded-xl p-4 text-sm font-mono text-slate-700 border border-slate-200 resize-none focus:outline-none"></textarea>
            <p class="text-xs text-slate-400 mt-2 text-center">點擊文字區可全選，再按下方按鈕複製</p>
          </div>
          <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
            <button @click="doCopyMsgText"
              class="w-full text-white font-bold py-4 rounded-2xl active:scale-95"
              style="background:#e85d04">
              📋 複製訊息
            </button>
          </div>
        </div>
      </div>

      <!-- Edit Order Modal -->
      <div v-if="showEditOrderModal" class="fixed inset-0 bg-black/50 z-[60] flex items-end" @click.self="showEditOrderModal=false">
        <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
          <div class="flex-shrink-0 px-5 pt-4 pb-3 border-b border-slate-100">
            <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
            <div class="flex justify-between items-center">
              <h3 class="text-base font-extrabold text-slate-800">修改訂單 — {{ editOrderTarget?.vendor_name }}</h3>
              <button @click="showEditOrderModal=false" class="text-slate-400 text-xl font-bold">✕</button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4 pt-3">
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">預計到貨日</label>
              <input v-model="editOrderForm.expected_delivery_date" type="date"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">訂單金額（選填）</label>
              <input v-model="editOrderForm.total_amount" type="number" inputmode="decimal" placeholder="0"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">備注</label>
              <input v-model="editOrderForm.note" type="text" placeholder="輸入備注…"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <label class="flex items-center gap-3 cursor-pointer py-1">
              <input type="checkbox" v-model="editOrderForm.is_prepaid" class="w-5 h-5 accent-green-500 rounded" />
              <div>
                <p class="text-sm font-bold text-slate-700">已收款（已付清）</p>
                <p class="text-xs text-slate-400">勾選後簽收時自動設為「已收款」，不計入零用金待付</p>
              </div>
            </label>

            <!-- 品項編輯 -->
            <div>
              <p class="text-xs font-bold text-slate-500 uppercase mb-2">品項數量</p>
              <div v-if="editOrderItemsLoading" class="text-center text-slate-400 text-sm py-4">載入中…</div>
              <div v-else class="space-y-2">
                <div v-for="(item, idx) in editOrderItems" :key="item.item_id ?? ('adhoc-' + idx)"
                  class="flex items-center gap-3 bg-slate-50 rounded-xl px-3 py-2.5"
                  :class="item.qty > 0 ? 'bg-orange-50 border border-orange-100' : ''">
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-bold text-slate-700 truncate">{{ item.name }}</p>
                    <p class="text-xs text-slate-400">{{ item.unit }}</p>
                  </div>
                  <div class="flex items-center gap-2 flex-shrink-0">
                    <button @click="item.qty = Math.max(0, item.qty - 1)"
                      class="w-8 h-8 rounded-full bg-slate-200 text-slate-600 text-lg font-bold flex items-center justify-center active:bg-slate-300">−</button>
                    <input v-model.number="item.qty" type="number" inputmode="numeric" min="0"
                      class="w-14 text-center text-sm font-extrabold border border-slate-200 rounded-lg py-1 focus:outline-none focus:ring-2 focus:ring-orange-400" />
                    <button @click="item.qty++"
                      class="w-8 h-8 rounded-full flex items-center justify-center active:opacity-80 text-white text-lg font-bold"
                      style="background:#e85d04">＋</button>
                  </div>
                </div>
                <p v-if="editOrderItems.length === 0" class="text-center text-slate-400 text-sm py-2">無品項資料</p>

                <!-- 新增臨時品項 -->
                <div class="mt-3 pt-3 border-t border-slate-100">
                  <p class="text-xs font-bold text-slate-400 mb-2">＋ 新增其他品項</p>
                  <div class="flex gap-2">
                    <input v-model="editOrderNewItem.name" type="text" placeholder="品項名稱"
                      class="flex-1 border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
                    <input v-model="editOrderNewItem.unit" type="text" placeholder="單位"
                      class="w-16 border border-slate-200 rounded-xl px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
                    <input v-model.number="editOrderNewItem.qty" type="number" inputmode="numeric" min="1" placeholder="數量"
                      class="w-16 border border-slate-200 rounded-xl px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
                    <button @click="addNewEditItem"
                      class="px-3 py-2 rounded-xl text-white text-sm font-bold active:opacity-80 flex-shrink-0"
                      style="background:#e85d04">加入</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
            <button @click="submitEditOrder" :disabled="editOrderSubmitting"
              class="w-full text-white font-bold py-4 rounded-2xl active:scale-95 disabled:opacity-40"
              style="background:#e85d04">
              {{ editOrderSubmitting ? '儲存中…' : '確認修改' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Receive bottom sheet -->
      <div v-if="showReceiveModal" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
        <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
          <!-- 固定 header -->
          <div class="flex-shrink-0 px-5 pt-4 pb-3">
            <div class="flex items-center justify-center w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
            <div class="flex justify-between items-center">
              <h3 class="text-base font-extrabold text-slate-800">{{ receiveTarget?.vendor_name }} — 簽收確認</h3>
              <button @click="showReceiveModal=false" class="text-slate-400 text-xl font-bold">✕</button>
            </div>
          </div>

          <!-- 可捲動內容 -->
          <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4">

            <!-- Order items preview -->
            <div v-if="receiveOrderItems.length">
              <p class="text-xs font-bold text-slate-500 uppercase mb-2">到貨品項確認</p>
              <div class="bg-slate-50 rounded-xl p-3 space-y-1.5">
                <div v-for="(item,idx) in receiveOrderItems" :key="idx" class="flex justify-between text-sm">
                  <span class="text-slate-700">{{ item.name || item.adhoc_name }}</span>
                  <span class="text-slate-500 font-bold">叫貨：{{ formatDualUnit(item.qty, item) }}</span>
                </div>
              </div>
            </div>

            <!-- Amount -->
            <div>
              <div class="flex items-center justify-between mb-1">
                <p class="text-xs font-bold text-slate-500">本次訂單金額<span class="ml-1 font-normal text-slate-400">（非必填，無金額請填備註）</span></p>
                <span v-if="receiveTarget?.reference_amount > 0" class="text-xs font-bold px-2 py-0.5 rounded-lg" style="background:#fff7ed;color:#ea580c">
                  參考 ${{ fmtMoney(receiveTarget.reference_amount) }}
                </span>
              </div>
              <p class="text-[10px] text-slate-400 mb-1">現場議價直接輸入；不知金額可留空並在備註說明</p>
              <input v-model="receiveForm.total_amount" type="number" inputmode="decimal" placeholder="0"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-2xl font-extrabold text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>

            <!-- Payment status (3-way) -->
            <div>
              <div class="flex items-center gap-2 mb-2">
                <p class="text-xs font-bold text-slate-500">付款方式</p>
                <span v-if="receiveTarget?.is_prepaid" class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-50 text-green-600">🔒 已在訂單標記已收款</span>
              </div>
              <div class="grid grid-cols-3 gap-2">
                <button @click="!receiveTarget?.is_prepaid && (receiveForm.payment_mode = 'cash')"
                  class="py-3 rounded-xl text-sm font-bold border transition-all text-center px-1"
                  :class="[receiveForm.payment_mode === 'cash' ? 'border-emerald-400 bg-emerald-50 text-emerald-700' : 'border-slate-200 text-slate-400', receiveTarget?.is_prepaid ? 'opacity-40 cursor-not-allowed' : '']">
                  <p class="font-extrabold text-sm">💵 現場現金</p>
                  <p class="text-[10px] mt-0.5 opacity-70">當場付清</p>
                </button>
                <button @click="!receiveTarget?.is_prepaid && (receiveForm.payment_mode = 'pre_paid')"
                  class="py-3 rounded-xl text-sm font-bold border transition-all text-center px-1"
                  :class="[receiveForm.payment_mode === 'pre_paid' ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-400', receiveTarget?.is_prepaid ? 'ring-2 ring-blue-300' : '']">
                  <p class="font-extrabold text-sm">🏦 已收款</p>
                  <p class="text-[10px] mt-0.5 opacity-70">匯款/先付</p>
                </button>
                <button @click="!receiveTarget?.is_prepaid && (receiveForm.payment_mode = 'unpaid')"
                  class="py-3 rounded-xl text-sm font-bold border transition-all text-center px-1"
                  :class="[receiveForm.payment_mode === 'unpaid' ? 'border-amber-400 bg-amber-50 text-amber-700' : 'border-slate-200 text-slate-400', receiveTarget?.is_prepaid ? 'opacity-40 cursor-not-allowed' : '']">
                  <p class="font-extrabold text-sm">📋 未付款</p>
                  <p class="text-[10px] mt-0.5 opacity-70">月結/週結</p>
                </button>
              </div>
            </div>

            <!-- Note -->
            <div>
              <label class="block text-xs font-bold text-slate-500 mb-1">
                備註
                <span v-if="!parseFloat(receiveForm.total_amount)" class="text-red-500 font-bold">（未填金額時必填）</span>
                <span v-else class="text-slate-400 font-normal">（選填）</span>
              </label>
              <input v-model="receiveForm.note" type="text"
                :placeholder="!parseFloat(receiveForm.total_amount) ? '未填金額時請說明原因…' : '如有差異請說明…'"
                :class="[
                  'w-full border rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400',
                  !parseFloat(receiveForm.total_amount) ? 'border-amber-300 bg-amber-50' : 'border-slate-200'
                ]" />
            </div>

            <!-- 拍照上傳 -->
            <div>
              <p class="text-xs font-bold text-slate-500 mb-2">拍攝單據 <span class="text-red-500">必填</span></p>
              <input ref="photoInput" type="file" accept="image/*" capture="environment"
                class="hidden" @change="handlePhotoSelect" />
              <button @click="photoInput.click()"
                class="w-full py-3 rounded-xl border-2 border-dashed text-sm font-bold active:bg-slate-50 flex items-center justify-center gap-2"
                :class="receivePhoto ? 'border-green-400 text-green-600' : 'border-red-300 text-red-400'">
                <span class="text-xl">📷</span>
                <span>{{ receivePhoto ? '重新拍攝單據' : '拍攝單據（必填）' }}</span>
              </button>
              <div v-if="receivePhotoPreview" class="mt-2 relative">
                <img :src="receivePhotoPreview" class="w-full max-h-40 object-cover rounded-xl border border-slate-200" />
                <button @click="receivePhoto=null; receivePhotoPreview=''"
                  class="absolute top-2 right-2 bg-black/50 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold">✕</button>
              </div>
            </div>

            <div v-if="receiveError" class="text-red-500 text-sm text-center">{{ receiveError }}</div>
          </div>

          <!-- 固定底部按鈕 -->
          <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
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
          <p class="text-slate-400 font-bold">{{ historySearch ? '查無符合紀錄' : '尚無收貨紀錄' }}</p>
        </div>
        <div v-else class="space-y-2">
          <div v-for="order in filteredHistory" :key="order.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div @click="toggleExpand(order.id)" class="px-4 py-3 cursor-pointer active:bg-slate-50">
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <p class="font-extrabold text-slate-800">{{ order.vendor_name }}</p>
                  <span class="text-[10px] font-mono text-slate-400">#{{ order.id }}</span>
                </div>
                <p class="text-xs text-slate-400">{{ fmtDate(order.updated_at || order.created_at) }}</p>
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
            <div v-if="expandedOrderId===order.id" class="border-t border-slate-100 px-4 py-3 space-y-2">
              <div v-for="(item,idx) in expandedItems" :key="idx" class="flex justify-between text-sm py-0.5">
                <span class="text-slate-700">{{ item.name || item.adhoc_name }}</span>
                <span class="text-slate-500 text-xs">{{ formatDualUnit(item.qty, item) }}</span>
              </div>
              <div v-if="order.note" class="text-xs text-slate-500 pt-1">📝 {{ order.note }}</div>
              <div class="pt-1">
                <div v-if="order.receipt_url" class="mb-2">
                  <a :href="order.receipt_url" target="_blank" rel="noopener">
                    <img :src="order.receipt_url" alt="收據照片"
                      class="w-full max-h-40 object-cover rounded-xl border border-slate-200" />
                  </a>
                  <p class="text-center text-[10px] text-slate-400 mt-1">點擊查看原圖</p>
                </div>
                <label class="block w-full cursor-pointer">
                  <input type="file" accept="image/*" capture="environment" class="hidden"
                    @change="handleRephotaSelect($event, order)" />
                  <div class="py-2 rounded-xl border border-dashed text-xs font-bold text-center flex items-center justify-center gap-1"
                    :class="rephotaUploading && rephotaOrderId === order.id ? 'border-orange-300 text-orange-400' : order.receipt_url ? 'border-slate-200 text-slate-400' : 'border-red-300 text-red-400'">
                    <span>📷</span>
                    <span>{{ rephotaUploading && rephotaOrderId === order.id ? '上傳中…' : order.receipt_url ? '補拍單據' : '上傳單據（尚未拍照）' }}</span>
                  </div>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 盤點歷史 ── -->
      <div v-else class="px-4 py-3">
        <div class="mb-3">
          <input v-model="stocktakeSearch" type="text" placeholder="🔍 搜尋群組 / 日期…"
            class="w-full bg-slate-100 rounded-xl py-2.5 pl-4 pr-4 text-sm font-medium focus:ring-2 focus:ring-blue-400 focus:outline-none" />
        </div>
        <div v-if="historyStocktakeLoading" class="flex justify-center py-16">
          <div class="animate-spin h-7 w-7 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        </div>
        <div v-else-if="filteredSessions.length === 0" class="text-center py-16">
          <p class="text-5xl mb-3">📋</p>
          <p class="text-slate-400 font-bold">{{ stocktakeSearch ? '查無符合紀錄' : '尚無盤點紀錄' }}</p>
        </div>
        <div v-else class="space-y-2">
          <div v-for="s in filteredSessions" :key="s.id" class="bg-white rounded-2xl shadow-sm overflow-hidden">
            <div class="px-4 py-3">
              <div class="flex items-center justify-between mb-1">
                <p class="font-extrabold text-slate-800 cursor-pointer" @click="toggleSession(s.id)">{{ s.group_name || '全部品項' }}</p>
                <div class="flex items-center gap-2">
                  <button v-if="isToday(s.created_at)" @click="startEditSession(s)"
                    class="text-[10px] font-bold text-blue-500 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
                    ✎ 修改
                  </button>
                  <p class="text-xs text-slate-400 cursor-pointer" @click="toggleSession(s.id)">{{ fmtDate(s.created_at) }}</p>
                </div>
              </div>
              <div class="flex items-center justify-between text-xs text-slate-500 cursor-pointer" @click="toggleSession(s.id)">
                <span v-if="s.performed_by">執行人：{{ s.performed_by.name || s.performed_by }}</span>
                <span>{{ s.items?.length || 0 }} 品項</span>
              </div>
              <div class="flex items-center justify-between mt-1 cursor-pointer" @click="toggleSession(s.id)">
                <span class="text-[10px] font-bold"
                  :class="(s.discrepancy_count || 0) > 0 ? 'text-red-500' : 'text-emerald-600'">
                  {{ (s.discrepancy_count || 0) > 0 ? `差異 ${s.discrepancy_count} 項` : '無差異 ✓' }}
                </span>
                <span class="text-slate-400 text-xs">{{ expandedSessions.has(s.id) ? '▲' : '▼' }}</span>
              </div>
            </div>
            <!-- 展開：查看模式 -->
            <div v-if="expandedSessions.has(s.id) && s.items?.length && editingSessionId !== s.id"
              class="border-t border-slate-100 px-4 py-3 space-y-1">
              <div v-for="d in s.items" :key="d.item_id" class="flex items-center justify-between text-sm">
                <span class="text-slate-700">{{ d.item_name }}</span>
                <span class="text-xs font-bold"
                  :class="(d.variance||0) !== 0 ? 'text-red-500' : 'text-slate-400'">
                  系統 {{ d.expected_qty ?? '?' }} → 實盤 {{ d.counted_qty ?? '?' }}
                  <span v-if="(d.variance||0) !== 0"> ({{ d.variance > 0 ? '+' : '' }}{{ d.variance }})</span>
                </span>
              </div>
            </div>
            <!-- 編輯模式（僅限當天） -->
            <div v-if="editingSessionId === s.id" class="border-t border-blue-100 px-4 py-3 bg-blue-50/30 space-y-2">
              <p class="text-xs font-bold text-blue-600 mb-2">✎ 修改盤點數量</p>
              <div v-for="it in editingItems" :key="it.item_id" class="flex items-center justify-between text-sm gap-2">
                <div class="flex-1 min-w-0">
                  <span class="text-slate-700 text-xs block truncate">{{ it.item_name }}</span>
                  <span v-if="it.counted_qty === null" class="text-[10px] text-amber-500 font-bold">未盤點</span>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                  <button @click="it.edit_qty = Math.max(0, parseFloat(it.edit_qty||0) - 1)"
                    class="w-7 h-7 bg-slate-200 rounded-lg text-sm font-bold flex items-center justify-center">−</button>
                  <input v-model.number="it.edit_qty" type="number" min="0" step="0.1"
                    class="w-16 text-center text-sm font-bold bg-white border border-slate-300 rounded-lg py-1 focus:outline-none focus:ring-1 focus:ring-blue-400" />
                  <button @click="it.edit_qty = (parseFloat(it.edit_qty||0) + 1)"
                    class="w-7 h-7 bg-slate-200 rounded-lg text-sm font-bold flex items-center justify-center">+</button>
                </div>
              </div>
              <div class="flex gap-2 mt-3">
                <button @click="cancelEditSession"
                  class="flex-1 py-2 bg-slate-100 text-slate-600 text-xs font-bold rounded-xl">取消</button>
                <button @click="saveEditSession" :disabled="editingSubmitting"
                  class="flex-1 py-2 text-white text-xs font-bold rounded-xl disabled:opacity-40"
                  style="background:#e85d04">
                  {{ editingSubmitting ? '儲存中…' : '確認儲存' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ═══ Order Preview Bottom Sheet ═══ -->
    <div v-if="showPreviewSheet" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="flex justify-between items-center">
            <h3 class="text-base font-extrabold text-slate-800">叫貨單預覽</h3>
            <button @click="showPreviewSheet=false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-3">
          <!-- Copy success alert -->
          <div v-if="previewCopied"
            class="rounded-xl px-3 py-2.5 text-center text-sm font-bold text-emerald-700"
            style="background:#f0fdf4;border:1px solid #bbf7d0">
            ✓ 已複製至剪貼簿，可直接貼到 LINE
          </div>

          <!-- Formatted text preview -->
          <pre class="bg-slate-50 border border-slate-200 rounded-xl p-4 text-sm text-slate-700 whitespace-pre-wrap font-mono overflow-x-auto">{{ previewText }}</pre>
        </div>

        <!-- Fixed bottom button -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
          <button @click="copyAndClose"
            class="w-full text-white font-bold py-4 rounded-2xl active:scale-95"
            style="background:#e85d04">
            📋 複製 LINE 訊息
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
