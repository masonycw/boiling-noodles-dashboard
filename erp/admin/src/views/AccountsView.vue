<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const activeTab = ref('accounts') // accounts | permissions

// ── 帳號列表 ──
const users = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const showPwModal = ref(false)
const pwForm = ref({ new_password: '', confirm: '' })
const pwError = ref('')
const pwSaving = ref(false)
const pwUserId = ref(null)
const toast = ref('')

// ── E5: Delete User Dialog ──
const showDeleteUserModal = ref(false)
const deleteUserRecord = ref(null)
const deleteUserSubmitting = ref(false)

const form = ref({
  username: '', password: '', full_name: '',
  role: 'staff', petty_cash_permission: false, is_active: true,
  new_password: '', confirm_password: ''
})

// ── C1: 動態權限矩陣 ──
const PERMISSION_SECTIONS = [
  {
    key: 'app_order', label: '📱 App 前台 — 叫貨', collapsed: ref(false),
    items: [
      { key: 'app_create_order', label: '建立叫貨單', staffDefault: true },
      { key: 'app_view_order_history', label: '查看叫貨/收貨紀錄', staffDefault: true },
      { key: 'app_delete_pending_order', label: '刪除未收貨叫貨單', staffDefault: false },
    ]
  },
  {
    key: 'app_stocktake', label: '📱 App 前台 — 盤點', collapsed: ref(false),
    items: [
      { key: 'app_execute_stocktake', label: '執行盤點（當日）', staffDefault: true },
      { key: 'app_view_stocktake_history', label: '查看盤點歷史', staffDefault: true },
    ]
  },
  {
    key: 'app_finance', label: '📱 App 前台 — 金流', collapsed: ref(false),
    items: [
      { key: 'app_create_transaction', label: '新增收支紀錄', staffDefault: true },
      { key: 'app_execute_settlement', label: '執行日結', staffDefault: false },
      { key: 'app_view_transactions', label: '查看金流紀錄', staffDefault: true },
    ]
  },
  {
    key: 'app_waste', label: '📱 App 前台 — 耗損', collapsed: ref(false),
    items: [
      { key: 'app_create_waste', label: '新增耗損紀錄', staffDefault: true },
      { key: 'app_view_waste', label: '查看耗損紀錄', staffDefault: true },
    ]
  },
  {
    key: 'admin_order', label: '🖥️ 後台 — 叫貨與收貨紀錄', collapsed: ref(false),
    items: [
      { key: 'admin_order_view', label: '查看叫貨/收貨紀錄（後台）', staffLocked: true },
      { key: 'admin_order_edit', label: '編輯叫貨/收貨紀錄', staffLocked: true },
      { key: 'admin_order_delete', label: '刪除叫貨/收貨紀錄', staffLocked: true },
    ]
  },
  {
    key: 'admin_stocktake', label: '🖥️ 後台 — 盤點紀錄', collapsed: ref(false),
    items: [
      { key: 'admin_stocktake_view', label: '查看盤點紀錄（後台）', staffLocked: true },
      { key: 'admin_stocktake_edit', label: '編輯盤點紀錄', staffLocked: true },
      { key: 'admin_stocktake_delete', label: '刪除盤點紀錄', staffLocked: true },
    ]
  },
  {
    key: 'admin_petty_cash', label: '🖥️ 後台 — 零用金管理', collapsed: ref(false),
    items: [
      { key: 'admin_petty_cash_view', label: '查看零用金紀錄（後台）', staffLocked: true },
      { key: 'admin_petty_cash_create', label: '新增零用金紀錄（後台）', staffLocked: true },
      { key: 'admin_petty_cash_edit', label: '編輯零用金紀錄', staffLocked: true, managerDefault: false, sensitive: true },
      { key: 'admin_petty_cash_delete', label: '刪除零用金紀錄', staffLocked: true, managerDefault: false, sensitive: true },
    ]
  },
  {
    key: 'admin_transaction', label: '🖥️ 後台 — 金流紀錄', collapsed: ref(false),
    items: [
      { key: 'admin_transaction_view', label: '查看金流紀錄（後台）', staffLocked: true },
      { key: 'admin_transaction_edit', label: '編輯金流紀錄', staffLocked: true, managerDefault: false, sensitive: true },
      { key: 'admin_transaction_delete', label: '刪除金流紀錄', staffLocked: true, managerDefault: false, sensitive: true },
      { key: 'admin_settlement_delete', label: '刪除日結記錄', staffLocked: true, managerDefault: false, sensitive: true },
    ]
  },
  {
    key: 'admin_waste', label: '🖥️ 後台 — 損耗紀錄', collapsed: ref(false),
    items: [
      { key: 'admin_waste_view', label: '查看損耗紀錄（後台）', staffLocked: true },
      { key: 'admin_waste_edit', label: '編輯損耗紀錄', staffLocked: true },
      { key: 'admin_waste_delete', label: '刪除損耗紀錄', staffLocked: true },
    ]
  },
  {
    key: 'admin_mgmt', label: '🖥️ 後台 — 供應商/品項/報表/管理', collapsed: ref(false),
    items: [
      { key: 'admin_vendor_manage', label: '供應商管理', staffLocked: true },
      { key: 'admin_item_manage', label: '品項管理', staffLocked: true },
      { key: 'admin_finance_report', label: '查看損益表/月度分析', staffLocked: true },
      { key: 'admin_manage_users', label: '人員管理', staffLocked: true, managerDefault: false },
      { key: 'admin_system_settings', label: '系統設置', staffLocked: true, managerDefault: false },
    ]
  },
]

