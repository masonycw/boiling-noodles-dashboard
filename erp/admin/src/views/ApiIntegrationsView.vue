<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const toast = ref('')
const testingId = ref(null)

// LINE Messaging API（O9：叫貨自動推播）
const lineMessaging = ref({ channel_secret: '', access_token: '' })
const lineMessagingSaving = ref(false)
const showLineHelpModal = ref(false)

async function loadLineMessaging() {
  try {
    const res = await fetch(`${API_BASE}/admin/settings/`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      if (data.line_channel_secret) lineMessaging.value.channel_secret = data.line_channel_secret
      if (data.line_access_token) lineMessaging.value.access_token = data.line_access_token
    }
  } catch (e) { /* 使用預設值 */ }
}

async function saveLineMessaging() {
  lineMessagingSaving.value = true
  try {
    await Promise.all([
      fetch(`${API_BASE}/admin/settings/line_channel_secret`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ value: lineMessaging.value.channel_secret })
      }),
      fetch(`${API_BASE}/admin/settings/line_access_token`, {
        method: 'PUT', headers: authHeaders(),
        body: JSON.stringify({ value: lineMessaging.value.access_token })
      }),
    ])
    showToast('✓ LINE Messaging API 憑證已儲存')
  } catch (e) {
    showToast('⚠ 儲存失敗')
  } finally {
    lineMessagingSaving.value = false
  }
}

// LINE 通知設定
const lineSettings = ref({
  enabled: false,
  token: '',
  notify_daily_settlement: true,
  notify_low_stock: true,
  notify_new_order: false,
  low_stock_threshold: 3,
})

// POS Webhook
const posSettings = ref({
  enabled: false,
  webhook_secret: '',
  auto_create_cashflow: true,
})

// 外送平台收入串接
const platforms = ref([
  { id: 'ubereats', name: 'UberEats', icon: '🍔', enabled: false, api_key: '', auto_sync: false, last_sync: null },
  { id: 'foodpanda', name: 'Foodpanda', icon: '🐼', enabled: false, api_key: '', auto_sync: false, last_sync: null },
  { id: 'linepay', name: 'LINE Pay', icon: '💳', enabled: false, api_key: '', auto_sync: false, last_sync: null },
])

// 同步紀錄
const syncLogs = ref([])
const loadingLogs = ref(false)

function authHeaders() {
  return { Authorization: `Bearer ${auth.token}`, 'Content-Type': 'application/json' }
}
function showToast(msg) { toast.value = msg; setTimeout(() => { toast.value = '' }, 2500) }
function fmtDateTime(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function load() {
  try {
    const res = await fetch(`${API_BASE}/settings/integrations`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      if (data.line) Object.assign(lineSettings.value, data.line)
      if (data.pos) Object.assign(posSettings.value, data.pos)
      if (data.platforms) platforms.value = data.platforms
    }
  } catch (e) { /* 使用預設值 */ }

  loadingLogs.value = true
  try {
    const logRes = await fetch(`${API_BASE}/settings/integrations/logs?limit=20`, { headers: authHeaders() })
    if (logRes.ok) syncLogs.value = await logRes.json()
  } catch (e) { } finally { loadingLogs.value = false }
}
onMounted(() => { load(); loadLineMessaging() })

async function saveLineSettings() {
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/line`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(lineSettings.value)
    })
    if (res.ok) showToast('✓ LINE 設定已儲存')
    else showToast('⚠ 儲存失敗（API 尚未實作）')
  } catch (e) { showToast('⚠ 儲存失敗') }
}

async function testLine() {
  testingId.value = 'line'
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/line/test`, {
      method: 'POST', headers: authHeaders()
    })
    if (res.ok) showToast('✓ LINE 測試通知已發送')
    else showToast('⚠ 發送失敗，請檢查 Token')
  } catch (e) { showToast('⚠ 測試失敗') } finally { testingId.value = null }
}

