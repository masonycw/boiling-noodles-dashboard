<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import UserBadge from '@/components/UserBadge.vue'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const executors = ref([])
const monthlyKpi = ref(null)
const vendors = ref([])
const allItems = ref([])
const groups = ref([])
const loading = ref(true)
const expandedId = ref(null)

// ── Edit Stocktake ──
const showEditModal = ref(false)
const editRecord = ref(null)
const editForm = ref({ stocktake_date: '', performed_by: '', note: '', items: [] })
const editSubmitting = ref(false)
const editError = ref('')

// ── Delete Stocktake ──
const showDeleteModal = ref(false)
const deleteRecord = ref(null)
const deleteSubmitting = ref(false)

// Filters
const filterDateFrom = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10))
const filterDateTo = ref(new Date().toISOString().slice(0, 10))
const filterExecutor = ref('')
const filterGroup = ref('')
const filterStatus = ref('')   // '' | 'has_discrepancy' | 'no_discrepancy'
const filterVendor = ref('')

const groupOptions = computed(() => groups.value.slice().sort((a, b) => a.display_order - b.display_order))

// Pagination
const page = ref(1)
const PAGE_SIZE = 10

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

const itemVendorMap = computed(() => {
  const m = {}
  allItems.value.forEach(i => { m[i.id] = i.vendor_id })
  return m
})

async function load() {
  loading.value = true
  const [recRes, execRes, kpiRes, vendorRes, itemRes, groupRes] = await Promise.all([
    fetch(`${API_BASE}/stocktake/?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/executors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/monthly-kpi`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/vendors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() }),
  ])
  if (recRes.ok) records.value = await recRes.json()
  if (execRes.ok) executors.value = await execRes.json()
  if (kpiRes.ok) monthlyKpi.value = await kpiRes.json()
  if (vendorRes.ok) vendors.value = await vendorRes.json()
  if (itemRes.ok) allItems.value = await itemRes.json()
  if (groupRes.ok) groups.value = await groupRes.json()
  loading.value = false
}

onMounted(load)