const matrixManager = ref({})  // key → boolean
const matrixStaff = ref({})
const matrixLoading = ref(false)
const matrixSaving = ref(false)

const MANAGER_DEFAULTS = {}
const STAFF_DEFAULTS = {}
PERMISSION_SECTIONS.forEach(s => {
  s.items.forEach(item => {
    MANAGER_DEFAULTS[item.key] = item.managerDefault !== false
    STAFF_DEFAULTS[item.key] = item.staffLocked ? false : (item.staffDefault !== false)
  })
})

async function loadMatrix() {
  matrixLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/permissions/matrix`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      matrixManager.value = { ...MANAGER_DEFAULTS, ...(data.manager || {}) }
      matrixStaff.value = { ...STAFF_DEFAULTS, ...(data.staff || {}) }
    } else {
      resetMatrix()
    }
  } catch {
    resetMatrix()
  } finally {
    matrixLoading.value = false
  }
}

function resetMatrix() {
  matrixManager.value = { ...MANAGER_DEFAULTS }
  matrixStaff.value = { ...STAFF_DEFAULTS }
}

async function saveMatrix() {
  matrixSaving.value = true
  try {
    const res = await fetch(`${API_BASE}/permissions/matrix`, {
      method: 'PUT', headers: authHeaders(),
      body: JSON.stringify({ manager: matrixManager.value, staff: matrixStaff.value })
    })
    if (!res.ok) throw new Error('儲存失敗')
    showToast('✓ 權限設定已儲存')
  } catch (e) {
    showToast('⚠ ' + e.message)
  } finally {
    matrixSaving.value = false
  }
}

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }
function roleName(role) {
  return { admin: '管理員', manager: '店長', staff: '員工' }[role] || role
}
function roleClass(role) {
  return { admin: 'bg-blue-900/50 text-blue-400', manager: 'bg-purple-900/50 text-purple-400', staff: 'bg-amber-900/30 text-amber-400' }[role] || 'bg-gray-700 text-gray-400'
}
function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/users/`, { headers: authHeaders() })
  if (res.ok) users.value = await res.json()
  loading.value = false
}

onMounted(() => { load(); loadMatrix() })

function onTabChange(tab) {
  activeTab.value = tab
}

