<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { compressImage } from '@/composables/useImageCompress'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---- State ----
const isLoading = ref(false)
const pettyBalance = ref(0)
const todayIncome = ref(0)
const todayExpense = ref(0)
const todayRecords = ref([])
const yesterdayRecords = ref([])
const settlements = ref([])  // A3: 多次日結記錄
const vendors = ref([])

// ---- Daily settlement (A3: 多次日結) ----
const showSettleModal = ref(false)
const settleSubmitting = ref(false)
const settleError = ref('')
const canSettle = ref(true)        // A3: 是否可再次日結
const settleToast = ref(false)
const settlementCount = ref(0)    // A3: 今日日結次數
const unsettledCount = ref(0)     // A3: 未日結紀錄數

// ---- Finance sheet modal ----
const showSheet = ref(false)
const sheetType = ref('expense')  // 'expense' | 'income' | 'withdrawal'
const sheetForm = ref({
  amount: '',
  description: '',
  date: new Date().toISOString().slice(0, 10),
  vendor_id: '',
  is_paid: true,
  income_source: '',
  withdrawal_purpose: 'bank'
})
const sheetError = ref('')
const sheetSubmitting = ref(false)

// A3: 附件上傳
const attachmentFiles = ref([])   // { file: File, preview: string }[]
const attachmentUploading = ref(false)

// A3: Lightbox
const lightboxImages = ref([])
const lightboxIndex = ref(0)
const showLightbox = ref(false)

function openLightbox(imgs, idx = 0) {
  lightboxImages.value = imgs
  lightboxIndex.value = idx
  showLightbox.value = true
}

async function handleAttachmentSelect(e) {
  const files = Array.from(e.target.files)
  if (attachmentFiles.value.length + files.length > 3) {
    alert('每筆紀錄最多 3 張照片')
    return
  }
  for (const file of files) {
    try {
      const compressed = await compressImage(file)
      const preview = URL.createObjectURL(compressed)
      attachmentFiles.value.push({ file: compressed, preview })
    } catch { console.warn('compress failed', file.name) }
  }
  e.target.value = ''
}

function removeAttachment(idx) {
  URL.revokeObjectURL(attachmentFiles.value[idx].preview)
  attachmentFiles.value.splice(idx, 1)
}

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

