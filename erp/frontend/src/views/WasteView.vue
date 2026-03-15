<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// --- State ---
const items = ref([])
const search = ref('')
const selectedItem = ref(null)
const adhocName = ref('')
const useAdhoc = ref(false)
const qty = ref('')
const unit = ref('')
const reason = ref('其他')
const note = ref('')
const submitting = ref(false)
const submitted = ref(false)
const error = ref('')

const reasons = ['過期', '破損', '烹調損耗', '其他']

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}

onMounted(async () => {
  const res = await fetch(`${API_BASE}/inventory/items?limit=500`, { headers: authHeaders() })
  if (res.ok) items.value = await res.json()
})

const filteredItems = computed(() => {
  if (!search.value.trim()) return items.value.slice(0, 20)
  const q = search.value.toLowerCase()
  return items.value.filter(i => i.name.toLowerCase().includes(q)).slice(0, 20)
})

function selectItem(item) {
  selectedItem.value = item
  unit.value = item.unit || ''
  search.value = item.name
  useAdhoc.value = false
}

function clearItem() {
  selectedItem.value = null
  search.value = ''
}

const canSubmit = computed(() =>
  (selectedItem.value || (useAdhoc.value && adhocName.value.trim())) &&
  parseFloat(qty.value) > 0
)

async function submit() {
  if (!canSubmit.value) { error.value = '請選擇品項並填寫數量'; return }
  submitting.value = true
  error.value = ''
  try {
    const payload = {
      qty: parseFloat(qty.value),
      unit: unit.value || null,
      reason: reason.value,
      note: note.value || null
    }
    if (selectedItem.value) {
      payload.item_id = selectedItem.value.id
    } else {
      payload.adhoc_name = adhocName.value.trim()
    }

    const res = await fetch(`${API_BASE}/waste/`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(payload)
    })
    if (!res.ok) throw new Error('提交失敗')
    submitted.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}

function reset() {
  submitted.value = false
  selectedItem.value = null
  adhocName.value = ''
  useAdhoc.value = false
  search.value = ''
  qty.value = ''
  unit.value = ''
  reason.value = '其他'
  note.value = ''
  error.value = ''
}
</script>

<template>
  <div class="min-h-full bg-slate-50 pb-8">
    <!-- Header -->
    <div class="bg-white border-b border-slate-100 px-4 pt-12 pb-4">
      <h1 class="text-xl font-extrabold text-slate-800">記錄損耗</h1>
      <p class="text-sm text-slate-400 mt-0.5">記錄食材耗損、破損或過期品項</p>
    </div>

    <!-- Success -->
    <div v-if="submitted" class="flex flex-col items-center justify-center px-6 py-20 text-center">
      <div class="text-6xl mb-4">✅</div>
      <h2 class="text-xl font-extrabold text-slate-800">損耗已記錄</h2>
      <p class="text-slate-400 text-sm mt-2">感謝確實記錄</p>
      <button @click="reset"
        class="mt-8 bg-rose-500 text-white font-bold px-8 py-3 rounded-2xl active:scale-95 transition-transform">
        繼續記錄
      </button>
    </div>

    <!-- Form -->
    <div v-else class="px-4 py-5 space-y-5">

      <!-- Item search -->
      <div>
        <label class="block text-sm font-bold text-slate-600 mb-2">品項選擇</label>

        <!-- Toggle adhoc -->
        <div class="flex gap-2 mb-3">
          <button @click="useAdhoc = false; clearItem()"
            class="px-3 py-1 rounded-full text-xs font-bold transition-all"
            :class="!useAdhoc ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-500'">
            從庫存選
          </button>
          <button @click="useAdhoc = true; clearItem()"
            class="px-3 py-1 rounded-full text-xs font-bold transition-all"
            :class="useAdhoc ? 'bg-orange-500 text-white' : 'bg-slate-100 text-slate-500'">
            手動輸入
          </button>
        </div>

        <!-- Inventory search -->
        <div v-if="!useAdhoc">
          <input
            v-if="!selectedItem"
            v-model="search"
            type="text"
            placeholder="搜尋品項名稱…"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
          <div v-if="!selectedItem && search" class="mt-1 bg-white border border-slate-200 rounded-xl shadow-md overflow-hidden max-h-48 overflow-y-auto">
            <button
              v-for="item in filteredItems" :key="item.id"
              @click="selectItem(item)"
              class="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-orange-50 border-b border-slate-50 last:border-0"
            >
              <span class="font-bold text-slate-800 text-sm">{{ item.name }}</span>
              <span class="text-xs text-slate-400 ml-auto">{{ item.unit }}</span>
            </button>
            <div v-if="filteredItems.length === 0" class="px-4 py-3 text-slate-400 text-sm">查無品項</div>
          </div>

          <!-- Selected item chip -->
          <div v-if="selectedItem" class="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-xl px-4 py-2.5">
            <span class="font-bold text-orange-700 text-sm flex-1">{{ selectedItem.name }}</span>
            <button @click="clearItem" class="text-orange-400 hover:text-orange-600 font-bold">✕</button>
          </div>
        </div>

        <!-- Adhoc name -->
        <div v-else>
          <input
            v-model="adhocName"
            type="text"
            placeholder="品項名稱（任意輸入）"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
        </div>
      </div>

      <!-- Quantity + Unit -->
      <div class="flex gap-3">
        <div class="flex-1">
          <label class="block text-sm font-bold text-slate-600 mb-2">數量</label>
          <input
            v-model="qty"
            type="number" inputmode="decimal" min="0" step="0.1"
            placeholder="0"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
        </div>
        <div class="w-24">
          <label class="block text-sm font-bold text-slate-600 mb-2">單位</label>
          <input
            v-model="unit"
            type="text"
            placeholder="kg / 個"
            class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
        </div>
      </div>

      <!-- Reason -->
      <div>
        <label class="block text-sm font-bold text-slate-600 mb-2">原因</label>
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="r in reasons" :key="r"
            @click="reason = r"
            class="py-2.5 rounded-xl text-sm font-bold border transition-all"
            :class="reason === r
              ? 'bg-rose-500 text-white border-rose-500'
              : 'bg-white text-slate-500 border-slate-200'"
          >
            {{ r }}
          </button>
        </div>
      </div>

      <!-- Note -->
      <div>
        <label class="block text-sm font-bold text-slate-600 mb-2">備註（選填）</label>
        <textarea
          v-model="note"
          rows="2"
          placeholder="補充說明…"
          class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400 resize-none"
        />
      </div>

      <!-- Error -->
      <div v-if="error" class="text-rose-500 text-sm font-medium text-center">{{ error }}</div>

      <!-- Submit -->
      <button
        @click="submit"
        :disabled="submitting || !canSubmit"
        class="w-full bg-rose-500 text-white font-bold py-4 rounded-2xl shadow active:scale-95 transition-transform disabled:opacity-40"
      >
        <span v-if="submitting">提交中…</span>
        <span v-else>確認記錄損耗</span>
      </button>
    </div>
  </div>
</template>