function openCreate() {
  editTarget.value = null
  form.value = { username: '', password: '', full_name: '', role: 'staff', petty_cash_permission: false, is_active: true, new_password: '', confirm_password: '' }
  saveError.value = ''
  showModal.value = true
}
function openEdit(u) {
  editTarget.value = u
  form.value = { ...u, password: '', new_password: '', confirm_password: '' }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!editTarget.value && !form.value.username.trim()) { saveError.value = '請填入帳號'; return }
  if (!form.value.full_name.trim()) { saveError.value = '請填入姓名'; return }
  saving.value = true; saveError.value = ''
  try {
    if (editTarget.value) {
      const updateData = {
        full_name: form.value.full_name,
        username: form.value.username,
        role: form.value.role,
        is_active: form.value.is_active,
        petty_cash_permission: form.value.petty_cash_permission,
      }
      if (form.value.new_password) {
        if (form.value.new_password !== form.value.confirm_password) {
          saveError.value = '兩次密碼不一致'; saving.value = false; return
        }
        if (form.value.new_password.length < 6) {
          saveError.value = '密碼至少 6 個字元'; saving.value = false; return
        }
        updateData.password = form.value.new_password
      }
      const res = await fetch(`${API_BASE}/users/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(), body: JSON.stringify(updateData)
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '更新失敗') }
    } else {
      if (!form.value.password) { saveError.value = '請填入初始密碼'; saving.value = false; return }
      const res = await fetch(`${API_BASE}/users/`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({
          username: form.value.username,
          password: form.value.password,
          full_name: form.value.full_name,
          role: form.value.role,
          petty_cash_permission: form.value.petty_cash_permission,
        })
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '建立失敗') }
    }
    showModal.value = false; showToast('✓ 帳號已儲存'); await load()
  } catch (e) { saveError.value = e.message } finally { saving.value = false }
}

function openDeleteUser(u) {
  if (u.id === auth.user?.id) { showToast('⚠ 不可刪除自己的帳號'); return }
  deleteUserRecord.value = u
  deleteUserSubmitting.value = false
  showDeleteUserModal.value = true
}

async function confirmDeleteUser() {
  deleteUserSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/users/${deleteUserRecord.value.id}`, {
      method: 'DELETE', headers: authHeaders()
    })
    if (!res.ok) {
      const d = await res.json()
      throw new Error(d.detail || '刪除失敗')
    }
    showDeleteUserModal.value = false
    showToast('帳號已刪除')
    await load()
  } catch (e) {
    showToast('⚠ ' + e.message)
    showDeleteUserModal.value = false
  } finally {
    deleteUserSubmitting.value = false
  }
}

function openChangePw(u) {
  pwUserId.value = u.id; pwForm.value = { new_password: '', confirm: '' }; pwError.value = ''; showPwModal.value = true
}
async function savePw() {
  if (pwForm.value.new_password.length < 6) { pwError.value = '密碼至少 6 個字元'; return }
  if (pwForm.value.new_password !== pwForm.value.confirm) { pwError.value = '兩次密碼不一致'; return }
  pwSaving.value = true; pwError.value = ''
  try {
    const res = await fetch(`${API_BASE}/users/${pwUserId.value}/password`, {
      method: 'PUT', headers: authHeaders(),
      body: JSON.stringify({ current_password: '_admin_reset_', new_password: pwForm.value.new_password })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '修改失敗') }
    showPwModal.value = false; showToast('✓ 密碼已重設')
  } catch (e) { pwError.value = e.message } finally { pwSaving.value = false }
}
</script>