// ---- Load data ----
async function loadAll() {
  isLoading.value = true
  try {
    const today = new Date().toISOString().slice(0, 10)
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)

    const [balRes, todayRes, yestRes, vendRes, settleRes, canSettleRes] = await Promise.all([
      fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/petty-cash?date=${today}&limit=100`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/petty-cash?date=${yesterday}&limit=100`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/inventory/vendors`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/daily-settlement/today`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/daily-settlement/can-settle`, { headers: { Authorization: `Bearer ${auth.token}` } }).catch(() => null),
    ])

    if (balRes.ok) pettyBalance.value = (await balRes.json()).balance
    if (todayRes.ok) {
      const records = await todayRes.json()
      todayRecords.value = Array.isArray(records) ? records : []
      todayIncome.value = todayRecords.value
        .filter(r => r.type === 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0)
      todayExpense.value = todayRecords.value
        .filter(r => r.type !== 'income').reduce((s, r) => s + parseFloat(r.amount || 0), 0)
    }
    if (yestRes.ok) {
      const records = await yestRes.json()
      yesterdayRecords.value = Array.isArray(records) ? records : []
    }
    if (vendRes.ok) vendors.value = await vendRes.json()
    if (settleRes.ok) {
      const sd = await settleRes.json()
      // A3: support multiple settlements
      if (Array.isArray(sd)) {
        settlements.value = sd
        settlementCount.value = sd.length
      } else {
        settlements.value = sd.settled ? [sd] : []
        settlementCount.value = sd.settled ? 1 : 0
      }
    }
    // A3: check if can settle again
    if (canSettleRes?.ok) {
      const cs = await canSettleRes.json()
      canSettle.value = cs.can_settle !== false
      unsettledCount.value = cs.unsettled_count || 0
    } else {
      // fallback: check if there are new transactions since last settlement
      if (!settlements.value.length) {
        canSettle.value = true
      } else {
        const lastSettlementTime = new Date(settlements.value[0].settled_at || settlements.value[0].created_at)
        canSettle.value = todayRecords.value.some(t =>
          new Date(t.created_at) > lastSettlementTime
        )
      }
    }
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAll)

// ---- Submit transaction ----
async function submitSheet() {
  sheetError.value = ''
  const amount = parseFloat(sheetForm.value.amount)
  if (!amount || amount <= 0) { sheetError.value = '請輸入金額'; return }

  sheetSubmitting.value = true
  try {
    const payload = {
      type: sheetType.value,
      amount,
      note: sheetForm.value.description || null,
      vendor_id: sheetForm.value.vendor_id || null,
      is_paid: sheetForm.value.is_paid,
    }
    const res = await fetch(`${API_BASE}/finance/petty-cash`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '儲存失敗')
    }
    const newRecord = await res.json()

    // A3: upload attachments if any
    if (attachmentFiles.value.length && newRecord?.id) {
      attachmentUploading.value = true
      for (const { file } of attachmentFiles.value) {
        const fd = new FormData()
        fd.append('file', file)
        await fetch(`${API_BASE}/finance/petty-cash/${newRecord.id}/attachments`, {
          method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: fd
        }).catch(() => {})
      }
      attachmentUploading.value = false
    }

    showSheet.value = false
    sheetForm.value = { amount: '', description: '', date: new Date().toISOString().slice(0, 10), vendor_id: '', is_paid: true, income_source: '', withdrawal_purpose: 'bank' }
    attachmentFiles.value.forEach(a => URL.revokeObjectURL(a.preview))
    attachmentFiles.value = []
    await loadAll()
  } catch (e) {
    sheetError.value = e.message
  } finally {
    sheetSubmitting.value = false
  }
}

// ---- Daily settlement submit (A3: 多次日結) ----
async function submitSettle() {
  settleSubmitting.value = true
  settleError.value = ''
  try {
    const res = await fetch(`${API_BASE}/finance/daily-settlement`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        income_total: todayIncome.value,
        expense_total: todayExpense.value,
        notes: null,
      })
    })
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '日結失敗')
    }
    showSettleModal.value = false
    settleToast.value = true
    setTimeout(() => { settleToast.value = false }, 3000)
    await loadAll()
  } catch (e) {
    settleError.value = e.message
  } finally {
    settleSubmitting.value = false
  }
}

// ---- E1: 零用金紀錄詳情 ----
const showDetailSheet = ref(false)
const detailRecord = ref(null)
const detailLoading = ref(false)

async function openDetail(r) {
  detailRecord.value = r
  showDetailSheet.value = true
  // fetch full detail (includes creator name, category, payment_method if not in list)
  detailLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/finance/petty-cash/${r.id}`, { headers: { Authorization: `Bearer ${auth.token}` } })
    if (res.ok) detailRecord.value = await res.json()
  } catch { /* use already-loaded data */ }
  finally { detailLoading.value = false }
}

function typeLabel(type) {
  if (type === 'income') return '收入'
  if (type === 'withdrawal') return '提領'
  return '支出'
}

// ---- Helpers ----
function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  const mm = String(dt.getMonth() + 1).padStart(2, '0')
  const dd = String(dt.getDate()).padStart(2, '0')
  const hh = String(dt.getHours()).padStart(2, '0')
  const min = String(dt.getMinutes()).padStart(2, '0')
  return `${mm}/${dd} ${hh}:${min}`
}
function fmtFullDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
function fmtMoney(n) {
  return Number(n || 0).toLocaleString('zh-TW')
}

