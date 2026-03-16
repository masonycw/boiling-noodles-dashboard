<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const records = ref([])
const loading = ref(true)
const expandedId = ref(null)
const details = ref({})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}` }
}

async function load() {
  loading.value = true
  const res = await fetch(`${API_BASE}/stocktake/?limit=50`, { headers: authHeaders() })
  if (res.ok) records.value = await res.json()
  loading.value = false
}

onMounted(load)

async function toggleExpand(r) {
  if (expandedId.value === r.id) { expandedId.value = null; return }
  expandedId.value = r.id
  if (!details.value[r.id]) {
    const res = await fetch(`${API_BASE}/stocktake/${r.id}`, { headers: authHeaders() })
    if (res.ok) {
      const d = await res.json()
      details.value[r.id] = d.items || []
    }
  }
}

const modeLabel = { stocktake: '純盤點', order: '純叫貨', both: '盤點+叫貨' }

function fmtDate(d) {
  return d ? new Date(d).toLocaleString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}
</script>

<template>
  <div>
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase tracking-wider">
            <th class="px-5 py-3 text-left">時間</th>
            <th class="px-5 py-3 text-left">群組</th>
            <th class="px-5 py-3 text-center">模式</th>
            <th class="px-5 py-3 text-center">狀態</th>
            <th class="px-5 py-3 text-center">展開</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="r in records" :key="r.id">
            <tr class="border-b border-[#2d3748] hover:bg-[#1f2937] cursor-pointer transition-colors"
              @click="toggleExpand(r)">
              <td class="px-5 py-3 text-gray-400">{{ fmtDate(r.created_at) }}</td>
              <td class="px-5 py-3 font-semibold text-gray-200">{{ r.group_name || '—' }}</td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs text-blue-400 font-medium">{{ modeLabel[r.mode] || r.mode }}</span>
              </td>
              <td class="px-5 py-3 text-center">
                <span class="text-xs font-bold" :class="r.submitted_at ? 'text-emerald-400' : 'text-amber-400'">
                  {{ r.submitted_at ? '已提交' : '草稿' }}
                </span>
              </td>
              <td class="px-5 py-3 text-center text-gray-500">{{ expandedId === r.id ? '▲' : '▼' }}</td>
            </tr>
            <tr v-if="expandedId === r.id" class="border-b border-[#2d3748] bg-[#0f1117]">
              <td colspan="5" class="px-8 py-4">
                <div v-if="!details[r.id]" class="text-gray-500 text-sm">載入中…</div>
                <table v-else class="w-full text-xs">
                  <thead>
                    <tr class="text-gray-500 border-b border-[#2d3748]">
                      <th class="pb-2 text-left">品項</th>
                      <th class="pb-2 text-right">盤點數量</th>
                      <th class="pb-2 text-right">上次庫存</th>
                      <th class="pb-2 text-right">差異</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="d in details[r.id]" :key="d.id" class="text-gray-400 border-b border-[#1a202c]">
                      <td class="py-1.5">{{ d.item_name }}</td>
                      <td class="py-1.5 text-right">{{ d.counted_qty }}</td>
                      <td class="py-1.5 text-right">{{ d.previous_stock ?? '—' }}</td>
                      <td class="py-1.5 text-right"
                        :class="d.counted_qty !== d.previous_stock ? 'text-amber-400' : 'text-gray-600'">
                        {{ d.previous_stock != null ? (d.counted_qty - d.previous_stock) : '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </td>
            </tr>
          </template>
          <tr v-if="records.length === 0">
            <td colspan="5" class="px-5 py-10 text-center text-gray-600">無盤點紀錄</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