<template>
  <div class="space-y-5">
    <!-- Toast -->
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <!-- Tab bar -->
    <div class="flex border-b border-[#2d3748]">
      <button v-for="t in [{ key: 'accounts', label: '帳號列表' }, { key: 'permissions', label: '權限設置' }]" :key="t.key"
        @click="activeTab = t.key"
        class="px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === t.key ? 'text-blue-400 border-blue-400' : 'text-gray-500 border-transparent hover:text-gray-300'">
        {{ t.label }}
      </button>
    </div>

    <!-- ── 帳號列表 Tab ── -->
    <template v-if="activeTab === 'accounts'">
      <div class="flex items-center justify-end">
        <button @click="openCreate"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          + 新增帳號
        </button>
      </div>

      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
        <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
              <th class="px-5 py-3 text-left">姓名</th>
              <th class="px-5 py-3 text-left">帳號</th>
              <th class="px-5 py-3 text-center">角色</th>
              <th class="px-5 py-3 text-center">零用金授權</th>
              <th class="px-5 py-3 text-center">狀態</th>
              <th class="px-5 py-3 text-left">最後登入</th>
              <th class="px-5 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="u in users" :key="u.id" class="hover:bg-[#1f2937] transition-colors">
              <td class="px-5 py-3 font-semibold text-gray-200">{{ u.full_name || '—' }}</td>
              <td class="px-5 py-3 font-mono text-gray-300">{{ u.username }}</td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold px-2 py-1 rounded-full" :class="roleClass(u.role)">{{ roleName(u.role) }}</span>
              </td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold" :class="u.petty_cash_permission ? 'text-emerald-400' : 'text-gray-600'">
                  {{ u.petty_cash_permission ? '✓ 授權' : '—' }}
                </span>
              </td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                  :class="u.is_active ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'">
                  {{ u.is_active ? '啟用' : '停用' }}
                </span>
              </td>
              <td class="px-5 py-3 text-gray-500 text-xs">{{ fmtDate(u.last_login) }}</td>
              <td class="px-5 py-3 text-center">
                <div class="flex items-center justify-center gap-2">
                  <button @click="openEdit(u)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
                  <button @click="openChangePw(u)" class="text-amber-400 hover:text-amber-300 text-xs font-bold">改密碼</button>
                  <button v-if="u.id !== auth.user?.id" @click="openDeleteUser(u)"
                    class="text-red-400 hover:text-red-300 text-xs font-bold">刪除</button>
                </div>
              </td>
            </tr>
            <tr v-if="users.length === 0">
              <td colspan="7" class="px-5 py-10 text-center text-gray-600">無人員資料</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- ── C1 動態權限矩陣 Tab ── -->
    <template v-if="activeTab === 'permissions'">
      <div class="space-y-4">
        <!-- 說明 + 操作按鈕 -->
        <div class="flex items-center justify-between">
          <div class="text-xs text-gray-500 space-y-0.5">
            <p><span class="text-emerald-400">✅ Admin</span> 固定全開不可修改 ·
               <span class="text-blue-400">☑</span> 可自定義 ·
               <span class="text-gray-600">✗</span> 此角色無此功能 ·
               <span class="text-amber-400">⚠</span> 預設關閉敏感操作</p>
          </div>
          <div class="flex gap-2">
            <button @click="resetMatrix"
              class="px-3 py-1.5 text-xs font-bold border border-[#2d3748] text-gray-400 hover:text-gray-200 rounded-lg transition-colors">
              重設預設值
            </button>
            <button @click="saveMatrix" :disabled="matrixSaving"
              class="px-4 py-1.5 text-xs font-bold bg-blue-500 hover:bg-blue-400 text-white rounded-lg transition-colors disabled:opacity-50">
              {{ matrixSaving ? '儲存中…' : '儲存設定' }}
            </button>
          </div>
        </div>

        <div v-if="matrixLoading" class="text-center py-8 text-gray-500">載入中…</div>
        <div v-else class="space-y-3">
          <div v-for="section in PERMISSION_SECTIONS" :key="section.key"
            class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
            <!-- Section header (collapsible) -->
            <button @click="section.collapsed.value = !section.collapsed.value"
              class="w-full px-5 py-3 bg-[#111827] border-b border-[#2d3748] flex items-center justify-between hover:bg-[#1a2436] transition-colors">
              <p class="text-xs font-bold text-gray-300">{{ section.label }}</p>
              <span class="text-gray-500 text-xs">{{ section.collapsed.value ? '▶' : '▼' }}</span>
            </button>

            <table v-if="!section.collapsed.value" class="w-full text-sm">
              <thead>
                <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
                  <th class="px-5 py-2 text-left">功能項目</th>
                  <th class="px-5 py-2 text-center w-24">Admin</th>
                  <th class="px-5 py-2 text-center w-32">店長 (Manager)</th>
                  <th class="px-5 py-2 text-center w-32">員工 (Staff)</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#2d3748]">
                <tr v-for="item in section.items" :key="item.key" class="hover:bg-[#1f2937]">
                  <td class="px-5 py-2.5">
                    <span class="text-gray-300">{{ item.label }}</span>
                    <span v-if="item.sensitive" class="ml-1.5 text-[10px] bg-amber-900/50 text-amber-400 px-1.5 py-0.5 rounded font-bold">預設關閉</span>
                  </td>
                  <!-- Admin: always on -->
                  <td class="px-5 py-2.5 text-center">
                    <span class="font-bold text-emerald-400 text-base">✅</span>
                  </td>
                  <!-- Manager: editable -->
                  <td class="px-5 py-2.5 text-center">
                    <input type="checkbox" :checked="matrixManager[item.key]"
                      @change="matrixManager[item.key] = $event.target.checked"
                      class="w-4 h-4 accent-blue-500 cursor-pointer" />
                  </td>
                  <!-- Staff: locked if staffLocked, editable otherwise -->
                  <td class="px-5 py-2.5 text-center">
                    <span v-if="item.staffLocked" class="text-gray-600 font-bold">✗</span>
                    <input v-else type="checkbox" :checked="matrixStaff[item.key]"
                      @change="matrixStaff[item.key] = $event.target.checked"
                      class="w-4 h-4 accent-blue-500 cursor-pointer" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- 新增/編輯 Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯帳號' : '新增帳號' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div v-if="!editTarget">
            <label class="block text-gray-400 text-xs font-semibold mb-1">帳號 *</label>
            <input v-model="form.username" type="text" maxlength="20"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div v-else>
            <label class="block text-gray-400 text-xs font-semibold mb-1">帳號（唯讀）</label>
            <div class="bg-[#0f1117] border border-[#2d3748] text-gray-500 rounded-lg px-3 py-2 font-mono">{{ editTarget.username }}</div>
          </div>
          <div v-if="!editTarget">
            <label class="block text-gray-400 text-xs font-semibold mb-1">初始密碼 *</label>
            <input v-model="form.password" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">姓名 *</label>
            <input v-model="form.full_name" type="text" maxlength="30"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">角色 *</label>
            <select v-model="form.role"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400">
              <option value="staff">員工</option>
              <option value="manager">店長</option>
              <option value="admin">管理員</option>
            </select>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="form.petty_cash_permission" type="checkbox" id="pcp" class="w-4 h-4 accent-blue-500" />
            <label for="pcp" class="text-gray-300">授予零用金提領權限</label>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="form.is_active" type="checkbox" id="active" class="w-4 h-4 accent-blue-500" />
            <label for="active" class="text-gray-300">帳號啟用中</label>
          </div>
          <!-- 重設密碼（僅編輯模式） -->
          <template v-if="editTarget">
            <div class="border-t border-[#2d3748] pt-3 mt-1">
              <p class="text-xs text-gray-500 font-semibold mb-2">重設密碼（選填）</p>
              <div class="space-y-2">
                <div>
                  <label class="block text-gray-400 text-xs font-semibold mb-1">新密碼</label>
                  <input v-model="form.new_password" type="password" placeholder="留空則不更改"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
                </div>
                <div>
                  <label class="block text-gray-400 text-xs font-semibold mb-1">確認新密碼</label>
                  <input v-model="form.confirm_password" type="password"
                    class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
                </div>
              </div>
            </div>
          </template>
          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>
          <button @click="save" :disabled="saving"
            class="w-full bg-blue-500 hover:bg-blue-400 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : (editTarget ? '更新帳號' : '建立帳號') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 刪除帳號確認 Dialog -->
    <div v-if="showDeleteUserModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
        <h3 class="text-base font-bold text-gray-200 mb-4">⚠️ 確認刪除帳號</h3>
        <div class="bg-[#0f1117] rounded-xl p-4 mb-4 space-y-1 text-sm">
          <div class="flex justify-between">
            <span class="text-gray-500">帳號</span>
            <span class="text-gray-300 font-mono">{{ deleteUserRecord?.username }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">姓名</span>
            <span class="text-gray-300">{{ deleteUserRecord?.full_name || '—' }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">角色</span>
            <span class="text-gray-300">{{ roleName(deleteUserRecord?.role) }}</span>
          </div>
        </div>
        <p class="text-xs text-red-400 mb-4">刪除後帳號無法登入，操作紀錄仍保留。</p>
        <div class="flex gap-3">
          <button @click="showDeleteUserModal = false"
            class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
            取消
          </button>
          <button @click="confirmDeleteUser" :disabled="deleteUserSubmitting"
            class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-40">
            {{ deleteUserSubmitting ? '刪除中…' : '確認刪除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 改密碼 Modal -->
    <div v-if="showPwModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">重設密碼</h3>
          <button @click="showPwModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">新密碼</label>
            <input v-model="pwForm.new_password" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">確認密碼</label>
            <input v-model="pwForm.confirm" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div v-if="pwError" class="text-red-400 text-xs text-center">{{ pwError }}</div>
          <button @click="savePw" :disabled="pwSaving"
            class="w-full bg-amber-600 hover:bg-amber-500 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ pwSaving ? '儲存中…' : '確認重設' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
