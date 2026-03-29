<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const period = ref('month')
const plData = ref(null)
const trendData = ref([])
const loading = ref(true)
const trendMonths = ref(6)
const chartCanvas = ref(null)

function authHeaders() { return { Authorization: `Bearer ${auth.token}` } }

async function load() {
  loading.value = true
  const [plRes, trendRes] = await Promise.all([
    fetch(`${API_BASE}/reports/pl?period=${period.value}`, { headers: authHeaders() }),
    fetch(`${API_BASE}/reports/pl/trend?months=${trendMonths.value}`, { headers: authHeaders() }),
  ])
  if (plRes.ok) plData.value = await plRes.json()
  if (trendRes.ok) trendData.value = await trendRes.json()
  loading.value = false
  setTimeout(drawChart, 50)
}

onMounted(load)
watch([period, trendMonths], load)

function drawChart() {
  const canvas = chartCanvas.value
  if (!canvas || !trendData.value.length) return
  const ctx = canvas.getContext('2d')
  const data = trendData.value
  const W = canvas.width = canvas.offsetWidth
  const H = canvas.height = 160
  ctx.clearRect(0, 0, W, H)

  const maxVal = Math.max(...data.map(d => Math.max(d.revenue, d.expenses, 1)))
  const padL = 50, padR = 10, padT = 10, padB = 30
  const chartW = W - padL - padR
  const chartH = H - padT - padB
  const barW = Math.floor(chartW / data.length * 0.3)
  const gap = chartW / data.length

  // Grid lines
  ctx.strokeStyle = '#374151'
  ctx.lineWidth = 1
  for (let i = 0; i <= 4; i++) {
    const y = padT + (chartH / 4) * i
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke()
  }

  data.forEach((d, i) => {
    const x = padL + gap * i + gap / 2

    // Revenue bar (green)
    const revH = maxVal > 0 ? (d.revenue / maxVal) * chartH : 0
    ctx.fillStyle = '#10b981'
    ctx.fillRect(x - barW - 2, padT + chartH - revH, barW, revH)

    // Expense bar (red)
    const expH = maxVal > 0 ? (d.expenses / maxVal) * chartH : 0
    ctx.fillStyle = '#ef4444'
    ctx.fillRect(x + 2, padT + chartH - expH, barW, expH)

    // X label
    ctx.fillStyle = '#9ca3af'
    ctx.font = '11px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(d.label, x, H - 8)
  })

  // Net profit line (orange)
  ctx.strokeStyle = '#e85d04'
  ctx.lineWidth = 2
  ctx.beginPath()
  data.forEach((d, i) => {
    const x = padL + gap * i + gap / 2
    const y = padT + chartH - (maxVal > 0 ? (Math.max(0, d.net) / maxVal) * chartH : 0)
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
  })
  ctx.stroke()
}

function fmtMoney(n) { return Number(n || 0).toLocaleString('zh-TW') }
function fmtPct(p) { if (p === null || p === undefined) return '—'; return (p >= 0 ? '+' : '') + p + '%' }
function pctClass(p) { if (!p) return 'text-gray-500'; return p >= 0 ? 'text-emerald-400' : 'text-red-400' }
</script>

