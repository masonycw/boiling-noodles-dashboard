<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ── Tabs ──
const activeTab = ref('record') // 'record' | 'history'

// ── State ──
const items = ref([])
const todayRecords = ref([])
const historyRecords = ref([])
const historyLoading = ref(false)
const monthlyKpi = ref(null)
const loading = ref(true)
const expandedIds = ref(new Set())

// ── Sheet ──
const showSheet = ref(false)
const submitting = ref(false)
const sheetError = ref('')
const search = ref('')
const showItemDropdown = ref(false)
const selectedItem = ref(null)
const isOtherItem = ref(false)
const qty = ref(1)
const unit = ref('')
const reason = ref('食材過期')
const noteText = ref('')

// ── Photo ──
const photoFile = ref(null)      // File object
const photoPreview = ref(null)   // base64 preview URL
const photoUrl = ref(null)       // uploaded URL from server
const photoUploading = ref(false)
const photoInput = ref(null)     // template ref

function onPhotoChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  photoFile.value = file
  photoUrl.value = null
  const reader = new FileReader()
  reader.onload = ev => { photoPreview.value = ev.target.result }
  reader.readAsDataURL(file)
}

function removePhoto() {
  photoFile.value = null
  photoPreview.value = null
  photoUrl.value = null
  if (photoInput.value) photoInput.value.value = ''
}

async function uploadPhoto() {
  if (!photoFile.value) return null
  if (photoUrl.value) return photoUrl.value   // already uploaded
  photoUploading.value = true
  try {
    const form = new FormData()
    form.append('file', photoFile.value)
    const res = await fetch(`${API_BASE}/uploads/image`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: form
    })
    if (!res.ok) throw new Error('圖片上傳失敗')
    const data = await res.json()
    // Build absolute URL so it works from GCP
    const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')
    photoUrl.value = base + data.url
    return photoUrl.value
  } finally {
    photoUploading.value = false
  }
}

const reasons = [
  { key: '食材過期', icon: '⌛' },
  { key: '物品損壞', icon: '💥' },
  { key: '試菜', icon: '🍳' },
  { key: '其他', icon: '📝' },
]

const reasonColors = {
  '食材過期': { bg: '#fef9c3', text: '#92400e' },
  '物品損壞': { bg: '#fee2e2', text: '#991b1b' },
  '試菜': { bg: '#f0fdf4', text: '#166534' },
  '其他': { bg: '#f1f5f9', text: '#475569' },
}

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtTime(d) {
  if (!d) return ''
  return new Date(d).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })
}
function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  return `${String(dt.getMonth()+1).padStart(2,'0')}/${String(dt.getDate()).padStart(2,'0')}`
}

const estimatedValue = computed(() => {
  const price = selectedItem.value?.price
  if (!price || !qty.value) return null
  return Math.round(parseFloat(price) * qty.value)
})

const filteredItems = computed(() => {
  if (!search.value.trim()) return items.value.slice(0, 15)
  const q = search.value.toLowerCase()
  return items.value.filter(i => i.name.toLowerCase().includes(q)).slice(0, 15)
})

// Group history records by date
const groupedHistory = computed(() => {
  const groups = {}
  historyRecords.value.forEach(r => {
    const d = fmtDate(r.created_at)
    if (!groups[d]) groups[d] = []
    groups[d].push(r)
  })
  return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]))
})

function toggleExpand(id) {
  const s = new Set(expandedIds.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expandedIds.value = s
}

function selectItem(item) {
  selectedItem.value = item
  isOtherItem.value = false
  unit.value = item.unit || ''
  search.value = item.name
  showItemDropdown.value = false
}

function selectOtherItem() {
  selectedItem.value = null
  isOtherItem.value = true
  search.value = ''
  showItemDropdown.value = false
}

function clearItem() {
  selectedItem.value = null
  isOtherItem.value = false
  search.value = ''
  unit.value = ''
}

function openSheet() {
  selectedItem.value = null
  isOtherItem.value = false
  search.value = ''
  unit.value = ''
  qty.value = 1
  reason.value = '食材過期'
  noteText.value = ''
  sheetError.value = ''
  photoFile.value = null
  photoPreview.value = null
  photoUrl.value = null
  showSheet.value = true
}

async function loadAll() {
  loading.value = true
  const today = new Date().toISOString().slice(0, 10)
  const [itemsRes, todayRes, kpiRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/?date=${today}&limit=100`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/monthly-kpi`, { headers: authHeaders() }),
  ])
  if (itemsRes.ok) items.value = await itemsRes.json()
  if (todayRes.ok) todayRecords.value = await todayRes.json()
  if (kpiRes.ok) monthlyKpi.value = await kpiRes.json()
  loading.value = false
}

