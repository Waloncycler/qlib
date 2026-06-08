<template>
  <div class="backtest-container">
    <div class="header">
      <h1 class="title">Strategy Backtest (Market Timing)</h1>
      <button class="run-btn" @click="runBacktest" :disabled="loading">
        {{ loading ? 'Loading...' : 'Refresh Results' }}
      </button>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-panel">
      <p>{{ error }}</p>
    </div>

    <div class="content-wrapper" v-if="!loading">
      
      <!-- Left side: Form & Metrics -->
      <div class="side-panel">
        
        <!-- Strategy Stock Pool Card -->
        <div class="info-card glass-panel pool-card" style="display: flex; flex-direction: column; max-height: 800px; flex: 1;">
          <h3>Strategy Stock Pool</h3>
          
          <div class="form-group">
            <label style="font-size: 0.8rem; color: #9ca3af; margin-bottom: 4px; display: block;">Select Trading Day</label>
            <select v-model="poolDate" class="styled-input" @change="fetchPool">
              <option v-for="d in validDates" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>

          <div v-if="poolLoading" class="loading-text" style="color: #9ca3af; font-size: 0.9rem; margin-top: 10px;">Loading pool data...</div>
          
          <div v-else-if="!poolData" class="empty-text" style="color: #6b7280; font-size: 0.9rem; margin-top: 10px;">Select a date to view stock pool.</div>
          
          <div v-else class="pool-scroll" style="overflow-y: auto; flex: 1; padding-right: 4px;">
            <!-- AI Reports -->
            <div class="pool-source">
              <div class="source-header" @click="toggleSource('ai')" style="cursor: pointer; display: flex; justify-content: space-between; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 6px; font-weight: 500; transition: background 0.2s;">
                <span style="color: #a78bfa;">🤖 AI Reports ({{ poolData.sources.ai_reports?.length || 0 }})</span>
                <span class="icon" style="color: #9ca3af; font-size: 0.8rem; align-self: center;">{{ openSource === 'ai' ? '▼' : '▶' }}</span>
              </div>
              <div class="source-body" v-show="openSource === 'ai'" style="padding: 10px 4px;">
                <div v-for="(theme, idx) in poolData.sources.ai_reports" :key="'ai-'+idx" class="theme-block" style="margin-bottom: 12px;">
                  <div class="theme-name" style="font-size: 0.95rem; font-weight: 600; color: #e5e7eb; margin-bottom: 6px;">
                    {{ theme.concept }}
                    <span v-if="theme.is_new" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">NEW</span>
                  </div>
                  <div class="stock-tags" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px;">
                    <span v-for="stock in theme.core_stocks" :key="stock.code || stock.name" @click="goToStock(stock.symbol)" style="cursor: pointer; background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ stock.name }}</span>
                    <span v-for="stock in theme.other_stocks" :key="stock.code || stock.name" @click="goToStock(stock.symbol)" style="cursor: pointer; background: rgba(255, 255, 255, 0.05); color: #9ca3af; border: 1px solid rgba(255, 255, 255, 0.1); padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ stock.name }}</span>
                  </div>
                </div>
                <div v-if="!poolData.sources.ai_reports?.length" style="color: #6b7280; font-size: 0.85rem; padding: 4px;">No themes found for this date.</div>
              </div>
            </div>

            <!-- Market Topics -->
            <div class="pool-source" style="margin-top: 12px;">
              <div class="source-header" @click="toggleSource('topics')" style="cursor: pointer; display: flex; justify-content: space-between; padding: 8px; background: rgba(255,255,255,0.05); border-radius: 6px; font-weight: 500; transition: background 0.2s;">
                <span style="color: #60a5fa;">📊 Market Topics ({{ poolData.sources.market_topics?.length || 0 }})</span>
                <span class="icon" style="color: #9ca3af; font-size: 0.8rem; align-self: center;">{{ openSource === 'topics' ? '▼' : '▶' }}</span>
              </div>
              <div class="source-body" v-show="openSource === 'topics'" style="padding: 10px 4px;">
                <div v-for="(theme, idx) in poolData.sources.market_topics" :key="'top-'+idx" class="theme-block" style="margin-bottom: 12px;">
                  <div class="theme-name" style="font-size: 0.95rem; font-weight: 600; color: #e5e7eb; margin-bottom: 6px;">{{ theme.concept }}</div>
                  <div class="stock-tags" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px;">
                    <span v-for="stock in theme.core_stocks" :key="stock.name" @click="goToStock(stock.symbol)" style="cursor: pointer; background: rgba(59, 130, 246, 0.1); color: #cbd5e1; border: 1px solid rgba(59, 130, 246, 0.2); padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ stock.name }}</span>
                  </div>
                </div>
                <div v-if="!poolData.sources.market_topics?.length" style="color: #6b7280; font-size: 0.85rem; padding: 4px;">No topics found.</div>
              </div>
            </div>
          </div>
        </div>

        <div class="info-card glass-panel form-card">
          <h3>Single Stock Validator</h3>
          
          <div class="form-group">
            <label>Stock Symbol</label>
            <input v-model="form.symbol" type="text" placeholder="e.g. SZ002199" class="styled-input" />
          </div>

          <div class="form-group">
            <label>Start Date</label>
            <input v-model="form.startDate" type="date" class="styled-input" />
          </div>

          <div class="form-group">
            <label>End Date</label>
            <input v-model="form.endDate" type="date" class="styled-input" />
          </div>
          
          <div class="form-group">
            <label>Strategy</label>
            <select v-model="form.strategy" class="styled-input" disabled>
              <option value="ai_timing">AI Timing Model (Linear)</option>
            </select>
          </div>

          <button class="run-btn w-full mt-4" @click="runSingleBacktest" :disabled="loading">
            {{ loading ? 'Running Backtest...' : 'Run Validator' }}
          </button>
        </div>

        <div class="metrics-grid" v-if="metrics">
          <div class="metric-item">
            <div class="m-label">Annualized Return</div>
            <div class="m-value" :class="{'positive': metrics.annualized_return > 0, 'negative': metrics.annualized_return < 0}">
              {{ (metrics.annualized_return * 100).toFixed(2) }}%
            </div>
          </div>
          <div class="metric-item">
            <div class="m-label">Max Drawdown</div>
            <div class="m-value negative">
              {{ (metrics.max_drawdown * 100).toFixed(2) }}%
            </div>
          </div>
        </div>

        <!-- Trade Logs -->
        <div class="info-card glass-panel daily-signals-card" v-if="reversedCurveData.length > 0" style="display: flex; flex-direction: column; max-height: 350px;">
          <h3>Trading Signals</h3>
          <div class="signals-scroll" style="overflow-y: auto; flex: 1; margin-top: 8px; padding-right: 4px;">
            <table class="signals-table" style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
              <thead>
                <tr style="text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); position: sticky; top: 0; background: rgba(30, 41, 59, 0.95); z-index: 10;">
                  <th style="padding: 6px 0; color: #9ca3af; font-weight: 500;">Date</th>
                  <th style="padding: 6px 0; color: #9ca3af; font-weight: 500; text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in reversedCurveData" :key="d.date" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                  <td style="padding: 8px 0; color: #e5e7eb;">{{ d.date }}</td>
                  <td style="padding: 8px 0; text-align: right; font-weight: 600;">
                    <span v-if="d.timing_signal === 1.0" style="color: #ef4444;">HOLD</span>
                    <span v-else style="color: #10b981;">EMPTY</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Right side: Dual Chart -->
      <div class="chart-container glass-panel">
        <v-chart class="chart" :option="chartOption" autoresize />
      </div>

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

