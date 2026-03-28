<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const loading = ref(true)
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const formError = ref('')

const form = ref({ content: '', expires_at: '' })

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/announcements?all=true`, { headers: authHeaders() })
  if (res.ok) records.value = await res.json()
  loading.value = false
}

onMounted(load)

function openAdd() {
  editTarget.value = null
  form.value = { content: '', expires_at: '' }
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editTarget.value = r
  form.value = {
    content: r.content,
    expires_at: r.expires_at ? r.expires_at.slice(0, 10) : '',
  }
  formError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.content.trim()) { formError.value = '請輸入公告內容'; return }
  saving.value = true
  formError.value = ''
  try {
    const payload = {
      content: form.value.content.trim(),
      expires_at: form.value.expires_at || null,
    }
    let res
    if (editTarget.value) {
      res = await fetch(`${API_BASE}/announcements/${editTarget.value.id}`, {
        method: 'PATCH', headers: authHeaders(), body: JSON.stringify(payload)
      })
    } else {
      res = await fetch(`${API_BASE}/announcements`, {
        method: 'POST', headers: authHeaders(), body: JSON.stringify(payload)
      })
    }
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    await load()
  } catch(e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function toggleActive(r) {
  await fetch(`${API_BASE}/announcements/${r.id}`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ is_active: !r.is_active })
  })
  await load()
}

async function deleteAnn(r) {
  if (!confirm(`確定要刪除此公告？`)) return
  const res = await fetch(`${API_BASE}/announcements/${r.id}`, { method: 'DELETE', headers: authHeaders() })
  if (res.ok) await load()
}

function fmtDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit', year: 'numeric' })
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-bold text-gray-400">公告管理</h3>
        <p class="text-xs text-gray-600 mt-0.5">公告會顯示在前台首頁，常用於通知廠商休假日等特殊事項</p>
      </div>
      <button @click="openAdd" class="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-bold bg-amber-500 text-[#0f1117] hover:bg-amber-400">
        📢 新增公告
      </button>
    </div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-4 py-3 text-left">公告內容</th>
            <th class="px-4 py-3 text-center">建立日期</th>
            <th class="px-4 py-3 text-center">到期日</th>
            <th class="px-4 py-3 text-center">狀態</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in records" :key="r.id" class="hover:bg-[#1f2937] transition-colors" :class="r.is_active ? '' : 'opacity-50'">
            <td class="px-4 py-3 text-gray-200 max-w-xs">
              <p class="line-clamp-2">{{ r.content }}</p>
            </td>
            <td class="px-4 py-3 text-center text-gray-500 text-xs">{{ fmtDate(r.created_at) }}</td>
            <td class="px-4 py-3 text-center text-xs" :class="r.expires_at ? 'text-amber-400' : 'text-gray-600'">
              {{ r.expires_at ? fmtDate(r.expires_at) : '長期' }}
            </td>
            <td class="px-4 py-3 text-center">
              <button @click="toggleActive(r)" class="text-xs font-bold px-2 py-0.5 rounded-full transition-colors"
                :class="r.is_active ? 'bg-emerald-900/40 text-emerald-400 hover:bg-emerald-900/60' : 'bg-gray-700 text-gray-500 hover:bg-gray-600'">
                {{ r.is_active ? '顯示中' : '已關閉' }}
              </button>
            </td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-2">
                <button @click="openEdit(r)" class="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400 hover:bg-blue-500/30">編輯</button>
                <button @click="deleteAnn(r)" class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="records.length === 0">
            <td colspan="5" class="px-5 py-10 text-center text-gray-600">尚無公告</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/編輯 Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 w-full max-w-md">
        <div class="flex justify-between items-center mb-4">
          <h3 class="font-bold text-gray-200">{{ editTarget ? '編輯公告' : '新增公告' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300">✕</button>
        </div>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-gray-500 mb-1 block">公告內容</label>
            <textarea v-model="form.content" rows="4" placeholder="例：點線麵 3/29（六）休假，請提前叫貨" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-400 resize-none"></textarea>
          </div>
          <div>
            <label class="text-xs text-gray-500 mb-1 block">到期日（留空表示長期顯示）</label>
            <input v-model="form.expires_at" type="date" class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-amber-400" />
          </div>
          <p v-if="formError" class="text-red-400 text-xs">{{ formError }}</p>
          <div class="flex gap-2 pt-2">
            <button @click="save" :disabled="saving"
              class="flex-1 py-2 rounded-lg font-bold text-sm bg-amber-500 text-[#0f1117] hover:bg-amber-400 disabled:opacity-40">
              {{ saving ? '儲存中…' : (editTarget ? '更新' : '建立') }}
            </button>
            <button @click="showModal = false" class="flex-1 py-2 rounded-lg text-sm text-gray-400 border border-[#2d3748] hover:bg-[#1f2937]">取消</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
