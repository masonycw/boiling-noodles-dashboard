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
const filterCategory = ref('')
const filterVendor = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const toast = ref('')

const categoryOptions = ['蔬菜', '肉品', '海鮮', '調味料', '主食', '其他']

const emptyForm = () => ({
  name: '', unit: '', category: '', vendor_id: null,
  stocktake_group_id: null, min_stock: 10, current_stock: 0,
  price: null, display_order: 999, is_active: true
})

const form = ref(emptyForm())

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = '' }, 2500)
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
    list = list.filter(i =>
      i.name.toLowerCase().includes(q) ||
      (i.category || '').toLowerCase().includes(q) ||
      (vendorName(i.vendor_id)).toLowerCase().includes(q)
    )
  }
  if (filterCategory.value) {
    list = list.filter(i => i.category === filterCategory.value)
  }
  if (filterVendor.value) {
    list = list.filter(i => String(i.vendor_id) === filterVendor.value)
  }
  return list
})

const vendorName = (id) => vendors.value.find(v => v.id === id)?.name || '—'
const groupName = (id) => groups.value.find(g => g.id === id)?.name || null

function stockStatus(item) {
  const stock = parseFloat(item.current_stock) || 0
  const min = parseFloat(item.min_stock) || 0
  if (min === 0) return { label: '正常', cls: 'bg-[#10b981] text-white' }
  if (stock <= 0) return { label: '缺貨', cls: 'bg-[#ef4444] text-white' }
  if (stock <= min) return { label: '預警', cls: 'bg-[#f59e0b] text-white' }
  return { label: '正常', cls: 'bg-[#10b981] text-white' }
}

function openCreate() {
  editTarget.value = null
  form.value = emptyForm()
  saveError.value = ''
  showModal.value = true
}

function openEdit(item) {
  editTarget.value = item
  form.value = {
    name: item.name || '',
    unit: item.unit || '',
    category: item.category || '',
    vendor_id: item.vendor_id,
    stocktake_group_id: item.stocktake_group_id,
    min_stock: item.min_stock ?? 10,
    current_stock: item.current_stock ?? 0,
    price: item.price ?? null,
    display_order: item.display_order ?? 999,
    is_active: item.is_active !== false,
  }
  saveError.value = ''
  showModal.value = true
}

async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入品項名稱'; return }
  if (!form.value.unit.trim()) { saveError.value = '請填入單位'; return }
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
    showToast('✓ 品項已儲存')
    await load()
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}

// B1: Drag & Drop 排序
const isDragging = computed(() => !!search.value.trim() || !!filterCategory.value || !!filterVendor.value)
const dragFromIdx = ref(null)
const dragOverIdx = ref(null)

function onDragStart(idx) {
  if (isDragging.value) return
  dragFromIdx.value = idx
}

function onDragOver(idx) {
  if (isDragging.value) return
  dragOverIdx.value = idx
}

function onDragEnd() {
  if (isDragging.value || dragFromIdx.value === null || dragOverIdx.value === null || dragFromIdx.value === dragOverIdx.value) {
    dragFromIdx.value = null; dragOverIdx.value = null; return
  }
  const arr = [...items.value]
  const [moved] = arr.splice(dragFromIdx.value, 1)
  arr.splice(dragOverIdx.value, 0, moved)
  items.value = arr.map((it, i) => ({ ...it, sort_order: i + 1 }))
  dragFromIdx.value = null; dragOverIdx.value = null
  saveReorder()
}

async function saveReorder() {
  const payload = { items: items.value.map((it, i) => ({ id: it.id, sort_order: i + 1 })) }
  await fetch(`${API_BASE}/inventory/items/reorder`, {
    method: 'PATCH', headers: authHeaders(), body: JSON.stringify(payload)
  }).catch(() => {})
}
</script>

