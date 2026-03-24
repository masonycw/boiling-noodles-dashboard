<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const groups = ref([])
const allItems = ref([])
const vendors = ref([])
const loading = ref(true)
const toast = ref('')

// 新增/編輯群組 Modal
const showModal = ref(false)
const editTarget = ref(null)
const saving = ref(false)
const saveError = ref('')
const form = ref({ name: '', description: '', suggested_frequency: '每日', is_active: true, stocktake_cycle_days: null, next_stocktake_due: '' })

// 品項管理 Modal（B3 新功能）
const showItemsModal = ref(false)
const itemsTarget = ref(null)
const selectedItemIds = ref(new Set())
const itemSearch = ref('')
const selectedVendorId = ref('')
const savingItems = ref(false)

const frequencyOptions = ['每日', '每週一', '每週二', '每週三', '每週四', '每週五', '每週六', '每月一次（月初）', '每月中旬', '自訂']

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

function itemCount(groupId) {
  return allItems.value.filter(i => i.stocktake_group_id === groupId).length
}

async function load() {
  loading.value = true
  const [grpRes, itemRes, vendorRes] = await Promise.all([
    fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
  ])
  if (grpRes.ok) groups.value = await grpRes.json()
  if (itemRes.ok) allItems.value = await itemRes.json()
  if (vendorRes.ok) vendors.value = await vendorRes.json()
  loading.value = false
}
onMounted(load)

// ── 群組 CRUD ──
function openCreate() {
  editTarget.value = null
  form.value = { name: '', description: '', suggested_frequency: '每日', is_active: true, stocktake_cycle_days: null, next_stocktake_due: '' }
  saveError.value = ''
  showModal.value = true
}
function openEdit(g) {
  editTarget.value = g
  form.value = {
    name: g.name || '',
    description: g.description || '',
    suggested_frequency: g.suggested_frequency || '每日',
    is_active: g.is_active !== false,
    stocktake_cycle_days: g.stocktake_cycle_days || null,
    next_stocktake_due: g.next_stocktake_due || ''
  }
  saveError.value = ''
  showModal.value = true
}
async function save() {
  if (!form.value.name.trim()) { saveError.value = '請填入群組名稱'; return }
  saving.value = true; saveError.value = ''
  try {
    const url = editTarget.value ? `${API_BASE}/stocktake/groups/${editTarget.value.id}` : `${API_BASE}/stocktake/groups`
    const method = editTarget.value ? 'PUT' : 'POST'
    const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(form.value) })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showModal.value = false; showToast('✓ 盤點群組已儲存'); await load()
  } catch (e) { saveError.value = e.message } finally { saving.value = false }
}
async function deleteGroup(g) {
  if (!confirm(`確定刪除盤點群組「${g.name}」？`)) return
  const res = await fetch(`${API_BASE}/stocktake/groups/${g.id}`, { method: 'DELETE', headers: authHeaders() })
  if (res.ok) { showToast('✓ 已刪除'); await load() }
  else { const d = await res.json(); alert(d.detail || '刪除失敗') }
}

// ── 品項管理（B3 新功能）──
function openItemsModal(g) {
  itemsTarget.value = g
  // 初始化：當前群組的品項勾選
  const currentIds = allItems.value.filter(i => i.stocktake_group_id === g.id).map(i => i.id)
  selectedItemIds.value = new Set(currentIds)
  itemSearch.value = ''
  selectedVendorId.value = ''
  showItemsModal.value = true
}

const filteredItems = computed(() => {
  let list = allItems.value
  if (itemSearch.value) list = list.filter(i => i.name?.toLowerCase().includes(itemSearch.value.toLowerCase()))
  if (selectedVendorId.value) list = list.filter(i => String(i.vendor_id) === selectedVendorId.value)
  return list
})

function toggleItem(itemId) {
  if (selectedItemIds.value.has(itemId)) selectedItemIds.value.delete(itemId)
  else selectedItemIds.value.add(itemId)
}
function toggleAll() {
  const ids = filteredItems.value.map(i => i.id)
  const allSelected = ids.every(id => selectedItemIds.value.has(id))
  if (allSelected) ids.forEach(id => selectedItemIds.value.delete(id))
  else ids.forEach(id => selectedItemIds.value.add(id))
}
function importVendorItems() {
  if (!selectedVendorId.value) return
  const vendorItems = allItems.value.filter(i => String(i.vendor_id) === selectedVendorId.value)
  vendorItems.forEach(i => selectedItemIds.value.add(i.id))
  showToast(`✓ 已匯入 ${vendorItems.length} 項品項`)
}

