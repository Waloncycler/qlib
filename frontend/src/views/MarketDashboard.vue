<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">Market Dashboard</h1>
        <p class="subtitle">市场总览 · 历史趋势 + 当日数据 + AI 策略</p>
      </div>
      <div class="actions">
        <!-- Tabs -->
        <div class="tab-bar glass-panel">
          <button
            v-for="tab in tabs" :key="tab.key"
            :class="{ active: activeTab === tab.key }"
            @click="activeTab = tab.key"
          >{{ tab.label }}</button>
        </div>
        <!-- Refresh -->
        <button v-if="activeTab === 'trend'" class="btn-refresh" @click="handleRefresh" :disabled="loading || backendUpdating">
          <RefreshCwIcon class="icon" :class="{ 'spin': loading || backendUpdating }" />
          {{ backendUpdating ? 'Updating...' : 'Refresh' }}
        </button>
        <button v-if="activeTab === 'trend'" class="btn-refresh" @click="triggerScan" :disabled="scanning">
          <LoaderIcon v-if="scanning" class="icon spin" />
          <ZapIcon v-else class="icon" />
          {{ scanning ? '分析中...' : '扫描' }}
        </button>
      </div>
    </header>

    <div v-if="error" class="error-panel glass-panel">
      <AlertTriangleIcon class="icon error-icon" />
      <p>{{ error }}</p>
    </div>

    <!-- ========== Tab: 趋势图表 ========== -->
    <template v-if="activeTab === 'trend'">
      <!-- Summary Stats -->
      <div class="grid-cards">
        <div class="stat-card glass-panel" v-for="stat in summaryStats" :key="stat.label">
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-value" :class="stat.colorClass">{{ stat.value }}</div>
        </div>
      </div>

      <!-- Table toggle -->
      <div class="view-toggle glass-panel">
        <button :class="{ active: displayMode === 'charts' }" @click="displayMode = 'charts'">
          <i class="fa-solid fa-chart-line mr-2"></i> Charts
        </button>
        <button :class="{ active: displayMode === 'table' }" @click="displayMode = 'table'">
          <i class="fa-solid fa-table mr-2"></i> Table
        </button>
      </div>

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

      <!-- Charts Grid -->
      <div class="charts-grid" v-show="displayMode === 'charts'">
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">1. Sentiment & Distribution</h3>
          <v-chart class="chart" :option="opts.c1" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">2. Market Breadth: Highs</h3>
          <v-chart class="chart" :option="opts.c2" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">3. Market Breadth: Lows</h3>
          <v-chart class="chart" :option="opts.c3" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">4. Limit Up / Down Pool</h3>
          <v-chart class="chart" :option="opts.c4" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">5. Speculation Quality</h3>
          <v-chart class="chart" :option="opts.c6" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">6. Board Structure</h3>
          <v-chart class="chart" :option="opts.c7" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">7. Institutional LHB Flow</h3>
          <v-chart class="chart" :option="opts.c8" group="market" autoresize />
        </div>
        <div class="chart-panel glass-panel">
          <h3 class="chart-title">8. Extreme Signals</h3>
          <v-chart class="chart" :option="opts.c10" group="market" autoresize />
        </div>
      </div>

      <!-- Pulse Snapshot (merged into trend tab) -->
      <div v-if="pulseData" class="pulse-section">
        <h3 class="section-divider">当日快照 · {{ pulseData.date }}</h3>

        <!-- Sector & Concept -->
        <div class="two-col" v-if="hasCharts">
          <div v-if="pulseData.structured?.top_sectors?.length" class="chart-card glass-panel">
            <h4 class="card-title">行业板块涨幅 Top 10</h4>
            <v-chart class="bar-chart" :option="sectorBarOption" autoresize />
          </div>
          <div v-if="pulseData.structured?.top_concepts?.length" class="chart-card glass-panel">
            <h4 class="card-title">概念题材涨幅 Top 10</h4>
            <v-chart class="bar-chart" :option="conceptBarOption" autoresize />
          </div>
        </div>
      </div>
    </template>

    <!-- ========== Tab: AI 策略报告 ========== -->
    <template v-if="activeTab === 'report'">
      <div v-if="pulseData?.report" class="report-panel glass-panel" id="report-card">
        <div class="report-header">
          <SparklesIcon class="icon-accent" />
          <h3>每日市场策略简报</h3>
          <span class="report-date">{{ pulseData.date }}</span>
          <button class="btn-export" @click="exportReportImage" :disabled="exporting">
            {{ exporting ? '导出中...' : '导出图片' }}
          </button>
        </div>
        <div class="report-content" v-html="renderMarkdown(pulseData.report)"></div>
      </div>
      <div v-else class="empty-panel glass-panel">
        <div class="empty-content">
          <SparklesIcon class="icon-large" />
          <h3>暂无 AI 报告</h3>
          <p>请先在「当日快照」Tab 执行扫描</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import {
  RefreshCwIcon, AlertTriangleIcon, LoaderIcon, ZapIcon,
  CalendarIcon, ClockIcon, SparklesIcon, ActivityIcon
} from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'

