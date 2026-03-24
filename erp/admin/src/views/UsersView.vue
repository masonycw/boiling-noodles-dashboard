<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

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

const form = ref({
  username: '', password: '', full_name: '',
  role: 'staff', petty_cash_permission: false, is_active: true
})

const permissionMatrix = [
  { feature: '查看儀表板', manager: true, staff: true },
  { feature: '編輯供應商', manager: true, staff: false },
  { feature: '新增叫貨', manager: true, staff: false },
  { feature: '驗收貨物', manager: true, staff: true },
  { feature: '執行盤點', manager: true, staff: true },
  { feature: '零用金提領', manager: true, staff: null },
  { feature: '查看財務報表', manager: true, staff: false },
  { feature: '帳號管理', manager: true, staff: false },
]

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

function roleName(role) {
  if (role === 'admin') return '店長'
  if (role === 'manager') return '主管'
  if (role === 'cashier') return '櫃檯'
  return '員工'
}
function roleClass(role) {
  if (role === 'admin') return 'bg-blue-900/50 text-[#3b82f6]'
  if (role === 'manager') return 'bg-purple-900/50 text-[#a78bfa]'
  if (role === 'cashier') return 'bg-teal-900/50 text-[#2dd4bf]'
  return 'bg-amber-900/30 text-[#f59e0b]'
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/users/`, { headers: authHeaders() })
  if (res.ok) users.value = await res.json()
  loading.value = false
}

onMounted(load)

function openCreate() {
  editTarget.value = null
  form.value = { username: '', password: '', full_name: '', role: 'staff', petty_cash_permission: false, is_active: true }
  saveError.value = ''
  showModal.value = true
}

function openEdit(u) {
  editTarget.value = u
  form.value = { ...u, password: '' }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!editTarget.value && !form.value.username.trim()) { saveError.value = '請填入帳號'; return }
  saving.value = true
  saveError.value = ''
  try {
    if (editTarget.value) {
      const { username, password, ...updateData } = form.value
      const res = await fetch(`${API_BASE}/users/${editTarget.value.id}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify(updateData)
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '更新失敗') }
    } else {
      if (!form.value.password) { saveError.value = '請填入初始密碼'; saving.value = false; return }
      const res = await fetch(`${API_BASE}/users/`, {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify(form.value)
      })
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '建立失敗') }
    }
    showModal.value = false
    showToast('✓ 帳號已儲存')
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

function openChangePw(u) {
  pwUserId.value = u.id
  pwForm.value = { new_password: '', confirm: '' }
  pwError.value = ''
  showPwModal.value = true
}

async function savePw() {
  if (pwForm.value.new_password.length < 6) { pwError.value = '密碼至少 6 個字元'; return }
  if (pwForm.value.new_password !== pwForm.value.confirm) { pwError.value = '兩次密碼不一致'; return }
  pwSaving.value = true
  pwError.value = ''
  try {
    const res = await fetch(`${API_BASE}/users/${pwUserId.value}/password`, {
      method: 'PUT', headers: authHeaders(),
      body: JSON.stringify({ current_password: '_admin_reset_', new_password: pwForm.value.new_password })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '修改失敗') }
    showPwModal.value = false
    showToast('✓ 密碼已重設')
  } catch (e) {
    pwError.value = e.message
  } finally {
    pwSaving.value = false
  }
}

function fmtDate(d) { return d ? new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—' }
</script>

<template>
  <div class="space-y-6">
    <!-- Toast -->
    <div v-if="toast"
      class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">
      {{ toast }}
    </div>

    <!-- Toolbar -->
    <div class="flex items-center">
      <button @click="openCreate"
        class="ml-auto bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增帳號
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-5 py-3 text-left">姓名</th>
            <th class="px-5 py-3 text-left">帳號</th>
            <th class="px-5 py-3 text-center">角色</th>
            <th class="px-5 py-3 text-center">零用金提領授權</th>
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
              <span class="text-xs font-bold px-2 py-1 rounded-full" :class="roleClass(u.role)">
                {{ roleName(u.role) }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold" :class="u.petty_cash_permission ? 'text-[#10b981]' : 'text-gray-600'">
                {{ u.petty_cash_permission ? '✓ 授權' : '— 無權限' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="u.is_active ? 'bg-emerald-900/50 text-[#10b981]' : 'bg-red-900/50 text-[#ef4444]'">
                {{ u.is_active ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-3 text-gray-500 text-xs">{{ fmtDate(u.last_login) }}</td>
            <td class="px-5 py-3 text-center flex items-center justify-center gap-3">
              <button @click="openEdit(u)" class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
              <button @click="openChangePw(u)" class="text-amber-400 hover:text-amber-300 text-xs font-bold">改密碼</button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="7" class="px-5 py-10 text-center text-gray-600">無人員資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Permission Matrix -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-3 border-b border-[#2d3748]">
        <h3 class="text-sm font-bold text-gray-200">權限矩陣</h3>
      </div>
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-[#111827] border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
            <th class="px-5 py-3 text-left">功能</th>
            <th class="px-5 py-3 text-center">店長</th>
            <th class="px-5 py-3 text-center">員工</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="row in permissionMatrix" :key="row.feature" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-300 pl-8">{{ row.feature }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="font-bold text-[#10b981]">✓</span>
            </td>
            <td class="px-5 py-2.5 text-center">
              <span v-if="row.staff === true" class="font-bold text-[#10b981]">✓</span>
              <span v-else-if="row.staff === false" class="font-bold text-[#6b7280]">—</span>
              <span v-else class="text-xs text-[#f59e0b]">依帳號設定</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯人員' : '新增帳號' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="space-y-3 text-sm">
          <div v-if="!editTarget">
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">帳號 <span class="text-red-400">*</span></label>
            <input v-model="form.username" type="text" maxlength="20"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div v-if="editTarget">
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">帳號（唯讀）</label>
            <div class="bg-[#0f1117] border border-[#2d3748] text-gray-500 rounded-lg px-3 py-2 font-mono">{{ editTarget.username }}</div>
          </div>
          <div v-if="!editTarget">
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">初始密碼 <span class="text-red-400">*</span></label>
            <input v-model="form.password" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">姓名 <span class="text-red-400">*</span></label>
            <input v-model="form.full_name" type="text" maxlength="30"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">角色 <span class="text-red-400">*</span></label>
            <select v-model="form.role"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
              <option value="cashier">櫃檯（僅金流）</option>
              <option value="staff">員工</option>
              <option value="manager">主管</option>
              <option value="admin">店長（管理員）</option>
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

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <button @click="save" :disabled="saving"
            class="w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '建立帳號' }}
          </button>
          <button v-if="editTarget && !editTarget.is_active === false" @click="form.is_active = false; save()"
            class="w-full bg-red-900 hover:bg-red-800 text-white font-bold py-2 rounded-lg transition-colors text-sm">
            停用帳號
          </button>
        </div>
      </div>
    </div>

    <!-- Change Password Modal -->
    <div v-if="showPwModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">重設密碼</h3>
          <button @click="showPwModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-3 text-sm">
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">新密碼</label>
            <input v-model="pwForm.new_password" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
          </div>
          <div>
            <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">確認密碼</label>
            <input v-model="pwForm.confirm" type="password"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
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