const chartOption = computed(() => {
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
  padding: 24px;
  height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  color: var(--text-primary);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;
}

.title {
  font-size: 2rem;
  font-weight: 700;
  margin: 0;
  background: linear-gradient(to right, #60a5fa, #a78bfa);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.run-btn {
  background: var(--accent-color);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.run-btn:hover:not(:disabled) {
  background: #2563eb;
}

.content-wrapper {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

.side-panel {
  width: 450px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.info-card {
  padding: 20px;
  border-radius: 12px;
}

.info-card h3 {
  margin: 0 0 16px 0;
  font-size: 1.1rem;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 8px;
}

.form-group {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.styled-input {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255,255,255,0.1);
  color: var(--text-primary);
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 0.95rem;
  outline: none;
  transition: all 0.2s;
}

.styled-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.styled-input:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.w-full {
  width: 100%;
}
.mt-4 {
  margin-top: 16px;
}

.param-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.param-list li {
  display: flex;
  justify-content: space-between;
  font-size: 0.95rem;
  color: var(--text-secondary);
}

.param-list .label {
  font-weight: 500;
  color: #9ca3af;
}

.logic-rule {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: flex-start;
}

.logic-rule:last-child {
  margin-bottom: 0;
}

.logic-rule .emoji {
  font-size: 1.2rem;
  background: rgba(255,255,255,0.05);
  padding: 6px;
  border-radius: 8px;
}

.logic-rule strong {
  display: block;
  font-size: 0.95rem;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.logic-rule p {
  margin: 0;
  font-size: 0.85rem;
  color: #9ca3af;
}

.metrics-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-item {
  background: rgba(255,255,255,0.05);
  padding: 16px;
  border-radius: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.m-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.m-value {
  font-size: 1.2rem;
  font-weight: 700;
}

.positive { color: #10b981; }
.negative { color: #ef4444; }

.chart-container {
  flex: 1;
  padding: 20px;
  border-radius: 12px;
  min-width: 0;
}

.chart {
  height: 100%;
  width: 100%;
}
</style>
