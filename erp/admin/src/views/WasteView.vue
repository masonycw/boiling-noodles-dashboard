<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const summary = ref(null)
const loading = ref(true)
const daysLimit = ref(30)
const filterReason = ref('')

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function load() {
  loading.value = true
  const [recRes, sumRes] = await Promise.all([
    fetch(`${API_BASE}/waste/?days_limit=${daysLimit.value}&limit=200`, { headers: authHeaders() }),
    fetch(`${API_BASE}/waste/summary?days_limit=${daysLimit.value}`, { headers: authHeaders() }),
  ])
  if (recRes.ok) records.value = await recRes.json()
  if (sumRes.ok) summary.value = await sumRes.json()
  loading.value = false
}

onMounted(load)

const reasons = ['過期', '破損', '烹調損耗', '其他']

function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}

const filtered = () => {
  if (!filterReason.value) return records.value
  return records.value.filter(r => r.reason === filterReason.value)
}
</script>

<template>
  <div class="space-y-5">
    <!-- Toolbar -->
    <div class="flex items-center gap-3 flex-wrap">
      <select v-model.number="daysLimit" @change="load"
        class="bg-[#111827] border border-[#374151] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
        <option :value="7">近 7 天</option>
        <option :value="30">近 30 天</option>
        <option :value="90">近 90 天</option>
      </select>
      <select v-model="filterReason"
        class="bg-[#111827] border border-[#374151] text-gray-400 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
        <option value="">全部原因</option>
        <option v-for="r in reasons" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>

    <!-- Summary cards -->
    <div v-if="summary" class="grid grid-cols-4 gap-3">
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 text-center">
        <p class="text-xs text-gray-500 uppercase tracking-wider">總筆數</p>
        <p class="text-2xl font-bold text-red-400 mt-1">{{ summary.total_records }}</p>
      </div>
      <div v-for="r in (summary.by_reason || [])" :key="r.reason"
        class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 text-center">
        <p class="text-xs text-gray-500">{{ r.reason }}</p>
        <p class="text-2xl font-bold text-amber-400 mt-1">{{ r.count }}</p>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">時間</th>
            <th class="px-5 py-3 text-left">品項</th>
            <th class="px-5 py-3 text-right">數量</th>
            <th class="px-5 py-3 text-center">原因</th>
            <th class="px-5 py-3 text-left">備註</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="r in filtered()" :key="r.id" class="hover:bg-[#1f2937] transition-colors">
            <td class="px-5 py-3 text-gray-500">{{ fmtDate(r.created_at) }}</td>
            <td class="px-5 py-3 font-medium text-gray-200">{{ r.item_name || r.adhoc_name }}</td>
            <td class="px-5 py-3 text-right text-gray-300">{{ r.qty }} {{ r.unit }}</td>
            <td class="px-5 py-3 text-center">
              <span class="text-xs font-bold text-amber-400">{{ r.reason }}</span>
            </td>
            <td class="px-5 py-3 text-gray-500 text-xs">{{ r.note || '—' }}</td>
          </tr>
          <tr v-if="filtered().length === 0">
            <td colspan="5" class="px-5 py-10 text-center text-gray-600">無損耗紀錄</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
