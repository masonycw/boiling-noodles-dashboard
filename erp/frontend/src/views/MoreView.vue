<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

// Sub-page: null | 'waste' | 'staff' | 'change-password' | 'notifications'
const subPage = ref(null)

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const isManager = (role) => role === 'admin' || role === 'manager' || role === 'store_manager'

// ──────────────────────────────────────────
// 損耗紀錄
// ──────────────────────────────────────────
const wasteRecords = ref([])
const loadingWaste = ref(false)

async function loadWaste() {
  subPage.value = 'waste'
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

// ──────────────────────────────────────────
// 人員管理
// ──────────────────────────────────────────
const staffList = ref([])
const loadingStaff = ref(false)
const showStaffModal = ref(false)
const staffEditTarget = ref(null)
const staffForm = ref({ username: '', full_name: '', role: 'staff', password: '', petty_cash_permission: false, is_active: true })
const staffError = ref('')
const staffSaving = ref(false)

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
    const url = staffEditTarget.value ? `${API_BASE}/users/${staffEditTarget.value.id}` : `${API_BASE}/users`
    const res = await fetch(url, {
      method: staffEditTarget.value ? 'PUT' : 'POST',
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

// ──────────────────────────────────────────
// 修改密碼
// ──────────────────────────────────────────
const oldPw = ref(''); const newPw = ref(''); const newPw2 = ref('')
const pwError = ref(''); const pwSuccess = ref(false); const pwSubmitting = ref(false)

async function changePassword() {
  pwError.value = ''
  if (newPw.value !== newPw2.value) { pwError.value = '兩次密碼不一致'; return }
  if (newPw.value.length < 6) { pwError.value = '密碼至少 6 個字元'; return }
  pwSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/users/${auth.user.id}/password`, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: oldPw.value, new_password: newPw.value })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '修改失敗') }
    pwSuccess.value = true
    oldPw.value = ''; newPw.value = ''; newPw2.value = ''
  } catch (e) {
    pwError.value = e.message
  } finally {
    pwSubmitting.value = false
  }
}

// ──────────────────────────────────────────
// 登出
// ──────────────────────────────────────────
function logout() {
  if (!confirm('確定要登出嗎？')) return
  auth.logout()
  router.push({ name: 'login' })
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''
}

const userName = () => auth.user?.full_name || auth.user?.username || '使用者'
const userInitial = () => (auth.user?.full_name || auth.user?.username || '?')[0]
const userRole = () => {
  const r = auth.user?.role
  if (r === 'admin') return '管理員'
  if (r === 'manager' || r === 'store_manager') return '店長'
  return '員工'
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-8">

    <!-- ══════════════ 損耗紀錄 sub-page ══════════════ -->
    <div v-if="subPage === 'waste'">
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
      <div v-else-if="wasteRecords.length === 0" class="text-center py-16 text-slate-400">近 30 天無損耗紀錄</div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="r in wasteRecords" :key="r.id" class="bg-white px-4 py-3">
          <div class="flex items-start justify-between">
            <div>
              <p class="font-bold text-slate-800 text-sm">{{ r.item_name || r.adhoc_name }}</p>
              <p class="text-xs text-slate-400 mt-0.5">{{ r.reason }} · {{ r.qty }} {{ r.unit }}</p>
              <p v-if="r.note" class="text-xs text-slate-400">{{ r.note }}</p>
            </div>
            <span class="text-xs text-slate-400 shrink-0 ml-3">{{ fmtDate(r.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════ 人員管理 sub-page ══════════════ -->
    <div v-else-if="subPage === 'staff'">
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button @click="subPage = null" class="text-orange-500 font-bold">← 返回</button>
          <h1 class="text-lg font-extrabold text-slate-800">人員管理</h1>
        </div>
        <button @click="openCreateStaff" class="bg-orange-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg">+ 新增</button>
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
              <span :class="u.role === 'admin' ? 'text-orange-500' : 'text-slate-400'">{{ u.role === 'admin' ? '管理員' : '員工' }}</span>
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
              <input v-model="staffForm.petty_cash_permission" type="checkbox" id="pcp_m" class="w-4 h-4 accent-orange-500" />
              <label for="pcp_m" class="text-slate-700 text-sm">零用金提領授權</label>
            </div>
            <div class="flex items-center gap-3">
              <input v-model="staffForm.is_active" type="checkbox" id="ia_m" class="w-4 h-4 accent-orange-500" />
              <label for="ia_m" class="text-slate-700 text-sm">啟用帳號</label>
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

    <!-- ══════════════ 修改密碼 sub-page ══════════════ -->
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
            <input v-model="oldPw" type="password" placeholder="••••••"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-2">新密碼</label>
            <input v-model="newPw" type="password" placeholder="至少 6 個字元"
              class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
          </div>
          <div>
            <label class="block text-sm font-bold text-slate-600 mb-2">確認新密碼</label>
            <input v-model="newPw2" type="password" placeholder="再輸入一次"
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

    <!-- ══════════════ 推播通知設定 sub-page ══════════════ -->
    <div v-else-if="subPage === 'notifications'">
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 flex items-center gap-3">
        <button @click="subPage = null" class="text-orange-500 font-bold">← 返回</button>
        <h1 class="text-lg font-extrabold text-slate-800">推播通知設定</h1>
      </div>
      <div class="px-4 py-8 text-center text-slate-400">
        <p class="text-4xl mb-3">🔔</p>
        <p class="text-sm">通知設定功能開發中</p>
      </div>
    </div>

    <!-- ══════════════ 主頁面 ══════════════ -->
    <div v-else>
      <!-- App Header -->
      <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4">
        <h1 class="text-xl font-extrabold text-slate-800">更多功能</h1>
      </div>

      <div class="px-4 py-4 space-y-5">

        <!-- 個人資料卡 -->
        <div class="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3"
          style="border-radius:var(--radius,8px)">
          <div class="w-10 h-10 rounded-full flex items-center justify-center font-extrabold text-lg shrink-0"
            style="background:#fff8f0;color:#e85d04">
            {{ userInitial() }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="font-bold text-slate-800" style="font-size:14px">{{ userName() }}</p>
            <p class="text-slate-400" style="font-size:11px">
              {{ userRole() }}
              <span v-if="auth.user?.petty_cash_permission" class="ml-1 text-emerald-500">· 有提領授權</span>
            </p>
          </div>
        </div>

        <!-- ─── 每日操作 ─── -->
        <div>
          <p class="font-bold text-slate-400 uppercase mb-2" style="font-size:11px">每日操作</p>
          <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <button @click="router.push('/waste')"
              class="w-full flex items-center gap-3 px-4 py-3.5 active:bg-slate-50 transition-colors"
              style="min-height:44px">
              <span style="font-size:16px;flex-shrink:0">🗑</span>
              <span class="font-semibold text-slate-700 flex-1 text-left" style="font-size:13px">損耗紀錄</span>
              <span class="text-slate-300" style="font-size:16px">›</span>
            </button>
          </div>
        </div>

        <!-- ─── 管理（店長限定）─── -->
        <div v-if="isManager(auth.user?.role)">
          <p class="font-bold text-slate-400 uppercase mb-2" style="font-size:11px">管理（店長限定）</p>
          <div class="bg-white rounded-xl shadow-sm overflow-hidden">
            <button @click="loadStaff"
              class="w-full flex items-center gap-3 px-4 py-3.5 active:bg-slate-50 transition-colors"
              style="min-height:44px">
              <span style="font-size:16px;flex-shrink:0">👥</span>
              <span class="font-semibold text-slate-700 flex-1 text-left" style="font-size:13px">人員管理</span>
              <span class="font-bold text-white text-[10px] px-2 py-0.5 rounded-full mr-1"
                style="background:#e85d04">店長</span>
              <span class="text-slate-300" style="font-size:16px">›</span>
            </button>
          </div>
        </div>

        <!-- ─── 個人設定 ─── -->
        <div>
          <p class="font-bold text-slate-400 uppercase mb-2" style="font-size:11px">個人設定</p>
          <div class="bg-white rounded-xl shadow-sm overflow-hidden divide-y divide-slate-100">
            <button @click="subPage = 'change-password'; pwSuccess = false"
              class="w-full flex items-center gap-3 px-4 py-3.5 active:bg-slate-50 transition-colors"
              style="min-height:44px">
              <span style="font-size:16px;flex-shrink:0">🔑</span>
              <span class="font-semibold text-slate-700 flex-1 text-left" style="font-size:13px">修改密碼</span>
              <span class="text-slate-300" style="font-size:16px">›</span>
            </button>
            <button @click="subPage = 'notifications'"
              class="w-full flex items-center gap-3 px-4 py-3.5 active:bg-slate-50 transition-colors"
              style="min-height:44px">
              <span style="font-size:16px;flex-shrink:0">🔔</span>
              <span class="font-semibold text-slate-700 flex-1 text-left" style="font-size:13px">推播通知設定</span>
              <span class="text-slate-300" style="font-size:16px">›</span>
            </button>
            <button @click="logout"
              class="w-full flex items-center gap-3 px-4 py-3.5 active:bg-slate-50 transition-colors"
              style="min-height:44px">
              <span style="font-size:16px;flex-shrink:0">🚪</span>
              <span class="font-semibold flex-1 text-left" style="font-size:13px;color:#ef4444">登出</span>
              <span class="text-slate-300" style="font-size:16px">›</span>
            </button>
          </div>
        </div>

        <p class="text-center text-slate-300 text-xs pt-2">滾麵 ERP v3.0.0</p>
      </div>
    </div>

  </div>
</template>