const filtered = computed(() => {
  let list = records.value
  if (filterDateFrom.value) {
    list = list.filter(r => r.created_at >= filterDateFrom.value)
  }
  if (filterDateTo.value) {
    const to = filterDateTo.value + 'T23:59:59'
    list = list.filter(r => r.created_at <= to)
  }
  if (filterExecutor.value) {
    list = list.filter(r => String(r.user_id) === filterExecutor.value)
  }
  if (filterGroup.value) {
    list = list.filter(r => String(r.stocktake_group_id) === filterGroup.value)
  }
  if (filterStatus.value === 'has_discrepancy') {
    list = list.filter(r => r.discrepancy_count > 0)
  } else if (filterStatus.value === 'no_discrepancy') {
    list = list.filter(r => r.discrepancy_count === 0)
  }
  if (filterVendor.value) {
    const vendId = parseInt(filterVendor.value)
    list = list.filter(r => r.items?.some(i => itemVendorMap.value[i.item_id] === vendId))
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paginated = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

function changePage(p) {
  page.value = Math.max(1, Math.min(p, totalPages.value))
}

function toggleExpand(r) {
  expandedId.value = expandedId.value === r.id ? null : r.id
}

function openEditStocktake(r, e) {
  e.stopPropagation()
  editRecord.value = r
  editError.value = ''
  editForm.value = {
    stocktake_date: r.created_at?.slice(0, 10) || '',
    performed_by: r.user_id || '',
    note: r.note || '',
    items: (r.items || []).map(i => ({
      item_id: i.item_id,
      item_name: i.item_name,
      expected_qty: i.expected_qty,
      counted_qty: parseFloat(i.counted_qty) || 0,
    }))
  }
  showEditModal.value = true
}

async function saveEditStocktake() {
  editSubmitting.value = true
  editError.value = ''
  try {
    const res = await fetch(`${API_BASE}/stocktake/${editRecord.value.id}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        stocktake_date: editForm.value.stocktake_date,
        performed_by: parseInt(editForm.value.performed_by) || null,
        note: editForm.value.note,
        items: editForm.value.items.map(i => ({ item_id: i.item_id, counted_qty: parseFloat(i.counted_qty) || 0 }))
      })
    })
    if (!res.ok) { const d = await res.json(); throw new Error(d.detail || '儲存失敗') }
    showEditModal.value = false
    await load()
  } catch (e) {
    editError.value = e.message
  } finally {
    editSubmitting.value = false
  }
}

function openDeleteStocktake(r, e) {
  e.stopPropagation()
  deleteRecord.value = r
  deleteSubmitting.value = false
  showDeleteModal.value = true
}

async function confirmDeleteStocktake() {
  deleteSubmitting.value = true
  try {
    const res = await fetch(`${API_BASE}/stocktake/${deleteRecord.value.id}`, {
      method: 'DELETE', headers: authHeaders()
    })
    if (!res.ok) throw new Error('刪除失敗')
    showDeleteModal.value = false
    if (expandedId.value === deleteRecord.value.id) expandedId.value = null
    await load()
  } catch (e) { alert(e.message) }
  finally { deleteSubmitting.value = false }
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}
</script>

<template>
  <div class="space-y-5">

    <!-- KPI Cards -->
    <div v-if="monthlyKpi" class="grid grid-cols-2 gap-3">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
        <p class="text-xs text-[#9ca3af] uppercase tracking-wider">本月盤點次數</p>
        <p class="text-3xl font-bold text-[#63b3ed] mt-1">{{ monthlyKpi.month_count }}</p>
      </div>
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
        <p class="text-xs text-[#9ca3af] uppercase tracking-wider">平均差異品項</p>
        <p class="text-3xl font-bold mt-1"
          :class="monthlyKpi.average_discrepancy_count > 0 ? 'text-[#ef4444]' : 'text-[#10b981]'">
          {{ monthlyKpi.average_discrepancy_count }}
        </p>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 flex-wrap">
      <input v-model="filterDateFrom" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <span class="text-gray-500 text-sm">至</span>
      <input v-model="filterDateTo" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterExecutor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部執行人</option>
        <option v-for="e in executors" :key="e.id" :value="String(e.id)">{{ e.name }}</option>
      </select>
      <select v-model="filterGroup"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部群組</option>
        <option v-for="g in groupOptions" :key="g.id" :value="String(g.id)">{{ g.name }}</option>
      </select>
      <select v-model="filterStatus"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部狀態</option>
        <option value="has_discrepancy">有差異</option>
        <option value="no_discrepancy">無差異</option>
      </select>
      <select v-model="filterVendor"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部廠商</option>
        <option v-for="v in vendors" :key="v.id" :value="String(v.id)">{{ v.name }}</option>
      </select>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <template v-else>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
              <th class="px-4 py-3 text-left">日期</th>
              <th class="px-4 py-3 text-left">執行人</th>
              <th class="px-4 py-3 text-left">群組</th>
              <th class="px-4 py-3 text-center">品項數</th>
              <th class="px-4 py-3 text-center">差異品項</th>
              <th class="px-4 py-3 text-center">狀態</th>
              <th class="px-4 py-3 text-center">查看</th>
              <th class="px-4 py-3 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="r in paginated" :key="r.id">
              <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] transition-colors cursor-pointer"
                @click="toggleExpand(r)">
                <td class="px-4 py-3 text-gray-400 text-xs">{{ fmtDate(r.created_at) }}</td>
                <td class="px-4 py-3"><UserBadge :user="r.performed_by" size="sm" /></td>
                <td class="px-4 py-3 text-gray-400">{{ r.group_name || '—' }}</td>
                <td class="px-4 py-3 text-center text-gray-400">{{ r.items?.length ?? 0 }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="font-bold" :class="r.discrepancy_count > 0 ? 'text-amber-400' : 'text-gray-600'">
                    {{ r.discrepancy_count }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                    :class="r.discrepancy_count > 0
                      ? 'bg-amber-900/40 text-[#f59e0b]'
                      : 'bg-emerald-900/40 text-[#10b981]'">
                    {{ r.discrepancy_count > 0 ? '⚠ 有差異' : '✓ 無差異' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-center text-[#63b3ed] text-xs font-bold">
                  {{ expandedId === r.id ? '▲' : '查看' }}
                </td>
                <td class="px-4 py-3 text-center" @click.stop>
                  <button @click="openEditStocktake(r, $event)"
                    class="text-xs px-2 py-1 rounded bg-[#2d3748] text-[#63b3ed] hover:bg-[#3d4f63] mr-1">
                    編輯
                  </button>
                  <button @click="openDeleteStocktake(r, $event)"
                    class="text-xs px-2 py-1 rounded bg-[#2d3748] text-red-400 hover:bg-red-900/30">
                    刪除
                  </button>
                </td>
              </tr>
              <!-- Expanded detail -->
              <tr v-if="expandedId === r.id" class="border-b border-[#2d3748]"
                :style="r.discrepancy_count > 0 ? 'background:rgba(239,68,68,0.04)' : 'background:#0f1117'">
                <td colspan="8" class="px-6 py-4">
                  <p class="text-xs font-bold text-[#9ca3af] mb-3 flex items-center gap-2">
                    盤點詳細 — <UserBadge :user="r.performed_by" size="sm" /> · {{ fmtDate(r.created_at) }}
                  </p>
                  <div v-if="!r.items || r.items.length === 0" class="text-gray-500 text-sm">
                    無品項資料
                  </div>
                  <table v-else class="w-full text-xs">
                    <thead>
                      <tr class="text-[#9ca3af] border-b border-[#2d3748]">
                        <th class="pb-2 text-left">品項</th>
                        <th class="pb-2 text-right">系統庫存</th>
                        <th class="pb-2 text-right">實盤</th>
                        <th class="pb-2 text-right">差異</th>
                        <th class="pb-2 text-center">狀態</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="d in r.items" :key="d.id"
                        class="border-b border-[#1a202c]"
                        :class="d.variance !== 0 && d.variance !== null ? 'bg-amber-900/10' : 'text-gray-400'">
                        <td class="py-1.5 text-gray-300">{{ d.item_name }}</td>
                        <td class="py-1.5 text-right text-gray-400">{{ d.expected_qty ?? '—' }}</td>
                        <td class="py-1.5 text-right text-gray-400">{{ d.counted_qty ?? '—' }}</td>
                        <td class="py-1.5 text-right font-bold"
                          :class="d.variance !== null && d.variance !== 0 ? 'text-amber-400' : 'text-gray-600'">
                          {{ d.variance !== null ? (d.variance > 0 ? '+' : '') + d.variance : '—' }}
                        </td>
                        <td class="py-1.5 text-center">
                          <span v-if="d.variance !== null && d.variance !== 0"
                            class="text-xs text-amber-400">差異</span>
                          <span v-else class="text-xs text-gray-600">—</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </td>
              </tr>
            </template>
            <tr v-if="filtered.length === 0">
              <td colspan="8" class="px-5 py-10 text-center text-gray-600">無盤點紀錄</td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalPages > 1" class="flex items-center justify-center gap-1 px-5 py-4 border-t border-[#2d3748]">
          <button @click="changePage(page - 1)" :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30">
            上一頁
          </button>
          <button v-for="p in totalPages" :key="p" @click="changePage(p)"
            class="w-8 h-8 rounded-lg text-sm font-bold transition-colors"
            :class="p === page ? 'bg-[#63b3ed] text-black' : 'text-gray-400 hover:bg-[#1f2937]'">
            {{ p }}
          </button>
          <button @click="changePage(page + 1)" :disabled="page === totalPages"
            class="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:bg-[#1f2937] disabled:opacity-30">
            下一頁
          </button>
        </div>
        <div class="px-5 py-2 text-xs text-gray-600 text-right">共 {{ filtered.length }} 筆</div>
      </template>
    </div>
  <!-- Edit Stocktake Modal -->
  <div v-if="showEditModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between px-6 py-4 border-b border-[#2d3748]">
        <h3 class="text-base font-bold text-gray-200">編輯盤點紀錄</h3>
        <button @click="showEditModal = false" class="text-gray-500 hover:text-gray-300 text-xl">✕</button>
      </div>
      <div class="px-6 py-5 space-y-4">
        <!-- 盤點群組（唯讀） -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">盤點群組（不可更改）</label>
          <p class="text-gray-400 text-sm px-3 py-2 bg-[#0f1117] rounded-lg">{{ editRecord?.group_name || '—' }}</p>
        </div>
        <!-- 盤點日期 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">盤點日期</label>
          <input v-model="editForm.stocktake_date" type="date"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <!-- 執行人 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">執行人</label>
          <select v-model="editForm.performed_by"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
            <option value="">— 選擇執行人 —</option>
            <option v-for="e in executors" :key="e.id" :value="e.id">{{ e.name }}</option>
          </select>
        </div>
        <!-- 品項數量 -->
        <div>
          <label class="block text-xs text-gray-500 mb-2">品項盤點數量</label>
          <div class="space-y-1">
            <div v-for="item in editForm.items" :key="item.item_id"
              class="flex items-center gap-3 bg-[#0f1117] rounded-lg px-3 py-2">
              <span class="flex-1 text-xs text-gray-300">{{ item.item_name }}</span>
              <span class="text-xs text-gray-500 w-16 text-right">庫存 {{ item.expected_qty ?? '—' }}</span>
              <input v-model.number="item.counted_qty" type="number" min="0" step="0.5"
                class="w-20 bg-[#1a202c] border border-[#2d3748] text-gray-300 rounded px-2 py-1 text-xs text-center focus:outline-none" />
              <span class="text-xs w-14 text-right font-bold"
                :class="item.counted_qty - item.expected_qty < 0 ? 'text-red-400' : item.counted_qty - item.expected_qty > 0 ? 'text-amber-400' : 'text-emerald-400'">
                {{ item.expected_qty != null ? ((item.counted_qty - item.expected_qty) > 0 ? '+' : '') + (item.counted_qty - item.expected_qty).toFixed(1) : '—' }}
              </span>
            </div>
          </div>
        </div>
        <!-- 備注 -->
        <div>
          <label class="block text-xs text-gray-500 mb-1">備注</label>
          <input v-model="editForm.note" type="text" placeholder="備注說明…"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <p v-if="editError" class="text-red-400 text-sm text-center">{{ editError }}</p>
      </div>
      <div class="flex gap-3 px-6 pb-6">
        <button @click="showEditModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="saveEditStocktake" :disabled="editSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-[#63b3ed] text-black hover:bg-blue-400 disabled:opacity-40">
          {{ editSubmitting ? '儲存中…' : '儲存修改' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Delete Stocktake Dialog -->
  <div v-if="showDeleteModal" class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center px-4">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-sm p-6">
      <h3 class="text-base font-bold text-gray-200 mb-4">⚠️ 確認刪除盤點紀錄</h3>
      <div class="bg-[#0f1117] rounded-xl p-4 mb-4 space-y-1 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">群組</span>
          <span class="text-gray-300">{{ deleteRecord?.group_name || '—' }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">日期</span>
          <span class="text-gray-300">{{ fmtDate(deleteRecord?.created_at) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">執行人</span>
          <span class="text-gray-300">{{ deleteRecord?.executor_name || '—' }}</span>
        </div>
      </div>
      <p class="text-xs text-red-400 mb-1">• 刪除後，此次盤點的所有品項紀錄也將一併移除</p>
      <p class="text-xs text-red-400 mb-4">• 此操作不可復原</p>
      <div class="flex gap-3">
        <button @click="showDeleteModal = false"
          class="flex-1 py-2.5 rounded-xl text-sm font-semibold border border-[#2d3748] text-gray-400 hover:bg-[#0f1117]">
          取消
        </button>
        <button @click="confirmDeleteStocktake" :disabled="deleteSubmitting"
          class="flex-1 py-2.5 rounded-xl text-sm font-bold bg-red-600 text-white hover:bg-red-500 disabled:opacity-40">
          {{ deleteSubmitting ? '刪除中…' : '確認刪除' }}
        </button>
      </div>
    </div>
  </div>

  </div>
</template>
