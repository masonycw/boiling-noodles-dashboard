<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const vendors = ref([])
const loading = ref(true)
const search = ref('')
const selectedId = ref(null)
const isNew = ref(false)
const saving = ref(false)
const saveError = ref('')
const toast = ref('')

const emptyForm = () => ({
  name: '', contact_person: '', phone: '', line_id: '',
  payment_method: '現金',
  expense_category: '食材費用',
  payment_terms: '現付',
  bank_account: '', bank_account_holder: '',
  reminder_days: 5,
  order_cycle: '',
})

const form = ref(emptyForm())

const paymentMethodOptions = ['現金', '轉帳', '支票']
const expenseCategoryOptions = ['食材費用', '人事費用', '營業費用', '平台費用', '金融費用', '其他']
const paymentTermsOptions = ['現付', '月結30日', '月結60日', '貨到7天', '貨到14天']
const reminderDaysOptions = [3, 5, 7, 14]

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() })
  if (res.ok) vendors.value = await res.json()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  if (!search.value.trim()) return vendors.value
  const q = search.value.toLowerCase()
  return vendors.value.filter(v =>
    v.name.toLowerCase().includes(q) ||
    (v.contact_person || '').toLowerCase().includes(q) ||
    (v.phone || '').includes(q)
  )
})

function selectVendor(v) {
  isNew.value = false
  selectedId.value = v.id
  saveError.value = ''
  form.value = {
    name: v.name || '',
    contact_person: v.contact_person || '',
    phone: v.phone || '',
    line_id: v.line_id || '',
    payment_method: v.payment_method || '現金',
    expense_category: v.expense_category || '食材費用',
    payment_terms: v.payment_terms || '現付',
    bank_account: v.bank_account || '',
    bank_account_holder: v.bank_account_holder || '',
    reminder_days: v.reminder_days || 5,
    order_cycle: v.order_cycle || '',
  }
}

function openNew() {
  isNew.value = true
  selectedId.value = null
  saveError.value = ''
  form.value = emptyForm()
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入供應商名稱'; return }
  if (!form.value.contact_person.trim()) { saveError.value = '請填入聯絡人'; return }
  if (!form.value.phone.trim()) { saveError.value = '請填入電話'; return }
  saving.value = true
  saveError.value = ''
  try {
    const url = isNew.value
      ? `${API_BASE}/inventory/vendors`
      : `${API_BASE}/inventory/vendors/${selectedId.value}`
    const method = isNew.value ? 'POST' : 'PUT'
    const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(form.value) })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    const saved = await res.json()
    showToast('✓ 供應商已儲存')
    await load()
    if (isNew.value) {
      isNew.value = false
      selectedId.value = saved.id
    }
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

async function deleteVendor() {
  if (!selectedId.value) return
  const v = vendors.value.find(v => v.id === selectedId.value)
  if (!confirm(`確定要刪除「${v?.name}」？`)) return
  const res = await fetch(`${API_BASE}/inventory/vendors/${selectedId.value}`, {
    method: 'DELETE', headers: authHeaders()
  })
  if (res.ok) {
    selectedId.value = null
    isNew.value = false
    await load()
    showToast('✓ 已刪除')
  }
}
</script>