async function savePlatform(p) {
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/platform/${p.id}`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(p)
    })
    if (res.ok) showToast(`✓ ${p.name} 設定已儲存`)
    else showToast('⚠ 儲存失敗（API 尚未實作）')
  } catch (e) { showToast('⚠ 儲存失敗') }
}

async function syncPlatform(p) {
  testingId.value = p.id
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/platform/${p.id}/sync`, {
      method: 'POST', headers: authHeaders()
    })
    if (res.ok) { showToast(`✓ ${p.name} 同步成功`); await load() }
    else showToast('⚠ 同步失敗')
  } catch (e) { showToast('⚠ 同步失敗') } finally { testingId.value = null }
}

async function savePosSettings() {
  try {
    const res = await fetch(`${API_BASE}/settings/integrations/pos`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(posSettings.value)
    })
    if (res.ok) showToast('✓ POS Webhook 設定已儲存')
    else showToast('⚠ 儲存失敗（API 尚未實作）')
  } catch (e) { showToast('⚠ 儲存失敗') }
}

function copyWebhookUrl() {
  const url = `${window.location.origin}/api/webhooks/pos`
  navigator.clipboard.writeText(url).then(() => showToast('✓ Webhook URL 已複製'))
}
</script>

<template>
  <div class="space-y-6">
    <div v-if="toast" class="fixed top-5 right-5 z-50 bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl shadow-lg">{{ toast }}</div>

    <!-- LINE Messaging API（O9：叫貨自動推播） -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h3 class="font-bold text-gray-100 text-sm">LINE Messaging API</h3>
          <button @click="showLineHelpModal = true"
            class="w-5 h-5 rounded-full bg-[#2d3748] hover:bg-[#374151] text-gray-400 hover:text-gray-200 text-xs font-bold flex items-center justify-center transition-colors border border-[#4a5568] shrink-0"
            title="設定說明">?</button>
        </div>
        <div class="flex items-center gap-2">
          <p class="text-xs text-gray-500">叫貨送出時自動推播至廠商 LINE 群組</p>
          <span class="text-xs px-2 py-1 rounded-full bg-emerald-900/40 text-emerald-400 font-bold shrink-0">啟用中</span>
        </div>
      </div>
      <div class="px-5 py-4 space-y-4">
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-1">Channel Secret</label>
          <input v-model="lineMessaging.channel_secret" type="password"
            placeholder="填入 Channel Secret"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-1">Channel Access Token（長期）</label>
          <input v-model="lineMessaging.access_token" type="password"
            placeholder="填入 Long-lived Channel Access Token"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#63b3ed]" />
        </div>
        <div class="text-xs text-gray-500 space-y-1">
          <p>• Webhook URL：<span class="text-gray-300 font-mono">https://preoffensive-chasteningly-taunya.ngrok-free.dev/api/v1/webhook/line</span></p>
          <p>• 廠商 LINE 群組 ID 在供應商管理頁填入</p>
        </div>
        <div class="flex justify-end">
          <button @click="saveLineMessaging" :disabled="lineMessagingSaving"
            class="px-4 py-2 bg-[#63b3ed] hover:bg-blue-400 disabled:opacity-50 text-black text-sm font-bold rounded-lg transition-colors">
            {{ lineMessagingSaving ? '儲存中...' : '儲存憑證' }}
          </button>
        </div>
      </div>
    </div>

    <!-- LINE 通知設定 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div>
          <h3 class="text-sm font-bold text-gray-200">💬 LINE 通知</h3>
          <p class="text-xs text-gray-500 mt-0.5">透過 LINE Notify 發送日結提醒、低庫存警告</p>
        </div>
        <button @click="lineSettings.enabled = !lineSettings.enabled"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
          :class="lineSettings.enabled ? 'bg-green-500' : 'bg-gray-700'">
          <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            :class="lineSettings.enabled ? 'translate-x-6' : 'translate-x-1'"></span>
        </button>
      </div>
      <div class="px-5 py-4 space-y-4">
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-1">LINE Notify Token</label>
          <input v-model="lineSettings.token" type="password" placeholder="貼上 LINE Notify Token"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div class="space-y-2">
          <label class="block text-gray-400 text-xs font-semibold">通知事件</label>
          <div class="flex items-center gap-3">
            <input v-model="lineSettings.notify_daily_settlement" type="checkbox" id="ln1" class="w-4 h-4 accent-green-500" />
            <label for="ln1" class="text-sm text-gray-300">每日日結完成通知</label>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="lineSettings.notify_low_stock" type="checkbox" id="ln2" class="w-4 h-4 accent-green-500" />
            <label for="ln2" class="text-sm text-gray-300">庫存低於門檻警告（閾值：
              <input v-model.number="lineSettings.low_stock_threshold" type="number" min="1" max="100"
                class="w-12 bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded px-2 text-xs text-center" /> 件）
            </label>
          </div>
          <div class="flex items-center gap-3">
            <input v-model="lineSettings.notify_new_order" type="checkbox" id="ln3" class="w-4 h-4 accent-green-500" />
            <label for="ln3" class="text-sm text-gray-300">新叫貨單建立通知</label>
          </div>
        </div>
        <div class="flex gap-2">
          <button @click="saveLineSettings"
            class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
            儲存設定
          </button>
          <button @click="testLine" :disabled="!lineSettings.token || testingId === 'line'"
            class="bg-green-700 hover:bg-green-600 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-40">
            {{ testingId === 'line' ? '測試中…' : '發送測試通知' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 外送平台收入串接 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748]">
        <h3 class="text-sm font-bold text-gray-200">🚀 外送平台收入串接</h3>
        <p class="text-xs text-gray-500 mt-0.5">自動同步外送平台訂單收入至金流紀錄</p>
      </div>
      <div class="divide-y divide-[#2d3748]">
        <div v-for="p in platforms" :key="p.id" class="px-5 py-4">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <span class="text-2xl">{{ p.icon }}</span>
              <div>
                <p class="text-sm font-bold text-gray-200">{{ p.name }}</p>
                <p class="text-xs text-gray-500">最後同步：{{ fmtDateTime(p.last_sync) }}</p>
              </div>
            </div>
            <button @click="p.enabled = !p.enabled"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
              :class="p.enabled ? 'bg-blue-500' : 'bg-gray-700'">
              <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                :class="p.enabled ? 'translate-x-6' : 'translate-x-1'"></span>
            </button>
          </div>
          <div v-if="p.enabled" class="space-y-2">
            <div>
              <label class="block text-gray-400 text-xs font-semibold mb-1">API Key</label>
              <input v-model="p.api_key" type="password" :placeholder="`${p.name} API Key`"
                class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
            </div>
            <div class="flex items-center gap-3">
              <input v-model="p.auto_sync" type="checkbox" :id="`as_${p.id}`" class="w-4 h-4 accent-blue-500" />
              <label :for="`as_${p.id}`" class="text-sm text-gray-300">每日自動同步</label>
            </div>
            <div class="flex gap-2">
              <button @click="savePlatform(p)"
                class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-colors">
                儲存
              </button>
              <button @click="syncPlatform(p)" :disabled="!p.api_key || testingId === p.id"
                class="bg-purple-700 hover:bg-purple-600 text-white font-bold px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-40">
                {{ testingId === p.id ? '同步中…' : '手動同步' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- POS Webhook -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748] flex items-center justify-between">
        <div>
          <h3 class="text-sm font-bold text-gray-200">🔌 POS Webhook</h3>
          <p class="text-xs text-gray-500 mt-0.5">接收 POS 系統推送的收入資料</p>
        </div>
        <button @click="posSettings.enabled = !posSettings.enabled"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
          :class="posSettings.enabled ? 'bg-blue-500' : 'bg-gray-700'">
          <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
            :class="posSettings.enabled ? 'translate-x-6' : 'translate-x-1'"></span>
        </button>
      </div>
      <div class="px-5 py-4 space-y-4">
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-1">Webhook URL</label>
          <div class="flex gap-2">
            <div class="flex-1 bg-[#0f1117] border border-[#2d3748] text-gray-500 rounded-lg px-3 py-2 text-sm font-mono text-xs">
              {{ `${window?.location?.origin || 'https://your-domain.com'}/api/webhooks/pos` }}
            </div>
            <button @click="copyWebhookUrl"
              class="bg-gray-700 hover:bg-gray-600 text-gray-200 font-bold px-3 py-2 rounded-lg text-xs transition-colors">
              複製
            </button>
          </div>
        </div>
        <div>
          <label class="block text-gray-400 text-xs font-semibold mb-1">HMAC Secret（用於驗簽）</label>
          <input v-model="posSettings.webhook_secret" type="password" placeholder="設定 Webhook Secret"
            class="w-full bg-[#0f1117] border border-[#2d3748] text-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div class="flex items-center gap-3">
          <input v-model="posSettings.auto_create_cashflow" type="checkbox" id="pos_auto" class="w-4 h-4 accent-blue-500" />
          <label for="pos_auto" class="text-sm text-gray-300">自動建立金流收入紀錄</label>
        </div>
        <button @click="savePosSettings"
          class="bg-blue-500 hover:bg-blue-400 text-white font-bold px-4 py-2 rounded-lg text-sm transition-colors">
          儲存設定
        </button>
      </div>
    </div>

    <!-- 同步紀錄 -->
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-hidden">
      <div class="px-5 py-4 border-b border-[#2d3748]">
        <h3 class="text-sm font-bold text-gray-200">📋 近期同步紀錄</h3>
      </div>
      <div v-if="loadingLogs" class="py-8 text-center text-gray-500">載入中…</div>
      <div v-else-if="syncLogs.length === 0" class="py-8 text-center text-gray-600">
        尚無同步紀錄（API 實作後顯示）
      </div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-[#2d3748] text-xs text-gray-500 uppercase">
            <th class="px-5 py-2 text-left">時間</th>
            <th class="px-5 py-2 text-left">來源</th>
            <th class="px-5 py-2 text-center">狀態</th>
            <th class="px-5 py-2 text-right">筆數</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#2d3748]">
          <tr v-for="log in syncLogs" :key="log.id" class="hover:bg-[#1f2937]">
            <td class="px-5 py-2.5 text-gray-500 text-xs">{{ fmtDateTime(log.created_at) }}</td>
            <td class="px-5 py-2.5 text-gray-300">{{ log.source }}</td>
            <td class="px-5 py-2.5 text-center">
              <span class="text-xs font-bold px-2 py-0.5 rounded-full"
                :class="log.success ? 'bg-emerald-900/50 text-emerald-400' : 'bg-red-900/50 text-red-400'">
                {{ log.success ? '成功' : '失敗' }}
              </span>
            </td>
            <td class="px-5 py-2.5 text-right text-gray-400">{{ log.records_count ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- LINE Messaging API 說明 Modal -->
  <div v-if="showLineHelpModal"
    class="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
    @click.self="showLineHelpModal = false">
    <div class="bg-[#1a202c] border border-[#2d3748] rounded-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto">
      <div class="px-6 py-4 border-b border-[#2d3748] flex items-center justify-between sticky top-0 bg-[#1a202c] z-10">
        <h3 class="font-bold text-gray-100">LINE Messaging API 設定說明</h3>
        <button @click="showLineHelpModal = false" class="text-gray-500 hover:text-gray-300 text-xl leading-none">✕</button>
      </div>
      <div class="px-6 py-5 space-y-6 text-sm">

        <!-- 第一節：Channel Secret -->
        <div>
          <h4 class="text-[#63b3ed] font-bold mb-2 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-[#63b3ed]/20 text-[#63b3ed] text-xs flex items-center justify-center font-bold shrink-0">1</span>
            取得 Channel Secret
          </h4>
          <ol class="space-y-1.5 text-gray-400 pl-7 list-decimal list-inside">
            <li>前往 <span class="text-gray-200 font-mono text-xs bg-[#0f1117] px-1.5 py-0.5 rounded">developers.line.biz</span> 並登入</li>
            <li>選擇你的 Messaging API Channel</li>
            <li>點選「Basic settings」分頁</li>
            <li>找到「Channel secret」欄位並複製</li>
          </ol>
        </div>

        <!-- 第二節：Access Token -->
        <div>
          <h4 class="text-[#63b3ed] font-bold mb-2 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-[#63b3ed]/20 text-[#63b3ed] text-xs flex items-center justify-center font-bold shrink-0">2</span>
            取得 Channel Access Token（長期）
          </h4>
          <ol class="space-y-1.5 text-gray-400 pl-7 list-decimal list-inside">
            <li>在同一個 Channel 頁面，點選「Messaging API」分頁</li>
            <li>找到「Channel access token (long-lived)」區塊</li>
            <li>點「Issue」產生後複製（長期 Token 不需每次重新產生）</li>
          </ol>
        </div>

        <!-- 第三節：Webhook URL -->
        <div>
          <h4 class="text-[#63b3ed] font-bold mb-2 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-[#63b3ed]/20 text-[#63b3ed] text-xs flex items-center justify-center font-bold shrink-0">3</span>
            設定 Webhook URL
          </h4>
          <ol class="space-y-1.5 text-gray-400 pl-7 list-decimal list-inside">
            <li>在「Messaging API」分頁找到「Webhook settings」</li>
            <li>點「Edit」填入以下網址：</li>
          </ol>
          <div class="mt-2 ml-7 bg-[#0f1117] border border-[#2d3748] rounded-lg px-3 py-2 font-mono text-xs text-gray-300 break-all select-all">
            https://preoffensive-chasteningly-taunya.ngrok-free.dev/api/v1/webhook/line
          </div>
          <p class="mt-2 ml-7 text-gray-600 text-xs">記得勾選「Use webhook」並點「Verify」確認回應正常</p>
        </div>

        <!-- 第四節：廠商群組配對 -->
        <div>
          <h4 class="text-[#63b3ed] font-bold mb-2 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-[#63b3ed]/20 text-[#63b3ed] text-xs flex items-center justify-center font-bold shrink-0">4</span>
            廠商 LINE 群組自動配對流程
          </h4>
          <div class="space-y-2 text-gray-400 pl-7">
            <div class="flex items-start gap-2">
              <span class="text-emerald-400 shrink-0">①</span>
              <span>請廠商建立 LINE 群組，並將本系統的 LINE Bot 加入群組</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-emerald-400 shrink-0">②</span>
              <span>Bot 加入後系統自動偵測並記錄群組 ID（<span class="text-gray-300">C 開頭的字串</span>）</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-emerald-400 shrink-0">③</span>
              <span>前往「<span class="text-gray-200">庫存管理 → 供應商管理</span>」頁面</span>
            </div>
            <div class="flex items-start gap-2">
              <span class="text-emerald-400 shrink-0">④</span>
              <span>選擇對應廠商，在「LINE 群組」欄位從下拉選取偵測到的群組，儲存完成配對</span>
            </div>
          </div>
          <div class="mt-3 ml-7 bg-amber-900/20 border border-amber-800/40 rounded-lg px-3 py-2">
            <p class="text-amber-400 text-xs">若群組清單為空，請確認 Bot 已成功加入群組，且 Webhook 設定正確並通過 Verify。</p>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>