const vendorName = (vid) => vendors.value.find(v => String(v.id) === String(vid))?.name || '—'

async function saveGroupItems() {
  if (!itemsTarget.value) return
  savingItems.value = true
  try {
    // Update each item's stocktake_group_id
    const groupId = itemsTarget.value.id
    const toAdd = allItems.value.filter(i => selectedItemIds.value.has(i.id) && i.stocktake_group_id !== groupId)
    const toRemove = allItems.value.filter(i => !selectedItemIds.value.has(i.id) && i.stocktake_group_id === groupId)

    const updates = [
      ...toAdd.map(i => fetch(`${API_BASE}/inventory/items/${i.id}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ stocktake_group_id: groupId })
      })),
      ...toRemove.map(i => fetch(`${API_BASE}/inventory/items/${i.id}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ stocktake_group_id: null })
      })),
    ]
    await Promise.all(updates)
    showItemsModal.value = false; showToast('✓ 群組品項已更新'); await load()
  } catch (e) { showToast('⚠ 更新失敗') } finally { savingItems.value = false }
}
</script>

<template>
  <div>
    <!-- Toast -->
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <p class="text-gray-500 text-sm mb-4">盤點群組用於安排定期盤點排程，每個品項可屬於一個群組。</p>

    <!-- Toolbar -->
    <div class="flex items-center mb-4">
      <button @click="openCreate"
        class="ml-auto bg-blue-500 hover:bg-blue-400 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
        + 新增群組
      </button>
    </div>

    <!-- 群組列表 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">群組名稱</th>
            <th class="px-5 py-3 text-center">品項數</th>
            <th class="px-5 py-3 text-left">盤點頻率</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="g in groups" :key="g.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 font-semibold text-gray-200">
              {{ g.name }}
              <p v-if="g.description" class="text-xs text-gray-500 font-normal mt-0.5">{{ g.description }}</p>
            </td>
            <td class="px-5 py-3 text-center text-gray-400">{{ itemCount(g.id) }} 項</td>
            <td class="px-5 py-3 text-gray-400">
              {{ g.suggested_frequency || '—' }}
              <span v-if="g.stocktake_cycle_days" class="ml-2 text-xs bg-blue-900/40 text-blue-400 px-1.5 py-0.5 rounded font-bold">
                每 {{ g.stocktake_cycle_days }} 天
              </span>
              <p v-if="g.next_stocktake_due" class="text-xs text-gray-600 mt-0.5">
                下次：{{ g.next_stocktake_due }}
              </p>
            </td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="g.is_active !== false ? 'bg-emerald-900/50 text-emerald-400' : 'bg-gray-800 text-gray-600'">
                {{ g.is_active !== false ? '啟用' : '停用' }}
              </span>
            </td>
            <td class="px-5 py-3 text-center">
              <div class="flex items-center justify-center gap-2">
                <button @click="openItemsModal(g)"
                  class="bg-blue-900/40 hover:bg-blue-900/60 text-blue-400 text-xs font-bold px-2 py-1 rounded transition-colors">
                  管理品項
                </button>
                <button @click="openEdit(g)" class="text-blue-400 hover:text-blue-300 text-xs font-bold">編輯</button>
                <button @click="deleteGroup(g)" class="text-red-400 hover:text-red-300 text-xs font-bold">刪除</button>
              </div>
            </td>
          </tr>
          <tr v-if="groups.length === 0">
            <td colspan="5" class="px-5 py-10 text-center text-gray-600">無盤點群組資料</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/編輯群組 Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-md p-6">
        <div class="flex justify-between items-center mb-5">
          <h3 class="text-lg font-bold text-gray-100">{{ editTarget ? '編輯盤點群組' : '新增盤點群組' }}</h3>
          <button @click="showModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>
        <div class="space-y-4 text-sm">
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">群組名稱 *</label>
            <input v-model="form.name" type="text" maxlength="30"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">描述</label>
            <textarea v-model="form.description" rows="2" maxlength="200"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400 resize-none"></textarea>
          </div>
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">建議盤點頻率 *</label>
            <select v-model="form.suggested_frequency"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400">
              <option v-for="f in frequencyOptions" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
          <!-- O5: 盤點週期 -->
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">盤點週期（天）</label>
            <input v-model.number="form.stocktake_cycle_days" type="number" min="1" max="365" placeholder="空白 = 不設提醒"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
            <p class="text-xs text-gray-600 mt-1">設定後 HomeView 會顯示待盤點提醒</p>
          </div>
          <!-- O5: 下次預定盤點日 -->
          <div>
            <label class="block text-gray-400 text-xs font-semibold mb-1">下次預定盤點日</label>
            <input v-model="form.next_stocktake_due" type="date"
              class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-400" />
            <p class="text-xs text-gray-600 mt-1">可手動覆蓋；盤點完成後系統自動 +週期天數</p>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="form.is_active" type="checkbox" id="grp_active" class="w-4 h-4 accent-blue-500" />
            <label for="grp_active" class="text-gray-300">啟用此群組</label>
          </div>
          <div v-if="saveError" class="text-red-400 text-xs text-center">{{ saveError }}</div>
          <button @click="save" :disabled="saving"
            class="w-full bg-blue-500 hover:bg-blue-400 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ saving ? '儲存中…' : '儲存群組' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 品項管理 Modal（B3 批次匯入 + 手動勾選） -->
    <div v-if="showItemsModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-2xl flex flex-col" style="max-height:90vh">
        <div class="flex justify-between items-center px-6 py-4 border-b border-[#2d3748]">
          <div>
            <h3 class="text-lg font-bold text-gray-100">管理品項：{{ itemsTarget?.name }}</h3>
            <p class="text-xs text-gray-500 mt-0.5">已選 {{ selectedItemIds.size }} 項</p>
          </div>
          <button @click="showItemsModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
        </div>

        <div class="px-6 py-4 border-b border-[#2d3748] space-y-3">
          <!-- 批次匯入廠商品項 -->
          <div class="flex items-center gap-2">
            <span class="text-xs text-gray-400 shrink-0">依廠商批次匯入：</span>
            <select v-model="selectedVendorId"
              class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400">
              <option value="">選擇廠商…</option>
              <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
            </select>
            <button @click="importVendorItems" :disabled="!selectedVendorId"
              class="bg-purple-700 hover:bg-purple-600 text-white font-bold px-3 py-1.5 rounded-lg text-sm transition-colors disabled:opacity-40">
              匯入
            </button>
          </div>
          <!-- 搜尋 + 全選 -->
          <div class="flex items-center gap-2">
            <input v-model="itemSearch" type="text" placeholder="搜尋品項名稱…"
              class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400" />
            <button @click="toggleAll" class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 shrink-0">
              {{ filteredItems.every(i => selectedItemIds.has(i.id)) ? '全不選' : '全選' }}
            </button>
          </div>
        </div>

        <!-- 品項列表 -->
        <div class="overflow-y-auto flex-1 px-6 py-2">
          <div v-if="filteredItems.length === 0" class="py-8 text-center text-gray-600">無符合品項</div>
          <div v-for="item in filteredItems" :key="item.id"
            class="flex items-center gap-3 py-2 border-b border-[#2d3748]/50 hover:bg-[#1f2937] -mx-2 px-2 rounded cursor-pointer"
            @click="toggleItem(item.id)">
            <input type="checkbox" :checked="selectedItemIds.has(item.id)" @click.stop="toggleItem(item.id)"
              class="w-4 h-4 accent-blue-500 shrink-0" />
            <div class="flex-1 min-w-0">
              <span class="text-sm text-gray-200">{{ item.name }}</span>
              <span v-if="item.unit" class="text-xs text-gray-500 ml-1">{{ item.unit }}</span>
            </div>
            <span class="text-xs text-gray-500 shrink-0">{{ vendorName(item.vendor_id) }}</span>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-[#2d3748] flex gap-3">
          <button @click="showItemsModal = false"
            class="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-200 font-bold py-2.5 rounded-lg transition-colors">
            取消
          </button>
          <button @click="saveGroupItems" :disabled="savingItems"
            class="flex-1 bg-blue-500 hover:bg-blue-400 text-white font-bold py-2.5 rounded-lg transition-colors disabled:opacity-50">
            {{ savingItems ? '儲存中…' : '儲存群組品項' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
