<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const settings = ref([])
const notifications = ref([])
const loading = ref(true)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

async function load() {
  loading.value = true
  const [sRes, nRes] = await Promise.all([
    fetch(`${API_BASE}/notifications/settings`, { headers: authHeaders() }),
    fetch(`${API_BASE}/notifications?limit=30`, { headers: authHeaders() }),
  ])
  if (sRes.ok) settings.value = await sRes.json()
  if (nRes.ok) notifications.value = await nRes.json()
  loading.value = false
}

onMounted(load)

async function toggleSetting(rule) {
  const res = await fetch(`${API_BASE}/notifications/settings/${rule.key}`, {
    method: 'PUT', headers: authHeaders()
  })
  if (res.ok) {
    const d = await res.json()
    rule.is_enabled = d.is_enabled
  }
}

async function toggleRead(notif) {
  const res = await fetch(`${API_BASE}/notifications/${notif.id}/read`, {
    method: 'PUT', headers: authHeaders()
  })
  if (res.ok) {
    const d = await res.json()
    notif.is_read = d.is_read
  }
}

function fmtDate(d) {
  return d ? new Date(d).toLocaleDateString('zh-TW') : '—'
}
</script>

<template>
  <div>
    <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
    <div v-else class="grid grid-cols-[280px_1fr] gap-5">

      <!-- Left: Rules -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 h-fit">
        <p class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-4">通知規則</p>
        <div class="space-y-3">
          <div v-for="rule in settings" :key="rule.key" class="flex items-center justify-between">
            <span class="text-sm text-gray-300">{{ rule.label }}</span>
            <!-- Toggle -->
            <button @click="toggleSetting(rule)"
              class="relative w-11 h-6 rounded-full transition-colors focus:outline-none"
              :class="rule.is_enabled ? 'bg-[#e85d04]' : 'bg-[#374151]'">
              <span class="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform"
                :class="rule.is_enabled ? 'translate-x-5' : 'translate-x-0.5'"></span>
            </button>
          </div>
        </div>
      </div>

      <!-- Right: History -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
        <div class="px-4 py-3 border-b border-[#2d3748]">
          <p class="text-xs font-bold text-gray-500 uppercase tracking-wider">通知歷史</p>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase tracking-wider">
              <th class="px-4 py-3 text-left">日期</th>
              <th class="px-4 py-3 text-center">類型</th>
              <th class="px-4 py-3 text-left">內容</th>
              <th class="px-4 py-3 text-center">狀態</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="n in notifications" :key="n.id"
              class="hover:bg-[#1f2937] cursor-pointer transition-colors"
              :class="n.is_read ? 'opacity-60' : ''"
              @click="toggleRead(n)">
              <td class="px-4 py-3 text-gray-500 text-xs">{{ fmtDate(n.created_at) }}</td>
              <td class="px-4 py-3 text-center text-gray-400 text-xs">{{ n.type }}</td>
              <td class="px-4 py-3 text-gray-300">
                <p class="font-medium text-xs">{{ n.title }}</p>
                <p v-if="n.body" class="text-gray-500 text-xs mt-0.5 truncate max-w-xs">{{ n.body }}</p>
              </td>
              <td class="px-4 py-3 text-center">
                <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                  :class="n.is_read ? 'bg-gray-700 text-gray-400' : 'bg-red-900/40 text-red-400'">
                  {{ n.is_read ? '已讀' : '未讀' }}
                </span>
              </td>
            </tr>
            <tr v-if="notifications.length === 0">
              <td colspan="4" class="px-5 py-10 text-center text-gray-600">無通知紀錄</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
