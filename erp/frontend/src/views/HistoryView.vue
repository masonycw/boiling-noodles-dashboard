<script setup>
import { ref, onMounted, computed } from 'vue'

const orders = ref([])
const isLoading = ref(true)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const selectedOrder = ref(null)
const selectedOrderDetails = ref([])
const isDetailLoading = ref(false)

const activeTab = ref('today') // today, received, history, future
const getTodayStr = () => new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Taipei' }).substring(0, 10)

const deleteOrder = async (orderId) => {
  if (!confirm('確定要刪除這筆叫貨單嗎？刪除後無法復原。')) return
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${orderId}`, { method: 'DELETE' })
    if (res.ok) {
      alert('已刪除！')
      if (selectedOrder.value) showDetails(selectedOrder.value) // re-fetch details if modal open
      fetchOrders()
    }
  } catch(err) {
    alert('刪除失敗')
  }
}

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

const displayedOrders = computed(() => {
  const today = getTodayStr()
  return groupedOrders.value.filter(group => {
    const isPending = group.status === 'pending'
    const isReceived = group.status === 'received'
    
    if (activeTab.value === 'today') return isPending && group.dateStr <= today
    if (activeTab.value === 'future') return isPending && group.dateStr > today
    if (activeTab.value === 'received') return isReceived && group.dateStr === today
    if (activeTab.value === 'history') return isReceived && group.dateStr < today
    return false
  })
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
const receiveForm = ref({ total_amount: '', is_paid: true, note: '', file: null })
const isReceiving = ref(false)

const getFile = (e) => {
  receiveForm.value.file = e.target.files[0]
}

const openReceiveModal = (order) => {
  receivingOrder.value = order
  receiveForm.value = { total_amount: '', is_paid: true, note: '', file: null }
  showReceiveModal.value = true
}

const submitReceive = async () => {
  if (receiveForm.value.total_amount === '') {
    alert('請輸入帳單總金額 (若為0請輸入0)')
    return
  }
  
  isReceiving.value = true
  try {
    let first = true
    for (const id of receivingOrder.value.ids) {
      // Only attach full amount & payment to the first order ID in the group to avoid duplicate accounting
      const tAmount = first ? Number(receiveForm.value.total_amount) : 0
      const aPaid = (first && receiveForm.value.is_paid) ? tAmount : 0
      const note = first ? receiveForm.value.note : '(合併收貨)'
      
      const res = await fetch(`${API_BASE}/inventory/orders/${id}/receive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          amount_paid: aPaid,
          total_amount: tAmount,
          is_paid: receiveForm.value.is_paid,
          note: note 
        })
      })
      if (!res.ok) throw new Error('部分收貨失敗')
      
      // Upload receipt to the first order ID if file exists
      if (first && receiveForm.value.file) {
        const formData = new FormData()
        formData.append('file', receiveForm.value.file)
        await fetch(`${API_BASE}/inventory/orders/${id}/receipt`, {
          method: 'POST',
          body: formData
        })
      }
      
      first = false
    }
    
    showReceiveModal.value = false
    alert('點收完畢，已同步更新後台紀錄！')
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
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 px-4 pt-6 pb-4">
      <h2 class="text-2xl font-black text-slate-900 mb-4">收貨與紀錄</h2>
      
      <!-- Tabs -->
      <div class="flex space-x-2 overflow-x-auto custom-scrollbar pb-2">
        <button 
          @click="activeTab = 'today'"
          :class="['whitespace-nowrap px-4 py-2 rounded-full text-sm font-bold transition-all', activeTab === 'today' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200']"
        >
          今日到貨
        </button>
        <button 
          @click="activeTab = 'future'"
          :class="['whitespace-nowrap px-4 py-2 rounded-full text-sm font-bold transition-all', activeTab === 'future' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200']"
        >
          未來到貨
        </button>
        <button 
          @click="activeTab = 'received'"
          :class="['whitespace-nowrap px-4 py-2 rounded-full text-sm font-bold transition-all', activeTab === 'received' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200']"
        >
          今日已簽收
        </button>
        <button 
          @click="activeTab = 'history'"
          :class="['whitespace-nowrap px-4 py-2 rounded-full text-sm font-bold transition-all', activeTab === 'history' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200']"
        >
          歷史到貨
        </button>
      </div>
    </header>

    <main class="px-4 py-6">
      <div v-if="isLoading" class="flex flex-col items-center justify-center py-20">
        <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full mb-4"></div>
        <p class="text-slate-400">載入紀錄中...</p>
      </div>

      <div v-else-if="displayedOrders.length === 0" class="text-center py-20 bg-white rounded-3xl border border-dashed border-slate-300">
        <p class="text-slate-400 font-bold">目前分頁尚無資料</p>
      </div>

      <div v-else class="space-y-4">
        <div 
          v-for="order in displayedOrders" 
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
            <div class="mt-2 flex space-x-2">
              <button 
                v-if="order.status === 'pending'"
                @click="openReceiveModal(order)" 
                class="bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold shadow-sm hover:bg-emerald-400 transition-colors"
              >
                點收/上傳
              </button>
              <button @click="showDetails(order)" class="bg-slate-100 text-slate-600 px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-slate-200">管理</button>
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

          <div v-else class="space-y-4 max-h-[40vh] overflow-y-auto pr-2 custom-scrollbar">
            <div v-for="item in selectedOrderDetails" :key="item.name" class="flex justify-between items-center py-3 border-b border-slate-50">
              <span class="text-slate-700 font-bold">{{ item.name }}</span>
              <span class="text-slate-900 font-black">{{ item.qty }} <span class="text-xs font-normal text-slate-400">{{ item.unit }}</span></span>
            </div>
          </div>

          <div class="mt-8 flex flex-col space-y-3">
            <button v-if="selectedOrder.status === 'pending'" @click="deleteOrder(selectedOrder.ids[0])" class="w-full bg-rose-50 text-rose-500 font-bold py-3.5 rounded-2xl border border-rose-100 active:bg-rose-100 transition-all text-sm">
              刪除此單 (重叫)
            </button>
            <button @click="selectedOrder = null" class="w-full bg-slate-900 text-white font-bold py-4 rounded-2xl active:scale-95 transition-all">
              關閉視窗
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal for Receiving Order -->
    <div v-if="showReceiveModal" class="fixed inset-0 z-[70] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div @click="showReceiveModal = false" class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
      
      <div class="relative w-full max-w-sm bg-white rounded-t-[2.5rem] sm:rounded-[2.5rem] shadow-2xl overflow-hidden animate-in slide-in-from-bottom duration-300 p-8 pb-10">
        <h3 class="text-2xl font-black text-slate-900 mb-2">相機收貨點收</h3>
        <p class="text-slate-500 text-sm mb-6">{{ receivingOrder.vendor_name }} | 預計: {{ receivingOrder.dateStr }}</p>
        
        <div class="space-y-5 max-h-[60vh] overflow-y-auto custom-scrollbar pr-2">
          
          <!-- File Upload -->
          <div class="bg-slate-50 p-4 rounded-xl border border-slate-100 flex flex-col items-center justify-center relative overflow-hidden">
            <input type="file" accept="image/*" capture="environment" @change="getFile" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" />
            <svg class="w-8 h-8 text-slate-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span v-if="!receiveForm.file" class="text-sm font-bold text-slate-500">點擊拍照上傳收據 (選填)</span>
            <span v-else class="text-sm font-bold text-emerald-500 break-all text-center">已選擇相片: {{ receiveForm.file.name }}</span>
          </div>

          <div>
            <label class="block text-xs font-bold text-slate-500 mb-2">請輸入帳單總金額</label>
            <input v-model.number="receiveForm.total_amount" type="number" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 text-lg font-bold focus:ring-2 focus:ring-emerald-500/20" placeholder="$ 0" />
          </div>
          
          <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl">
            <label class="text-sm font-bold text-slate-700">本次是否已經付款？</label>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" v-model="receiveForm.is_paid" class="sr-only peer">
              <div class="w-11 h-6 bg-slate-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-500"></div>
            </label>
          </div>
          <p v-if="!receiveForm.is_paid" class="text-[10px] text-rose-500 font-bold -mt-2">注意：將建立一筆未付帳款紀錄</p>

          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1">備註提醒</label>
            <textarea v-model="receiveForm.note" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4 focus:ring-2 focus:ring-emerald-500/20 text-sm" rows="2" placeholder="(選填) 取代品或少送紀錄"></textarea>
          </div>
        </div>

        <div class="flex space-x-3 mt-6">
          <button @click="showReceiveModal = false" class="flex-1 bg-slate-100 text-slate-500 font-bold py-4 rounded-2xl">取消</button>
          <button 
            @click="submitReceive" 
            :disabled="isReceiving"
            class="flex-[2] bg-emerald-500 text-white font-bold py-4 rounded-2xl shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center justify-center"
          >
            <span v-if="isReceiving" class="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full mr-2"></span>
            確認歸檔紀錄
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
