<template>
  <div class="backtest-container">
    <div class="top-control-bar glass-panel">
      <div class="controls-left">
        <div class="control-item">
          <label>Trading Day</label>
          <select v-model="poolDate" class="mini-input" @change="fetchPool">
            <option v-for="d in validDates" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div class="control-item window-control">
          <label>Window:</label>
          <div class="dual-range">
            <span class="range-hint">Pre</span>
            <input type="range" v-model="rangePre" min="0" max="5" step="1" class="mini-slider" />
            <span class="range-val">{{ rangePre }}</span>
            <span class="range-hint" style="margin-left: 8px;">Post</span>
            <input type="range" v-model="rangePost" min="0" max="5" step="1" class="mini-slider" :disabled="isLatestDate" />
            <span class="range-val">{{ isLatestDate ? 0 : rangePost }}</span>
          </div>
        </div>
        <button class="icon-btn" @click="showPool = !showPool" :title="showPool ? 'Hide Pool' : 'Show Pool'">
          {{ showPool ? '📂 Hide Pool' : '📁 Show Pool' }}
        </button>
      </div>

      <div class="controls-right">
        <div class="control-item" style="margin-right: 15px; display: flex; align-items: center; gap: 8px;">
          <label style="color: #60a5fa; font-weight: bold; cursor: pointer;">
            <input type="checkbox" v-model="enableMlFilter" @change="fetchResults" style="accent-color: #3b82f6; width: 16px; height: 16px; cursor: pointer;" />
            🧠 Enable ML Filter (Top 10)
          </label>
        </div>
        <button class="mini-btn" @click="downloadData" :disabled="downloading" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">
          <i class="fa-solid fa-download mr-1"></i>
          {{ downloading ? 'Downloading...' : '📥 Download Data' }}
        </button>
        <button class="mini-btn" @click="runIntelligentBacktest" :disabled="loading" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);">
          <i class="fa-solid fa-play mr-1"></i>
          {{ loading ? 'Running...' : 'Run Backtest' }}
        </button>
      </div>
    </div>

    <transition name="slide">
      <div v-if="showPool" class="top-pool-section glass-panel">
        <div class="pool-content">
          <!-- AI Reports Row -->
          <div class="pool-row">
            <div class="row-label">AI</div>
            <div class="horizontal-scroll">
              <div v-for="(theme, idx) in poolData?.sources?.ai_reports" :key="'ai-'+idx" 
                   class="theme-chip" :class="{'active-chip': selectedTheme?.concept === theme.concept && isComparisonMode}"
                   @click="selectTheme(theme)">
                {{ theme.concept }}
                <span v-if="theme.is_new" class="new-dot"></span>
              </div>
            </div>
          </div>
          <!-- Market Topics Row -->
          <div class="pool-row">
            <div class="row-label">Topics</div>
            <div class="horizontal-scroll">
              <div v-for="(theme, idx) in poolData?.sources?.market_topics" :key="'top-'+idx" 
                   class="theme-chip" :class="{'active-chip': selectedTheme?.concept === theme.concept && isComparisonMode}"
                   @click="selectTheme(theme)">
                {{ theme.concept }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <div class="content-wrapper" v-show="!loading">
      
      <!-- Chart Area (Full Width) -->
      <div class="chart-container glass-panel" style="position: relative; flex: 1;">
        <div v-if="comparisonLoading" class="comparison-overlay">
          <div class="spinner"></div>
          <p>Comparing {{ selectedTheme?.concept }}...</p>
        </div>
        <button v-if="isComparisonMode" @click="isComparisonMode = false" class="close-comparison-btn">
          ✕ Return to Backtest
        </button>
        <v-chart class="chart" :option="chartOption" :update-options="{ notMerge: true }" autoresize />
      </div>

      <!-- Analysis Side Panel -->
      <div class="side-panel-right" v-if="!isComparisonMode">
        <div class="glass-panel p-4 info-card" style="height: 100%; display: flex; flex-direction: column; overflow-y: auto;">
          <h4 class="text-sky-400 font-bold mb-3"><i class="fa-solid fa-chart-line mr-2"></i> Signal Backtest Metrics</h4>
          
          <div class="metrics-row mb-3" v-if="metrics && metrics.total_return !== undefined">
            <div class="mini-metric">
              <span class="l">Total Return</span>
              <span class="v" :class="metrics.total_return >= 0 ? 'text-emerald-400' : 'text-red-400'">{{ (metrics.total_return * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Ann. Return</span>
              <span class="v" :class="metrics.annualized_return >= 0 ? 'text-emerald-400' : 'text-red-400'">{{ (metrics.annualized_return * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Max Drawdown</span>
              <span class="v text-red-400">{{ (metrics.max_drawdown * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Sharpe</span>
              <span class="v text-blue-400">{{ metrics.sharpe_ratio?.toFixed(3) || 'N/A' }}</span>
            </div>
            <div class="mini-metric">
              <span class="l">Hit Rate</span>
              <span class="v text-amber-400">{{ ((metrics.hit_rate || 0) * 100).toFixed(1) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">P/L Ratio</span>
              <span class="v text-purple-400">{{ metrics.profit_loss_ratio?.toFixed(2) || 'N/A' }}</span>
            </div>
            <div class="mini-metric" style="grid-column: span 2;">
              <span class="l">Benchmark Return</span>
              <span class="v text-gray-400">{{ ((metrics.benchmark_total_return || 0) * 100).toFixed(2) }}%</span>
            </div>
          </div>
          <div v-else-if="metrics && metrics.annualized_return !== undefined" class="metrics-row mb-3">
            <div class="mini-metric"><span class="l">Ann. Return</span><span class="v text-emerald-400">{{ (metrics.annualized_return * 100).toFixed(2) }}%</span></div>
            <div class="mini-metric"><span class="l">Max Drawdown</span><span class="v text-red-400">{{ (metrics.max_drawdown * 100).toFixed(2) }}%</span></div>
          </div>
          <div v-else class="text-sm text-gray-400 text-center py-4">Run backtest to see metrics</div>

          <!-- Concept Attribution -->
          <h4 class="text-sky-400 font-bold mt-3 mb-2"><i class="fa-solid fa-tags mr-2"></i> Top Concepts</h4>
          <div class="signals-scroll" style="max-height: 180px;">
            <div v-if="conceptAttribution && conceptAttribution.length > 0">
              <div v-for="(c, idx) in conceptAttribution.slice(0, 15)" :key="idx" 
                   class="mb-1 p-2 rounded text-xs" 
                   :style="{ background: c.total_return > 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: '1px solid ' + (c.total_return > 0 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)') }">
                <div class="flex justify-between">
                  <span class="text-gray-300 truncate" style="max-width: 140px;">{{ c.concept }}</span>
                  <span :class="c.total_return > 0 ? 'text-emerald-400' : 'text-red-400'" class="font-bold">{{ (c.total_return * 100).toFixed(1) }}%</span>
                </div>
                <div class="text-gray-500 mt-1">{{ c.days_active }}d · hit {{ (c.hit_rate * 100).toFixed(0) }}%</div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 text-center py-2">No concept data</div>
          </div>

          <!-- Daily Holdings -->
          <h4 class="text-sky-400 font-bold mt-3 mb-2"><i class="fa-solid fa-list mr-2"></i> Daily Trades</h4>
          <div class="signals-scroll flex-1">
            <div v-if="holdings && holdings.length > 0">
              <div v-for="(h, idx) in reversedHoldings" :key="idx" class="mb-2 p-2 bg-slate-800/50 rounded border border-slate-700/50">
                <div class="text-xs text-gray-400 font-bold mb-1">{{ h.date }} <span class="text-gray-600">· {{ h.holdings?.length || 0 }} held</span></div>
                
                <!-- Entries -->
                <div v-if="h.entries && h.entries.length" class="flex flex-wrap gap-1 mb-1">
                  <span v-for="sym in h.entries" :key="'e'+sym" class="stock-tag" style="padding: 1px 5px; font-size: 0.65rem; background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3);">
                    ▲ {{ sym }} <span v-if="getScore(h.holdings, sym)" class="text-sky-300 ml-1">({{ getScore(h.holdings, sym) }})</span>
                  </span>
                </div>
                
                <!-- Exits -->
                <div v-if="h.exits && h.exits.length" class="flex flex-wrap gap-1">
                  <span v-for="sym in h.exits" :key="'x'+sym" class="stock-tag" style="padding: 1px 5px; font-size: 0.65rem; background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3);">▼ {{ sym }}</span>
                </div>
                
                <!-- Detailed Trades (交割单) -->
                <div v-if="h.trades && h.trades.length" class="mt-2 text-[0.7rem] border-t border-slate-700/50 pt-1">
                  <div class="text-gray-500 mb-1">Transaction Details (交割单)</div>
                  <table class="w-full text-left border-collapse" style="color: #9ca3af;">
                    <thead>
                      <tr>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Symbol</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Action</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Price</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Shares</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Amount</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Fee</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(t, i) in h.trades" :key="'t'+i" class="border-b border-slate-800/50 hover:bg-slate-800">
                        <td class="py-1">{{ t.symbol }}</td>
                        <td class="py-1">
                          <span :class="t.action === 'buy' ? 'text-emerald-400' : 'text-red-400'">{{ t.action.toUpperCase() }}</span>
                          <span class="text-[0.6rem] text-gray-600 ml-1">({{ t.reason }})</span>
                        </td>
                        <td class="py-1">{{ t.price }}</td>
                        <td class="py-1">{{ t.shares }}</td>
                        <td class="py-1">{{ t.amount }}</td>
                        <td class="py-1">{{ t.fee }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                
                <!-- If neither entries nor exits nor trades, just show held count -->
                <div v-if="(!h.entries || !h.entries.length) && (!h.exits || !h.exits.length) && (!h.trades || !h.trades.length) && h.holdings && h.holdings.length" class="text-xs text-gray-500 mt-1">
                  No trades. Holding {{ h.holdings.length }} symbols.
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 text-center py-4">No holdings data</div>
          </div>
        </div>
      </div>


    </div>

    <!-- Global Loading State -->
    <div v-if="loading" class="global-loading-panel">
      <div class="spinner"></div>
      <p>{{ loadingMsg }}</p>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-panel">
      <p>{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
import VChart, { THEME_KEY } from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  AxisPointerComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  AxisPointerComponent
])

const loading = ref(false)
const enableMlFilter = ref(false)
const loadingMsg = ref('Loading...')
const downloading = ref(false)
const error = ref(null)
const metrics = ref(null)
const curveData = ref(null)
const holdings = ref([])
const conceptAttribution = ref([])
const reversedHoldings = computed(() => {
  return [...holdings.value].reverse()
})

// Pool State
const poolDate = ref('')
const validDates = ref([])
const poolData = ref(null)
const poolLoading = ref(false)
const openSource = ref('ai')

// Comparison Mode State
const selectedTheme = ref(null)
const themeStocksData = ref({}) // symbol -> { name, data }
const isComparisonMode = ref(false)
const comparisonLoading = ref(false)
const showPool = ref(true)
const rangePre = ref(1)
const rangePost = ref(1)
const isLatestDate = ref(false)

const selectTheme = async (theme) => {
  selectedTheme.value = theme
  isComparisonMode.value = true
  comparisonLoading.value = true
  themeStocksData.value = {}
  
  const stocks = [
    ...(theme.core_stocks || []),
    ...(theme.other_stocks || [])
  ].slice(0, 15) // Limit to 15 stocks to avoid overcrowding
  
  const date = poolDate.value
  const pre = parseInt(rangePre.value) || 0
  const post = isLatestDate.value ? 0 : (parseInt(rangePost.value) || 0)

  let targetDates = [date]
  if (pre > 0 || post > 0) {
    try {
      const res = await axios.get(`/api/market/trading_days?date=${date}&pre_n=${pre}&post_n=${post}`)
      if (res.data.status === 'success') {
        targetDates = res.data.data
        isLatestDate.value = res.data.is_latest
      }
    } catch (e) {
      console.warn("Failed to fetch trading days", e)
    }
  }

  // Define standard 5-minute intervals for a trading day (uniform width)
  const generateDayGrid = (d) => {
    const grid = []
    // Morning: 09:35 to 11:30
    for (let h = 9; h <= 11; h++) {
      for (let m = 0; m < 60; m += 5) {
        if (h === 9 && m <= 30) continue
        if (h === 11 && m > 30) continue
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
        grid.push(`${d} ${timeStr}`)
      }
    }
    // Afternoon: 13:05 to 15:00
    for (let h = 13; h <= 15; h++) {
      for (let m = 0; m < 60; m += 5) {
        if (h === 13 && m === 0) continue
        if (h === 15 && m > 0) continue
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
        grid.push(`${d} ${timeStr}`)
      }
    }
    return grid
  }

  const allTargetTimes = []
  targetDates.forEach(d => {
    allTargetTimes.push(...generateDayGrid(d))
  })

  const promises = stocks.map(async (s) => {
    let symbol = s.symbol
    if (!symbol && s.name) {
      try {
        const res = await axios.get(`/api/resolve_symbol/${s.name}`)
        symbol = res.data.symbol
      } catch (e) {
        console.warn(`Failed to resolve symbol for ${s.name}`)
      }
    }
    
    if (symbol) {
      try {
        const stockAllData = []
        for (const d of targetDates) {
          const res = await axios.get(`/api/stock/${symbol}/intraday/${d}`)
          if (res.data.status === 'success' && res.data.data) {
            // Filter and downsample/map to 5-min if needed
            // But for now, we just collect and we will map to the grid in getComparisonOption
            const formatted = res.data.data
              .filter(item => item.time <= '15:00')
              .map(item => ({
                ...item,
                time: `${d} ${item.time}`
              }))
            stockAllData.push(...formatted)
          }
        }
        
        if (stockAllData.length > 0) {
          themeStocksData.value[symbol] = {
            name: s.name,
            data: stockAllData,
            grid: allTargetTimes // Attach the grid to keep it consistent
          }
        }
      } catch (err) {
        console.error(`Failed to fetch data for ${symbol}`, err)
      }
    }
  })
  
  await Promise.all(promises)
  comparisonLoading.value = false
}

const toggleSource = (src) => {
  if (openSource.value === src) {
    openSource.value = null
  } else {
    openSource.value = src
  }
}

const goToStock = (symbol) => {
  if (symbol) {
    router.push(`/stock/${symbol}`)
  }
}

const isST = (name) => {
  return name && (name.toUpperCase().includes('ST'))
}

const fetchValidDates = async () => {
  try {
    const res = await axios.get('/api/backtest/pool/dates')
    validDates.value = res.data.dates
    if (validDates.value.length > 0) {
      poolDate.value = validDates.value[0]
      fetchPool()
    }
  } catch (err) {
    console.error("Failed to fetch valid dates:", err)
  }
}

const fetchPool = async () => {
  if (!poolDate.value) return
  poolLoading.value = true
  try {
    const res = await axios.get(`/api/backtest/pool?date=${poolDate.value}`)
    poolData.value = res.data
  } catch (err) {
    console.error("Failed to fetch pool data:", err)
  } finally {
    poolLoading.value = false
  }
}

const form = ref({
  symbol: 'SH600519',
  startDate: '2023-01-01',
  endDate: new Date().toISOString().split('T')[0],
  strategy: 'ai_timing'
})

const getComparisonOption = () => {
  const allData = themeStocksData.value
  const series = []
  const symbols = Object.keys(allData)
  
  const baseOption = {
    title: { 
      textStyle: { color: '#e5e7eb', fontSize: 16 },
      left: 'center',
      top: 5
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#f8fafc' }
    },
    legend: {
      textStyle: { color: '#e5e7eb' },
      bottom: 25,
      type: 'scroll'
    },
    grid: {
      top: '12%',
      bottom: '15%',
      left: '5%',
      right: '5%'
    },
    xAxis: {
      type: 'category',
      axisLabel: { color: '#9ca3af' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      data: []
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { show: true, type: 'slider', bottom: 5, start: 0, end: 100, height: 15 }
    ],
    series: []
  }

  if (symbols.length === 0) {
    return {
      ...baseOption,
      title: { 
        ...baseOption.title,
        text: comparisonLoading.value ? 'Fetching data...' : 'No intraday data found for this theme', 
        textStyle: { color: comparisonLoading.value ? '#9ca3af' : '#ef4444', fontSize: 14 }, 
        top: 'center' 
      },
      legend: { show: false }
    }
  }

  // Use the grid from the first stock (all stocks share the same grid)
  const sortedTimes = allData[symbols[0]].grid || []
  baseOption.xAxis.data = sortedTimes
  
  const pre = parseInt(rangePre.value) || 0
  const post = isLatestDate.value ? 0 : (parseInt(rangePost.value) || 0)

  baseOption.xAxis.axisLabel.interval = (index, value) => {
    if (pre > 0 || post > 0) {
      return value.includes(' 09:30')
    }
    return index % 60 === 0
  }
  baseOption.xAxis.axisLabel.formatter = (value) => {
    const parts = value.split(' ')
    if (pre > 0 || post > 0) {
      return parts[0]
    }
    return parts[1] || parts[0]
  }

  // Boundary markers for each day (at 15:00)
  const markLines = []
  sortedTimes.forEach((t, idx) => {
    if (t.endsWith(' 15:00') && idx < sortedTimes.length - 1) {
      markLines.push({
        xAxis: idx,
        lineStyle: { color: 'rgba(255, 255, 255, 0.3)', type: 'dashed', width: 1 },
        label: { show: false }
      })
    }
  })

  symbols.forEach(s => {
    const stock = allData[s]
    const dataPoints = stock.data
    if (!dataPoints || dataPoints.length === 0) return

    const basePrice = dataPoints[0].pre_close || dataPoints[0].price
    if (!basePrice) return
    
    const relativeData = sortedTimes.map(t => {
      const point = dataPoints.find(p => p.time === t)
      if (point) {
        return ((point.price - basePrice) / basePrice * 100).toFixed(2)
      }
      return null
    })
    
    if (relativeData.some(v => v !== null)) {
      series.push({
        name: stock.name,
        type: 'line',
        data: relativeData,
        showSymbol: false,
        smooth: true,
        connectNulls: true,
        lineStyle: { width: 2 },
        markLine: markLines.length > 0 ? {
          symbol: ['none', 'none'],
          data: markLines
        } : undefined
      })
    }
  })
  
  const title = selectedTheme.value?.concept || 'Theme'

  return {
    ...baseOption,
    title: { ...baseOption.title, text: title },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        let res = `<div style="font-weight:bold;margin-bottom:4px;color:#9ca3af;">${params[0].name}</div>`
        const validParams = params.filter(p => p.value !== null && p.value !== undefined && !isNaN(p.value))
        const sortedParams = validParams.sort((a, b) => Number(b.value) - Number(a.value))
        
        sortedParams.forEach(p => {
          const val = Number(p.value)
          const color = val >= 0 ? '#ef4444' : '#10b981'
          const displayVal = val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)
          res += `<div style="display:flex;justify-content:space-between;gap:20px;">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="font-weight:bold;color:${color};">${displayVal}%</span>
          </div>`
        })
        return res
      }
    },
    legend: { ...baseOption.legend, data: series.map(s => s.name) },
    series: series
  }
}

const chartOption = computed(() => {
  if (isComparisonMode.value) {
    return getComparisonOption()
  }

  // Define default series names to ensure legend matches
  const seriesNames = [
    'AI Strategy Return',
    'Stock Buy&Hold'
  ]

  const baseBacktestOption = {
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      data: seriesNames,
      textStyle: { color: '#e5e7eb' },
      top: 5
    },
    axisPointer: {
      link: { xAxisIndex: 'all' }
    },
    grid: [
      { left: '5%', right: '4%', top: '10%', bottom: '15%' }
    ],
    xAxis: [
      { type: 'category', boundaryGap: false, axisLabel: { color: '#9ca3af' }, data: [] }
    ],
    yAxis: [
      { type: 'value', axisLabel: { color: '#9ca3af', formatter: '{value} %' }, splitLine: { lineStyle: { color: '#374151', type: 'dashed' } } }
    ],
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { show: true, type: 'slider', bottom: '2%', start: 0, end: 100 }
    ],
    series: []
  }

  if (!curveData.value || curveData.value.length === 0) {
    return {
      ...baseBacktestOption,
      title: { text: loading.value ? 'Running backtest...' : 'No backtest data', left: 'center', top: 'center', textStyle: { color: '#9ca3af' } },
      series: seriesNames.map(name => ({ 
        name, 
        type: 'line', 
        data: [] 
      }))
    }
  }

  const dates = curveData.value.map(d => d.date)
  const strategySeries = curveData.value.map(d => (d.strategy * 100).toFixed(2))
  const benchSeries = curveData.value.map(d => (d.benchmark * 100).toFixed(2))

  baseBacktestOption.xAxis[0].data = dates

  return {
    ...baseBacktestOption,
    tooltip: {
      ...baseBacktestOption.tooltip,
      formatter: function(params) {
        let res = '';
        let date = '';
        let strat = '';
        let bench = '';
        
        params.forEach(p => {
          date = p.name;
          if (p.seriesName === 'AI Strategy Return') {
            strat = `<span style="color:#3b82f6;font-weight:bold;">${p.value}%</span>`;
          } else if (p.seriesName === 'Stock Buy&Hold') {
            bench = `<span style="color:#9ca3af;">${p.value}%</span>`;
          }
        });
        
        res += `<div style="font-weight:bold;margin-bottom:4px;color:#f8fafc;">${date}</div>`;
        if (strat) res += `Strategy Return: ${strat}<br/>`;
        if (bench) res += `Benchmark Return: ${bench}<br/>`;
        return res;
      }
    },
    series: [
      {
        name: 'AI Strategy Return',
        type: 'line',
        data: strategySeries,
        itemStyle: { color: '#3b82f6' },
        lineStyle: { width: 3 },
        showSymbol: false,
        smooth: true
      },
      {
        name: 'Stock Buy&Hold',
        type: 'line',
        data: benchSeries,
        itemStyle: { color: '#6b7280' },
        lineStyle: { width: 2, type: 'dashed' },
        showSymbol: false,
        smooth: true
      }
    ]
  }
})

const reversedCurveData = computed(() => {
  if (!curveData.value) return []
  return [...curveData.value].reverse()
})

const runSingleBacktest = async () => {
  if (!form.value.symbol) {
    error.value = "Please enter a stock symbol."
    return
  }

  isComparisonMode.value = false
  loading.value = true
  error.value = null
  try {
    const res = await axios.post('/api/backtest/single', {
      symbol: form.value.symbol,
      start_date: form.value.startDate,
      end_date: form.value.endDate
    })
    
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
    } else {
      error.value = res.data.message || 'Unknown error occurred.'
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const fetchResults = async () => {
  loading.value = true
  loadingMsg.value = 'Loading cached results...'
  error.value = null
  try {
    const res = await axios.get(`/api/backtest/results?enable_ml_filter=${enableMlFilter.value}`)
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics || null
      curveData.value = res.data.data.curve || null
      holdings.value = res.data.data.holdings || []
      conceptAttribution.value = res.data.data.concept_attribution || []
    }
  } catch (err) {
    console.error("Failed to fetch backtest results:", err)
  } finally {
    loading.value = false
  }
}

const downloadData = async () => {
  downloading.value = true
  error.value = null
  try {
    const res = await axios.post('/api/backtest/download-data', {}, { timeout: 1800000 })
    if (res.data.status === 'success') {
      alert(`Downloaded ${res.data.downloaded} stocks (${res.data.failed} failed)`)
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    downloading.value = false
  }
}

const runIntelligentBacktest = async () => {
  isComparisonMode.value = false
  loading.value = true
  loadingMsg.value = enableMlFilter.value ? 'Running ML Hybrid Backtest...' : 'Running Signal Backtest...'
  error.value = null
  try {
    const res = await axios.post(`/api/backtest/intelligent?enable_ml_filter=${enableMlFilter.value}`, {}, { timeout: 600000 })
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
      holdings.value = res.data.data.holdings || []
      conceptAttribution.value = res.data.data.concept_attribution || []
    } else {
      error.value = res.data.message || 'Unknown error occurred.'
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const getScore = (holdingsList, symbol) => {
  if (!holdingsList) return null;
  const item = holdingsList.find(h => h.symbol === symbol);
  return item && item.score !== null ? item.score : null;
}

onMounted(() => {
  fetchResults()
  fetchValidDates()
})
</script>

<style scoped>
.backtest-container {
  padding: 12px;
  height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  color: var(--text-primary);
  gap: 12px;
}

.top-control-bar {
  padding: 8px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 8px;
}

.controls-left, .controls-right {
  display: flex;
  gap: 16px;
  align-items: center;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #9ca3af;
}

.window-control {
  margin-left: 12px;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.dual-range {
  display: flex;
  align-items: center;
  gap: 6px;
}

.range-hint {
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  font-weight: 600;
}

.range-val {
  font-size: 0.85rem;
  color: #60a5fa;
  font-weight: 700;
  min-width: 12px;
  text-align: center;
}

.mini-slider {
  width: 60px;
  accent-color: #3b82f6;
  cursor: pointer;
  height: 4px;
}

.mini-slider:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.mini-input {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255,255,255,0.1);
  color: #f8fafc;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  outline: none;
}

.icon-btn, .mini-btn {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover, .mini-btn:hover {
  background: rgba(59, 130, 246, 0.3);
}

.top-pool-section {
  padding: 12px;
  border-radius: 12px;
  overflow: hidden;
}

.pool-settings {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.setting-label {
  font-size: 0.85rem;
  color: #9ca3af;
}

.range-slider {
  width: 150px;
  accent-color: #3b82f6;
  cursor: pointer;
}

.range-value {
  font-size: 0.85rem;
  color: #60a5fa;
  font-weight: 600;
  min-width: 100px;
}

.pool-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.pool-row:last-child {
  margin-bottom: 0;
}

.row-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: #9ca3af;
  width: 60px;
  text-transform: uppercase;
}

.horizontal-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  flex: 1;
}

.horizontal-scroll::-webkit-scrollbar {
  height: 4px;
}
.horizontal-scroll::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
}

.theme-chip {
  background: rgba(255,255,255,0.05);
  color: #e5e7eb;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.85rem;
  white-space: nowrap;
  cursor: pointer;
  border: 1px solid rgba(255,255,255,0.1);
  transition: all 0.2s;
  position: relative;
}

.theme-chip:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}

.active-chip {
  background: rgba(59, 130, 246, 0.3) !important;
  color: #60a5fa !important;
  border-color: #3b82f6 !important;
}

.new-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
}

.content-wrapper {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.side-panel-right {
  width: 240px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-card h4 {
  margin: 0 0 8px 0;
  font-size: 0.85rem;
  color: #9ca3af;
  text-transform: uppercase;
}

.form-group-mini {
  display: flex;
  gap: 4px;
}

.mini-run-btn {
  background: #3b82f6;
  border: none;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
}

.metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mini-metric {
  background: rgba(255,255,255,0.05);
  padding: 8px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-metric .l { font-size: 0.7rem; color: #9ca3af; }
.mini-metric .v { font-size: 1rem; font-weight: 700; }

.signals-scroll {
  max-height: 300px;
  overflow-y: auto;
  font-size: 0.75rem;
}

.signals-table {
  width: 100%;
}

.signals-table td {
  padding: 4px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.hold { color: #ef4444; font-weight: 700; }
.empty { color: #10b981; font-weight: 700; }

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
  max-height: 200px;
}
.slide-enter-from, .slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
}

.global-loading-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
  gap: 16px;
}

.chart-container {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  min-width: 0;
}

.chart {
  height: 100%;
  width: 100%;
}

.stock-tag {
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.core-tag {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.other-tag {
  background: rgba(255, 255, 255, 0.05);
  color: #9ca3af;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.topic-tag {
  background: rgba(59, 130, 246, 0.1);
  color: #cbd5e1;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.st-stock {
  border-color: rgba(245, 158, 11, 0.5) !important;
  background: rgba(245, 158, 11, 0.1) !important;
  color: #f59e0b !important;
}

.st-badge {
  background: #f59e0b;
  color: #000;
  font-size: 0.65rem;
  font-weight: 800;
  padding: 1px 3px;
  border-radius: 3px;
  line-height: 1;
}

.clickable-theme {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
  display: inline-block;
}

.clickable-theme:hover {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.active-theme {
  background: rgba(59, 130, 246, 0.3);
  color: #3b82f6;
  border-left: 3px solid #3b82f6;
}

.close-comparison-btn {
  position: absolute;
  top: 15px;
  right: 15px;
  z-index: 100;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #9ca3af;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.close-comparison-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}

.comparison-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(4px);
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #e5e7eb;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.3);
  border-radius: 50%;
  border-top-color: #3b82f6;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
