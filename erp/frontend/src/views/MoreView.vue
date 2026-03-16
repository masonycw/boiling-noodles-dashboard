<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

// Sub-page: null | 'waste-history' | 'change-password' | 'staff'
const subPage = ref(null)

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// ---- Staff management ----
const staffList = ref([])
const loadingStaff = ref(false)
const showStaffModal = ref(false)
const staffForm = ref({ username: '', full_name: '', role: 'staff', password: '', petty_cash_permission: false, is_active: true })
const staffError = ref('')
const staffSaving = ref(false)
const staffEditTarget = ref(null)

async function loadStaff() {
  subPage.value = 'staff'
  loadingStaff.value = true
  try {
    const res = await fetch(`${API_BASE}/users`, {
      headers: { Authorization: `Bearer ${auth.token}` }
    })
    if (res.ok) staffList.value = await res.json()
  } finally {
    loadingStaff.value = false
  }
}

function openCreateStaff() {
  staffEditTarget.value = null
  staffForm.value = { username: '', full_name: '', role: 'staff', password: '', petty_cash_permission: false, is_active: true }
  staffError.value = ''
  showStaffModal.value = true
}

function openEditStaff(u) {
  staffEditTarget.value = u
  staffForm.value = { ...u, password: '' }
  staffError.value = ''
  showStaffModal.value = true
}

