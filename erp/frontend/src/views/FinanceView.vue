<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---- State ----
const isLoading = ref(false)
const pettyBalance = ref(0)
const todayIncome = ref(0)
const todayExpense = ref(0)
const todayRecords = ref([])
const yesterdayRecords = ref([])
const lastSettlement = ref(null)
const vendors = ref([])

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

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

// ---- Load data ----
async function loadAll() {
  isLoading.value = true
  try {
    const today = new Date().toISOString().slice(0, 10)
    const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)

    const [balRes, todayRes, yestRes, vendRes] = await Promise.all([
      fetch(`${API_BASE}/finance/petty-cash/balance`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/petty-cash?date=${today}&limit=100`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/finance/petty-cash?date=${yesterday}&limit=100`, { headers: { Authorization: `Bearer ${auth.token}` } }),
      fetch(`${API_BASE}/inventory/vendors`, { headers: { Authorization: `Bearer ${auth.token}` } }),
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
    showSheet.value = false
    sheetForm.value = { amount: '', description: '', date: new Date().toISOString().slice(0, 10), vendor_id: '', is_paid: true, income_source: '', withdrawal_purpose: 'bank' }
    await loadAll()
  } catch (e) {
    sheetError.value = e.message
  } finally {
    sheetSubmitting.value = false
  }
}

// ---- Helpers ----
function fmtDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-TW', { hour: '2-digit', minute: '2-digit' })
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
            style="background:#fff8f0;border:1.5px solid #e85d04">
            <p class="font-bold" style="font-size:9px;color:#e85d04">今日帳目</p>
            <button @click="alert('日結功能待開放')"
              class="mt-1 text-white font-extrabold rounded-md px-2 py-0.5"
              style="font-size:11px;background:#e85d04">
              🔒 日結
            </button>
          </div>
        </div>
      </div>

      <!-- 今日流水 -->
      <div class="px-4 mt-5">
        <p class="font-bold text-slate-600 mb-2" style="font-size:12px">
          今日流水 — {{ new Date().toLocaleDateString('zh-TW', { month:'numeric', day:'numeric' }) }}
        </p>
        <div v-if="todayRecords.length === 0" class="text-center py-6 text-slate-400 text-sm bg-white rounded-xl">
          今日尚無紀錄
        </div>
        <div v-else class="space-y-2">
          <div v-for="r in todayRecords" :key="r.id"
            class="bg-white rounded-xl px-4 py-3 flex items-center gap-3 shadow-sm">
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
            class="rounded-xl px-4 py-3 flex items-center gap-3 shadow-sm"
            :class="r.type === 'withdrawal' ? '' : 'bg-white'"
            :style="r.type === 'withdrawal' ? 'background:#fff8f0;border:1px solid #fed7aa' : ''">
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

          <div v-if="sheetError" class="text-red-500 text-sm text-center">{{ sheetError }}</div>

          <button @click="submitSheet" :disabled="sheetSubmitting"
            class="w-full text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40"
            style="background:#e85d04">
            {{ sheetSubmitting ? '送出中…' : '送出紀錄' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>
