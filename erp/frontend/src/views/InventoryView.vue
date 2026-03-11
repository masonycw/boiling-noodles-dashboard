<script setup>
import { ref, onMounted, computed } from 'vue'

const items = ref([])
const vendor = ref({ name: '菜商（高青）', deadline: '21:00' })
const searchQuery = ref('')
const isLoading = ref(true)

// Mock data based on seeded items
// In next step, we'll connect this to real fetch() from FastAPI
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const expectedDeliveryDate = ref('')
const initDate = () => {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  expectedDeliveryDate.value = tomorrow.toISOString().split('T')[0]
}

onMounted(async () => {
  initDate()
  try {
    // 1. Fetch Vendors to get Gaoqing (ID 1)
    const vRes = await fetch(`${API_BASE}/inventory/vendors`)
    const vendors = await vRes.json()
    if (vendors.length > 0) {
      vendor.value = { 
        id: vendors[0].id,
        name: vendors[0].name, 
        deadline: vendors[0].order_deadline ? vendors[0].order_deadline.substring(0, 5) : '21:00'
      }
    }

    // 2. Fetch Items for the first vendor
    const iRes = await fetch(`${API_BASE}/inventory/items?vendor_id=${vendor.value.id}`)
    const data = await iRes.json()
    items.value = data.map(item => ({
      ...item,
      qty: 0 // Initialize UI qty state
    }))
  } catch (err) {
    console.error('Failed to fetch items:', err)
  } finally {
    isLoading.value = false
  }
})