async function loadHistory() {
  historyLoading.value = true
  const res = await fetch(`${API_BASE}/waste/?days_limit=30&limit=200`, { headers: authHeaders() })
  if (res.ok) historyRecords.value = await res.json()
  historyLoading.value = false
}

async function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'history' && historyRecords.value.length === 0) {
    await loadHistory()
  }
}

onMounted(loadAll)

async function submit() {
  if (!selectedItem.value && !isOtherItem.value) { sheetError.value = '請選擇品項'; return }
  if (!qty.value || qty.value <= 0) { sheetError.value = '數量必須大於 0'; return }
  if (isOtherItem.value && !noteText.value.trim()) { sheetError.value = '選擇「其他」時，備注為必填欄位'; return }
  submitting.value = true
  sheetError.value = ''
  try {
    // Upload photo first if any
    let uploadedUrl = null
    if (photoFile.value) {
      uploadedUrl = await uploadPhoto()
    }
    const payload = {
      qty: qty.value, unit: unit.value || null, reason: reason.value,
      note: noteText.value || null, estimated_value: estimatedValue.value || null,
      photo_url: uploadedUrl || null,
    }
    if (selectedItem.value) payload.item_id = selectedItem.value.id
    else if (isOtherItem.value) payload.adhoc_name = '其他（非常規品項）'
    const res = await fetch(`${API_BASE}/waste/`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('提交失敗')
    showSheet.value = false
    historyRecords.value = [] // reset so next history load is fresh
    await loadAll()
  } catch (e) {
    sheetError.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="min-h-full pb-24" style="background:#f8f9fb">

    <!-- Header -->
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-0">
      <div class="flex items-center justify-between pb-3">
        <div class="flex items-center gap-3">
          <button @click="router.push('/more')" class="font-bold" style="color:#e85d04">← 返回</button>
          <h1 class="text-lg font-extrabold text-slate-800">損耗紀錄</h1>
        </div>
        <span class="text-xs text-slate-400">
          {{ new Date().toLocaleDateString('zh-TW', { month:'numeric', day:'numeric' }) }}
        </span>
      </div>
      <!-- Tab bar -->
      <div class="flex border-b border-slate-100">
        <button v-for="t in [{k:'record',l:'記錄耗損'},{k:'history',l:'歷史紀錄'}]" :key="t.k"
          @click="switchTab(t.k)"
          class="flex-1 py-2.5 text-sm font-bold transition-colors"
          :style="activeTab===t.k ? 'color:#e85d04;border-bottom:2px solid #e85d04' : 'color:#94a3b8'">
          {{ t.l }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <svg class="animate-spin h-8 w-8" style="color:#e85d04" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>

    <!-- ── 記錄耗損 Tab ── -->
    <div v-else-if="activeTab === 'record'" class="px-4 py-4 space-y-4">

      <div @click="openSheet"
        class="bg-white rounded-2xl shadow-sm p-4 flex items-center gap-3 cursor-pointer active:scale-[0.98] transition-transform"
        style="border:1.5px solid #fde8d8">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style="background:#fff3ec">🗑</div>
        <div class="flex-1">
          <p class="font-bold text-slate-800 text-sm">記錄損耗品項</p>
          <p class="text-xs text-slate-400 mt-0.5">過期、損壞、試菜…</p>
        </div>
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
          style="background:#e85d04">＋</div>
      </div>

      <div>
        <p class="text-xs font-bold text-slate-500 uppercase mb-2">今日損耗紀錄</p>
        <div v-if="todayRecords.length === 0"
          class="bg-white rounded-2xl p-6 text-center text-slate-400 text-sm shadow-sm">
          今日尚無損耗紀錄
        </div>
        <div v-else class="space-y-2">
          <div v-for="r in todayRecords" :key="r.id"
            class="bg-white rounded-2xl px-4 py-3 shadow-sm flex items-start gap-3">
            <div class="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-base flex-shrink-0 mt-0.5">🗑</div>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800 text-sm">{{ r.item_name || r.adhoc_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">
                {{ r.reason }} · {{ fmtTime(r.created_at) }}
                <span v-if="r.estimated_value"> · 估值 ${{ fmtMoney(r.estimated_value) }}</span>
              </p>
            </div>
            <div class="shrink-0 text-right">
              <p class="font-bold text-sm" style="color:#ef4444">{{ r.qty }} {{ r.unit }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="monthlyKpi" class="bg-white rounded-2xl shadow-sm p-4">
        <p class="text-xs font-bold text-slate-500 uppercase mb-3">本月損耗彙整</p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-xs text-slate-400">總次數</p>
            <p class="text-2xl font-black text-slate-800">{{ monthlyKpi.total_count }}</p>
          </div>
          <div>
            <p class="text-xs text-slate-400">總損耗估值</p>
            <p class="text-2xl font-black" style="color:#ef4444">${{ fmtMoney(monthlyKpi.total_value) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 歷史紀錄 Tab ── -->
    <div v-else class="px-4 py-4">
      <div v-if="historyLoading" class="flex justify-center py-12">
        <div class="animate-spin h-6 w-6 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>
      <div v-else-if="historyRecords.length === 0" class="text-center py-12 text-slate-400 text-sm">
        近 30 天無損耗紀錄
      </div>
      <div v-else class="space-y-4">
        <div v-for="[date, records] in groupedHistory" :key="date">
          <p class="text-xs font-bold text-slate-400 mb-2">{{ date }}</p>
          <div class="space-y-2">
            <div v-for="r in records" :key="r.id"
              class="bg-white rounded-2xl shadow-sm overflow-hidden">
              <!-- Card header (always visible) -->
              <div @click="toggleExpand(r.id)"
                class="px-4 py-3 flex items-center gap-3 cursor-pointer active:bg-slate-50">
                <span class="text-xs font-bold px-2 py-0.5 rounded-full shrink-0"
                  :style="`background:${reasonColors[r.reason]?.bg||'#f1f5f9'};color:${reasonColors[r.reason]?.text||'#475569'}`">
                  {{ r.reason }}
                </span>
                <p class="flex-1 font-bold text-slate-800 text-sm truncate">{{ r.item_name || r.adhoc_name }}</p>
                <p class="font-bold text-sm shrink-0" style="color:#ef4444">{{ r.qty }} {{ r.unit }}</p>
                <span class="text-slate-400 text-xs shrink-0">{{ expandedIds.has(r.id) ? '▲' : '▼' }}</span>
              </div>
              <!-- Expanded details -->
              <div v-if="expandedIds.has(r.id)"
                class="px-4 pb-3 pt-1 border-t border-slate-100 space-y-1.5 text-xs text-slate-500">
                <p>🕐 時間：{{ fmtTime(r.created_at) }}</p>
                <p v-if="r.estimated_value">💰 損耗估值：<span class="font-bold text-red-500">−${{ fmtMoney(r.estimated_value) }}</span></p>
                <p v-if="r.note">📝 備注：{{ r.note }}</p>
                <p v-if="r.recorded_by_name">👤 記錄人：{{ r.recorded_by_name }}</p>
                <div v-if="r.photo_url" class="pt-1">
                  <a :href="r.photo_url" target="_blank" rel="noopener">
                    <img :src="r.photo_url" alt="損耗照片"
                      class="w-full max-h-40 object-cover rounded-lg border border-slate-200" />
                  </a>
                  <p class="text-center text-slate-400 mt-1">點擊查看原圖</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Sheet -->
    <div v-if="showSheet" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="flex justify-between items-center">
            <h3 class="text-lg font-extrabold text-slate-800">新增損耗紀錄</h3>
            <button @click="showSheet = false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4">
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">品項</label>
            <div v-if="selectedItem || isOtherItem"
              class="flex items-center gap-2 rounded-xl px-4 py-2.5"
              style="background:#fff3ec;border:1.5px solid #fed7aa">
              <span class="font-bold text-sm flex-1" style="color:#c2410c">
                {{ isOtherItem ? '其他（非常規品項）' : selectedItem.name }}
              </span>
              <button @click="clearItem" class="font-bold" style="color:#fb923c">✕</button>
            </div>
            <div v-else>
              <input v-model="search" @focus="showItemDropdown = true" type="text"
                placeholder="搜尋品項名稱…"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2" />
              <div v-if="showItemDropdown"
                class="mt-1 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden max-h-48 overflow-y-auto">
                <button v-for="item in filteredItems" :key="item.id" @click="selectItem(item)"
                  class="w-full text-left px-4 py-3 flex items-center gap-2 border-b border-slate-50 active:bg-orange-50">
                  <span class="font-bold text-slate-800 text-sm flex-1">{{ item.name }}</span>
                  <span class="text-xs text-slate-400">{{ item.unit }}</span>
                </button>
                <div v-if="filteredItems.length === 0" class="px-4 py-3 text-slate-400 text-sm">查無品項</div>
                <div class="border-t border-slate-200"></div>
                <button @click="selectOtherItem"
                  class="w-full text-left px-4 py-3 flex items-center gap-2 active:bg-orange-50">
                  <span class="text-sm font-medium text-slate-500">📝 其他（非常規品項）</span>
                </button>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">數量</label>
              <input v-model.number="qty" type="number" min="1"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-center font-bold focus:outline-none" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">單位</label>
              <input v-model="unit" type="text" placeholder="包 / kg / 個"
                class="w-full border border-slate-200 rounded-xl px-3 py-3 text-sm focus:outline-none" />
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-2">損耗原因</label>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="r in reasons" :key="r.key" @click="reason = r.key"
                class="py-3 rounded-xl text-sm font-bold border transition-all flex items-center justify-center gap-1.5"
                :style="reason === r.key
                  ? 'border:1.5px solid #e85d04;background:#fff3ec;color:#c2410c'
                  : 'border:1px solid #e2e8f0;background:white;color:#64748b'">
                <span>{{ r.icon }}</span><span>{{ r.key }}</span>
              </button>
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold mb-1"
              :class="isOtherItem ? 'text-rose-500' : 'text-slate-500 uppercase'">
              {{ isOtherItem ? '備注 *（必填）' : '備注（選填）' }}
            </label>
            <textarea v-model="noteText" rows="2"
              :placeholder="isOtherItem ? '請描述耗損品項' : '說明損耗原因…'"
              class="w-full rounded-xl px-4 py-3 text-sm focus:outline-none resize-none"
              :class="isOtherItem && !noteText.trim() ? 'border-2 border-rose-500' : 'border border-slate-200'">
            </textarea>
          </div>

          <div v-if="estimatedValue !== null"
            class="rounded-xl p-3" style="background:#fef2f2;border:1px solid #fecaca">
            <p class="font-bold text-sm" style="color:#dc2626">
              💰 損耗估值：−${{ fmtMoney(estimatedValue) }}
            </p>
          </div>

          <!-- Photo capture -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-2">拍照存證（選填）</label>
            <!-- No photo yet -->
            <div v-if="!photoPreview">
              <label class="flex items-center justify-center gap-2 w-full py-3 rounded-xl border border-dashed border-slate-300 cursor-pointer active:bg-orange-50 transition-colors"
                style="background:#fafafa">
                <span class="text-xl">📷</span>
                <span class="text-sm font-medium text-slate-500">拍照 / 選取圖片</span>
                <input ref="photoInput" type="file" accept="image/*" capture="environment"
                  class="hidden" @change="onPhotoChange" />
              </label>
            </div>
            <!-- Preview -->
            <div v-else class="relative rounded-xl overflow-hidden"
              style="border:1.5px solid #fed7aa">
              <img :src="photoPreview" alt="損耗照片" class="w-full max-h-48 object-cover" />
              <button @click="removePhoto"
                class="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/50 text-white flex items-center justify-center text-sm font-bold">✕</button>
              <div v-if="photoUploading"
                class="absolute inset-0 bg-white/70 flex items-center justify-center">
                <div class="animate-spin h-6 w-6 border-4 border-orange-500 border-t-transparent rounded-full"></div>
              </div>
            </div>
          </div>

          <div v-if="sheetError" class="text-rose-500 text-sm text-center">{{ sheetError }}</div>
        </div>

        <!-- Fixed bottom button -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100">
          <button @click="submit" :disabled="submitting"
            class="w-full text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40"
            style="background:#e85d04">
            {{ submitting ? '送出中…' : '確認送出' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>