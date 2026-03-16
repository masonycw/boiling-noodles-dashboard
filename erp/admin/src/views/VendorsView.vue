<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const vendors = ref([])
const loading = ref(true)
const search = ref('')
const showModal = ref(false)
const editTarget = ref(null)  // null = create mode
const saving = ref(false)
const saveError = ref('')

const form = ref({
  name: '', contact_name: '', phone: '', line_id: '', address: '',
  expense_category: '', payment_terms: 'monthly',
  payment_days: 30, bank_name: '', bank_account: '', bank_account_holder: '',
  free_shipping_threshold: null, delivery_days_to_arrive: null,
  order_deadline: '', note: ''
})

const expenseCategoryOptions = ['食材', '飲品', '醬料', '包裝材料', '日用品', '設備', '其他']
const paymentTermsOptions = [
  { value: 'cash', label: '現金 / 即期' },
  { value: 'monthly', label: '月結' },
  { value: 'net30', label: 'Net 30' },
  { value: 'net60', label: 'Net 60' },
  { value: 'credit_card', label: '信用卡' },
  { value: 'transfer', label: '轉帳' },
]

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
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
  return vendors.value.filter(v => v.name.toLowerCase().includes(q) || (v.contact_name || '').toLowerCase().includes(q))
})

function openCreate() {
  editTarget.value = null
  form.value = { name: '', contact_name: '', phone: '', line_id: '', address: '', expense_category: '', payment_terms: 'monthly', payment_days: 30, bank_name: '', bank_account: '', bank_account_holder: '', free_shipping_threshold: null, delivery_days_to_arrive: null, order_deadline: '', note: '' }
  saveError.value = ''
  showModal.value = true
}

function openEdit(v) {
  editTarget.value = v
  form.value = { ...v }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入供應商名稱'; return }
  saving.value = true
  saveError.value = ''
  try {
    const url = editTarget.value
      ? `${API_BASE}/inventory/vendors/${editTarget.value.id}`
      : `${API_BASE}/inventory/vendors`
    const method = editTarget.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(form.value) })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-5">
      <input v-model="search" type="text" placeholder="搜尋供應商…"
        class="bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-4 py-2 text-sm w-64 focus:outline-none focus:border-blue-500" />
      <button @click="openCreate"
        class="ml-auto bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增供應商
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">供應商名稱</th>
            <th class="px-5 py-3 text-left">聯絡人</th>
            <th class="px-5 py-3 text-left">電話</th>
            <th class="px-5 py-3 text-left">電話 / LINE</th>
            <th class="px-5 py-3 text-left">費用科目</th>
            <th class="px-5 py-3 text-left">付款條件</th>
            <th class="px-5 py-3 text-left">免運門檻</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="v in filtered" :key="v.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-semibold text-gray-200">{{ v.name }}</td>
            <td class="px-5 py-3 text-gray-400">{{ v.contact_name || '—' }}</td>
            <td class="px-5 py-3 text-gray-400">
              <div>{{ v.phone || '—' }}</div>
              <div v-if="v.line_id" class="text-xs text-green-400">LINE: {{ v.line_id }}</div>
            </td>
            <td class="px-5 py-3 text-gray-400">{{ v.expense_category || '—' }}</td>
            <td class="px-5 py-3 text-gray-400">{{ v.payment_terms || '—' }} / {{ v.payment_days }}天</td>
            <td class="px-5 py-3 text-gray-400">{{ v.free_shipping_threshold ? '$' + v.free_shipping_threshold : '—' }}</td>
            <td class="px-5 py-3 text-center">
              <button @click="openEdit(v)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="7" class="px-5 py-10 text-center text-gray-600">無供應商資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯供應商' : '新增供應商' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="space-y-4 text-sm">
          <div class="grid grid-cols-2 gap-4">
            <div class="col-span-2">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">供應商名稱 *</label>
              <input v-model="form.name" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <!-- 基本資訊 -->
            <div class="col-span-2 text-xs font-bold text-blue-400 uppercase pt-1">基本資訊</div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">聯絡人</label>
              <input v-model="form.contact_name" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">電話</label>
              <input v-model="form.phone" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">LINE ID</label>
              <input v-model="form.line_id" type="text" placeholder="@line_id" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">截單時間</label>
              <input v-model="form.order_deadline" type="time" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div class="col-span-2">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">地址</label>
              <input v-model="form.address" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>

            <!-- 費用 / 付款 -->
            <div class="col-span-2 text-xs font-bold text-blue-400 uppercase pt-1">費用 / 付款</div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">費用科目</label>
              <select v-model="form.expense_category" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
                <option value="">— 請選擇 —</option>
                <option v-for="opt in expenseCategoryOptions" :key="opt" :value="opt">{{ opt }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">付款條件</label>
              <select v-model="form.payment_terms" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
                <option v-for="opt in paymentTermsOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">付款天數</label>
              <input v-model.number="form.payment_days" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">免運門檻 ($)</label>
              <input v-model.number="form.free_shipping_threshold" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">配送天數</label>
              <input v-model.number="form.delivery_days_to_arrive" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>

            <!-- 銀行資訊 -->
            <div class="col-span-2 text-xs font-bold text-blue-400 uppercase pt-1">銀行資訊</div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">銀行名稱</label>
              <input v-model="form.bank_name" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">銀行帳號</label>
              <input v-model="form.bank_account" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div class="col-span-2">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">帳戶持有人</label>
              <input v-model="form.bank_account_holder" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>

            <!-- 備註 -->
            <div class="col-span-2">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">備註</label>
              <textarea v-model="form.note" rows="2" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 resize-none"></textarea>
            </div>
          </div>

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <button @click="save" :disabled="saving"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '儲存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
