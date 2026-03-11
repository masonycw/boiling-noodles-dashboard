<script setup>
import { ref, onMounted } from 'vue'

const orders = ref([])
const isLoading = ref(true)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const selectedOrder = ref(null)
const selectedOrderDetails = ref([])
const isDetailLoading = ref(false)

const fetchOrders = async () => {
  try {
    const res = await fetch(`${API_BASE}/inventory/orders`)
    orders.value = await res.json()
  } catch (err) {
    console.error('Failed to fetch history:', err)
  } finally {
    isLoading.value = false
  }
}

const showDetails = async (order) => {
  selectedOrder.value = order
  isDetailLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}`)
    selectedOrderDetails.value = await res.json()
  } catch (err) {
    console.error('Failed to fetch details:', err)
  } finally {
    isDetailLoading.value = false
  }
}

onMounted(fetchOrders)

const formatDate = (dateStr) => {
  return new Date(dateStr).toLocaleString('zh-TW', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getStatusColor = (status) => {
  switch (status) {
    case 'pending': return 'bg-amber-100 text-amber-700'
    case 'ordered': return 'bg-blue-100 text-blue-700'
    case 'received': return 'bg-emerald-100 text-emerald-700'
    default: return 'bg-slate-100 text-slate-700'
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 pb-24">
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 px-4 py-6">
      <h2 class="text-2xl font-black text-slate-900">叫貨紀錄</h2>
      <p class="text-sm text-slate-500">查看過去的訂單狀態</p>
    </header>

    <main class="px-4 py-6">
      <div v-if="isLoading" class="flex flex-col items-center justify-center py-20">
        <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full mb-4"></div>
        <p class="text-slate-400">載入紀錄中...</p>
      </div>

      <div v-else-if="orders.length === 0" class="text-center py-20 bg-white rounded-3xl border border-dashed border-slate-300">
        <p class="text-slate-400">目前尚無叫貨紀錄</p>
      </div>

      <div v-else class="space-y-4">
        <div 
          v-for="order in orders" 
          :key="order.id"
          class="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm flex items-center justify-between"
        >
          <div class="space-y-1">
            <div class="flex items-center space-x-2">
              <span class="font-black text-slate-900 text-lg">{{ order.vendor_name }}</span>
              <span :class="['text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider', getStatusColor(order.status)]">
                {{ order.status }}
              </span>
            </div>
            <p class="text-xs text-slate-400">{{ formatDate(order.created_at) }}</p>
          </div>
          
          <div class="text-right">
            <p class="text-lg font-black text-slate-900">{{ order.total_items }} <span class="text-xs font-normal text-slate-400">項品項</span></p>
            <button @click="showDetails(order)" class="text-orange-500 text-xs font-bold hover:underline">查看詳情</button>
          </div>
        </div>
      </div>
    </main>

    <!-- Modal for Order Details -->
    <div v-if="selectedOrder" class="fixed inset-0 z-[60] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div @click="selectedOrder = null" class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
      
      <div class="relative w-full max-w-lg bg-white rounded-t-[2.5rem] sm:rounded-[2.5rem] shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-300">
        <div class="p-8 pb-10">
          <div class="flex justify-between items-start mb-6">
            <div>
              <h3 class="text-2xl font-black text-slate-900">{{ selectedOrder.vendor_name }}</h3>
              <p class="text-slate-400 text-sm italic">{{ formatDate(selectedOrder.created_at) }}</p>
            </div>
            <button @click="selectedOrder = null" class="bg-slate-100 p-2 rounded-full text-slate-400 hover:bg-slate-200">
              <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div v-if="isDetailLoading" class="py-12 flex justify-center">
             <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full"></div>
          </div>

          <div v-else class="space-y-4 max-h-[50vh] overflow-y-auto pr-2 custom-scrollbar">
            <div v-for="item in selectedOrderDetails" :key="item.name" class="flex justify-between items-center py-3 border-b border-slate-50">
              <span class="text-slate-700 font-bold">{{ item.name }}</span>
              <span class="text-slate-900 font-black">{{ item.qty }} <span class="text-xs font-normal text-slate-400">{{ item.unit }}</span></span>
            </div>
          </div>

          <button @click="selectedOrder = null" class="w-full mt-8 bg-slate-900 text-white font-bold py-4 rounded-2xl active:scale-95 transition-all">
            關閉視窗
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
</style>
