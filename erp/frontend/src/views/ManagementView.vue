<script setup>
import { ref, onMounted } from 'vue'

const activeTab = ref('vendors') // 'vendors', 'items'
const vendors = ref([])
const items = ref([])
const isLoading = ref(false)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// Form State
const showVendorModal = ref(false)
const editingVendor = ref(null)
const vendorForm = ref({ name: '', contact_person: '', phone: '', order_deadline: '21:00' })

const showItemModal = ref(false)
const editingItem = ref(null)
const itemForm = ref({ name: '', unit: '', vendor_id: null, min_stock: 0 })

const fetchData = async () => {
  isLoading.value = true
  try {
    const vRes = await fetch(`${API_BASE}/inventory/vendors`)
    vendors.value = await vRes.json()
    
    if (activeTab.value === 'items') {
      const iRes = await fetch(`${API_BASE}/inventory/items`)
      items.value = await iRes.json()
    }
  } catch (err) {
    console.error('Fetch error:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchData)

const saveVendor = async () => {
  const method = editingVendor.value ? 'PUT' : 'POST'
  const url = editingVendor.value ? `${API_BASE}/inventory/vendors/${editingVendor.value.id}` : `${API_BASE}/inventory/vendors`
  
  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(vendorForm.value)
    })
    if (res.ok) {
      showVendorModal.value = false
      fetchData()
    }
  } catch (err) {
    alert('儲存失敗')
  }
}

const deleteVendor = async (id) => {
  if (!confirm('確定要刪除此供應商嗎？')) return
  try {
    await fetch(`${API_BASE}/inventory/vendors/${id}`, { method: 'DELETE' })
    fetchData()
  } catch (err) {
    alert('刪除失敗')
  }
}

const saveItem = async () => {
  const method = editingItem.value ? 'PUT' : 'POST'
  const url = editingItem.value ? `${API_BASE}/inventory/items/${editingItem.value.id}` : `${API_BASE}/inventory/items`
  
  try {
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(itemForm.value)
    })
    if (res.ok) {
      showItemModal.value = false
      fetchData()
    }
  } catch (err) {
    alert('儲存失敗')
  }
}

const openVendorEdit = (v) => {
  editingVendor.value = v
  vendorForm.value = { ...v }
  showVendorModal.value = true
}

const openItemEdit = (item) => {
  editingItem.value = item
  itemForm.value = { ...item }
  showItemModal.value = true
}

// Password Change
const passwordForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdErrorMsg = ref('')
const pwdSuccessMsg = ref('')
const isPwdLoading = ref(false)

