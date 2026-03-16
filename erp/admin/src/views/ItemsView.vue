<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const items = ref([])
const vendors = ref([])
const groups = ref([])
const loading = ref(true)
const search = ref('')
const filterVendor = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')

const form = ref({
  name: '', unit: '', vendor_id: null, category: '',
  price: null, min_order_qty: null, current_stock: 0,
  secondary_unit: '', secondary_unit_ratio: null,
  stocktake_group_id: null, display_order: 0, is_active: true
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const [itemsRes, vendorsRes, groupsRes] = await Promise.all([
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
  ])
  if (itemsRes.ok) items.value = await itemsRes.json()
  if (vendorsRes.ok) vendors.value = await vendorsRes.json()
  if (groupsRes.ok) groups.value = await groupsRes.json()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  let list = items.value
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    list = list.filter(i => i.name.toLowerCase().includes(q))
  }
  if (filterVendor.value) {
    list = list.filter(i => String(i.vendor_id) === filterVendor.value)
  }
  return list
})

const vendorName = (id) => vendors.value.find(v => v.id === id)?.name || '—'
const groupName = (id) => groups.value.find(g => g.id === id)?.name || '—'

function stockStatus(item) {
  const stock = parseFloat(item.current_stock) || 0
  const min = parseFloat(item.min_stock) || 0
  if (min === 0) return { label: '正常', cls: 'bg-emerald-900/50 text-emerald-400' }
  if (stock <= 0) return { label: '缺貨', cls: 'bg-red-900/50 text-red-400' }
  if (stock <= min) return { label: '預警', cls: 'bg-amber-900/50 text-amber-400' }
  return { label: '正常', cls: 'bg-emerald-900/50 text-emerald-400' }
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', unit: '', vendor_id: null, category: '', price: null, min_order_qty: null, current_stock: 0, secondary_unit: '', secondary_unit_ratio: null, stocktake_group_id: null, display_order: 0, is_active: true }
  saveError.value = ''
  showModal.value = true
}

function openEdit(item) {
  editTarget.value = item
  form.value = { ...item }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入品項名稱'; return }
  saving.value = true
  saveError.value = ''
  try {
    const url = editTarget.value
      ? `${API_BASE}/inventory/items/${editTarget.value.id}`
      : `${API_BASE}/inventory/items`
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
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <input v-model="search" type="text" placeholder="搜尋品項…"
        class="bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-4 py-2 text-sm w-56 focus:outline-none focus:border-blue-500" />
      <select v-model="filterVendor"
        class="bg-[#111827] border border-[#374151] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
        <option value="">全部供應商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <button @click="openCreate"
        class="ml-auto bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增品項
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">品項名稱</th>
            <th class="px-5 py-3 text-left">供應商</th>
            <th class="px-5 py-3 text-left">盤點群組</th>
            <th class="px-5 py-3 text-right">庫存 / 安全</th>
            <th class="px-5 py-3 text-right">單價</th>
            <th class="px-5 py-3 text-center">庫存狀態</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="item in filtered" :key="item.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-semibold text-gray-200">
              {{ item.name }}
              <span class="text-gray-500 font-normal ml-1 text-xs">/ {{ item.unit }}</span>
            </td>
            <td class="px-5 py-3 text-gray-400">{{ vendorName(item.vendor_id) }}</td>
            <td class="px-5 py-3 text-gray-400">{{ groupName(item.stocktake_group_id) }}</td>
            <td class="px-5 py-3 text-right font-mono">
              <span :class="parseFloat(item.min_stock) > 0 && parseFloat(item.current_stock) <= parseFloat(item.min_stock) ? 'text-amber-400 font-bold' : 'text-gray-300'">
                {{ item.current_stock }}
              </span>
              <span class="text-gray-600"> / {{ item.min_stock || 0 }} {{ item.unit }}</span>
            </td>
            <td class="px-5 py-3 text-right font-mono text-gray-300">{{ item.price ? '$' + item.price : '—' }}</td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="stockStatus(item).cls">
                {{ stockStatus(item).label }}
              </span>
              <span v-if="!item.is_active" class="ml-1 text-xs text-gray-600">(停用)</span>
            </td>
            <td class="px-5 py-3 text-center">
              <button @click="openEdit(item)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="7" class="px-5 py-10 text-center text-gray-600">無品項資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯品項' : '新增品項' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="space-y-3 text-sm">
          <div class="grid grid-cols-2 gap-3">
            <div class="col-span-2">
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">品項名稱 *</label>
              <input v-model="form.name" type="text" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">單位</label>
              <input v-model="form.unit" type="text" placeholder="kg / 個 / 包" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">供應商</label>
              <select v-model.number="form.vendor_id" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
                <option :value="null">—</option>
                <option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">單價</label>
              <input v-model.number="form.price" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">最小叫貨量</label>
              <input v-model.number="form.min_order_qty" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">盤點群組</label>
              <select v-model.number="form.stocktake_group_id" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500">
                <option :value="null">—</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">目前庫存</label>
              <input v-model.number="form.current_stock" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">安全庫存（預警值）</label>
              <input v-model.number="form.min_stock" type="number" placeholder="0" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 uppercase mb-1">顯示排序</label>
              <input v-model.number="form.display_order" type="number" class="w-full bg-[#111827] border border-[#374151] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500" />
            </div>
            <div class="col-span-2 flex items-center gap-3 pt-1">
              <input v-model="form.is_active" type="checkbox" id="is_active" class="w-4 h-4 accent-blue-500" />
              <label for="is_active" class="text-gray-300 text-sm">啟用此品項</label>
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
