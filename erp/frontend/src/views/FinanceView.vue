<script setup>
import { ref, onMounted } from 'vue'

const transactions = ref([])
const unpaidOrders = ref([])
const currentBalance = ref(0)
const isLoading = ref(false)
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

// Form State
const showAddModal = ref(false)
const txForm = ref({ amount: '', type: 'expense', category: '食材採購', note: '' })
const showPinModal = ref(false)
const pin = ref('')
const pendingTx = ref(null)

const showSettingsModal = ref(false)
const alertThreshold = ref(Number(localStorage.getItem('erp_finance_alert_threshold')) || 10000)

const saveThreshold = () => {
  localStorage.setItem('erp_finance_alert_threshold', alertThreshold.value)
  alert('已更新警示上限設定')
  showSettingsModal.value = false
}

const categories = ['食材採購', '店內雜項', '員工薪資', '零用金提領', '其他收入']

const fetchTransactions = async () => {
  isLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/finance/transactions?days_limit=3`)
    transactions.value = await res.json()
    
    // Fetch unpaid orders
    const orderRes = await fetch(`${API_BASE}/inventory/orders?status=received`)
    const orders = await orderRes.json()
    unpaidOrders.value = orders.filter(o => !o.is_paid && o.total_amount > 0)
    
    // Fetch total balance
    const balRes = await fetch(`${API_BASE}/finance/balance`)
    const balData = await balRes.json()
    currentBalance.value = balData.balance
    
  } catch (err) {
    console.error('Fetch error:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchTransactions)

const settleOrder = async (order) => {
  if (!confirm(`確認要結清 ${order.vendor_name} 的帳款 $${order.total_amount} 嗎？`)) return
  try {
    const res = await fetch(`${API_BASE}/inventory/orders/${order.id}/receive`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        amount_paid: order.total_amount,
        total_amount: order.total_amount,
        is_paid: true,
        note: `自金流後台結清`
      })
    })
    if (res.ok) {
      alert('已結清款項並記錄至收支！')
      fetchTransactions()
    } else {
      alert('結清失敗')
    }
  } catch(err) {
    alert('網路錯誤')
  }
}

const submitTransaction = async () => {
  // If withdrawal, require PIN
  if (txForm.value.type === 'withdrawal' && !pendingTx.value) {
    pendingTx.value = { ...txForm.value }
    showPinModal.value = true
    return
  }

  try {
    const res = await fetch(`${API_BASE}/finance/transactions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(txForm.value)
    })
    if (res.ok) {
      showAddModal.value = false
      txForm.value = { amount: '', type: 'expense', category: '食材採購', note: '' }
      fetchTransactions()
      alert('紀錄已儲存')
    }
  } catch (err) {
    alert('儲存失敗')
  }
}

