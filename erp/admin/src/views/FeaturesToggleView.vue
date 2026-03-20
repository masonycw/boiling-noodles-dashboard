<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const toast = ref('')
const saving = ref(false)

const features = ref([
  { key: 'waste_record', label: '耗損記錄', customName: '', enabled: true, icon: '🗑️', desc: '員工可在 App 記錄食材耗損' },
  { key: 'petty_cash', label: '零用金管理', customName: '', enabled: true, icon: '💰', desc: '啟用零用金收支與日結功能' },
  { key: 'accounts_payable', label: '應付帳款', customName: '', enabled: true, icon: '🧾', desc: '月結廠商的應付帳款追蹤' },
  { key: 'recurring_charges', label: '重複預約費用', customName: '', enabled: false, icon: '🔁', desc: '定期固定支出自動提醒' },
  { key: 'ratio_costs', label: '比例費用', customName: '', enabled: false, icon: '📐', desc: '依營收比例計算的費用（如平台抽成）' },
  { key: 'reports', label: '損益報表', customName: '', enabled: true, icon: '📈', desc: '月度損益分析報表' },
])

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }

async function load() {
  try {
    const res = await fetch(`${API_BASE}/settings/features`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      if (Array.isArray(data)) features.value = data
    }
  } catch (e) { /* 使用預設值 */ }
}

async function save() {
  saving.value = true
  try {
    const res = await fetch(`${API_BASE}/settings/features`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(features.value)
    })
    if (res.ok) showToast('✓ 功能開關已儲存')
    else showToast('⚠ 儲存失敗（API 尚未實作）')
  } catch (e) { showToast('⚠ 儲存失敗') } finally { saving.value = false }
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748]">
        <h3 class="text-sm font-bold text-gray-200">功能模組開關</h3>
        <p class="text-xs text-gray-500 mt-0.5">啟用或停用系統功能模組，並可自訂 App 顯示名稱</p>
      </div>

      <div class="divide-y divide-[#2d3748]">
        <div v-for="f in features" :key="f.key" class="px-5 py-4 flex items-center gap-4">
          <span class="text-xl w-8">{{ f.icon }}</span>
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <p class="text-sm font-medium text-gray-200">{{ f.label }}</p>
              <input v-model="f.customName" type="text" :placeholder="`自訂名稱（預設：${f.label}）`"
                class="text-xs bg-[#0f1117] border border-[#2d3748] text-gray-400 rounded px-2 py-0.5 w-48 focus:outline-none focus:border-blue-400" />
            </div>
            <p class="text-xs text-gray-600 mt-0.5">{{ f.desc }}</p>
          </div>
          <button @click="f.enabled = !f.enabled"
            class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
            :class="f.enabled ? 'bg-blue-500' : 'bg-gray-700'">
            <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="f.enabled ? 'translate-x-6' : 'translate-x-1'"></span>
          </button>
        </div>
      </div>

      <div class="px-5 py-4 border-t border-[#2d3748] flex justify-end">
        <button @click="save" :disabled="saving"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-5 py-2 rounded-lg text-sm transition-colors disabled:opacity-50">
          {{ saving ? '儲存中…' : '儲存設定' }}
        </button>
      </div>
    </div>

    <div class="bg-amber-900/20 border border-amber-500/30 rounded-xl px-5 py-4">
      <p class="text-xs text-amber-200/70">功能開關需後端 <code class="text-amber-300">/api/v1/settings/features</code> 支援（D1 完整實作後生效）。自訂名稱目前為前端暫存。</p>
    </div>
  </div>
</template>