function txIcon(r) {
  if (r.type === 'income') return '📥'
  if (r.type === 'withdrawal') return '🏧'
  if (r.vendor_name) return '📦'
  return '💵'
}
function txSubtitle(r) {
  const parts = []
  if (r.created_at) parts.push(fmtDate(r.created_at))
  if (r.type === 'income') parts.push('收入')
  else if (r.type === 'withdrawal') parts.push('提領')
  else parts.push('支出')
  return parts.join(' · ')
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-24 relative">

    <!-- Header -->
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4">
      <h1 class="text-xl font-extrabold text-slate-800">零用金管理</h1>
      <p class="text-xs text-slate-400 mt-0.5">
        {{ new Date().toLocaleDateString('zh-TW', { year:'numeric', month:'numeric', day:'numeric' }) }} · 現場紀錄
      </p>
    </div>

    <div v-if="isLoading" class="flex justify-center py-16">
      <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
    </div>

    <div v-else>
      <!-- 摘要卡片 -->
      <div class="px-4 mt-4 space-y-2">
        <!-- 全寬：零用金餘額 -->
        <div class="bg-white rounded-xl shadow-sm p-3 flex items-center gap-3">
          <span class="text-xl">💰</span>
          <div class="flex-1">
            <p class="text-xs font-bold text-slate-400">目前零用金餘額</p>
            <p class="text-2xl font-black text-emerald-600">${{ fmtMoney(pettyBalance) }}</p>
          </div>
        </div>

        <!-- 三欄：本日收入 / 本日支出 / 今日帳目 -->
        <div class="grid grid-cols-3 gap-2">
          <div class="bg-white rounded-xl shadow-sm p-2.5">
            <p class="font-bold text-slate-400" style="font-size:9px">本日收入</p>
            <p class="font-black text-emerald-500 mt-0.5" style="font-size:16px">+${{ fmtMoney(todayIncome) }}</p>
          </div>
          <div class="bg-white rounded-xl shadow-sm p-2.5">
            <p class="font-bold text-slate-400" style="font-size:9px">本日支出</p>
            <p class="font-black text-red-500 mt-0.5" style="font-size:16px">−${{ fmtMoney(todayExpense) }}</p>
          </div>
          <div class="rounded-xl shadow-sm p-2.5 flex flex-col items-center justify-center"
            :style="canSettle ? 'background:#fff8f0;border:1.5px solid #e85d04' : 'background:#f1f5f9;border:1.5px solid #cbd5e1'">
            <p class="font-bold" style="font-size:9px" :style="canSettle ? 'color:#e85d04' : 'color:#94a3b8'">今日帳目</p>
            <!-- A3: 多次日結按鈕 -->
            <button v-if="canSettle" @click="showSettleModal = true"
              class="mt-1 text-white font-extrabold rounded-md px-2 py-0.5 active:scale-95 transition-transform"
              style="font-size:11px;background:#e85d04">
              🔒 {{ settlementCount > 0 ? `第${settlementCount+1}次日結` : '日結' }}
            </button>
            <button v-else disabled
              class="mt-1 font-extrabold rounded-md px-2 py-0.5"
              style="font-size:10px;background:#e2e8f0;color:#94a3b8">
              無新紀錄
            </button>
            <p v-if="settlementCount > 0" class="text-[8px] text-slate-400 mt-0.5">已日結 {{ settlementCount }} 次</p>
          </div>
        </div>
      </div>

      <!-- 今日流水 -->
      <div class="px-4 mt-5">
        <p class="font-bold text-slate-600 mb-2" style="font-size:12px">
          今日流水 — {{ new Date().toLocaleDateString('zh-TW', { month:'numeric', day:'numeric' }) }}
        </p>
        <!-- A3: 多次日結分隔線（非可展開，純樣式分隔） -->
        <div v-for="(s, si) in settlements" :key="s.id || si" class="my-3">
          <div class="flex items-center gap-2">
            <div class="flex-1 h-px bg-orange-200"></div>
            <div class="flex items-center gap-1.5 text-[10px] font-bold text-orange-600 bg-orange-50 border border-orange-200 rounded-full px-3 py-1 whitespace-nowrap">
              <span>🔒</span>
              <span>第 {{ s.settlement_number || (si+1) }} 次日結</span>
              <span class="text-orange-400">·</span>
              <span>{{ s.settled_at ? fmtDate(s.settled_at) : '' }}</span>
              <span v-if="s.settled_by_name" class="text-orange-400">·</span>
              <span v-if="s.settled_by_name">{{ s.settled_by_name }}</span>
              <span v-if="s.closing_balance != null" class="text-orange-400">·</span>
              <span v-if="s.closing_balance != null">NT${{ fmtMoney(s.closing_balance) }}</span>
            </div>
            <div class="flex-1 h-px bg-orange-200"></div>
          </div>
        </div>

        <div v-if="todayRecords.length === 0" class="text-center py-6 text-slate-400 text-sm bg-white rounded-xl">
          今日尚無紀錄
        </div>
        <div v-else class="space-y-2">
          <div v-for="r in todayRecords" :key="r.id"
            class="bg-white rounded-xl px-4 py-3 shadow-sm cursor-pointer active:scale-[0.98] transition-transform"
            @click="openDetail(r)">
            <div class="flex items-center gap-3">
              <span style="font-size:20px">{{ txIcon(r) }}</span>
              <div class="flex-1 min-w-0">
                <p class="font-bold text-slate-800 truncate" style="font-size:13px">
                  {{ r.note || r.vendor_name || '零用金紀錄' }}
                </p>
                <p class="text-slate-400" style="font-size:11px">{{ txSubtitle(r) }}</p>
              </div>
              <p class="font-black shrink-0" style="font-size:14px"
                :class="r.type === 'income' ? 'text-emerald-500' : 'text-red-500'">
                {{ r.type === 'income' ? '+' : '−' }}${{ fmtMoney(r.amount) }}
              </p>
            </div>
            <!-- A3: 附件縮圖 -->
            <div v-if="r.attachments?.length" class="mt-2 flex gap-1.5 flex-wrap" @click.stop>
              <button v-for="(att, aidx) in r.attachments" :key="att.id"
                @click="openLightbox(r.attachments.map(a=>a.file_url), aidx)"
                class="w-10 h-10 rounded-lg overflow-hidden border border-slate-200 flex-shrink-0">
                <img :src="att.file_url" class="w-full h-full object-cover" />
              </button>
              <span class="text-[10px] text-slate-400 self-center">📎 {{ r.attachments.length }} 張</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 昨日流水 -->
      <div v-if="yesterdayRecords.length > 0" class="px-4 mt-5">
        <!-- 分隔線 -->
        <div class="flex items-center gap-2 my-3">
          <div class="flex-1 h-px bg-slate-200"></div>
          <span class="text-slate-400 bg-slate-50 px-3 rounded-full" style="font-size:10px;border:1px solid #e2e8f0">
            🔒 昨日日結完成
          </span>
          <div class="flex-1 h-px bg-slate-200"></div>
        </div>
        <p class="font-bold text-slate-600 mb-2" style="font-size:12px">
          昨日流水 — {{ new Date(Date.now()-86400000).toLocaleDateString('zh-TW', { month:'numeric', day:'numeric' }) }}（最遠可查）
        </p>
        <div class="space-y-2">
          <div v-for="r in yesterdayRecords" :key="r.id"
            class="rounded-xl px-4 py-3 flex items-center gap-3 shadow-sm cursor-pointer active:scale-[0.98] transition-transform"
            :class="r.type === 'withdrawal' ? '' : 'bg-white'"
            :style="r.type === 'withdrawal' ? 'background:#fff8f0;border:1px solid #fed7aa' : ''"
            @click="openDetail(r)">
            <span style="font-size:20px">{{ txIcon(r) }}</span>
            <div class="flex-1 min-w-0">
              <p class="font-bold text-slate-800 truncate" style="font-size:13px">
                {{ r.note || r.vendor_name || '零用金紀錄' }}
              </p>
              <p class="text-slate-400" style="font-size:11px">{{ txSubtitle(r) }}</p>
            </div>
            <p class="font-black shrink-0" style="font-size:14px"
              :class="r.type === 'income' ? 'text-emerald-500' : r.type === 'withdrawal' ? 'text-orange-500' : 'text-red-500'">
              {{ r.type === 'income' ? '+' : '−' }}${{ fmtMoney(r.amount) }}
            </p>
          </div>
        </div>
      </div>

      <!-- 歷史提示 -->
      <p class="text-center text-slate-400 mt-6 px-4" style="font-size:11px">
        近 2 天零用金紀錄 · 完整歷史請至後台「零用金管理」查詢
      </p>
    </div>

    <!-- FAB -->
    <button
      @click="showSheet = true"
      class="fixed right-5 text-white font-bold shadow-lg flex items-center justify-center z-30"
      style="bottom:90px;width:52px;height:52px;border-radius:16px;background:#e85d04;font-size:26px;line-height:1">
      ＋
    </button>

    <!-- Finance Sheet Modal -->
    <div v-if="showSheet" class="fixed inset-0 bg-black/50 z-50 flex items-end justify-center">
      <div class="bg-white w-full max-w-md rounded-t-3xl max-h-[90vh] overflow-y-auto">
        <!-- Handle -->
        <div class="flex justify-center pt-3 pb-1">
          <div class="w-10 h-1 bg-slate-200 rounded-full"></div>
        </div>
        <div class="flex justify-between items-center px-5 py-3">
          <h3 class="text-lg font-extrabold text-slate-800">新增金流紀錄</h3>
          <button @click="showSheet = false; sheetError = ''" class="text-slate-400 text-xl font-bold">✕</button>
        </div>

        <div class="px-5 pb-8 space-y-4">
          <!-- 類型選擇 -->
          <div class="flex gap-2">
            <button v-for="t in [{key:'expense',label:'📤 支出'},{key:'income',label:'📥 收入'},{key:'withdrawal',label:'🏧 提領'}]"
              :key="t.key"
              @click="sheetType = t.key"
              class="flex-1 py-2.5 rounded-xl text-sm font-bold border transition-all"
              :class="sheetType === t.key ? 'text-white border-orange-500' : 'bg-white border-slate-200 text-slate-500'"
              :style="sheetType === t.key ? 'background:#e85d04' : ''">
              {{ t.label }}
            </button>
          </div>

          <!-- 提領警示 -->
          <div v-if="sheetType === 'withdrawal'"
            class="rounded-xl p-3" style="background:#fff8f0;border:1.5px solid #e85d04">
            <p class="font-bold text-sm" style="color:#e85d04">
              🏧 零用金提領 — 零用金餘額將減少
            </p>
            <p class="text-xs text-slate-500 mt-1">僅後台授權帳號可執行此操作・需拍照存證</p>
          </div>

          <!-- 支出對象 -->
          <div v-if="sheetType === 'expense'">
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">支出對象</label>
            <select v-model="sheetForm.vendor_id"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-orange-400">
              <option value="">零用金雜費</option>
              <option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.name }}</option>
            </select>
          </div>

          <!-- 是否付款 -->
          <div v-if="sheetType === 'expense'">
            <label class="block text-xs font-bold text-slate-500 uppercase mb-2">是否有實際付錢？</label>
            <div class="flex gap-2">
              <button @click="sheetForm.is_paid = true"
                class="flex-1 py-2.5 rounded-xl text-sm font-bold border transition-all"
                :class="sheetForm.is_paid ? 'border-emerald-400 bg-emerald-50 text-emerald-700' : 'border-slate-200 text-slate-400'">
                ✓ 有付錢
              </button>
              <button @click="sheetForm.is_paid = false"
                class="flex-1 py-2.5 rounded-xl text-sm font-bold border transition-all"
                :class="!sheetForm.is_paid ? 'border-slate-600 bg-slate-100 text-slate-700' : 'border-slate-200 text-slate-400'">
                未付款
              </button>
            </div>
          </div>

          <!-- 收入來源 -->
          <div v-if="sheetType === 'income'">
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">收入來源</label>
            <select v-model="sheetForm.income_source"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-orange-400">
              <option value="">錢櫃收入（現金）</option>
              <option value="advance">領錢期款收入</option>
              <option value="other">其他收入</option>
            </select>
          </div>

          <!-- 金額 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">金額</label>
            <input v-model="sheetForm.amount"
              type="number" inputmode="decimal" min="0" placeholder="0"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-2xl font-extrabold text-center focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>

          <!-- 說明 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">說明 / 備注</label>
            <input v-model="sheetForm.description"
              type="text" placeholder="輸入說明…"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>

          <!-- 日期 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-1">日期</label>
            <input v-model="sheetForm.date" type="date"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>

          <p class="text-center text-slate-400" style="font-size:10px">科目由系統依廠商自動對應，無需手動選擇</p>

          <!-- A3: 附件上傳 -->
          <div>
            <label class="block text-xs font-bold text-slate-500 uppercase mb-2">單據附件（最多 3 張）</label>
            <div class="flex gap-2 flex-wrap">
              <div v-for="(att, idx) in attachmentFiles" :key="idx"
                class="relative w-16 h-16 rounded-xl overflow-hidden border border-slate-200">
                <img :src="att.preview" class="w-full h-full object-cover" />
                <button @click="removeAttachment(idx)"
                  class="absolute top-0.5 right-0.5 w-5 h-5 bg-black/60 text-white rounded-full text-xs flex items-center justify-center">✕</button>
              </div>
              <label v-if="attachmentFiles.length < 3"
                class="w-16 h-16 rounded-xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center cursor-pointer text-slate-400 hover:border-orange-400 hover:text-orange-400">
                <span class="text-lg">📷</span>
                <span class="text-[9px] font-bold">拍照</span>
                <input type="file" accept="image/*" capture="environment" class="hidden" @change="handleAttachmentSelect" />
              </label>
              <label v-if="attachmentFiles.length < 3"
                class="w-16 h-16 rounded-xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center cursor-pointer text-slate-400 hover:border-orange-400 hover:text-orange-400">
                <span class="text-lg">📁</span>
                <span class="text-[9px] font-bold">相簿</span>
                <input type="file" accept="image/*" class="hidden" @change="handleAttachmentSelect" />
              </label>
            </div>
          </div>

          <div v-if="sheetError" class="text-red-500 text-sm text-center">{{ sheetError }}</div>

          <button @click="submitSheet" :disabled="sheetSubmitting || attachmentUploading"
            class="w-full text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40"
            style="background:#e85d04">
            {{ attachmentUploading ? '上傳附件中…' : sheetSubmitting ? '送出中…' : '送出紀錄' }}
          </button>
        </div>
      </div>
    </div>

    <!-- A3: Lightbox -->
    <div v-if="showLightbox" class="fixed inset-0 bg-black/90 z-[60] flex items-center justify-center"
      @click.self="showLightbox=false">
      <button @click="showLightbox=false" class="absolute top-4 right-4 text-white text-2xl">✕</button>
      <button v-if="lightboxIndex > 0" @click="lightboxIndex--"
        class="absolute left-4 text-white text-3xl">‹</button>
      <img :src="lightboxImages[lightboxIndex]" class="max-w-full max-h-full rounded-xl object-contain" />
      <button v-if="lightboxIndex < lightboxImages.length-1" @click="lightboxIndex++"
        class="absolute right-4 text-white text-3xl">›</button>
      <p class="absolute bottom-4 text-white text-sm">{{ lightboxIndex+1 }} / {{ lightboxImages.length }}</p>
    </div>

    <!-- Daily Settlement Modal -->
    <div v-if="showSettleModal" class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center px-4">
      <div class="bg-white w-full max-w-sm rounded-3xl shadow-2xl overflow-hidden">
        <div class="px-6 pt-6 pb-2">
          <h3 class="text-lg font-extrabold text-slate-800">確認{{ settlementCount > 0 ? `第 ${settlementCount+1} 次` : '' }}日結</h3>
          <p class="text-xs text-slate-500 mt-1">
            {{ new Date().toLocaleDateString('zh-TW', { year:'numeric', month:'numeric', day:'numeric' }) }}
          </p>
        </div>

        <div class="px-6 py-4 space-y-3">
          <!-- Today summary -->
          <div class="rounded-2xl p-4 space-y-2" style="background:#f8f9fb">
            <div class="flex justify-between items-center">
              <span class="text-sm text-slate-500">今日收入</span>
              <span class="font-black text-emerald-600 text-base">+${{ fmtMoney(todayIncome) }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-slate-500">今日支出</span>
              <span class="font-black text-red-500 text-base">−${{ fmtMoney(todayExpense) }}</span>
            </div>
            <div class="border-t border-slate-200 pt-2 flex justify-between items-center">
              <span class="text-sm font-bold text-slate-700">淨額</span>
              <span class="font-black text-base"
                :class="(todayIncome - todayExpense) >= 0 ? 'text-emerald-600' : 'text-red-500'">
                {{ (todayIncome - todayExpense) >= 0 ? '+' : '' }}${{ fmtMoney(todayIncome - todayExpense) }}
              </span>
            </div>
          </div>

          <!-- Warning -->
          <div class="rounded-xl p-3 flex gap-2" style="background:#fff8f0;border:1px solid #fed7aa">
            <span class="text-base flex-shrink-0">⚠️</span>
            <p class="text-xs text-orange-700">
              日結後今日帳目將鎖定，僅後台可做修正
            </p>
          </div>

          <div v-if="settleError" class="text-red-500 text-sm text-center">{{ settleError }}</div>
        </div>

        <div class="px-6 pb-6 flex gap-3">
          <button @click="showSettleModal = false; settleError = ''"
            class="flex-1 py-3 rounded-2xl font-bold text-slate-600 border border-slate-200 bg-slate-50 active:scale-95 transition-transform">
            取消
          </button>
          <button @click="submitSettle" :disabled="settleSubmitting"
            class="flex-1 py-3 rounded-2xl font-bold text-white active:scale-95 transition-transform disabled:opacity-40"
            style="background:#e85d04">
            {{ settleSubmitting ? '日結中…' : '確認日結' }}
          </button>
        </div>
      </div>
    </div>

    <!-- E1: 零用金紀錄詳情 Bottom Sheet -->
    <div v-if="showDetailSheet" class="fixed inset-0 bg-black/50 z-50 flex items-end justify-center"
      @click.self="showDetailSheet = false">
      <div class="bg-white w-full max-w-md rounded-t-3xl max-h-[85vh] overflow-y-auto">
        <div class="flex justify-center pt-3 pb-1">
          <div class="w-10 h-1 bg-slate-200 rounded-full"></div>
        </div>
        <div class="px-5 py-3 flex items-center justify-between border-b border-slate-100">
          <h3 class="text-base font-extrabold text-slate-800">零用金紀錄詳情</h3>
          <button @click="showDetailSheet = false" class="text-slate-400 text-xl font-bold">✕</button>
        </div>

        <div v-if="detailLoading" class="flex justify-center py-8">
          <svg class="animate-spin h-6 w-6 text-orange-400" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
        </div>

        <div v-else-if="detailRecord" class="px-5 pb-8 space-y-5">
          <!-- 類型大字 + 金額 -->
          <div class="flex items-center justify-between pt-2">
            <span class="text-xl font-extrabold"
              :class="detailRecord.type === 'income' ? 'text-emerald-600' : detailRecord.type === 'withdrawal' ? 'text-orange-500' : 'text-red-500'">
              {{ typeLabel(detailRecord.type) }}
            </span>
            <span class="text-2xl font-black"
              :class="detailRecord.type === 'income' ? 'text-emerald-600' : 'text-red-500'">
              {{ detailRecord.type === 'income' ? '+' : '−' }}NT$ {{ fmtMoney(detailRecord.amount) }}
            </span>
          </div>

          <!-- 欄位列表 -->
          <div class="rounded-2xl bg-slate-50 divide-y divide-slate-100 overflow-hidden">
            <div v-if="detailRecord.account_category" class="flex items-center justify-between px-4 py-3">
              <span class="text-sm text-slate-500">科目分類</span>
              <span class="text-sm font-bold text-slate-800">{{ detailRecord.account_category }}</span>
            </div>
            <div v-if="detailRecord.payment_method" class="flex items-center justify-between px-4 py-3">
              <span class="text-sm text-slate-500">付款方式</span>
              <span class="text-sm font-bold text-slate-800">{{ detailRecord.payment_method }}</span>
            </div>
            <div v-if="detailRecord.vendor_name" class="flex items-center justify-between px-4 py-3">
              <span class="text-sm text-slate-500">廠商</span>
              <span class="text-sm font-bold text-slate-800">{{ detailRecord.vendor_name }}</span>
            </div>
            <div class="flex items-center justify-between px-4 py-3">
              <span class="text-sm text-slate-500">記錄時間</span>
              <span class="text-sm font-bold text-slate-800">{{ fmtFullDate(detailRecord.created_at) }}</span>
            </div>
            <div v-if="detailRecord.created_by_name" class="flex items-center justify-between px-4 py-3">
              <span class="text-sm text-slate-500">建立人</span>
              <span class="text-sm font-bold text-slate-800">{{ detailRecord.created_by_name }}</span>
            </div>
          </div>

          <!-- 備注 -->
          <div>
            <p class="text-xs font-bold text-slate-500 uppercase mb-2">備注</p>
            <div v-if="detailRecord.note"
              class="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-800 border border-slate-100">
              {{ detailRecord.note }}
            </div>
            <p v-else class="text-sm text-slate-400">無備注</p>
          </div>

          <!-- 附件照片 -->
          <div>
            <p class="text-xs font-bold text-slate-500 uppercase mb-2">附件照片</p>
            <div v-if="detailRecord.attachments?.length" class="flex gap-2 flex-wrap">
              <button v-for="(att, aidx) in detailRecord.attachments" :key="att.id"
                @click="openLightbox(detailRecord.attachments.map(a=>a.file_url), aidx)"
                class="w-16 h-16 rounded-xl overflow-hidden border border-slate-200 flex-shrink-0">
                <img :src="att.file_url" class="w-full h-full object-cover" />
              </button>
            </div>
            <p v-else class="text-sm text-slate-400">無附件</p>
          </div>

          <button @click="showDetailSheet = false"
            class="w-full py-3 rounded-2xl border border-slate-200 text-slate-600 font-bold text-sm">
            關閉
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="settleToast"
      class="fixed top-16 left-1/2 -translate-x-1/2 z-50 px-5 py-3 rounded-2xl shadow-lg font-bold text-white text-sm transition-all"
      style="background:#16a34a">
      ✓ 日結成功
    </div>

  </div>
</template>