async function saveStaff() {
  if (!staffForm.value.username.trim()) { staffError.value = '請填入帳號'; return }
  staffSaving.value = true
  staffError.value = ''
  try {
    const payload = { ...staffForm.value }
    if (!payload.password) delete payload.password
    const url = staffEditTarget.value
      ? `${API_BASE}/users/${staffEditTarget.value.id}`
      : `${API_BASE}/users`
    const method = staffEditTarget.value ? 'PUT' : 'POST'
    const res = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showStaffModal.value = false
    await loadStaff()
  } catch (e) {
    staffError.value = e.message
  } finally {
    staffSaving.value = false
  }
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

// ---- Waste history ----
const wasteRecords = ref([])
const loadingWaste = ref(false)

async function loadWasteHistory() {
  subPage.value = 'waste-history'
  loadingWaste.value = true
  try {
    const res = await fetch(`${API_BASE}/waste/?days_limit=30&limit=100`, {
      headers: { Authorization: `Bearer ${auth.token}` }
    })
    if (res.ok) wasteRecords.value = await res.json()
  } finally {
    loadingWaste.value = false
  }
}

// ---- Password change ----
const oldPassword = ref('')
const newPassword = ref('')
const newPassword2 = ref('')
const pwError = ref('')
const pwSuccess = ref(false)
const pwSubmitting = ref(false)

async function changePassword() {
  pwError.value = ''
  if (newPassword.value !== newPassword2.value) {
    pwError.value = '兩次密碼不一致'
    return
  }
  if (newPassword.value.length < 6) {
    pwError.value = '密碼至少 6 個字元'
    return
  }
  pwSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/users/${auth.user.id}/password`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: oldPassword.value, new_password: newPassword.value })
    })
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '修改失敗')
    }
    pwSuccess.value = true
    oldPassword.value = ''
    newPassword.value = ''
    newPassword2.value = ''
  } catch (e) {
    pwError.value = e.message
  } finally {
    pwSubmitting.value = false
  }
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-8">

    <!-- Sub-page: waste history -->
    <div v-if="subPage === 'waste-history'">
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center gap-3">
        <button @click="subPage = null" class="text-orange-500 font-bold">← 返回</button>
        <h1 class="text-lg font-extrabold text-slate-800">損耗紀錄（30天）</h1>
      </div>
      <div v-if="loadingWaste" class="flex justify-center py-16">
        <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
      <div v-else-if="wasteRecords.length === 0" class="text-center py-16 text-slate-400">
        近 30 天無損耗紀錄
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="r in wasteRecords" :key="r.id" class="bg-white px-4 py-3">
          <div class="flex items-start justify-between">
            <div>
              <p class="font-bold text-slate-800 text-sm">{{ r.item_name || r.adhoc_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">
                {{ r.reason }} · {{ r.qty }} {{ r.unit }}
              </p>
              <p v-if="r.note" class="text-xs text-slate-400">{{ r.note }}</p>
            </div>
            <span class="text-xs text-slate-400 shrink-0 ml-3">{{ fmtDate(r.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Sub-page: staff management -->
    <div v-else-if="subPage === 'staff'">
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button @click="subPage = null" class="text-orange-500 font-bold">← 返回</button>
          <h1 class="text-lg font-extrabold text-slate-800">人員管理</h1>
        </div>
        <button @click="openCreateStaff"
          class="bg-orange-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg">+ 新增</button>
      </div>
      <div v-if="loadingStaff" class="flex justify-center py-16">
        <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="u in staffList" :key="u.id" class="bg-white px-4 py-3 flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-lg font-extrabold text-orange-500 shrink-0">
            {{ (u.full_name || u.username || '?')[0] }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="font-bold text-slate-800 text-sm">{{ u.full_name || u.username }}</p>
            <p class="text-xs text-slate-400">
              @{{ u.username }} ·
              <span :class="u.role === 'admin' ? 'text-orange-500' : 'text-slate-400'">
                {{ u.role === 'admin' ? '管理員' : '員工' }}
              </span>
              <span v-if="!u.is_active" class="ml-1 text-rose-400">（停用）</span>
              <span v-if="u.petty_cash_permission" class="ml-1 text-emerald-500">· 零用金授權</span>
            </p>
          </div>
          <button @click="openEditStaff(u)" class="text-blue-400 text-xs font-bold shrink-0">編輯</button>
        </div>
        <div v-if="staffList.length === 0" class="text-center py-16 text-slate-400">無人員資料</div>
      </div>

      <!-- Staff modal -->
      <div v-if="showStaffModal" class="fixed inset-0 bg-black/60 z-50 flex items-end justify-center">
        <div class="bg-white rounded-t-3xl w-full max-w-lg p-6 max-h-[85vh] overflow-y-auto">
          <div class="flex justify-between items-center mb-5">
            <h3 class="text-lg font-extrabold text-slate-800">{{ staffEditTarget ? '編輯人員' : '新增人員' }}</h3>
            <button @click="showStaffModal = false" class="text-slate-400 text-xl">✕</button>
          </div>
          <div class="space-y-4 text-sm">
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">帳號 *</label>
              <input v-model="staffForm.username" type="text" :disabled="!!staffEditTarget"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-400 disabled:bg-slate-50 disabled:text-slate-400" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">顯示名稱</label>
              <input v-model="staffForm.full_name" type="text"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">{{ staffEditTarget ? '新密碼（不填則不更改）' : '密碼 *' }}</label>
              <input v-model="staffForm.password" type="password" placeholder="至少 6 個字元"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-400" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 uppercase mb-1">角色</label>
              <select v-model="staffForm.role"
                class="w-full border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-orange-400">
                <option value="staff">員工</option>
                <option value="admin">管理員</option>
              </select>
            </div>
            <div class="flex items-center gap-3 pt-1">
              <input v-model="staffForm.petty_cash_permission" type="checkbox" id="pcp" class="w-4 h-4 accent-orange-500" />
              <label for="pcp" class="text-slate-700 text-sm">零用金提領授權</label>
            </div>
            <div class="flex items-center gap-3">
              <input v-model="staffForm.is_active" type="checkbox" id="is_active_staff" class="w-4 h-4 accent-orange-500" />
              <label for="is_active_staff" class="text-slate-700 text-sm">啟用帳號</label>
            </div>
            <div v-if="staffError" class="text-rose-500 text-sm text-center">{{ staffError }}</div>
            <button @click="saveStaff" :disabled="staffSaving"
              class="w-full bg-orange-500 text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40">
              {{ staffSaving ? '儲存中…' : '儲存' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sub-page: change password -->
    <div v-else-if="subPage === 'change-password'">
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center gap-3">
        <button @click="subPage = null; pwSuccess = false" class="text-orange-500 font-bold">← 返回</button>
        <h1 class="text-lg font-extrabold text-slate-800">修改密碼</h1>
      </div>
      <div class="px-4 py-6 space-y-4">
        <div v-if="pwSuccess" class="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-emerald-700 text-sm font-medium text-center">
          密碼已修改成功 ✅
        </div>
        <template v-if="!pwSuccess">
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-2">目前密碼</label>
            <input v-model="oldPassword" type="password" placeholder="••••••"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-2">新密碼</label>
            <input v-model="newPassword" type="password" placeholder="至少 6 個字元"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-2">確認新密碼</label>
            <input v-model="newPassword2" type="password" placeholder="再輸入一次"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>
          <div v-if="pwError" class="text-rose-500 text-sm text-center">{{ pwError }}</div>
          <button @click="changePassword" :disabled="pwSubmitting"
            class="w-full bg-orange-500 text-white font-bold py-4 rounded-2xl active:scale-95 transition-transform disabled:opacity-40">
            {{ pwSubmitting ? '儲存中…' : '儲存新密碼' }}
          </button>
        </template>
      </div>
    </div>

    <!-- Main More page -->
    <div v-else>
      <!-- Header -->
      <div class="bg-gradient-to-br from-slate-800 to-slate-900 text-white px-5 pt-12 pb-8">
        <h1 class="text-xl font-extrabold">更多功能</h1>
      </div>

      <!-- User card -->
      <div class="mx-4 -mt-5 bg-white rounded-2xl shadow-sm p-5 flex items-center gap-4">
        <div class="w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center text-2xl font-extrabold text-orange-500">
          {{ (auth.user?.full_name || auth.user?.username || '?')[0] }}
        </div>
        <div>
          <p class="font-extrabold text-slate-800">{{ auth.user?.full_name || auth.user?.username }}</p>
          <p class="text-xs text-slate-400">{{ auth.user?.role === 'admin' ? '管理員' : '員工' }}
            <span v-if="auth.user?.petty_cash_permission" class="ml-1 text-emerald-500">· 有提領授權</span>
          </p>
        </div>
      </div>

      <!-- Menu list -->
      <div class="mx-4 mt-5 bg-white rounded-2xl shadow-sm overflow-hidden divide-y divide-slate-100">
        <button @click="loadWasteHistory"
          class="w-full flex items-center gap-4 px-4 py-4 active:bg-slate-50 transition-colors">
          <span class="text-xl">🗑️</span>
          <span class="font-bold text-slate-700 text-sm flex-1 text-left">損耗紀錄（30天）</span>
          <svg class="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>

        <button @click="subPage = 'change-password'; pwSuccess = false"
          class="w-full flex items-center gap-4 px-4 py-4 active:bg-slate-50 transition-colors">
          <span class="text-xl">🔑</span>
          <span class="font-bold text-slate-700 text-sm flex-1 text-left">修改密碼</span>
          <svg class="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>

        <button v-if="auth.user?.role === 'admin'" @click="loadStaff"
          class="w-full flex items-center gap-4 px-4 py-4 active:bg-slate-50 transition-colors">
          <span class="text-xl">👥</span>
          <span class="font-bold text-slate-700 text-sm flex-1 text-left">人員管理</span>
          <span class="text-[10px] font-bold text-orange-500 bg-orange-50 px-2 py-0.5 rounded-full mr-1">管理員</span>
          <svg class="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      </div>

      <!-- Logout -->
      <div class="mx-4 mt-4">
        <button @click="logout"
          class="w-full bg-white border border-rose-200 text-rose-500 font-bold py-4 rounded-2xl active:scale-95 transition-transform">
          登出
        </button>
      </div>

      <p class="text-center text-xs text-slate-300 mt-8">滾麵 ERP v3.0.0</p>
    </div>
  </div>
</template>