<template>
  <div class="space-y-5">
    <!-- Period tabs -->
    <div class="flex items-center gap-2">
      <button v-for="t in [{v:'month',l:'本月'},{v:'quarter',l:'本季'},{v:'year',l:'本年'}]" :key="t.v"
        @click="period = t.v"
        class="px-4 py-2 rounded-lg text-sm font-bold transition-colors"
        :class="period === t.v ? 'bg-[#63b3ed] text-[#0f1117]' : 'text-gray-400 bg-[#1a202c] border border-[#2d3748] hover:bg-[#1f2937]'">
        {{ t.l }}
      </button>
    </div>

    <div v-if="loading" class="p-8 text-center text-gray-500">載入中…</div>
    <template v-else-if="plData">
      <!-- KPI cards -->
      <div class="grid grid-cols-5 gap-3">
        <div v-for="kpi in [
          {key:'revenue', label:'營收', color:'text-emerald-400'},
          {key:'cogs', label:'成本', color:'text-red-400'},
          {key:'gross_profit', label:'毛利', color:'text-emerald-400'},
          {key:'expenses', label:'費用', color:'text-red-400'},
          {key:'net_profit', label:'淨利', color:'text-emerald-400'},
        ]" :key="kpi.key" class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-3">
          <p class="text-xs text-[#9ca3af]">{{ kpi.label }}</p>
          <p class="text-xl font-black mt-1" :class="kpi.color">
            ${{ fmtMoney(plData.kpis[kpi.key]?.current) }}
          </p>
          <p class="text-xs mt-0.5" :class="pctClass(plData.kpis[kpi.key]?.change_percent)">
            {{ fmtPct(plData.kpis[kpi.key]?.change_percent) }}
          </p>
        </div>
      </div>

      <!-- Trend chart -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-bold text-[#9ca3af] uppercase">趨勢圖</p>
          <div class="flex gap-2">
            <button v-for="m in [6, 12]" :key="m" @click="trendMonths = m"
              class="text-xs px-3 py-1 rounded-full font-bold transition-colors"
              :class="trendMonths === m ? 'bg-[#e85d04] text-white' : 'bg-[#1f2937] text-gray-400 hover:bg-[#2d3748]'">
              {{ m }}個月
            </button>
          </div>
        </div>
        <!-- Legend -->
        <div class="flex gap-4 mb-2 text-xs">
          <span class="flex items-center gap-1"><span class="w-3 h-3 bg-emerald-500 inline-block rounded-sm"></span> 收入</span>
          <span class="flex items-center gap-1"><span class="w-3 h-3 bg-red-500 inline-block rounded-sm"></span> 支出</span>
          <span class="flex items-center gap-1"><span class="w-3 h-1.5 inline-block rounded" style="background:#e85d04"></span> 淨利</span>
        </div>
        <canvas ref="chartCanvas" class="w-full" style="height:160px"></canvas>
      </div>

      <!-- P&L Tables -->
      <!-- Revenue -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
        <div class="px-4 py-3 border-b border-[#2d3748] bg-emerald-900/20">
          <p class="text-xs font-bold text-emerald-400 uppercase">收入明細</p>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-4 py-3 text-left">科目</th>
              <th class="px-4 py-3 text-right">本期</th>
              <th class="px-4 py-3 text-right">上期</th>
              <th class="px-4 py-3 text-right">差異</th>
              <th class="px-4 py-3 text-right">變化率</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="line in plData.revenue_lines" :key="line.account" class="hover:bg-[#1f2937]">
              <td class="px-4 py-3 text-gray-300">{{ line.account }}</td>
              <td class="px-4 py-3 text-right font-mono text-emerald-400">${{ fmtMoney(line.current) }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-500">${{ fmtMoney(line.previous) }}</td>
              <td class="px-4 py-3 text-right font-mono" :class="line.variance >= 0 ? 'text-emerald-400' : 'text-red-400'">
                {{ line.variance >= 0 ? '+' : '' }}${{ fmtMoney(line.variance) }}
              </td>
              <td class="px-4 py-3 text-right text-xs" :class="pctClass(line.change_percent)">
                {{ fmtPct(line.change_percent) }}
              </td>
            </tr>
            <!-- Subtotal -->
            <tr class="bg-emerald-900/10 font-bold">
              <td class="px-4 py-3 text-emerald-400">小計</td>
              <td class="px-4 py-3 text-right font-mono text-emerald-400">${{ fmtMoney(plData.kpis.revenue?.current) }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-500">${{ fmtMoney(plData.kpis.revenue?.previous) }}</td>
              <td class="px-4 py-3 text-right font-mono text-emerald-400">
                +${{ fmtMoney((plData.kpis.revenue?.current || 0) - (plData.kpis.revenue?.previous || 0)) }}
              </td>
              <td class="px-4 py-3 text-right text-xs" :class="pctClass(plData.kpis.revenue?.change_percent)">
                {{ fmtPct(plData.kpis.revenue?.change_percent) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Expenses -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl overflow-x-auto">
        <div class="px-4 py-3 border-b border-[#2d3748] bg-red-900/20">
          <p class="text-xs font-bold text-red-400 uppercase">支出明細</p>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-[#2d3748] text-xs text-[#9ca3af] uppercase">
              <th class="px-4 py-3 text-left">科目</th>
              <th class="px-4 py-3 text-right">本期</th>
              <th class="px-4 py-3 text-right">上期</th>
              <th class="px-4 py-3 text-right">差異</th>
              <th class="px-4 py-3 text-right">變化率</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#2d3748]">
            <tr v-for="line in plData.expense_lines" :key="line.account" class="hover:bg-[#1f2937]">
              <td class="px-4 py-3 text-gray-300">{{ line.account }}</td>
              <td class="px-4 py-3 text-right font-mono text-red-400">${{ fmtMoney(line.current) }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-500">${{ fmtMoney(line.previous) }}</td>
              <td class="px-4 py-3 text-right font-mono" :class="line.variance >= 0 ? 'text-red-400' : 'text-emerald-400'">
                {{ line.variance >= 0 ? '+' : '' }}${{ fmtMoney(line.variance) }}
              </td>
              <td class="px-4 py-3 text-right text-xs" :class="pctClass(line.change_percent)">
                {{ fmtPct(line.change_percent) }}
              </td>
            </tr>
            <!-- Subtotal -->
            <tr class="bg-red-900/10 font-bold">
              <td class="px-4 py-3 text-red-400">小計</td>
              <td class="px-4 py-3 text-right font-mono text-red-400">${{ fmtMoney(plData.kpis.expenses?.current) }}</td>
              <td class="px-4 py-3 text-right font-mono text-gray-500">${{ fmtMoney(plData.kpis.expenses?.previous) }}</td>
              <td class="px-4 py-3 text-right font-mono text-red-400">
                +${{ fmtMoney((plData.kpis.expenses?.current || 0) - (plData.kpis.expenses?.previous || 0)) }}
              </td>
              <td class="px-4 py-3 text-right text-xs" :class="pctClass(plData.kpis.expenses?.change_percent)">
                {{ fmtPct(plData.kpis.expenses?.change_percent) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Net Profit Summary -->
      <div class="bg-[#1a202c] border border-[#2d3748] rounded-xl p-4 flex items-center justify-between">
        <span class="text-sm font-bold text-gray-300">{{ plData.period_label }} 淨利</span>
        <span class="text-3xl font-black" :class="(plData.kpis.net_profit?.current || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
          {{ (plData.kpis.net_profit?.current || 0) >= 0 ? '+' : '' }}${{ fmtMoney(plData.kpis.net_profit?.current) }}
        </span>
      </div>
    </template>
  </div>
</template>