// ===== Tab 管理 =====
const tabs = [
  { key: 'trend', label: '趋势图表' },
  { key: 'report', label: 'AI 策略报告' },
]
const activeTab = ref('trend')

// ===== 历史趋势数据 (原 MarketDashboard 逻辑) =====
const { loading, error, fetchCsv, triggerBackendRefresh, checkRefreshStatus } = useDataLoader()
const backendUpdating = ref(false)
const sentimentData = ref([])
const displayMode = ref('charts')
const opts = shallowRef({ c1: {}, c2: {}, c3: {}, c4: {}, c6: {}, c7: {}, c8: {}, c10: {} })

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
  }, 5000)
}

const summaryStats = computed(() => {
  if (!sentimentData.value.length) return []
  const latest = sentimentData.value[sentimentData.value.length - 1]
  return [
    { label: 'Date', value: latest.date, colorClass: '' },
    { label: 'Up / Down', value: `${latest.up_count} / ${latest.down_count}`, colorClass: latest.up_count > latest.down_count ? 'up' : 'down' },
    { label: 'Limit Up', value: latest.limit_up_count, colorClass: 'up' },
    { label: 'Limit Down', value: latest.limit_down_count, colorClass: 'down' },
    { label: 'Sentiment', value: Number(latest.sentiment_score).toFixed(2), colorClass: 'text-accent' }
  ]
})

const tableColumns = computed(() => {
  if (!sentimentData.value?.length) return []
  return ['date', ...Object.keys(sentimentData.value[0]).filter(k => k !== 'date')]
})