<template>
  <div>
    <!-- Toast -->
    <div v-if="toast"
      class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">
      {{ toast }}
    </div>

    <!-- Toolbar -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <input v-model="search" type="text" placeholder="搜尋品項、分類、供應商…"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-4 py-2 text-sm w-56 focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterCategory"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部分類</option>
        <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filterVendor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部供應商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
      <button @click="openCreate"
        class="ml-auto bg-[#63b3ed] hover:bg-blue-400 text-black font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增品項
      </button>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
            <th class="px-2 py-3 text-center" style="width:30px"></th>
            <th class="px-4 py-3 text-left" style="width:150px">品項名稱</th>
            <th class="px-4 py-3 text-left" style="width:80px">分類</th>
            <th class="px-4 py-3 text-left" style="width:100px">主要供應商</th>
            <th class="px-4 py-3 text-left" style="width:100px">盤點群組</th>
            <th class="px-4 py-3 text-center" style="width:50px">單位</th>
            <th class="px-4 py-3 text-right" style="width:70px">安全庫存</th>
            <th class="px-4 py-3 text-right" style="width:70px">目前庫存</th>
            <th class="px-4 py-3 text-right" style="width:70px">參考價格</th>
            <th class="px-4 py-3 text-center" style="width:80px">狀態</th>
            <th class="px-4 py-3 text-center" style="width:120px">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="(item, idx) in filtered" :key="item.id"
            class="hover:bg-[#1f2937] transition-colors"
            :class="dragOverIdx === idx ? 'bg-[#1e3a5f]' : ''"
            :draggable="!isDragging"
            @dragstart="onDragStart(idx)"
            @dragover.prevent="onDragOver(idx)"
            @dragend="onDragEnd">
            <td class="px-2 py-3 text-center">
              <span :class="isDragging ? 'text-gray-700 cursor-not-allowed' : 'text-gray-500 cursor-grab'"
                title="拖曳排序（搜尋/篩選狀態下不可拖曳）">⠿</span>
            </td>
            <td class="px-4 py-3 font-semibold text-gray-200">{{ item.name }}</td>
            <td class="px-4 py-3 text-gray-400">{{ item.category || '—' }}</td>
            <td class="px-4 py-3 text-gray-400">{{ vendorName(item.vendor_id) }}</td>
            <td class="px-4 py-3">
              <span v-if="groupName(item.stocktake_group_id)"
                class="text-[11px] px-1.5 py-0.5 rounded"
                style="background:#1f2937; color:#9ca3af; border:1px solid #2d3748;">
                {{ groupName(item.stocktake_group_id) }}
              </span>
              <span v-else class="text-gray-600">—</span>
            </td>
            <td class="px-4 py-3 text-center text-gray-400">{{ item.unit }}</td>
            <td class="px-4 py-3 text-right font-mono text-gray-300">{{ item.min_stock ?? 0 }}</td>
            <td class="px-4 py-3 text-right font-mono"
              :class="parseFloat(item.min_stock) > 0 && parseFloat(item.current_stock) <= parseFloat(item.min_stock) ? 'text-amber-400 font-bold' : 'text-gray-300'">
              {{ item.current_stock ?? 0 }}
            </td>
            <td class="px-4 py-3 text-right font-mono text-gray-400">
              {{ item.price != null ? '$' + Number(item.price).toLocaleString('zh-TW') : '—' }}
            </td>
            <td class="px-4 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full" :class="stockStatus(item).cls">
                {{ stockStatus(item).label }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <button @click="openEdit(item)" class="text-[#63b3ed] hover:text-blue-300 text-xs font-bold">編輯</button>
            </td>
          </tr>
          <tr v-if="filtered.length === 0">
            <td colspan="11" class="px-4 py-10 text-center text-gray-600">無品項資料</td>
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
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                品項名稱 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.name" type="text" maxlength="50"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                分類 <span class="text-red-400">*</span>
              </label>
              <select v-model="form.category"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option value="">— 請選擇 —</option>
                <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                單位 <span class="text-red-400">*</span>
              </label>
              <input v-model="form.unit" type="text" placeholder="包 / 把 / 瓶 / 箱"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">主要供應商 <span class="text-red-400">*</span></label>
              <select v-model.number="form.vendor_id"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option :value="null">—</option>
                <option v-for="v in vendors" :key="v.id" :value="v.id">{{ v.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">盤點群組 <span class="text-red-400">*</span></label>
              <select v-model.number="form.stocktake_group_id"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]">
                <option :value="null">—</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">
                安全庫存量 <span class="text-red-400">*</span>
              </label>
              <input v-model.number="form.min_stock" type="number" min="0"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">參考價格</label>
              <input v-model.number="form.price" type="number" min="0" step="0.01"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div>
              <label class="block text-[#9ca3af] text-[13px] font-semibold mb-1">陳列順序</label>
              <input v-model.number="form.display_order" type="number"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-[#63b3ed]" />
            </div>
            <div class="col-span-2 flex items-center gap-3 pt-1">
              <input v-model="form.is_active" type="checkbox" id="is_active" class="w-4 h-4 accent-blue-500" />
              <label for="is_active" class="text-gray-300 text-sm">啟用此品項</label>
            </div>
          </div>

          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>

          <button @click="save" :disabled="saving"
            class="w-full bg-[#63b3ed] hover:bg-blue-400 text-black font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
