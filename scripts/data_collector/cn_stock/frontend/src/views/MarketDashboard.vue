<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">Market Sentiment Radar</h1>
        <p class="subtitle">Comprehensive Macro Indicators & Breadth</p>
      </div>
      <div class="actions">
        <div class="view-toggle glass-panel">
          <button :class="{ active: displayMode === 'charts' }" @click="displayMode = 'charts'">
            <i class="fa-solid fa-chart-line mr-2"></i> Charts
          </button>
          <button :class="{ active: displayMode === 'table' }" @click="displayMode = 'table'">
            <i class="fa-solid fa-table mr-2"></i> Table
          </button>
        </div>
        <button class="btn-refresh" @click="handleRefresh" :disabled="loading || backendUpdating">
          <RefreshCwIcon class="icon" :class="{ 'spin': loading || backendUpdating }" />
          {{ backendUpdating ? 'Updating Backend...' : 'Refresh' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="error-panel glass-panel">
      <AlertTriangleIcon class="icon error-icon" />
      <p>{{ error }}</p>
    </div>

    <!-- Summary Stats -->
    <div class="grid-cards">
      <div class="stat-card glass-panel" v-for="stat in summaryStats" :key="stat.label">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value" :class="stat.colorClass">{{ stat.value }}</div>
      </div>
    </div>

    <!-- Master Zoom control could be here, but we will rely on chart dataZoom & echarts.connect -->
    
    <!-- Table View -->
    <div class="table-container glass-panel" v-if="displayMode === 'table' && sentimentData.length > 0">
      <div class="table-scroll custom-scrollbar">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in tableColumns" :key="col" :class="{ 'sticky-col': col === 'date' }">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in [...sentimentData].reverse()" :key="idx">
              <td v-for="col in tableColumns" :key="col" :class="{ 'sticky-col': col === 'date' }">
                {{ formatTableCell(row[col]) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 12 Charts Grid -->
    <div class="charts-grid" v-show="displayMode === 'charts'">
      <!-- 1 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">1. Sentiment & Distribution</h3>
        <v-chart class="chart" :option="opts.c1" group="market" autoresize />
      </div>
      <!-- 2 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">2. Market Breadth: Highs</h3>
        <v-chart class="chart" :option="opts.c2" group="market" autoresize />
      </div>
      <!-- 3 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">3. Market Breadth: Lows</h3>
        <v-chart class="chart" :option="opts.c3" group="market" autoresize />
      </div>
      <!-- 4 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">4. Limit Up Pool</h3>
        <v-chart class="chart" :option="opts.c4" group="market" autoresize />
      </div>
      <!-- 5 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">5. Limit Down Pool</h3>
        <v-chart class="chart" :option="opts.c5" group="market" autoresize />
      </div>
      <!-- 6 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">6. Speculation Quality</h3>
        <v-chart class="chart" :option="opts.c6" group="market" autoresize />
      </div>
      <!-- 7 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">7. Board Structure</h3>
        <v-chart class="chart" :option="opts.c7" group="market" autoresize />
      </div>
      <!-- 8 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">8. Institutional LHB Flow</h3>
        <v-chart class="chart" :option="opts.c8" group="market" autoresize />
      </div>
      <!-- 9 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">9. VIP Market Timing Signal</h3>
        <v-chart class="chart" :option="opts.c9" group="market" autoresize />
      </div>
      <!-- 10 -->
      <div class="chart-panel glass-panel">
        <h3 class="chart-title">10. Extreme Signals (Tiandi/Ditian)</h3>
        <v-chart class="chart" :option="opts.c10" group="market" autoresize />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, shallowRef } from 'vue'
import * as echarts from 'echarts/core'
import { RefreshCwIcon, AlertTriangleIcon } from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'

const { loading, error, fetchCsv, triggerBackendRefresh, checkRefreshStatus } = useDataLoader()

const backendUpdating = ref(false)

const handleRefresh = async () => {
  if (backendUpdating.value) return
  backendUpdating.value = true
  
  const res = await triggerBackendRefresh()
  if (res && (res.status === 'started' || res.status === 'busy')) {
    pollStatus()
  } else {
    backendUpdating.value = false
    loadData()
  }
}

const pollStatus = () => {
  const timer = setInterval(async () => {
    const status = await checkRefreshStatus()
    if (!status || !status.running) {
      clearInterval(timer)
      backendUpdating.value = false
      loadData()
    }
  }, 2000)
}

const sentimentData = ref([])
const displayMode = ref('charts')

// Store all options in a shallow object
const opts = shallowRef({
  c1: {}, c2: {}, c3: {}, c4: {}, c5: {}, c6: {}, 
  c7: {}, c8: {}, c9: {}, c10: {}
})

const summaryStats = computed(() => {
  if (!sentimentData.value.length) return []
  const latest = sentimentData.value[sentimentData.value.length - 1]
  return [
    { label: 'Date', value: latest.date, colorClass: '' },
    { label: 'Up / Down', value: `${latest.up_count} / ${latest.down_count}`, colorClass: latest.up_count > latest.down_count ? 'up' : 'down' },
    { label: 'Limit Up', value: latest.limit_up_count, colorClass: 'up' },
    { label: 'Limit Down', value: latest.limit_down_count, colorClass: 'down' },
    { label: 'Sentiment Score', value: Number(latest.sentiment_score).toFixed(2), colorClass: 'text-accent' }
  ]
})

// Dynamic Table Columns
const tableColumns = computed(() => {
  if (!sentimentData.value || !sentimentData.value.length) return []
  const keys = Object.keys(sentimentData.value[0])
  const cols = ['date', ...keys.filter(k => k !== 'date')]
  return cols
})

const formatTableCell = (val) => {
  if (val === null || val === undefined) return '--'
  if (typeof val === 'number') {
    if (val % 1 !== 0) return val.toFixed(2)
  }
  return val
}

const buildCharts = (data) => {
  const dates = data.map(d => String(d.date))
  const common = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    grid: { left: '8%', right: '5%', bottom: '15%', top: '25%' },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#64748b', fontSize: 9 } },
    dataZoom: [{ type: 'inside', start: 80, end: 100 }, { type: 'slider', show: true, bottom: 0, textStyle: { color: '#9ba1a6' } }]
  }

  const merge = (opt) => ({ ...common, ...opt })

  const newOpts = {}

  newOpts.c1 = merge({
    legend: { data: ['Score', 'Up', 'Down'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Score', max: 100, splitLine: { show: false } }],
    series: [
      { name: 'Up', type: 'bar', stack: 'a', data: data.map(d => d.up_count ?? d.up_num), color: '#10b981' },
      { name: 'Down', type: 'bar', stack: 'a', data: data.map(d => d.down_count ?? d.down_num), color: '#f43f5e' },
      { name: 'Score', type: 'line', yAxisIndex: 1, data: data.map(d => d.sentiment_score), color: '#f59e0b', smooth: true }
    ]
  })

  newOpts.c2 = merge({
    legend: { data: ['Index', 'Hi120', 'Hi60', 'Hi20'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Index', position: 'right', scale: true, splitLine: { show: false } }],
    series: [
      { name: 'Index', type: 'line', yAxisIndex: 1, data: data.map(d => d.index_close), color: 'rgba(255,255,255,0.2)', lineStyle: { type: 'dashed' } },
      { name: 'Hi120', type: 'line', data: data.map(d => d.high120), color: '#ef4444' },
      { name: 'Hi60', type: 'line', data: data.map(d => d.high60), color: '#f87171' },
      { name: 'Hi20', type: 'line', data: data.map(d => d.high20), color: '#fca5a5' }
    ]
  })

  newOpts.c3 = merge({
    legend: { data: ['Index', 'Lo120', 'Lo60', 'Lo20'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Index', position: 'right', scale: true, splitLine: { show: false } }],
    series: [
      { name: 'Index', type: 'line', yAxisIndex: 1, data: data.map(d => d.index_close), color: 'rgba(255,255,255,0.2)', lineStyle: { type: 'dashed' } },
      { name: 'Lo120', type: 'line', data: data.map(d => d.low120), color: '#0ea5e9' },
      { name: 'Lo60', type: 'line', data: data.map(d => d.low60), color: '#38bdf8' },
      { name: 'Lo20', type: 'line', data: data.map(d => d.low20), color: '#7dd3fc' }
    ]
  })

  newOpts.c4 = merge({
    legend: { data: ['RealUp', 'ST-Up', 'Broken'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Count' },
    series: [
      { name: 'RealUp', type: 'bar', stack: 'u', data: data.map(d => d.real_limit_up_count ?? d.uplimit_n_num ?? d.limit_up_count ?? d.uplimit_num ?? 0), color: '#ef4444' },
      { name: 'ST-Up', type: 'bar', stack: 'u', data: data.map(d => d.st_limit_up_count ?? 0), color: '#fca5a5' },
      { name: 'Broken', type: 'bar', data: data.map(d => d.broken_limit_up_count ?? d.zb_num ?? 0), color: '#f59e0b' }
    ]
  })

  newOpts.c5 = merge({
    legend: { data: ['RealDn', 'ST-Dn'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Count' },
    series: [
      { name: 'RealDn', type: 'bar', stack: 'd', data: data.map(d => d.real_limit_down_count ?? d.limit_down_count ?? d.downlimit_num ?? 0), color: '#0ea5e9' },
      { name: 'ST-Dn', type: 'bar', stack: 'd', data: data.map(d => d.st_limit_down_count ?? 0), color: '#7dd3fc' }
    ]
  })

  newOpts.c6 = merge({
    legend: { data: ['PrevRet%', 'BrokenRate%'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Percent' },
    series: [
      { name: 'PrevRet%', type: 'line', data: data.map(d => d.yesterday_limit_up_avg_return), color: '#8b5cf6' },
      { name: 'BrokenRate%', type: 'line', data: data.map(d => {
        if (d.broken_limit_up_rate !== null && d.broken_limit_up_rate !== undefined && !isNaN(d.broken_limit_up_rate)) {
          return d.broken_limit_up_rate * 100
        }
        const zb = d.broken_limit_up_count ?? d.zb_num ?? 0
        const zt = d.limit_up_count ?? d.uplimit_num ?? 0
        const total = zb + zt
        return total > 0 ? (zb / total) * 100 : 0
      }), color: '#d946ef' }
    ]
  })

  newOpts.c7 = merge({
    legend: { data: ['2-Con', '3+Con', 'MaxHeight'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Height', position: 'right', splitLine: { show: false } }],
    series: [
      { name: '2-Con', type: 'bar', data: data.map(d => d.lb_2_count ?? d.consecutive_limit_up_2_count ?? d.lb_2_num), color: '#ec4899' },
      { name: '3+Con', type: 'bar', data: data.map(d => d.lb_3_plus_count ?? d.consecutive_limit_up_3_plus_count ?? d.lb_3_num ?? d.lb_h_num), color: '#9d174d' },
      { name: 'MaxHeight', type: 'line', yAxisIndex: 1, data: data.map(d => d.highest_consecutive_limit_up ?? d.max_lb_num), color: '#fff', smooth: true }
    ]
  })

  newOpts.c8 = merge({
    legend: { data: ['NetBuy(10k)', 'Stocks'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'NetBuy' }, { type: 'value', name: 'Stocks', position: 'right', splitLine: { show: false } }],
    series: [
      { name: 'NetBuy(10k)', type: 'bar', data: data.map(d => d.dt_net_buy_wan / 10000), color: '#10b981' },
      { name: 'Stocks', type: 'line', yAxisIndex: 1, data: data.map(d => d.dt_stock_count), color: '#38bdf8' }
    ]
  })

  newOpts.c9 = merge({
    legend: { data: ['Timing Signal'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', axisLabel: { formatter: v => v > 0 ? 'BULL' : v < 0 ? 'BEAR' : 'NEUTRAL' } },
    series: [
      { name: 'Timing Signal', type: 'line', step: 'start', data: data.map(d => d.timing_signal_type ?? d.zizi_market_timing ?? 0), color: '#facc15', lineStyle: { width: 3 } }
    ]
  })

  newOpts.c10 = merge({
    legend: { data: ['Tiandi', 'Ditian', 'BigLeg'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Count' },
    series: [
      { name: 'Tiandi', type: 'bar', data: data.map(d => d.tiandi_num), color: '#ef4444' },
      { name: 'Ditian', type: 'bar', data: data.map(d => d.ditian_num), color: '#10b981' },
      { name: 'BigLeg', type: 'line', data: data.map(d => d.bigleg_num), color: '#38bdf8', smooth: true }
    ]
  })

  opts.value = newOpts
}

const loadData = async () => {
  const data = await fetchCsv('signals', 'market_sentiment.csv')
  
  let enhancedData = []
  try {
    enhancedData = await fetchCsv('signals', 'market_sentiment_enhanced.csv')
  } catch (e) {
    console.warn('Enhanced sentiment data not available or failed to load.')
  }

  if (data && data.length) {
    if (enhancedData && enhancedData.length) {
      const enhancedMap = {}
      enhancedData.forEach(d => { enhancedMap[d.date] = d })
      
      data.forEach(d => {
        const ext = enhancedMap[d.date]
        if (ext) {
          for (const key in ext) {
            if (d[key] === undefined || d[key] === null) {
              d[key] = ext[key]
            }
          }
        }
      })
    }
    
    sentimentData.value = data
    buildCharts(data)
  }
}

onMounted(() => {
  echarts.connect('market')
  loadData()
})
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 24px; padding-bottom: 24px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; flex-shrink: 0; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }
.actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.view-toggle {
  display: flex;
  padding: 4px;
  border-radius: 8px;
  gap: 4px;
}

.view-toggle button {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
  font-size: 0.85rem;
}

.view-toggle button:hover {
  color: #fff;
}

.view-toggle button.active {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.btn-refresh { display: flex; align-items: center; gap: 8px; background: rgba(59, 130, 246, 0.15); color: var(--accent-color); border: 1px solid rgba(59, 130, 246, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
.btn-refresh:hover:not(:disabled) { background: rgba(59, 130, 246, 0.25); box-shadow: 0 0 12px var(--accent-glow); }
.icon.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

.grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; flex-shrink: 0; }
.stat-card { padding: 20px; display: flex; flex-direction: column; gap: 8px; }
.stat-label { color: var(--text-secondary); font-size: 0.9rem; font-weight: 500; }
.stat-value { font-size: 1.8rem; font-weight: 700; }
.text-accent { color: var(--accent-color); }
.up { color: var(--danger); }
.down { color: var(--success); }

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 600px), 1fr));
  gap: 20px;
}

.chart-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.chart-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.chart {
  width: 100%;
  height: 320px;
  min-height: 320px;
}

.table-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 12px;
}

.table-scroll {
  overflow: auto;
  flex: 1;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
  white-space: nowrap;
}

.data-table th, .data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table th {
  position: sticky;
  top: 0;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(8px);
  color: var(--text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  z-index: 10;
  font-size: 0.75rem;
  border-bottom: 2px solid rgba(255,255,255,0.1);
}

.data-table tr:hover td {
  background: rgba(255, 255, 255, 0.03);
}

.sticky-col {
  position: sticky;
  left: 0;
  background: #0f172a;
  z-index: 5;
  font-weight: 700;
  color: #38bdf8;
  border-right: 1px solid rgba(255,255,255,0.1);
}

.data-table th.sticky-col {
  z-index: 15;
  background: rgba(15, 23, 42, 0.95);
}

.custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

@media (max-width: 768px) {
  .dashboard {
    padding-bottom: 30px;
  }
  .stat-card {
    padding: 12px;
  }
  .stat-value {
    font-size: 1.4rem;
  }
  .chart {
    height: 250px;
    min-height: 250px;
  }
}
</style>