const changePassword = async () => {
  pwdErrorMsg.value = ''
  pwdSuccessMsg.value = ''
  
  if (!passwordForm.value.oldPassword || !passwordForm.value.newPassword) {
    pwdErrorMsg.value = '請填寫完整密碼資訊'
    return
  }
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    pwdErrorMsg.value = '新密碼與確認密碼不一致'
    return
  }
  
  isPwdLoading.value = true
  try {
    const token = localStorage.getItem('erp_token')
    const res = await fetch(`${API_BASE}/auth/users/me/password`, {
      method: 'PUT',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        old_password: passwordForm.value.oldPassword,
        new_password: passwordForm.value.newPassword
      })
    })
    
    if (res.ok) {
      pwdSuccessMsg.value = '密碼修改成功！下次請使用新密碼登入。'
      passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
    } else {
      const data = await res.json()
      pwdErrorMsg.value = data.detail || '修改密碼失敗，請確認原密碼是否正確'
    }
  } catch (err) {
    pwdErrorMsg.value = '連線錯誤，請稍後再試'
  } finally {
    isPwdLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 pb-32">
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 p-4">
      <h1 class="text-xl font-bold text-slate-900 mb-4">系統管理</h1>
      <div class="flex space-x-2 bg-slate-100 p-1 rounded-xl">
        <button 
          @click="activeTab = 'vendors'; fetchData()"
          class="flex-1 py-2 rounded-lg text-sm font-bold transition-all"
          :class="activeTab === 'vendors' ? 'bg-white text-orange-600 shadow-sm' : 'text-slate-500'"
        >
          供應商管理
        </button>
        <button 
          @click="activeTab = 'items'; fetchData()"
          class="flex-1 py-2 rounded-lg text-sm font-bold transition-all"
          :class="activeTab === 'items' ? 'bg-white text-orange-600 shadow-sm' : 'text-slate-500'"
        >
          品項管理
        </button>
        <button 
          @click="activeTab = 'profile'"
          class="flex-1 py-2 rounded-lg text-sm font-bold transition-all"
          :class="activeTab === 'profile' ? 'bg-white text-orange-600 shadow-sm' : 'text-slate-500'"
        >
          個人設定
        </button>
      </div>
    </header>

    <main class="p-4">
      <div v-if="isLoading" class="flex justify-center py-20">
        <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>

      <!-- Vendors List -->
      <div v-else-if="activeTab === 'vendors'" class="space-y-3">
        <div v-for="v in vendors" :key="v.id" class="bg-white p-4 rounded-2xl border border-slate-200 flex justify-between items-center">
          <div>
            <p class="font-bold text-slate-900">{{ v.name }}</p>
            <p class="text-xs text-slate-400">截單: {{ v.order_deadline }}</p>
          </div>
          <div class="flex space-x-2">
            <button @click="openVendorEdit(v)" class="p-2 text-slate-400 hover:text-orange-500">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
            </button>
            <button @click="deleteVendor(v.id)" class="p-2 text-slate-400 hover:text-rose-500">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-4v6m4-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
          </div>
        </div>
        <button @click="editingVendor = null; vendorForm = { name: '', order_deadline: '21:00' }; showVendorModal = true" class="w-full py-4 border-2 border-dashed border-slate-300 rounded-2xl text-slate-400 font-bold hover:border-orange-300 hover:text-orange-500 transition-all">
          + 新增供應商
        </button>
      </div>

      <!-- Items List -->
      <div v-else-if="activeTab === 'items'" class="space-y-3">
        <div v-for="item in items" :key="item.id" class="bg-white p-4 rounded-2xl border border-slate-200 flex justify-between items-center">
          <div>
            <p class="font-bold text-slate-900">{{ item.name }}</p>
            <p class="text-xs text-slate-400">單位: {{ item.unit }} | 供應商ID: {{ item.vendor_id }}</p>
          </div>
          <button @click="openItemEdit(item)" class="p-2 text-slate-400 hover:text-orange-500">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
          </button>
        </div>
        <button @click="editingItem = null; itemForm = { name: '', unit: '', vendor_id: 1 }; showItemModal = true" class="w-full py-4 border-2 border-dashed border-slate-300 rounded-2xl text-slate-400 font-bold hover:border-orange-300 hover:text-orange-500 transition-all">
          + 新增品項
        </button>
      </div>

      <!-- User Profile (Change Password) -->
      <div v-else-if="activeTab === 'profile'" class="space-y-4 max-w-md mx-auto">
        <div class="bg-white p-6 rounded-3xl border border-slate-200 shadow-sm">
          <h3 class="font-black text-slate-900 text-lg mb-4">修改密碼</h3>
          <div class="space-y-4">
            <div>
              <label class="block text-xs font-bold text-slate-500 mb-1">目前密碼</label>
              <input v-model="passwordForm.oldPassword" type="password" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 focus:ring-2 focus:ring-orange-500/20" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 mb-1">新密碼</label>
              <input v-model="passwordForm.newPassword" type="password" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 focus:ring-2 focus:ring-orange-500/20" />
            </div>
            <div>
              <label class="block text-xs font-bold text-slate-500 mb-1">確認新密碼</label>
              <input v-model="passwordForm.confirmPassword" type="password" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 focus:ring-2 focus:ring-orange-500/20" />
            </div>
            <p v-if="pwdErrorMsg" class="text-rose-500 text-sm font-bold">{{ pwdErrorMsg }}</p>
            <p v-if="pwdSuccessMsg" class="text-emerald-500 text-sm font-bold">{{ pwdSuccessMsg }}</p>
            <button 
              @click="changePassword"
              :disabled="isPwdLoading"
              class="w-full bg-slate-900 text-white font-bold py-4 rounded-2xl active:scale-95 transition-all disabled:opacity-50 mt-4"
            >
              {{ isPwdLoading ? '處理中...' : '確認修改' }}
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- Vendor Modal -->
    <div v-if="showVendorModal" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-bold text-slate-800">{{ editingVendor ? '編輯供應商' : '新增供應商' }}</h3>
            <button @click="showVendorModal = false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
        </div>
        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4">
          <input v-model="vendorForm.name" type="text" placeholder="名稱" class="w-full p-3 bg-slate-50 rounded-xl" />
          <input v-model="vendorForm.order_deadline" type="text" placeholder="截單時間 (HH:mm)" class="w-full p-3 bg-slate-50 rounded-xl" />
        </div>
        <!-- Fixed bottom buttons -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100 flex space-x-2">
          <button @click="showVendorModal = false" class="flex-1 py-3 bg-slate-100 rounded-xl font-bold">取消</button>
          <button @click="saveVendor" class="flex-1 py-3 bg-orange-500 text-white rounded-xl font-bold">儲存</button>
        </div>
      </div>
    </div>

    <!-- Item Modal -->
    <div v-if="showItemModal" class="fixed inset-0 bg-black/50 z-[60] flex items-end">
      <div class="bg-white w-full rounded-t-3xl max-h-[92vh] flex flex-col">
        <!-- Fixed header -->
        <div class="flex-shrink-0 px-5 pt-4 pb-3">
          <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-3"></div>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-bold text-slate-800">{{ editingItem ? '編輯品項' : '新增品項' }}</h3>
            <button @click="showItemModal = false" class="text-slate-400 text-xl font-bold">✕</button>
          </div>
        </div>
        <!-- Scrollable content -->
        <div class="flex-1 overflow-y-auto px-5 pb-2 space-y-4">
          <input v-model="itemForm.name" type="text" placeholder="名稱" class="w-full p-3 bg-slate-50 rounded-xl" />
          <input v-model="itemForm.unit" type="text" placeholder="單位" class="w-full p-3 bg-slate-50 rounded-xl" />
          <select v-model="itemForm.vendor_id" class="w-full p-3 bg-slate-50 rounded-xl">
            <option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.name }}</option>
          </select>
        </div>
        <!-- Fixed bottom buttons -->
        <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100 flex space-x-2">
          <button @click="showItemModal = false" class="flex-1 py-3 bg-slate-100 rounded-xl font-bold">取消</button>
          <button @click="saveItem" class="flex-1 py-3 bg-orange-500 text-white rounded-xl font-bold">儲存</button>
        </div>
      </div>
    </div>
  </div>
</template>
