<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const executors = ref([])
const monthlyKpi = ref(null)
const loading = ref(true)
const expandedId = ref(null)

// Filters
const filterDateFrom = ref(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10))
const filterDateTo = ref(new Date().toISOString().slice(0, 10))
const filterExecutor = ref('')
const filterStatus = ref('')   // '' | 'has_discrepancy' | 'no_discrepancy'

// Pagination
const page = ref(1)
const PAGE_SIZE = 10

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function load() {
  loading.value = true
  const [recRes, execRes, kpiRes] = await Promise.all([
    fetch(`${API_BASE}/stocktake/?limit=500`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/executors`, { headers: authHeaders() }),
    fetch(`${API_BASE}/stocktake/monthly-kpi`, { headers: authHeaders() }),
  ])
  if (recRes.ok) records.value = await recRes.json()
  if (execRes.ok) executors.value = await execRes.json()
  if (kpiRes.ok) monthlyKpi.value = await kpiRes.json()
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
  if (filterStatus.value === 'has_discrepancy') {
    list = list.filter(r => r.discrepancy_count > 0)
  } else if (filterStatus.value === 'no_discrepancy') {
    list = list.filter(r => r.discrepancy_count === 0)
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
      <select v-model="filterStatus"
        class="bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]">
        <option value="">全部</option>
        <option value="has_discrepancy">有差異</option>
        <option value="no_discrepancy">無差異</option>
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
            </tr>
          </thead>
          <tbody>
            <template v-for="r in paginated" :key="r.id">
              <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] transition-colors cursor-pointer"
                @click="toggleExpand(r)">
                <td class="px-4 py-3 text-gray-400 text-xs">{{ fmtDate(r.created_at) }}</td>
                <td class="px-4 py-3 text-gray-300 font-medium">{{ r.executor_name || '—' }}</td>
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
              </tr>
              <!-- Expanded detail -->
              <tr v-if="expandedId === r.id" class="border-b border-[#2d3748]"
                :style="r.discrepancy_count > 0 ? 'background:rgba(239,68,68,0.04)' : 'background:#0f1117'">
                <td colspan="7" class="px-6 py-4">
                  <p class="text-xs font-bold text-[#9ca3af] mb-3">
                    盤點詳細 — {{ r.executor_name || 'N/A' }} · {{ fmtDate(r.created_at) }}
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
              <td colspan="7" class="px-5 py-10 text-center text-gray-600">無盤點紀錄</td>
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
