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
        <button class="icon-btn" @click="showPool = !showPool" :title="showPool ? 'Hide Pool' : 'Show Pool'">
          {{ showPool ? '📂 Hide Pool' : '📁 Show Pool' }}
        </button>
      </div>

      <div class="controls-right">
        <button class="mini-btn" @click="runBacktest" :disabled="loading">
          {{ loading ? '...' : 'Refresh' }}
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

    <div class="content-wrapper" v-if="!loading">
      
      <!-- Chart Area (Full Width) -->
      <div class="chart-container glass-panel" style="position: relative;">
        <div v-if="comparisonLoading" class="comparison-overlay">
          <div class="spinner"></div>
          <p>Comparing {{ selectedTheme?.concept }}...</p>
        </div>
        <button v-if="isComparisonMode" @click="isComparisonMode = false" class="close-comparison-btn">
          ✕ Return to Backtest
        </button>
        <v-chart class="chart" :option="chartOption" autoresize />
      </div>

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
const error = ref(null)
const metrics = ref(null)
const curveData = ref(null)

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
        const res = await axios.get(`/api/stock/${symbol}/intraday/${date}`)
        if (res.data.status === 'success' && res.data.data && res.data.data.length > 0) {
          themeStocksData.value[symbol] = {
            name: s.name,
            data: res.data.data
          }
        }
      } catch (err) {
        console.error(`Failed to fetch intraday for ${symbol}`, err)
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
  
  if (symbols.length === 0) return {
    title: { text: 'Loading comparison data...', textStyle: { color: '#9ca3af' }, left: 'center', top: 'center' }
  }

  // Find a common time axis (union of all times)
  const allTimes = new Set()
  symbols.forEach(s => {
    allData[s].data.forEach(d => allTimes.add(d.time))
  })
  const sortedTimes = Array.from(allTimes).sort()
  
  symbols.forEach(s => {
    const stock = allData[s]
    const dataPoints = stock.data
    if (dataPoints.length === 0) return

    // Use pre_close if available from API, otherwise fallback to first price of the day
    const basePrice = dataPoints[0].pre_close || dataPoints[0].price
    const relativeData = sortedTimes.map(t => {
      const point = dataPoints.find(p => p.time === t)
      if (point) {
        return ((point.price - basePrice) / basePrice * 100).toFixed(2)
      }
      return null
    })
    
    series.push({
      name: stock.name,
      type: 'line',
      data: relativeData,
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2 }
    })
  })
  
  return {
    title: {
      text: `${selectedTheme.value.concept} - Intra-day Comparison (${poolDate.value})`,
      textStyle: { color: '#e5e7eb', fontSize: 16 },
      left: 'center',
      top: 5
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#f8fafc' },
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        let res = `<div style="font-weight:bold;margin-bottom:4px;color:#9ca3af;">${params[0].name}</div>`
        // Filter out null/undefined/NaN values and sort descending
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
    legend: {
      data: symbols.map(s => allData[s].name),
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
      data: sortedTimes,
      axisLabel: { color: '#9ca3af' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
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
    series: series
  }
}

const chartOption = computed(() => {
  if (isComparisonMode.value) {
    return getComparisonOption()
  }
  if (!curveData.value) return {}

  const dates = curveData.value.map(d => d.date)
  const strategySeries = curveData.value.map(d => (d.strategy * 100).toFixed(2))
  const benchSeries = curveData.value.map(d => (d.benchmark * 100).toFixed(2))
  const sentimentSeries = curveData.value.map(d => d.sentiment_score.toFixed(1))
  const timingSeries = curveData.value.map(d => d.timing_signal !== undefined ? d.timing_signal : 0.0)

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function(params) {
        let res = '';
        let date = '';
        let strat = '';
        let bench = '';
        let signal = '';
        let sentiment = '';
        
        params.forEach(p => {
          date = p.name;
          if (p.seriesName === 'AI Strategy Return') {
            strat = `<span style="color:#3b82f6;font-weight:bold;">${p.value}%</span>`;
          } else if (p.seriesName === 'Stock Buy&Hold') {
            bench = `<span style="color:#9ca3af;">${p.value}%</span>`;
          } else if (p.seriesName === 'Position Signal') {
            signal = (p.value === '1.00' || p.value == 1.0) ? '<span style="color:#ef4444;font-weight:bold;">HOLD</span>' : '<span style="color:#10b981;font-weight:bold;">EMPTY</span>';
          }
        });
        
        res += `<div style="font-weight:bold;margin-bottom:4px;color:#f8fafc;">${date}</div>`;
        if (strat) res += `Strategy Return: ${strat}<br/>`;
        if (bench) res += `Benchmark Return: ${bench}<br/>`;
        if (signal) res += `Timing Signal: ${signal}<br/>`;
        if (sentiment) res += `Sentiment Score: ${sentiment}<br/>`;
        return res;
      }
    },
    legend: {
      data: [
        { name: 'AI Strategy Return' },
        { name: 'Stock Buy&Hold' },
        { name: 'Position Signal', itemStyle: { color: '#ef4444' } }
      ],
      textStyle: { color: '#e5e7eb' },
      top: 5
    },
    axisPointer: {
      link: { xAxisIndex: 'all' }
    },
    grid: [
      {
        left: '5%',
        right: '4%',
        top: '10%',
        height: '50%'
      },
      {
        left: '5%',
        right: '4%',
        top: '68%',
        height: '22%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        boundaryGap: false,
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisTick: { show: false }
      },
      {
        type: 'category',
        boundaryGap: false,
        data: dates,
        gridIndex: 1,
        axisLabel: { color: '#9ca3af' }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        axisLabel: { color: '#9ca3af', formatter: '{value} %' },
        splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
      },
      {
        type: 'value',
        gridIndex: 0,
        min: 0,
        max: 6,
        show: false,
        splitLine: { show: false }
      },
      {
        type: 'value',
        gridIndex: 1,
        name: 'Sentiment',
        nameTextStyle: { color: '#9ca3af' },
        axisLabel: { color: '#9ca3af' },
        splitLine: { lineStyle: { color: '#374151', type: 'dashed' } },
        min: 0,
        max: 100
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        bottom: '2%',
        start: 0,
        end: 100
      }
    ],
    series: [
      {
        name: 'AI Strategy Return',
        type: 'line',
        data: strategySeries,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: '#3b82f6' },
        lineStyle: { width: 3 },
        showSymbol: false,
        smooth: true
      },
      {
        name: 'Stock Buy&Hold',
        type: 'line',
        data: benchSeries,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: { color: '#9ca3af' },
        lineStyle: { width: 2, type: 'dashed' },
        showSymbol: false,
        smooth: true
      },
      {
        name: 'Position Signal',
        type: 'line',
        step: 'start',
        data: timingSeries,
        xAxisIndex: 0,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: '#ef4444' },
        areaStyle: {
          opacity: 0.35,
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: '#ef4444' },
              { offset: 1, color: 'rgba(239, 68, 68, 0.05)' }
            ]
          }
        },
        symbol: 'none'
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
  error.value = null
  try {
    const res = await axios.get('/api/backtest/results')
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
    }
  } catch (err) {
    console.error("Failed to fetch backtest results:", err)
    // Don't show full error panel for initial results fetch to avoid blocking pool
  } finally {
    loading.value = false
  }
}

const runBacktest = () => {
  runSingleBacktest()
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
