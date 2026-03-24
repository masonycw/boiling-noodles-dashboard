<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const toast = ref('')
const saving = ref(false)

const settings = ref({
  stocktake_history_days: 7,
  order_history_days: 14,
  petty_cash_history_days: 2,
  waste_history_days: 7,
})

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

async function load() {
  try {
    const res = await fetch(`${API_BASE}/admin/settings/`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      for (const key of Object.keys(settings.value)) {
        if (data[key] !== undefined) settings.value[key] = Number(data[key])
      }
    }
  } catch {}
}

async function save() {
  saving.value = true
  try {
    const promises = Object.entries(settings.value).map(([key, value]) =>
      fetch(`${API_BASE}/admin/settings/${key}`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ value: String(value) })
      })
    )
    await Promise.all(promises)
    showToast('✓ 顯示設置已儲存')
  } catch { showToast('⚠ 儲存失敗') } finally { saving.value = false }
}

onMounted(load)

const settingItems = [
  { key: 'stocktake_history_days', label: 'App 盤點紀錄顯示天數', icon: '🗂️', desc: 'App 前台可查看的盤點歷史天數' },
  { key: 'order_history_days',     label: 'App 叫貨紀錄顯示天數', icon: '🚚', desc: 'App 前台可查看的叫貨歷史天數' },
  { key: 'petty_cash_history_days',label: 'App 零用金顯示天數',   icon: '💰', desc: 'App 前台可查看的零用金紀錄天數' },
  { key: 'waste_history_days',     label: 'App 耗損紀錄顯示天數', icon: '🗑️', desc: 'App 前台可查看的耗損歷史天數' },
]
</script>

<template>
  <div>
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div>
          <h3 class="text-sm font-bold text-gray-200">App 歷史紀錄顯示設定</h3>
          <p class="text-xs text-gray-500 mt-0.5">控制 App 前台各模組可顯示的歷史資料天數</p>
        </div>
        <button @click="save" :disabled="saving"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-5 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 shrink-0">
          {{ saving ? '儲存中…' : '儲存設定' }}
        </button>
      </div>

      <div class="divide-y divide-[#2d3748]">
        <div v-for="item in settingItems" :key="item.key" class="px-5 py-4 flex items-center gap-4">
          <span class="text-xl">{{ item.icon }}</span>
          <div class="flex-1">
            <p class="text-sm text-gray-200">{{ item.label }}</p>
            <p class="text-xs text-gray-500 mt-0.5">{{ item.desc }}</p>
          </div>
          <div class="flex items-center gap-2">
            <input v-model.number="settings[item.key]" type="number" min="1" max="365"
              class="w-20 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:border-blue-400" />
            <span class="text-sm text-gray-500">天</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