const formatTableCell = (val) => {
  if (val === null || val === undefined) return '--'
  if (typeof val === 'number' && val % 1 !== 0) return val.toFixed(2)
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
  const o = {}

  o.c1 = merge({
    legend: { data: ['Score', 'Up', 'Down'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Score', max: 100, splitLine: { show: false } }],
    series: [
      { name: 'Up', type: 'bar', stack: 'a', data: data.map(d => d.up_count ?? d.up_num), color: '#10b981' },
      { name: 'Down', type: 'bar', stack: 'a', data: data.map(d => d.down_count ?? d.down_num), color: '#f43f5e' },
      { name: 'Score', type: 'line', yAxisIndex: 1, data: data.map(d => d.sentiment_score), color: '#f59e0b', smooth: true }
    ]
  })

  o.c2 = merge({
    legend: { data: ['Index', 'Hi120', 'Hi60', 'Hi20'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Index', position: 'right', scale: true, splitLine: { show: false } }],
    series: [
      { name: 'Index', type: 'line', yAxisIndex: 1, data: data.map(d => d.index_close), color: 'rgba(255,255,255,0.2)', lineStyle: { type: 'dashed' } },
      { name: 'Hi120', type: 'line', data: data.map(d => d.high120), color: '#ef4444' },
      { name: 'Hi60', type: 'line', data: data.map(d => d.high60), color: '#f87171' },
      { name: 'Hi20', type: 'line', data: data.map(d => d.high20), color: '#fca5a5' }
    ]
  })

  o.c3 = merge({
    legend: { data: ['Index', 'Lo120', 'Lo60', 'Lo20'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Index', position: 'right', scale: true, splitLine: { show: false } }],
    series: [
      { name: 'Index', type: 'line', yAxisIndex: 1, data: data.map(d => d.index_close), color: 'rgba(255,255,255,0.2)', lineStyle: { type: 'dashed' } },
      { name: 'Lo120', type: 'line', data: data.map(d => d.low120), color: '#0ea5e9' },
      { name: 'Lo60', type: 'line', data: data.map(d => d.low60), color: '#38bdf8' },
      { name: 'Lo20', type: 'line', data: data.map(d => d.low20), color: '#7dd3fc' }
    ]
  })

  // Merged: Limit Up + Limit Down
  o.c4 = merge({
    legend: { data: ['RealUp', 'ST-Up', 'Broken', 'RealDn', 'ST-Dn'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Count' },
    series: [
      { name: 'RealUp', type: 'bar', stack: 'up', data: data.map(d => d.real_limit_up_count ?? d.uplimit_n_num ?? d.limit_up_count ?? d.uplimit_num ?? 0), color: '#ef4444' },
      { name: 'ST-Up', type: 'bar', stack: 'up', data: data.map(d => d.st_limit_up_count ?? 0), color: '#fca5a5' },
      { name: 'Broken', type: 'bar', stack: 'up', data: data.map(d => d.broken_limit_up_count ?? d.zb_num ?? 0), color: '#f59e0b' },
      { name: 'RealDn', type: 'bar', stack: 'dn', data: data.map(d => -(d.real_limit_down_count ?? d.limit_down_count ?? d.downlimit_num ?? 0)), color: '#0ea5e9' },
      { name: 'ST-Dn', type: 'bar', stack: 'dn', data: data.map(d => -(d.st_limit_down_count ?? 0)), color: '#7dd3fc' }
    ]
  })

  o.c6 = merge({
    legend: { data: ['PrevRet%', 'BrokenRate%'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Percent' },
    series: [
      { name: 'PrevRet%', type: 'line', data: data.map(d => d.yesterday_limit_up_avg_return), color: '#8b5cf6' },
      { name: 'BrokenRate%', type: 'line', data: data.map(d => {
        if (d.broken_limit_up_rate != null && !isNaN(d.broken_limit_up_rate)) return d.broken_limit_up_rate * 100
        const zb = d.broken_limit_up_count ?? d.zb_num ?? 0
        const zt = d.limit_up_count ?? d.uplimit_num ?? 0
        return zb + zt > 0 ? (zb / (zb + zt)) * 100 : 0
      }), color: '#d946ef' }
    ]
  })

  o.c7 = merge({
    legend: { data: ['2-Con', '3+Con', 'MaxHeight'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'Count' }, { type: 'value', name: 'Height', position: 'right', splitLine: { show: false } }],
    series: [
      { name: '2-Con', type: 'bar', data: data.map(d => d.lb_2_count ?? d.consecutive_limit_up_2_count ?? d.lb_2_num), color: '#ec4899' },
      { name: '3+Con', type: 'bar', data: data.map(d => d.lb_3_plus_count ?? d.consecutive_limit_up_3_plus_count ?? d.lb_3_num ?? d.lb_h_num), color: '#9d174d' },
      { name: 'MaxHeight', type: 'line', yAxisIndex: 1, data: data.map(d => d.highest_consecutive_limit_up ?? d.max_lb_num), color: '#fff', smooth: true }
    ]
  })

  o.c8 = merge({
    legend: { data: ['NetBuy(10k)', 'Stocks'], textStyle: { color: '#94a3b8' } },
    yAxis: [{ type: 'value', name: 'NetBuy' }, { type: 'value', name: 'Stocks', position: 'right', splitLine: { show: false } }],
    series: [
      { name: 'NetBuy(10k)', type: 'bar', data: data.map(d => d.dt_net_buy_wan / 10000), color: '#10b981' },
      { name: 'Stocks', type: 'line', yAxisIndex: 1, data: data.map(d => d.dt_stock_count), color: '#38bdf8' }
    ]
  })

  o.c10 = merge({
    legend: { data: ['Tiandi', 'Ditian', 'BigLeg'], textStyle: { color: '#94a3b8' } },
    yAxis: { type: 'value', name: 'Count' },
    series: [
      { name: 'Tiandi', type: 'bar', data: data.map(d => d.tiandi_num), color: '#ef4444' },
      { name: 'Ditian', type: 'bar', data: data.map(d => d.ditian_num), color: '#10b981' },
      { name: 'BigLeg', type: 'line', data: data.map(d => d.bigleg_num), color: '#38bdf8', smooth: true }
    ]
  })

  opts.value = o
}

const loadData = async () => {
  const data = await fetchCsv('signals', 'market_sentiment.csv')
  let enhanced = []
  try { enhanced = await fetchCsv('signals', 'market_sentiment_enhanced.csv') } catch {}

  if (data?.length) {
    if (enhanced?.length) {
      const map = {}
      enhanced.forEach(d => { map[d.date] = d })
      data.forEach(d => {
        const ext = map[d.date]
        if (ext) for (const k in ext) if (d[k] === undefined || d[k] === null) d[k] = ext[k]
      })
    }
    sentimentData.value = data
    buildCharts(data)
  }
}

// ===== Market Pulse 数据 =====
const pulseData = ref(null)
const loadingPulse = ref(false)
const pulseError = ref(null)
const scanning = ref(false)
const exporting = ref(false)

const loadPulse = async () => {
  loadingPulse.value = true
  pulseError.value = null
  try {
    const res = await fetch('/api/market/pulse')
    const data = await res.json()
    if (data.status === 'success') pulseData.value = data.data
    else throw new Error(data.message || 'Failed')
  } catch (e) { pulseError.value = e.message }
  finally { loadingPulse.value = false }
}

const triggerScan = async () => {
  scanning.value = true
  pulseError.value = null
  try {
    const res = await fetch('/api/market/pulse/scan', { method: 'POST' })
    if (!res.ok) throw new Error(`Server returned ${res.status}`)
    const data = await res.json()
    if (data.status === 'success') pulseData.value = data.data
    else throw new Error(data.detail || data.message || 'Scan failed')
  } catch (e) { pulseError.value = e.message }
  finally { scanning.value = false }
}

const exportReportImage = async () => {
  exporting.value = true
  try {
    // 动态加载 html2canvas
    const { default: html2canvas } = await import('html2canvas')
    const el = document.getElementById('report-card')
    if (!el) return
    const canvas = await html2canvas(el, {
      backgroundColor: '#0f172a',
      scale: 2,
      useCORS: true,
      logging: false,
    })
    // 下载
    const link = document.createElement('a')
    const date = pulseData.value?.date || new Date().toISOString().slice(0, 10)
    link.download = `市场策略简报_${date}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  } catch (e) {
    console.error('Export failed:', e)
    alert('导出失败: ' + e.message)
  } finally {
    exporting.value = false
  }
}

const formatTime = (iso) => {
  if (!iso) return '--'
  try { return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
  catch { return '--' }
}

const numCls = (v) => {
  if (v == null || isNaN(v)) return ''
  if (v > 0) return 'val-up'
  if (v < 0) return 'val-down'
  return ''
}

// Pulse computed
const breadthMetrics = computed(() => {
  const b = pulseData.value?.structured?.market_breadth
  if (!b) return []
  return [
    { label: '上涨', value: b.advance_count ?? '--', cls: 'val-up' },
    { label: '下跌', value: b.decline_count ?? '--', cls: 'val-down' },
    { label: '涨停', value: b.limit_up_count ?? '--', cls: 'val-up' },
    { label: '跌停', value: b.limit_down_count ?? '--', cls: 'val-down' },
    { label: '平盘', value: b.flat_count ?? '--', cls: '' },
  ]
})

const sentimentItems = computed(() => {
  const s = pulseData.value?.structured?.sentiment
  if (!s) return []
  return [
    { label: '首板', value: s.first_board_count ?? '--', cls: 'val-up' },
    { label: '连板', value: s.consecutive_board_count ?? '--', cls: 'val-up' },
    { label: '炸板', value: s.failed_board_count ?? '--', cls: 'val-down' },
    { label: '成功率', value: s.limit_up_success_rate_pct != null ? s.limit_up_success_rate_pct + '%' : '--', cls: numCls(s.limit_up_success_rate_pct) },
  ]
})

const hasSentimentOrCapital = computed(() => pulseData.value?.structured?.sentiment || hasCapital.value)
const hasCapital = computed(() => {
  const b = pulseData.value?.structured?.market_breadth
  if (!b) return false
  return b.total_turnover_yi != null || b.north_net_inflow_yi != null || b.main_net_inflow_yi != null
})

const capitalItems = computed(() => {
  const b = pulseData.value?.structured?.market_breadth
  if (!b) return []
  return [
    { label: '两市成交额', value: b.total_turnover_yi != null ? b.total_turnover_yi.toFixed(0) + '亿' : '--', cls: '' },
    { label: '北向净流入', value: b.north_net_inflow_yi != null ? (b.north_net_inflow_yi > 0 ? '+' : '') + b.north_net_inflow_yi.toFixed(1) + '亿' : '--', cls: numCls(b.north_net_inflow_yi) },
    { label: '主力净流入', value: b.main_net_inflow_yi != null ? (b.main_net_inflow_yi > 0 ? '+' : '') + b.main_net_inflow_yi.toFixed(1) + '亿' : '--', cls: numCls(b.main_net_inflow_yi) },
  ]
})

const sentimentClass = computed(() => {
  const label = pulseData.value?.structured?.sentiment?.sentiment_label || ''
  const score = pulseData.value?.structured?.sentiment?.sentiment_score
  if (label.includes('亢奋') || label.includes('高涨')) return 'tag-hot'
  if (label.includes('低迷') || label.includes('冰点')) return 'tag-cold'
  if (score != null && score >= 70) return 'tag-hot'
  if (score != null && score <= 30) return 'tag-cold'
  return 'tag-neutral'
})

const hasCharts = computed(() => pulseData.value?.structured?.top_sectors?.length > 0 || pulseData.value?.structured?.top_concepts?.length > 0)

const buildHorizontalBar = (data, valueKey, label) => {
  if (!data?.length) return {}
  const sorted = [...data].sort((a, b) => (b[valueKey] ?? -999) - (a[valueKey] ?? -999))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(22,24,30,0.9)', borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f2f2f2', fontSize: 12 }, trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>${label}: <strong style="color:${p.color}">${p.value?.toFixed(2)}%</strong>`
      }
    },
    grid: { top: 8, bottom: 8, left: 8, right: 40, containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: '#9ba1a6', fontSize: 10, formatter: (v) => v + '%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
    yAxis: { type: 'category', data: sorted.map(d => d.name), inverse: true, axisLabel: { color: '#cbd5e1', fontSize: 11 }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisTick: { show: false } },
    series: [{
      type: 'bar',
      data: sorted.map(d => ({ value: d[valueKey] ?? 0, itemStyle: { color: (d[valueKey] ?? 0) > 0 ? '#ef4444' : '#22c55e', borderRadius: [0, 3, 3, 0] } })),
      barWidth: '55%',
      label: { show: true, position: 'right', color: '#9ba1a6', fontSize: 10, formatter: (p) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%' }
    }]
  }
}

const sectorBarOption = computed(() => buildHorizontalBar(pulseData.value?.structured?.top_sectors, 'change_pct', '涨跌幅'))
const conceptBarOption = computed(() => buildHorizontalBar(pulseData.value?.structured?.top_concepts, 'change_pct', '涨跌幅'))

const hasFinance = computed(() => {
  const f = pulseData.value?.structured?.finance
  if (!f) return false
  return f.bank || f.securities || f.insurance
})

const financeBarOption = computed(() => {
  const f = pulseData.value?.structured?.finance
  if (!f) return {}
  const items = []
  if (f.bank?.change_pct != null) items.push({ name: '银行', change_pct: f.bank.change_pct, turnover: f.bank.turnover_yi, inflow: f.bank.main_inflow_yi })
  if (f.securities?.change_pct != null) items.push({ name: '证券', change_pct: f.securities.change_pct, turnover: f.securities.turnover_yi, inflow: f.securities.main_inflow_yi })
  if (f.insurance?.change_pct != null) items.push({ name: '保险', change_pct: f.insurance.change_pct, turnover: f.insurance.turnover_yi, inflow: f.insurance.main_inflow_yi })
  if (!items.length) return {}

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(22,24,30,0.9)', borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f2f2f2' }, trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const item = items[params[0].dataIndex]
        let html = `${item.name}板块<br/>涨跌幅: <strong style="color:${item.change_pct >= 0 ? '#ef4444' : '#22c55e'}">${item.change_pct?.toFixed(2)}%</strong>`
        if (item.turnover != null) html += `<br/>成交额: ${item.turnover?.toFixed(0)}亿`
        if (item.inflow != null) html += `<br/>主力净流入: <span style="color:${item.inflow >= 0 ? '#ef4444' : '#22c55e'}">${item.inflow?.toFixed(1)}亿</span>`
        return html
      }
    },
    grid: { top: 8, bottom: 8, left: 8, right: 50, containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: '#9ba1a6', fontSize: 10, formatter: (v) => v + '%' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
    yAxis: { type: 'category', data: items.map(i => i.name), axisLabel: { color: '#cbd5e1', fontSize: 13, fontWeight: 600 }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisTick: { show: false } },
    series: [{
      type: 'bar',
      data: items.map(i => ({ value: i.change_pct, itemStyle: { color: i.change_pct >= 0 ? '#ef4444' : '#22c55e', borderRadius: [0, 4, 4, 0] } })),
      barWidth: '40%',
      label: { show: true, position: 'right', color: '#9ba1a6', fontSize: 12, fontWeight: 600, formatter: (p) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%' }
    }]
  }
})

// Markdown renderer
const renderMarkdown = (md) => {
  if (!md) return ''
  let html = md
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^---+$/gm, '<hr/>')
    .replace(/^#### (.+)$/gm, '<h5>$1</h5>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br/>')
  html = html.replace(/(<li>.*?<\/li>(<br\/>)?)+/gs, (m) => `<ul>${m.replace(/<br\/>/g, '')}</ul>`)
  return `<p>${html}</p>`
}

// 切换到 report tab 或首次加载时自动加载 pulse 数据
watch(activeTab, (tab) => {
  if (tab === 'report' && !pulseData.value && !pulseError.value) {
    loadPulse()
  }
})

onMounted(() => {
  echarts.connect('market')
  loadData()
  loadPulse()  // 趋势图表 Tab 也需要 pulse 数据（板块/金融图表）
})
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 16px; padding-bottom: 24px; height: 100%; overflow: hidden; }
.header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; flex-shrink: 0; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }
.actions { display: flex; gap: 10px; align-items: center; }

.tab-bar { display: flex; padding: 4px; border-radius: 8px; gap: 2px; }
.tab-bar button {
  background: transparent; border: none; color: var(--text-secondary);
  padding: 8px 18px; border-radius: 6px; cursor: pointer;
  font-weight: 600; transition: all 0.2s; font-size: 0.85rem;
}
.tab-bar button:hover { color: #fff; }
.tab-bar button.active { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }

.view-toggle { display: flex; padding: 4px; border-radius: 8px; gap: 4px; align-self: flex-start; }
.view-toggle button { background: transparent; border: none; color: var(--text-secondary); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
.view-toggle button:hover { color: #fff; }
.view-toggle button.active { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }

.btn-refresh { display: flex; align-items: center; gap: 6px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: all 0.2s; }
.btn-refresh:hover:not(:disabled) { background: rgba(56, 189, 248, 0.25); border-color: #38bdf8; }
.btn-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
.icon.spin { animation: spin 1s linear infinite; }
.icon-sm { width: 14px; height: 14px; opacity: 0.7; }
.icon-accent { width: 18px; height: 18px; color: #facc15; }
.icon-large { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* Stats */
.grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; flex-shrink: 0; }
.stat-card { padding: 16px; display: flex; flex-direction: column; gap: 4px; }
.stat-label { color: var(--text-secondary); font-size: 0.8rem; font-weight: 500; }
.stat-value { font-size: 1.6rem; font-weight: 700; }
.text-accent { color: #38bdf8; }
.up { color: var(--danger); }
.down { color: var(--success); }

/* Charts Grid */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 580px), 1fr)); gap: 16px; overflow-y: auto; flex: 1; }

.pulse-section { margin-top: 20px; }
.section-divider {
  color: #38bdf8; font-size: 1rem; font-weight: bold;
  margin: 20px 0 12px; padding-bottom: 8px;
  border-bottom: 1px solid rgba(56, 189, 248, 0.2);
}
.chart-panel { padding: 14px; display: flex; flex-direction: column; }
.chart-title { font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px; }
.chart { width: 100%; height: 300px; min-height: 300px; }

/* Table */
.table-container { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-radius: 12px; }
.table-scroll { overflow: auto; flex: 1; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; white-space: nowrap; }
.data-table th, .data-table td { padding: 10px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
.data-table th { position: sticky; top: 0; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(8px); color: var(--text-secondary); font-weight: 600; z-index: 10; font-size: 0.75rem; border-bottom: 2px solid rgba(255,255,255,0.1); }
.data-table tr:hover td { background: rgba(255, 255, 255, 0.03); }
.sticky-col { position: sticky; left: 0; background: #0f172a; z-index: 5; font-weight: 700; color: #38bdf8; border-right: 1px solid rgba(255,255,255,0.1); }
.data-table th.sticky-col { z-index: 15; }

/* ===== Pulse Section ===== */
.pulse-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.pulse-meta { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 8px; font-size: 0.8rem; color: var(--text-secondary); flex-shrink: 0; }
.pulse-meta .dot { opacity: 0.4; }
.sentiment-tag { font-weight: 600; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.tag-hot { background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.tag-cold { background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.tag-neutral { background: rgba(250,204,21,0.15); color: #facc15; border: 1px solid rgba(250,204,21,0.3); }

.metrics-row { display: flex; gap: 8px; flex-shrink: 0; }
.metric-card { flex: 1; padding: 12px 16px; border-radius: 8px; text-align: center; }
.metric-label { font-size: 0.7rem; color: rgba(255,255,255,0.4); margin-bottom: 4px; }
.metric-value { font-size: 1.4rem; font-weight: 800; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex-shrink: 0; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }
.chart-card { padding: 14px 16px; border-radius: 10px; }
.card-title { font-size: 0.85rem; color: var(--text-secondary); margin: 0 0 8px 0; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.06); }

.sentiment-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.sent-item { text-align: center; background: rgba(15,23,42,0.3); border-radius: 6px; padding: 8px 4px; }
.sent-num { font-size: 1.2rem; font-weight: 800; }
.sent-label { font-size: 0.68rem; color: rgba(255,255,255,0.4); margin-top: 2px; }

.score-bar-wrapper { margin-top: 10px; }
.score-bar-label { font-size: 0.7rem; color: rgba(255,255,255,0.4); margin-bottom: 4px; }
.score-bar { position: relative; height: 20px; background: rgba(15,23,42,0.5); border-radius: 10px; overflow: hidden; }
.score-bar-fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.score-bar-fill.tag-hot { background: linear-gradient(90deg, rgba(239,68,68,0.3), #ef4444); }
.score-bar-fill.tag-cold { background: linear-gradient(90deg, rgba(34,197,94,0.3), #22c55e); }
.score-bar-fill.tag-neutral { background: linear-gradient(90deg, rgba(250,204,21,0.3), #facc15); }
.score-num { position: absolute; right: 8px; top: 0; line-height: 20px; font-size: 0.72rem; font-weight: 700; color: #fff; }

.capital-grid { display: flex; flex-direction: column; gap: 6px; }
.cap-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: rgba(15,23,42,0.3); border-radius: 6px; }
.cap-label { font-size: 0.75rem; color: rgba(255,255,255,0.5); }
.cap-value { font-size: 1rem; font-weight: 700; }

.bar-chart { width: 100%; height: 280px; }
.finance-chart { width: 100%; height: 180px; }

/* Report */
.report-panel { padding: 16px 20px; border-radius: 12px; flex: 1; overflow-y: auto; }
.report-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.report-header h3 { margin: 0; font-size: 1rem; color: #facc15; }
.btn-export {
  margin-left: auto; padding: 4px 12px; font-size: 0.72rem;
  background: rgba(34,197,94,0.15); color: #4ade80;
  border: 1px solid rgba(34,197,94,0.3); border-radius: 6px;
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.btn-export:hover { background: rgba(34,197,94,0.25); }
.btn-export:disabled { opacity: 0.5; cursor: not-allowed; }
.report-date { font-size: 0.75rem; color: var(--text-secondary); }
.report-content { font-size: 0.82rem; line-height: 1.5; color: var(--text-primary); }
.report-content :deep(h1), .report-content :deep(h2) { font-size: 0.92rem; color: #38bdf8; margin: 10px 0 4px; font-weight: 600; }
.report-content :deep(h3) { font-size: 0.88rem; color: #38bdf8; margin: 8px 0 3px; font-weight: 600; }
.report-content :deep(h4) { font-size: 0.82rem; color: #7dd3fc; margin: 6px 0 2px; font-weight: 600; }
.report-content :deep(h5) { font-size: 0.78rem; color: #7dd3fc; margin: 4px 0 2px; font-weight: 500; }
.report-content :deep(strong) { color: #fff; }
.report-content :deep(code) { background: rgba(56,189,248,0.15); color: #7dd3fc; padding: 1px 4px; border-radius: 3px; font-size: 0.78rem; }
.report-content :deep(ul), .report-content :deep(ol) { padding-left: 18px; margin: 2px 0; }
.report-content :deep(li) { margin: 1px 0; }
.report-content :deep(hr) { border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 8px 0; }
.report-content :deep(p) { margin: 0 0 2px; }

.val-up { color: #ef4444; }
.val-down { color: #22c55e; }

.error-panel { padding: 16px; border-radius: 12px; display: flex; align-items: center; gap: 12px; color: #f87171; flex-shrink: 0; }
.error-panel .error-icon { width: 20px; height: 20px; flex-shrink: 0; }

.empty-panel { flex: 1; display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.empty-content { text-align: center; color: var(--text-secondary); }
.empty-content h3 { margin: 0 0 8px 0; color: var(--text-primary); }
.empty-content p { margin: 0; }

.custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>
