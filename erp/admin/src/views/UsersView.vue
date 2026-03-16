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

const form = ref({
  username: '', password: '', full_name: '',
  role: 'staff', petty_cash_permission: false, is_active: true
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
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
    // Admin reset: use a dummy current_password (admin privilege bypassed via backend adjustment)
    const res = await fetch(`${API_BASE}/users/${pwUserId.value}/password`, {
      method: 'PUT', headers: authHeaders(),
      body: JSON.stringify({ current_password: '_admin_reset_', new_password: pwForm.value.new_password })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '修改失敗') }
    showPwModal.value = false
  } catch (e) {
    pwError.value = e.message
  } finally {
    pwSaving.value = false
  }
}

function fmtDate(d) { return d ? new Date(d).toLocaleDateString('zh-TW') : '—' }
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="flex items-center mb-5">
      <button @click="openCreate"
        class="ml-auto bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增人員
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">帳號</th>
            <th class="px-5 py-3 text-left">姓名</th>
            <th class="px-5 py-3 text-center">角色</th>
            <th class="px-5 py-3 text-center">提領授權</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-left">最後登入</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="u in users" :key="u.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-mono text-gray-300">{{ u.username }}</td>
            <td class="px-5 py-3 font-semibold text-gray-200">{{ u.full_name || '—' }}</td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-1 rounded-full"
                :class="u.role === 'admin' ? 'bg-blue-900/50 text-blue-400' : 'bg-gray-700 text-gray-400'">
                {{ u.role === 'admin' ? '管理員' : '員工' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold" :class="u.petty_cash_permission ? 'text-emerald-400' : 'text-gray-600'">
                {{ u.petty_cash_permission ? '✓' : '—' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold" :class="u.is_active ? 'text-emerald-400' : 'text-red-400'">
                {{ u.is_active ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-3 text-gray-500 text-xs">{{ fmtDate(u.last_login) }}</td>
            <td class="px-5 py-3 text-center flex items-center justify-center gap-3">
              <button @click="openEdit(u)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
              <button @click="openChangePw(u)" class="text-amber-400 hover:text-amber-300 text-xs font-bold">改密碼</button>
            </td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="7" class="px-5 py-10 text-center text-gray-600">無人員資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Edit/Create Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯人員' : '新增人員' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="space-y-3 text-sm">
          <div v-if="!editTarget">
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">帳號 *</label>
            <input v-model="form.username" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div v-if="!editTarget">
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">初始密碼 *</label>
            <input v-model="form.password" type="password" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">姓名</label>
            <input v-model="form.full_name" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">角色</label>
            <select v-model="form.role" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
              <option value="staff">員工</option>
              <option value="admin">管理員</option>
            </select>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="form.petty_cash_permission" type="checkbox" id="pcp" class="w-4 h-4 accent-blue-500" />
            <label for="pcp" class="text-gray-300">允許提領零用金</label>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="form.is_active" type="checkbox" id="active" class="w-4 h-4 accent-blue-500" />
            <label for="active" class="text-gray-300">帳號啟用中</label>
          </div>

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <button @click="save" :disabled="saving"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '儲存' }}
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
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">新密碼</label>
            <input v-model="pwForm.new_password" type="password" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 uppercase mb-1">確認密碼</label>
            <input v-model="pwForm.confirm" type="password" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
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
