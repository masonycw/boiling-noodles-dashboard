<script setup>
import { ref, onMounted, computed } from 'vue'

const orders = ref([])
const isLoading = ref(true)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const selectedOrder = ref(null)
const selectedOrderDetails = ref([])
const isDetailLoading = ref(false)

const fetchOrders = async () => {
  try {
    const res = await fetch(`${API_BASE}/inventory/orders?days_limit=7`)
    orders.value = await res.json()
  } catch (err) {
    console.error('Failed to fetch history:', err)
  } finally {
    isLoading.value = false
  }
}

const groupedOrders = computed(() => {
  const groups = {}
  orders.value.forEach(order => {
    // Treat null expected delivery date as just its created_at date for grouping
    const dateStr = order.expected_delivery_date 
      ? order.expected_delivery_date.substring(0, 10) 
      : order.created_at.substring(0, 10)
    
    const key = `${order.vendor_name}_${dateStr}`
    if (!groups[key]) {
      groups[key] = {
        ids: [],
        vendor_name: order.vendor_name,
        dateStr: dateStr,
        created_at: order.created_at,
        total_items: 0,
        status: 'received',
        orders: [],
      }
    }
    groups[key].ids.push(order.id)
    groups[key].orders.push(order)
    groups[key].total_items += order.total_items
    if (order.status === 'pending' || order.status === 'ordered') {
      groups[key].status = 'pending'
    }
  })
  
  return Object.values(groups).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
})

const showDetails = async (groupedOrder) => {
  selectedOrder.value = groupedOrder
  isDetailLoading.value = true
  selectedOrderDetails.value = []
  
  try {
    const allDetails = []
    for (const id of groupedOrder.ids) {
      const res = await fetch(`${API_BASE}/inventory/orders/${id}`)
      const data = await res.json()
      allDetails.push(...data)
    }
    
    const agg = {}
    allDetails.forEach(item => {
      const k = `${item.name}_${item.unit}`
      if (!agg[k]) agg[k] = { ...item }
      else agg[k].qty += item.qty
    })
    selectedOrderDetails.value = Object.values(agg)
  } catch (err) {
    console.error('Failed to fetch details:', err)
  } finally {
    isDetailLoading.value = false
  }
}

onMounted(fetchOrders)

const showReceiveModal = ref(false)
const receivingOrder = ref(null)
const receiveForm = ref({ amount_paid: '', note: '' })
const isReceiving = ref(false)

const openReceiveModal = (order) => {
  receivingOrder.value = order
  receiveForm.value = { amount_paid: '', note: '' }
  showReceiveModal.value = true
}

const submitReceive = async () => {
  if (receiveForm.value.amount_paid === '') {
    alert('請輸入付款金額 (若無則輸入 0)')
    return
  }
  
  isReceiving.value = true
  try {
    let first = true
    for (const id of receivingOrder.value.ids) {
      const amount = first ? Number(receiveForm.value.amount_paid) : 0
      const note = first ? receiveForm.value.note : '(依附於同批次收貨)'
      
      const res = await fetch(`${API_BASE}/inventory/orders/${id}/receive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_paid: amount, note: note })
      })
      if (!res.ok) throw new Error('部分收貨失敗')
      first = false
    }
    
    showReceiveModal.value = false
    alert('點收完畢，已同步更新金流！')
    fetchOrders()
  } catch (err) {
    alert('網路錯誤或部分失敗，請重新整理查看')
  } finally {
    isReceiving.value = false
  }
}

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

      <div v-else-if="groupedOrders.length === 0" class="text-center py-20 bg-white rounded-3xl border border-dashed border-slate-300">
        <p class="text-slate-400">目前尚無叫貨紀錄</p>
      </div>

      <div v-else class="space-y-4">
        <div 
          v-for="order in groupedOrders" 
          :key="order.ids.join('_')"
          class="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm flex items-center justify-between"
        >
          <div class="space-y-1">
            <div class="flex items-center space-x-2">
              <span class="font-black text-slate-900 text-lg">{{ order.vendor_name }}</span>
              <span :class="['text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider', getStatusColor(order.status)]">
                {{ order.status === 'pending' ? '待收貨' : '已收貨' }}
              </span>
            </div>
            <p class="text-xs text-slate-400 font-bold">預計到貨日: {{ order.dateStr }}</p>
            <p class="text-[10px] text-slate-300">共 {{ order.ids.length }} 筆合併叫貨單</p>
          </div>
          
          <div class="text-right flex flex-col items-end justify-between h-full">
            <p class="text-lg font-black text-slate-900">{{ order.total_items }} <span class="text-xs font-normal text-slate-400">總品項</span></p>
            <div class="mt-2 space-x-3">
              <button 
                v-if="order.status === 'pending' || order.status === 'ordered'"
                @click="openReceiveModal(order)" 
                class="bg-emerald-500 text-white px-3 py-1 rounded-lg text-xs font-bold shadow-sm hover:bg-emerald-400 transition-colors"
              >
                點收貨物
              </button>
              <button @click="showDetails(order)" class="text-orange-500 text-xs font-bold hover:underline">展開清單</button>
            </div>
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

    <!-- Modal for Receiving Order -->
    <div v-if="showReceiveModal" class="fixed inset-0 z-[60] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div @click="showReceiveModal = false" class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
      
      <div class="relative w-full max-w-sm bg-white rounded-t-[2.5rem] sm:rounded-[2.5rem] shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-300 p-8 pb-10">
        <h3 class="text-2xl font-black text-slate-900 mb-2">點收貨物</h3>
        <p class="text-slate-500 text-sm mb-6">點收 {{ receivingOrder.vendor_name }} 的訂單</p>
        
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1">實際付款金額 (若為月結請填 0)</label>
            <input v-model.number="receiveForm.amount_paid" type="number" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 text-lg font-bold focus:ring-2 focus:ring-emerald-500/20" placeholder="$ 0" />
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1">備註/差異提醒</label>
            <textarea v-model="receiveForm.note" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 focus:ring-2 focus:ring-emerald-500/20" rows="2" placeholder="(選填) 例如：少送兩顆高麗菜"></textarea>
          </div>
          <div class="flex space-x-3 mt-4">
            <button @click="showReceiveModal = false" class="flex-1 bg-slate-100 text-slate-500 font-bold py-4 rounded-2xl">取消</button>
            <button 
              @click="submitReceive" 
              :disabled="isReceiving"
              class="flex-1 bg-emerald-500 text-white font-bold py-4 rounded-2xl shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              確認點收
            </button>
          </div>
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