const filteredItems = computed(() => {
  return items.value.filter(item => 
    item.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

// Ad-hoc Item State
const adHocItemName = ref('')
const adHocItemQty = ref(1)
const adHocItemUnit = ref('⽄')
const adHocItems = ref([])
const showAdHocForm = ref(false)

const addAdHocItem = () => {
  if (!adHocItemName.value) return
  adHocItems.value.push({
    id: Date.now(), // Temp ID
    name: adHocItemName.value,
    qty: adHocItemQty.value,
    unit: adHocItemUnit.value,
    is_adhoc: true
  })
  adHocItemName.value = ''
  adHocItemQty.value = 1
  showAdHocForm.value = false
}

const generateOrderText = async () => {
  const regularOrdered = items.value.filter(i => i.qty > 0)
  const combinedItems = [...regularOrdered, ...adHocItems.value]
  
  if (combinedItems.length === 0) {
    alert('請先輸入叫貨數量')
    return
  }
  
  // 1. Prepare data for API
  const orderDetails = [
    ...regularOrdered.map(i => ({ item_id: i.id, qty: i.qty })),
    ...adHocItems.value.map(i => ({ adhoc_name: i.name, qty: i.qty, adhoc_unit: i.unit }))
  ]

  try {
    isLoading.value = true
    const payload = {
      vendor_id: vendor.value.id,
      expected_delivery_date: expectedDeliveryDate.value ? new Date(expectedDeliveryDate.value).toISOString() : null,
      items: orderDetails
    }
    const response = await fetch(`${API_BASE}/inventory/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    if (!response.ok) throw new Error('無法儲存叫貨紀錄')
    
    // 2. Generate Text for Clipping
    let text = `【滾麵 叫貨單 - ${vendor.value.name}】\n`
    text += `日期: ${new Date().toLocaleDateString()}\n`
    text += `------------------\n`
    combinedItems.forEach(item => {
      text += `${item.name} ${item.qty} ${item.unit}\n`
    })
    text += `------------------\n`
    text += `請確認收單，謝謝！`
    
    // 3. Copy to clipboard
    await navigator.clipboard.writeText(text)
    alert('叫貨紀錄已存檔，並已複製到剪貼簿！')
    adHocItems.value = [] // Clear ad-hoc after order
  } catch (err) {
    alert('儲存失敗: ' + err.message)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 pb-32">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 px-4 py-4">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-xl font-bold text-slate-900">{{ vendor.name }}</h2>
          <p class="text-xs text-rose-500 font-medium">截單時間: {{ vendor.deadline }} 前</p>
        </div>
        <div class="bg-slate-100 p-2 rounded-full">
          <svg class="w-6 h-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
      </div>
      
      <!-- Search -->
      <div class="relative">
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="搜尋品項..."
          class="w-full bg-slate-100 border-none rounded-xl py-3 pl-11 pr-4 text-slate-800 focus:ring-2 focus:ring-orange-500/20 transition-all font-medium"
        />
        <svg class="w-5 h-5 text-slate-400 absolute left-4 top-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>
      
      <!-- Expected Delivery Date -->
      <div class="mt-4 flex items-center justify-between bg-orange-50/50 p-3 rounded-xl border border-orange-100">
        <label class="text-sm font-bold text-orange-800 flex items-center">
          <svg class="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
          預計到貨日
        </label>
        <input 
          v-model="expectedDeliveryDate" 
          type="date"
          class="bg-white border-none rounded-lg text-sm text-slate-800 font-bold focus:ring-2 focus:ring-orange-500/20 py-1.5 px-3"
        />
      </div>
    </header>

    <!-- Item List -->
    <main class="px-4 py-6">
      <div v-if="isLoading" class="flex flex-col items-center justify-center py-20 space-y-4">
        <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full"></div>
        <p class="text-slate-400 text-sm">載入品項中...</p>
      </div>
      
      <div v-else class="space-y-3">
        <!-- Ad-hoc items list -->
        <div v-for="item in adHocItems" :key="item.id" 
          class="bg-orange-50 border border-orange-100 p-4 rounded-2xl flex items-center justify-between relative overflow-hidden"
        >
          <div class="absolute top-0 right-0 bg-orange-200 text-orange-700 text-[10px] px-2 py-0.5 rounded-bl-lg font-bold">臨時品項</div>
          <div class="flex flex-col">
            <span class="text-slate-900 font-bold text-lg">{{ item.name }}</span>
            <span class="text-slate-500 text-xs">單位: {{ item.unit }}</span>
          </div>
          <div class="flex items-center space-x-3">
             <span class="text-slate-900 font-black text-xl">{{ item.qty }}</span>
             <button @click="adHocItems = adHocItems.filter(i => i.id !== item.id)" class="text-rose-400 p-1">
               <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
               </svg>
             </button>
          </div>
        </div>

        <div 
          v-for="item in filteredItems" 
          :key="item.id"
          class="bg-white border border-slate-200 p-4 rounded-2xl flex items-center justify-between shadow-sm active:bg-slate-50 transition-colors"
        >
          <div class="flex flex-col">
            <span class="text-slate-900 font-bold text-lg">{{ item.name }}</span>
            <span class="text-slate-500 text-xs">單位: {{ item.unit }}</span>
          </div>
          
          <div class="flex items-center space-x-3">
            <button 
              @click="item.qty = Math.max(0, item.qty - 1)"
              class="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center text-slate-600 active:bg-slate-200 transition-colors"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
              </svg>
            </button>
            <input 
              v-model.number="item.qty"
              type="number" 
              class="w-16 bg-transparent border-b-2 border-slate-200 text-center font-bold text-xl text-slate-900 focus:outline-none focus:border-orange-500"
            />
            <button 
              @click="item.qty += 1"
              class="w-10 h-10 bg-orange-100 rounded-full flex items-center justify-center text-orange-600 active:bg-orange-200 transition-colors"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Ad-hoc Add Button -->
      <div v-if="!showAdHocForm" class="mt-8 flex justify-center">
        <button 
          @click="showAdHocForm = true"
          class="flex items-center space-x-2 text-orange-500 font-bold bg-white px-6 py-3 rounded-2xl border-2 border-orange-100 shadow-sm active:scale-95 transition-all"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>新增臨時品項</span>
        </button>
      </div>

      <!-- Ad-hoc Form Modal-style -->
      <div v-if="showAdHocForm" class="mt-6 bg-white p-6 rounded-3xl border-2 border-orange-100 shadow-lg animate-in fade-in zoom-in duration-200">
        <h3 class="text-slate-900 font-black mb-4">新增臨時品項</h3>
        <div class="space-y-4">
          <input v-model="adHocItemName" type="text" placeholder="品項名稱 (如: 甜玉米)" class="w-full bg-slate-50 border-none rounded-xl py-3 px-4" />
          <div class="flex space-x-2">
            <input v-model.number="adHocItemQty" type="number" placeholder="數量" class="flex-1 bg-slate-50 border-none rounded-xl py-3 px-4" />
            <input v-model="adHocItemUnit" type="text" placeholder="單位" class="w-20 bg-slate-50 border-none rounded-xl py-3 px-4" />
          </div>
          <div class="flex space-x-3">
            <button @click="showAdHocForm = false" class="flex-1 bg-slate-100 text-slate-500 font-bold py-3 rounded-xl">取消</button>
            <button @click="addAdHocItem" class="flex-1 bg-orange-500 text-white font-bold py-3 rounded-xl shadow-lg shadow-orange-500/20">加入清單</button>
          </div>
        </div>
      </div>
    </main>

    <!-- Bottom Action Bar -->
    <div class="sticky bottom-0 left-0 right-0 bg-white border-t border-slate-200 p-4 flex items-center space-x-4 shadow-[0_-4px_20px_rgba(0,0,0,0.05)] z-20">
      <div class="flex-1">
        <p class="text-[10px] text-slate-400 uppercase tracking-wider font-bold">已選品項</p>
        <p class="text-lg font-black text-slate-900">{{ items.filter(i => i.qty > 0).length }} 項</p>
      </div>
      <button 
        @click="generateOrderText"
        class="flex-[2] bg-gradient-to-r from-orange-500 to-rose-600 text-white font-bold py-4 rounded-2xl shadow-lg shadow-orange-500/20 active:scale-95 transition-all flex items-center justify-center"
      >
        <svg class="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
        </svg>
        複製叫貨訊息
      </button>
    </div>
  </div>
</template>

<style scoped>
/* Chrome, Safari, Edge, Opera */
input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

/* Firefox */
input[type=number] {
  -moz-appearance: textfield;
}
</style>