<template>
  <div>
    <!-- Toast -->
    <div v-if="toast"
      class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">
      {{ toast }}
    </div>

    <div class="grid gap-5" style="grid-template-columns: 1fr 1fr; max-width: 1400px;">
      <!-- Left: List -->
      <div>
        <div class="flex items-center gap-3 mb-4">
          <input v-model="search" type="text" placeholder="搜尋供應商..."
            class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-4 py-2 text-sm flex-1 focus:outline-none focus:border-[#63b3ed]" />
          <button @click="openNew"
            class="bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors whitespace-nowrap">
            + 新增供應商
          </button>
        </div>

        <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
          <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
                <th class="px-4 py-3 text-left">供應商名稱</th>
                <th class="px-4 py-3 text-left">聯絡人</th>
                <th class="px-4 py-3 text-left">電話</th>
                <th class="px-4 py-3 text-left">付款方式</th>
                <th class="px-4 py-3 text-left">叫貨週期</th>
                <th class="px-4 py-3 text-center">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[#2d3748]">
              <tr v-for="v in filtered" :key="v.id"
                class="cursor-pointer transition-colors"
                :class="selectedId === v.id ? 'bg-[#1e3a5f]' : 'hover:bg-[#1f2937]'"
                @click="selectVendor(v)">
                <td class="px-4 py-3 font-semibold text-gray-200">{{ v.name }}</td>
                <td class="px-4 py-3 text-gray-400">{{ v.contact_person || '—' }}</td>
                <td class="px-4 py-3 text-gray-400">
                  <div>{{ v.phone || '—' }}</div>
                  <div v-if="v.line_id" class="text-xs text-green-400">LINE: {{ v.line_id }}</div>
                </td>
                <td class="px-4 py-3 text-gray-400">{{ v.payment_method || '—' }}</td>
                <td class="px-4 py-3 text-gray-400 text-xs">{{ v.order_cycle || '—' }}</td>
                <td class="px-4 py-3 text-center">
                  <button @click.stop="selectVendor(v)"
                    class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
                </td>
              </tr>
              <tr v-if="filtered.length === 0">
                <td colspan="6" class="px-4 py-10 text-center text-gray-600">無供應商資料</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right: Form -->
      <div>
        <div v-if="!isNew && !selectedId"
          class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-8 text-center text-gray-600 mt-12">
          <p class="text-3xl mb-3">🏪</p>
          <p>點擊左側供應商進行編輯<br>或點擊「新增供應商」建立新記錄</p>
        </div>

        <div v-else class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-6 max-h-[800px] overflow-y-auto">
          <div class="flex justify-between items-center mb-5">
            <h3 class="text-base font-bold text-gray-100">{{ isNew ? '新增供應商' : '編輯供應商' }}</h3>
            <button v-if="!isNew" @click="deleteVendor"
              class="text-xs text-red-400 hover:text-red-300 font-bold border border-red-800 hover:border-red-600 px-2 py-1 rounded transition-colors">
              刪除
            </button>
          </div>

          <div class="space-y-4 text-sm">
            <!-- 基本資訊 -->
            <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748]">
              基本資訊
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                供應商名稱 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.name" type="text" maxlength="50"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  聯絡人 <span class="text-red-400">*</span>
                </label>
                <input v-model="form.contact_person" type="text" maxlength="30"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  電話 <span class="text-red-400">*</span>
                </label>
                <input v-model="form.phone" type="text"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
              </div>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">LINE ID</label>
              <input v-model="form.line_id" type="text" placeholder="@line_id"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>

            <!-- 財務與付款 -->
            <div class="text-xs font-bold text-[#63b3ed] uppercase tracking-wider pb-1 border-b border-[#2d3748] pt-2">
              財務與付款
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  付款方式 <span class="text-red-400">*</span>
                </label>
                <select v-model="form.payment_method"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="o in paymentMethodOptions" :key="o" :value="o">{{ o }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  預設科目分類 <span class="text-red-400">*</span>
                </label>
                <select v-model="form.expense_category"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="o in expenseCategoryOptions" :key="o" :value="o">{{ o }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                  付款條件 <span class="text-red-400">*</span>
                </label>
                <select v-model="form.payment_terms"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="o in paymentTermsOptions" :key="o" :value="o">{{ o }}</option>
                </select>
              </div>
              <div>
                <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">到期前提醒天數</label>
                <select v-model.number="form.reminder_days"
                  class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                  <option v-for="d in reminderDaysOptions" :key="d" :value="d">{{ d }} 天前</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">匯款帳號</label>
              <input v-model="form.bank_account" type="text" placeholder="004-012-345-678901"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">戶名</label>
              <input v-model="form.bank_account_holder" type="text"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                叫貨週期 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.order_cycle" type="text" placeholder="每週一、四 / 每日"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>

            <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

            <button @click="save" :disabled="saving"
              class="w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50 text-sm"
              style="height:44px;">
              {{ saving ? '儲存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
