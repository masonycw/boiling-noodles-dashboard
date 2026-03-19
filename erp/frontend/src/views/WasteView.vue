<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ── State ──
const items = ref([])
const todayRecords = ref([])
const monthlyKpi = ref(null)
const loading = ref(true)

// ── Sheet ──
const showSheet = ref(false)
const submitting = ref(false)
const sheetError = ref('')
const search = ref('')
const showItemDropdown = ref(false)
const selectedItem = ref(null)
const qty = ref(1)
const unit = ref('')
const reason = ref('過期')
const noteText = ref('')

const reasons = [
  { key: '過期', icon: '⌛' },
  { key: '損壞', icon: '💥' },
  { key: '試菜', icon: '🍳' },
  { key: '其他', icon: '📝' },
]

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtTime(d) {
  if (!d) return ''
  return new Date(d).toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })
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

function selectItem(item) {
  selectedItem.value = item
  unit.value = item.unit || ''
  search.value = item.name
  showItemDropdown.value = false
}

function clearItem() {
  selectedItem.value = null
  search.value = ''
  unit.value = ''
}

function openSheet() {
  selectedItem.value = null
  search.value = ''
  unit.value = ''
  qty.value = 1
  reason.value = '過期'
  noteText.value = ''
  sheetError.value = ''
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

onMounted(loadAll)

async function submit() {
  if (!selectedItem.value && !search.value.trim()) {
    sheetError.value = '請選擇品項'
    return
  }
  if (!qty.value || qty.value <= 0) {
    sheetError.value = '數量必須大於 0'
    return
  }
  submitting.value = true
  sheetError.value = ''
  try {
    const payload = {
      qty: qty.value,
      unit: unit.value || null,
      reason: reason.value,
      note: noteText.value || null,
      estimated_value: estimatedValue.value || null,
    }
    if (selectedItem.value) {
      payload.item_id = selectedItem.value.id
    } else {
      payload.adhoc_name = search.value.trim()
    }
    const res = await fetch(`${API_BASE}/waste/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('提交失敗')
    showSheet.value = false
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
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button @click="router.push('/more')" class="font-bold" style="color:#e85d04">← 返回</button>
        <h1 class="text-lg font-extrabold text-slate-800">損耗紀錄</h1>
      </div>
      <span class="text-xs text-slate-400">
        {{ new Date().toLocaleDateString('zh-TW', { month:'numeric', day:'numeric' }) }}
      </span>
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <svg class="animate-spin h-8 w-8" style="color:#e85d04" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>

    <div v-else class="px-4 py-4 space-y-4">

      <!-- 新增損耗 tappable card -->
      <div @click="openSheet"
        class="bg-white rounded-2xl shadow-sm p-4 flex items-center gap-3 cursor-pointer active:scale-[0.98] transition-transform"
        style="border:1.5px solid #fde8d8">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
          style="background:#fff3ec">
          🗑
        </div>
        <div class="flex-1">
          <p class="font-bold text-slate-800 text-sm">記錄損耗品項</p>
          <p class="text-xs text-slate-400 mt-0.5">過期、損壞、試菜…</p>
        </div>
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-lg flex-shrink-0"
          style="background:#e85d04">
          ＋
        </div>
      </div>

      <!-- 今日損耗紀錄 -->
      <div>
        <p class="text-xs font-bold text-slate-500 uppercase mb-2">今日損耗紀錄</p>
        <div v-if="todayRecords.length === 0"
          class="bg-white rounded-2xl p-6 text-center text-slate-400 text-sm shadow-sm">
          今日尚無損耗紀錄
        </div>
        <div v-else class="space-y-2">
          <div v-for="r in todayRecords" :key="r.id"
            class="bg-white rounded-2xl px-4 py-3 shadow-sm flex items-start gap-3">
            <div class="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-base flex-shrink-0 mt-0.5">
              🗑
            </div>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800 text-sm">{{ r.item_name || r.adhoc_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">
                {{ r.reason }} · {{ fmtTime(r.created_at) }}
                <span v-if="r.estimated_value"> · 估值 ${{ fmtMoney(r.estimated_value) }}</span>
              </p>
            </div>
            <div class="shrink-0 text-right">
              <p class="font-bold text-sm" style="color:#ef4444">
                {{ r.qty }} {{ r.unit }}
              </p>
              <p v-if="r.estimated_value" class="text-xs font-bold" style="color:#ef4444">
                −${{ fmtMoney(r.estimated_value) }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 本月損耗彙整 -->
      <div v-if="monthlyKpi" class="bg-white rounded-2xl shadow-sm p-4">
        <p class="text-xs font-bold text-slate-500 uppercase mb-3">本月損耗彙整</p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <p class="text-xs text-slate-400">總次數</p>
            <p class="text-2xl font-black text-slate-800">{{ monthlyKpi.total_count }}</p>
          </div>
          <div>
            <p class="text-xs text-slate-400">總損耗估值</p>
            <p class="text-2xl font-black" style="color:#ef4444">
              ${{ fmtMoney(monthlyKpi.total_value) }}
            </p>
          </div>
        </div>
        <div v-if="monthlyKpi.most_common_reason" class="mt-3 pt-3 border-t border-slate-100">
          <p class="text-xs text-slate-400">
            最常原因：<span class="font-bold text-slate-700">{{ monthlyKpi.most_common_reason }}</span>
            <span v-if="monthlyKpi.reason_breakdown[monthlyKpi.most_common_reason]">
              （{{ monthlyKpi.reason_breakdown[monthlyKpi.most_common_reason] }} 次）
            </span>
          </p>
        </div>
      </div>

    </div>

    <!-- Bottom Sheet -->
    <div v-if="showSheet" class="fixed inset-0 bg-black/50 z-50 flex items-end justify-center">
      <div class="bg-white w-full max-w-md rounded-t-3xl max-h-[90vh] overflow-y-auto">
        <!-- Drag handle -->
        <div class="flex justify-center pt-3 pb-1">
          <div class="w-10 h-1 rounded-full" style="background:#e2e8f0"></div>
        </div>
        <div class="flex justify-between items-center px-5 py-3">
          <h3 class="text-lg font-extrabold text-slate-800">新增損耗紀錄</h3>
          <button @click="showSheet = false" class="text-slate-400 text-xl font-bold">✕</button>
        </div>

        <div class="px-5 pb-8 space-y-4">

          <!-- 品項 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">品項</label>
            <div v-if="selectedItem"
              class="flex items-center gap-2 rounded-xl px-4 py-2.5"
              style="background:#fff3ec;border:1.5px solid #fed7aa">
              <span class="font-bold text-sm flex-1" style="color:#c2410c">{{ selectedItem.name }}</span>
              <button @click="clearItem" class="font-bold" style="color:#fb923c">✕</button>
            </div>
            <div v-else>
              <input v-model="search" @focus="showItemDropdown = true" type="text"
                placeholder="搜尋品項名稱…"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2"
                style="--tw-ring-color:#e85d04" />
              <div v-if="showItemDropdown && search"
                class="mt-1 bg-white border border-slate-200 rounded-xl shadow-lg overflow-hidden max-h-40 overflow-y-auto">
                <button v-for="item in filteredItems" :key="item.id"
                  @click="selectItem(item)"
                  class="w-full text-left px-4 py-3 flex items-center gap-2 border-b border-slate-50 last:border-0 active:bg-orange-50">
                  <span class="font-bold text-slate-800 text-sm flex-1">{{ item.name }}</span>
                  <span class="text-xs text-slate-400">{{ item.unit }}</span>
                </button>
                <div v-if="filteredItems.length === 0" class="px-4 py-3 text-slate-400 text-sm">查無品項</div>
              </div>
            </div>
          </div>

          <!-- 數量 + 單位 -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">數量</label>
              <div class="flex items-center gap-2 border border-slate-200 rounded-xl px-3 py-2">
                <button @click="qty = Math.max(0.5, qty - 0.5)"
                  class="w-7 h-7 rounded-full bg-slate-100 text-slate-600 font-bold text-lg flex items-center justify-center flex-shrink-0">
                  −
                </button>
                <span class="flex-1 text-center font-bold text-sm">{{ qty }}</span>
                <button @click="qty += 0.5"
                  class="w-7 h-7 rounded-full text-white font-bold text-lg flex items-center justify-center flex-shrink-0"
                  style="background:#e85d04">
                  ＋
                </button>
              </div>
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">單位</label>
              <input v-model="unit" type="text" placeholder="包 / kg / 個"
                class="w-full border border-slate-200 rounded-xl px-3 py-3 text-sm focus:outline-none" />
            </div>
          </div>

          <!-- 損耗原因 chips -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-2">損耗原因</label>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="r in reasons" :key="r.key"
                @click="reason = r.key"
                class="py-3 rounded-xl text-sm font-bold border transition-all flex items-center justify-center gap-1.5"
                :style="reason === r.key
                  ? 'border:1.5px solid #e85d04;background:#fff3ec;color:#c2410c'
                  : 'border:1px solid #e2e8f0;background:white;color:#64748b'">
                <span>{{ r.icon }}</span>
                <span>{{ r.key }}</span>
              </button>
            </div>
          </div>

          <!-- 備注 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">備注（選填）</label>
            <textarea v-model="noteText" rows="2" placeholder="說明損耗原因…"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none resize-none"></textarea>
          </div>

          <!-- 損耗估值 -->
          <div v-if="estimatedValue !== null"
            class="rounded-xl p-3" style="background:#fef2f2;border:1px solid #fecaca">
            <p class="font-bold text-sm" style="color:#dc2626">
              💰 損耗估值：−${{ fmtMoney(estimatedValue) }}
            </p>
            <p class="text-xs mt-0.5" style="color:#ef4444">
              依參考單價 ${{ fmtMoney(selectedItem?.price) }} / {{ unit || selectedItem?.unit }}
            </p>
          </div>

          <!-- 照片（佔位） -->
          <button class="w-full border-2 border-dashed border-slate-200 rounded-xl py-3 text-slate-400 text-sm font-medium">
            📷 選擇照片（選填）
          </button>

          <div v-if="sheetError" class="text-rose-500 text-sm text-center">{{ sheetError }}</div>

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
