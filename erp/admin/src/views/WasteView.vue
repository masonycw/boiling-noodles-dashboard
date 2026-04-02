<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const wasteItems = ref([])
const monthlyKpi = ref(null)
const loading = ref(true)

// Filters
const filterDateFrom = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10))
const filterDateTo = ref(new Date().toISOString().slice(0, 10))
const filterItem = ref('')
const filterReason = ref('')
const filterRecorder = ref('')

// Pagination
const page = ref(1)
const PAGE_SIZE = 10

const reasons = ['食材過期', '物品損壞', '試菜', '其他', '過期', '損壞', '破損', '烹調損耗', '自然耗損', '操作失誤', '品質不良']

// Photo expansion
const expandedPhotoId = ref(null)
function togglePhoto(id) {
  expandedPhotoId.value = expandedPhotoId.value === id ? null : id
}

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

function resolveUrl(url) {
  if (!url) return null
  if (url.startsWith('http')) return url
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '')
  return base + url
}

async function load() {
  loading.value = true
  const [recRes, itemsRes, kpiRes] = await Promise.all([
    fetch(`${API_BASE}/waste/?days_limit=90&limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/items-used`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/monthly-kpi`, { headers: authHeaders() }),
  ])
  if (recRes.ok) records.value = await recRes.json()
  if (itemsRes.ok) wasteItems.value = await itemsRes.json()
  if (kpiRes.ok) monthlyKpi.value = await kpiRes.json()
  loading.value = false
}

onMounted(load)

const recorderOptions = computed(() => {
  const names = new Set(records.value.map(r => r.recorded_by_name).filter(Boolean))
  return [...names].sort()
})

const filtered = computed(() => {
  let list = records.value
  if (filterDateFrom.value) {
    list = list.filter(r => r.created_at >= filterDateFrom.value)
  }
  if (filterDateTo.value) {
    const to = filterDateTo.value + 'T23:59:59'
    list = list.filter(r => r.created_at <= to)
  }
  if (filterItem.value) {
    list = list.filter(r => String(r.item_id) === filterItem.value)
  }
  if (filterReason.value) {
    list = list.filter(r => r.reason === filterReason.value)
  }
  if (filterRecorder.value) {
    list = list.filter(r => r.recorded_by_name === filterRecorder.value)
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paginated = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

function changePage(p) {
  page.value = Math.max(1, Math.min(p, totalPages.value))
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }) : '—'
}
function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
</script>

<template>
  <div class="space-y-5">

    <!-- KPI Card -->
    <div v-if="monthlyKpi" class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
      <p class="text-xs text-[#9ca3af] uppercase tracking-wider mb-1">本月耗損總值</p>
      <p class="text-3xl font-bold" style="color:#ef4444">
        ${{ fmtMoney(monthlyKpi.total_value) }}
      </p>
      <div class="flex items-center gap-4 mt-2">
        <span class="text-xs text-[#9ca3af]">共 {{ monthlyKpi.total_count }} 筆</span>
        <span v-if="monthlyKpi.most_common_reason" class="text-xs text-[#9ca3af]">
          最常原因：<span class="text-gray-300">{{ monthlyKpi.most_common_reason }}</span>
        </span>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 flex-wrap">
      <input v-model="filterDateFrom" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <span class="text-gray-500 text-sm">至</span>
      <input v-model="filterDateTo" type="date"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
      <select v-model="filterItem"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部品項</option>
        <option v-for="i in wasteItems" :key="i.id" :value="String(i.id)">{{ i.name }}</option>
      </select>
      <select v-model="filterReason"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部原因</option>
        <option v-for="r in reasons" :key="r" :value="r">{{ r }}</option>
      </select>
      <select v-model="filterRecorder"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部紀錄人</option>
        <option v-for="n in recorderOptions" :key="n" :value="n">{{ n }}</option>
      </select>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <template v-else>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
              <th class="px-4 py-3 text-left">日期</th>
              <th class="px-4 py-3 text-left">品項</th>
              <th class="px-4 py-3 text-right">數量</th>
              <th class="px-4 py-3 text-center">單位</th>
              <th class="px-4 py-3 text-center">原因</th>
              <th class="px-4 py-3 text-right">估值</th>
              <th class="px-4 py-3 text-left">記錄人</th>
              <th class="px-4 py-3 text-left">備註</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <template v-for="r in paginated" :key="r.id">
              <tr class="hover:bg-[#1f2937] transition-colors cursor-pointer"
                :class="expandedPhotoId === r.id ? 'bg-[#1f2937]' : ''"
                @click="r.photo_url ? togglePhoto(r.id) : null">
                <td class="px-4 py-3 text-gray-500 text-xs">{{ fmtDate(r.created_at) }}</td>
                <td class="px-4 py-3 font-medium text-gray-200">
                  {{ r.item_name || r.adhoc_name }}
                  <span v-if="r.photo_url" class="ml-1 text-blue-400 text-xs">📷</span>
                </td>
                <td class="px-4 py-3 text-right font-mono text-gray-300">{{ r.qty }}</td>
                <td class="px-4 py-3 text-center text-gray-400">{{ r.unit || '—' }}</td>
                <td class="px-4 py-3 text-center">
                  <span class="text-xs font-bold text-amber-400">{{ r.reason || '—' }}</span>
                </td>
                <td class="px-4 py-3 text-right font-mono text-sm"
                  :class="r.estimated_value ? 'text-[#ef4444]' : 'text-gray-600'">
                  {{ r.estimated_value ? '$' + fmtMoney(r.estimated_value) : '—' }}
                </td>
                <td class="px-4 py-3 text-gray-400 text-xs">{{ r.recorded_by_name || '—' }}</td>
                <td class="px-4 py-3 text-gray-500 text-xs">{{ r.note || '—' }}</td>
              </tr>
              <tr v-if="r.photo_url && expandedPhotoId === r.id">
                <td colspan="8" class="px-4 py-3 bg-[#0f1117]">
                  <img :src="resolveUrl(r.photo_url)" alt="耗損照片" class="max-h-64 rounded-lg object-contain" />
                </td>
              </tr>
            </template>
            <tr v-if="filtered.length === 0">
              <td colspan="8" class="px-5 py-10 text-center text-gray-600">無損耗紀錄</td>
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
  </div>
</template>
