<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// --- State ---
const groups = ref([])
const selectedGroup = ref(null)
const mode = ref('stocktake')          // 'stocktake' | 'order' | 'both'
const items = ref([])
const counts = ref({})                 // { item_id: qty }
const loading = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const error = ref('')

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

// --- Load groups ---
onMounted(async () => {
  const res = await fetch(`${API_BASE}/stocktake/groups`, { headers: authHeaders() })
  if (res.ok) {
    groups.value = await res.json()
    if (groups.value.length) selectGroup(groups.value[0])
  }
})

// --- Load items for selected group ---
async function selectGroup(g) {
  selectedGroup.value = g
  counts.value = {}
  submitted.value = false
  error.value = ''
  loading.value = true
  try {
    const res = await fetch(
      `${API_BASE}/inventory/items?stocktake_group_id=${g.id}&limit=200`,
      { headers: authHeaders() }
    )
    items.value = res.ok ? await res.json() : []
  } finally {
    loading.value = false
  }
}

// --- Qty helpers ---
function getQty(id) { return counts.value[id] ?? '' }
function setQty(id, val) {
  const n = parseFloat(val)
  if (val === '' || isNaN(n)) {
    delete counts.value[id]
  } else {
    counts.value[id] = n
  }
}
function increment(id) { counts.value[id] = (counts.value[id] ?? 0) + 1 }
function decrement(id) {
  const cur = counts.value[id] ?? 0
  if (cur > 0) counts.value[id] = cur - 1
}

const filledCount = computed(() => Object.keys(counts.value).length)

// --- Submit ---
async function submit() {
  if (filledCount.value === 0) { error.value = '請至少輸入一筆數量'; return }
  submitting.value = true
  error.value = ''
  try {
    // 1. Create stocktake session
    const createRes = await fetch(`${API_BASE}/stocktake/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        group_id: selectedGroup.value.id,
        mode: mode.value
      })
    })
    if (!createRes.ok) throw new Error('建立盤點失敗')
    const session = await createRes.json()

    // 2. Patch counted items
    const itemPayloads = Object.entries(counts.value).map(([item_id, qty]) => ({
      item_id: parseInt(item_id),
      counted_qty: qty
    }))
    const patchRes = await fetch(`${API_BASE}/stocktake/${session.id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ items: itemPayloads })
    })
    if (!patchRes.ok) throw new Error('更新數量失敗')

    // 3. Submit
    const submitRes = await fetch(`${API_BASE}/stocktake/${session.id}/submit`, {
      method: 'PUT',
      headers: authHeaders()
    })
    if (!submitRes.ok) throw new Error('提交失敗')

    submitted.value = true
  } catch (e) {
    error.value = e.message || '提交失敗'
  } finally {
    submitting.value = false
  }
}

function reset() {
  submitted.value = false
  counts.value = {}
  if (selectedGroup.value) selectGroup(selectedGroup.value)
}

const modeOptions = [
  { value: 'stocktake', label: '純盤點' },
  { value: 'order',     label: '純叫貨' },
  { value: 'both',      label: '盤點+叫貨' },
]
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-24">
    <!-- Header -->
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4 sticky top-0 z-10">
      <h1 class="text-xl font-extrabold text-slate-800">庫存盤點</h1>

      <!-- Group chips -->
      <div class="flex gap-2 mt-3 overflow-x-auto pb-1 scrollbar-hide">
        <button
          v-for="g in groups" :key="g.id"
          @click="selectGroup(g)"
          class="shrink-0 px-4 py-1.5 rounded-full text-sm font-bold transition-all"
          :class="selectedGroup?.id === g.id
            ? 'bg-orange-500 text-white shadow'
            : 'bg-slate-100 text-slate-500'"
        >
          {{ g.name }}
        </button>
      </div>

      <!-- Mode toggle -->
      <div class="flex gap-2 mt-3">
        <button
          v-for="m in modeOptions" :key="m.value"
          @click="mode = m.value"
          class="flex-1 py-1.5 rounded-xl text-xs font-bold border transition-all"
          :class="mode === m.value
            ? 'bg-blue-500 text-white border-blue-500'
            : 'bg-white text-slate-500 border-slate-200'"
        >
          {{ m.label }}
        </button>
      </div>
    </div>

    <!-- Success screen -->
    <div v-if="submitted" class="flex flex-col items-center justify-center px-6 py-20 text-center">
      <div class="text-6xl mb-4">✅</div>
      <h2 class="text-xl font-extrabold text-slate-800">盤點已提交</h2>
      <p class="text-slate-400 text-sm mt-2">庫存數量已更新</p>
      <button @click="reset"
        class="mt-8 bg-orange-500 text-white font-bold px-8 py-3 rounded-2xl active:scale-95 transition-transform">
        繼續盤點
      </button>
    </div>

    <!-- Item list -->
    <div v-else>
      <div v-if="loading" class="flex justify-center py-16">
        <svg class="animate-spin h-8 w-8 text-orange-400" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
      </div>

      <div v-else-if="items.length === 0" class="text-center py-16 text-slate-400">
        此分組暫無品項
      </div>

      <div v-else class="divide-y divide-slate-100">
        <div
          v-for="item in items" :key="item.id"
          class="bg-white px-4 py-3 flex items-center gap-3"
        >
          <!-- Item info -->
          <div class="flex-1 min-w-0">
            <p class="font-bold text-slate-800 truncate">{{ item.name }}</p>
            <p class="text-xs text-slate-400">
              庫存 {{ item.current_stock ?? 0 }} {{ item.unit }}
            </p>
          </div>

          <!-- Qty control -->
          <div class="flex items-center gap-1">
            <button @click="decrement(item.id)"
              class="w-8 h-8 rounded-full bg-slate-100 text-slate-600 font-bold flex items-center justify-center active:bg-slate-200">
              −
            </button>
            <input
              type="number" inputmode="decimal" min="0"
              :value="getQty(item.id)"
              @input="setQty(item.id, $event.target.value)"
              class="w-16 text-center border border-slate-200 rounded-xl py-1.5 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-orange-400"
              :class="counts[item.id] !== undefined ? 'border-orange-400 bg-orange-50' : ''"
              :placeholder="item.unit"
            />
            <button @click="increment(item.id)"
              class="w-8 h-8 rounded-full bg-orange-500 text-white font-bold flex items-center justify-center active:bg-orange-600">
              +
            </button>
          </div>
        </div>
      </div>

      <!-- Submit bar -->
      <div v-if="!loading" class="fixed bottom-16 inset-x-0 px-4 py-3 bg-white border-t border-slate-100 shadow-lg">
        <div v-if="error" class="text-rose-500 text-xs text-center mb-2">{{ error }}</div>
        <button
          @click="submit"
          :disabled="submitting || filledCount === 0"
          class="w-full bg-orange-500 text-white font-bold py-3.5 rounded-2xl shadow active:scale-95 transition-transform disabled:opacity-40"
        >
          <span v-if="submitting">提交中…</span>
          <span v-else>提交盤點（已填 {{ filledCount }} 筆）</span>
        </button>
      </div>
    </div>
  </div>
</template>