const verifyPin = async () => {
  try {
    const res = await fetch(`${API_BASE}/finance/verify-pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pin.value })
    })
    if (res.ok) {
      showPinModal.value = false
      pin.value = ''
      // Proceed with pending transaction
      const actualTx = pendingTx.value
      pendingTx.value = null
      txForm.value = actualTx
      submitTransaction()
    } else {
      alert('PIN 碼錯誤')
    }
  } catch (err) {
    alert('驗證失敗')
  }
}
</script>

<template>
  <div class="min-h-screen bg-slate-50 pb-32">
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 p-4">
      <div class="flex items-center justify-between">
        <h1 class="text-xl font-bold text-slate-900">金流管理</h1>
        <button 
          @click="showAddModal = true"
          class="bg-orange-500 text-white px-4 py-2 rounded-xl text-sm font-bold shadow-lg shadow-orange-500/20 active:scale-95 transition-all"
        >
          + 新增紀錄
        </button>
      </div>
    </header>

    <main class="p-4">
      <!-- Balance Summary Card -->
      <div class="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-6 mb-6 shadow-xl text-white relative overflow-hidden">
        <div v-if="currentBalance > alertThreshold" class="absolute top-0 left-0 right-0 bg-rose-500 text-white text-[10px] sm:text-xs font-bold text-center py-1.5 px-2">
          <span class="animate-pulse">⚠️ 警告：現有零用金已超過上限 ({{ alertThreshold.toLocaleString() }})，請通知主管</span>
        </div>
        <div class="flex justify-between items-start mt-4">
          <div>
            <p class="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1">當前應有金額 (現有零用金)</p>
            <h2 class="text-3xl font-black mb-4">
              $ {{ currentBalance.toLocaleString() }}
            </h2>
          </div>
          <button @click="showSettingsModal = true" class="bg-white/10 p-2 rounded-full hover:bg-white/20 transition-all active:scale-95">
            <svg class="w-5 h-5 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
          </button>
        </div>
        <div class="grid grid-cols-2 gap-4 border-t border-white/10 pt-4 mt-2">
          <div>
            <p class="text-[10px] text-slate-400 font-bold mb-1">今日支出估算</p>
            <p class="text-sm font-bold text-rose-300">- $ {{ transactions.filter(t => t.type !== 'income' && new Date(t.created_at).toDateString() === new Date().toDateString()).reduce((acc, t) => acc + Number(t.amount), 0).toLocaleString() }}</p>
          </div>
          <div>
            <p class="text-[10px] text-slate-400 font-bold mb-1">今日收入估算</p>
            <p class="text-sm font-bold text-emerald-300">+ $ {{ transactions.filter(t => t.type === 'income' && new Date(t.created_at).toDateString() === new Date().toDateString()).reduce((acc, t) => acc + Number(t.amount), 0).toLocaleString() }}</p>
          </div>
        </div>
      </div>

      <div v-if="isLoading" class="flex justify-center py-20">
        <div class="animate-spin h-8 w-8 border-4 border-orange-500 border-t-transparent rounded-full"></div>
      </div>

      <!-- Unpaid Orders (Accounts Payable) -->
      <div v-if="!isLoading && unpaidOrders.length > 0" class="mb-6 space-y-3">
        <h3 class="text-rose-600 font-bold px-1 flex items-center">
          <svg class="w-5 h-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          待付帳款 (應付)
        </h3>
        <div v-for="order in unpaidOrders" :key="'unpaid_'+order.id" class="bg-rose-50 border border-rose-200 p-4 rounded-2xl flex justify-between items-center shadow-sm">
          <div>
            <p class="font-black text-slate-900 border-b border-rose-200/50 pb-1 mb-1">{{ order.vendor_name }}</p>
            <p class="text-xs text-slate-500">進貨日: {{ new Date(order.created_at).toLocaleString().substring(0, 10) }}</p>
          </div>
          <div class="text-right">
            <p class="font-black text-xl text-rose-600 mb-2">$ {{ order.total_amount.toLocaleString() }}</p>
            <button @click="settleOrder(order)" class="bg-slate-900 text-white px-4 py-1.5 rounded-lg text-xs font-bold shadow-sm active:scale-95 transition-all w-full">結清帳款</button>
          </div>
        </div>
      </div>

      <!-- Transaction List -->
      <div v-if="!isLoading" class="space-y-3">
        <h3 class="text-slate-900 font-bold px-1">最近收支紀錄</h3>
        <div v-if="transactions.length === 0" class="text-center py-10 bg-white rounded-2xl border border-dashed border-slate-300">
          <p class="text-slate-400 font-bold">目前無紀錄</p>
        </div>
        <div v-for="tx in transactions" :key="tx.id" class="bg-white p-4 rounded-2xl border border-slate-200 flex justify-between items-center shadow-sm">
          <div class="flex items-center space-x-4">
            <div :class="[
              'w-10 h-10 rounded-full flex items-center justify-center min-w-[40px]',
              tx.type === 'income' ? 'bg-emerald-100 text-emerald-600' : 
              tx.type === 'withdrawal' ? 'bg-rose-100 text-rose-600' : 'bg-blue-100 text-blue-600'
            ]">
              <svg v-if="tx.type === 'income'" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M7 11l5-5m0 0l5 5m-5-5v12" /></svg>
              <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M17 13l-5 5m0 0l-5-5m5 5V6" /></svg>
            </div>
            <div>
              <p class="font-bold text-slate-900">{{ tx.category }}</p>
              <p class="text-[10px] text-slate-400">{{ new Date(tx.created_at).toLocaleString() }}</p>
            </div>
          </div>
          <div class="text-right">
            <p :class="['font-black text-lg', tx.type === 'income' ? 'text-emerald-500' : 'text-slate-900']">
              {{ tx.type === 'income' ? '+' : '-' }} ${{ Number(tx.amount).toLocaleString() }}
            </p>
            <p class="text-[10px] text-slate-400 truncate max-w-[100px]">{{ tx.note || '無備註' }}</p>
          </div>
        </div>
      </div>
    </main>

    <!-- Add Transaction Modal -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div class="bg-white w-full max-w-md rounded-t-3xl sm:rounded-3xl p-6 animate-in slide-in-from-bottom duration-300">
        <div class="flex justify-between items-center mb-6">
          <h3 class="text-xl font-black">新增財務紀錄</h3>
          <button @click="showAddModal = false" class="text-slate-400">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <div class="space-y-4">
          <div class="flex bg-slate-100 p-1 rounded-xl">
            <button @click="txForm.type = 'expense'" class="flex-1 py-2 rounded-lg text-xs font-bold" :class="txForm.type === 'expense' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'">一般支出</button>
            <button @click="txForm.type = 'withdrawal'" class="flex-1 py-2 rounded-lg text-xs font-bold" :class="txForm.type === 'withdrawal' ? 'bg-white text-rose-600 shadow-sm' : 'text-slate-500'">現金提領</button>
            <button @click="txForm.type = 'income'" class="flex-1 py-2 rounded-lg text-xs font-bold" :class="txForm.type === 'income' ? 'bg-white text-emerald-600 shadow-sm' : 'text-slate-500'">其他收入</button>
          </div>

          <div>
            <label class="text-[10px] font-bold text-slate-400 uppercase ml-1">金額</label>
            <input v-model.number="txForm.amount" type="number" placeholder="$ 0" class="w-full p-4 bg-slate-50 rounded-2xl text-2xl font-black text-slate-900 focus:ring-2 focus:ring-orange-500/20 transition-all" />
          </div>

          <div>
            <label class="text-[10px] font-bold text-slate-400 uppercase ml-1">類別</label>
            <select v-model="txForm.category" class="w-full p-4 bg-slate-50 rounded-2xl font-bold text-slate-700">
              <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
            </select>
          </div>

          <div>
            <label class="text-[10px] font-bold text-slate-400 uppercase ml-1">備註</label>
            <textarea v-model="txForm.note" placeholder="輸入備註 (選填)..." class="w-full p-4 bg-slate-50 rounded-2xl h-24 text-slate-700"></textarea>
          </div>

          <button 
            @click="submitTransaction"
            class="w-full py-4 bg-orange-500 text-white font-bold rounded-2xl shadow-lg shadow-orange-500/20 active:scale-95 transition-all text-lg"
          >
            儲存紀錄
          </button>
        </div>
      </div>
    </div>

    <!-- PIN Modal -->
    <div v-if="showPinModal" class="fixed inset-0 bg-black/80 z-[60] flex items-center justify-center p-4">
      <div class="bg-white w-full max-w-xs rounded-3xl p-8 text-center animate-in zoom-in duration-200">
        <div class="w-16 h-16 bg-rose-100 text-rose-500 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
        </div>
        <h3 class="text-xl font-black text-slate-900 mb-2">安全驗證</h3>
        <p class="text-slate-400 text-sm mb-6">提領現金需輸入安全 PIN 碼</p>
        
        <input 
          v-model="pin" 
          type="password" 
          maxlength="4" 
          placeholder="••••" 
          class="w-full text-center text-4xl tracking-widest font-black py-4 bg-slate-50 rounded-2xl border-2 border-slate-100 focus:border-orange-500 transition-all mb-6"
        />
        
        <div class="flex space-x-3">
          <button @click="showPinModal = false; pendingTx = null; pin = ''" class="flex-1 py-3 text-slate-400 font-bold">取消</button>
          <button @click="verifyPin" class="flex-1 py-3 bg-slate-900 text-white rounded-xl font-bold">驗證</button>
        </div>
      </div>
    </div>

    <!-- Settings Modal -->
    <div v-if="showSettingsModal" class="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4">
      <div class="bg-white w-full max-w-xs rounded-3xl p-6 animate-in zoom-in duration-200">
        <div class="flex justify-between items-center mb-6">
          <h3 class="text-lg font-black text-slate-900">金流設定</h3>
          <button @click="showSettingsModal = false" class="text-slate-400 bg-slate-100 rounded-full p-2">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
        
        <div class="space-y-4 mb-6">
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-2">零用金異常警示上限 ($)</label>
            <p class="text-[10px] text-slate-400 mb-2">當零用金超過此金額時，系統會跳出紅色警告提示主管。</p>
            <input 
              v-model.number="alertThreshold" 
              type="number" 
              class="w-full text-center text-2xl font-black py-3 bg-slate-50 rounded-2xl border-none focus:ring-2 focus:ring-orange-500 transition-all"
            />
          </div>
        </div>
        
        <button @click="saveThreshold" class="w-full py-3.5 bg-slate-900 text-white rounded-xl font-bold shadow-lg shadow-slate-900/20 active:scale-95 transition-all">
          儲存設定
        </button>
      </div>
    </div>
  </div>
</template>
