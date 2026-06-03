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

    <div class="content-wrapper" v-if="metrics && !loading">
      
      <!-- Left side: Metrics & Logic -->
      <div class="side-panel">
        
        <div class="info-card glass-panel">
          <h3>Parameters</h3>
          <ul class="param-list">
            <li><span class="label">Strategy:</span> TimingTopkDropout</li>
            <li><span class="label">TopK:</span> 2</li>
            <li><span class="label">Drop N:</span> 1</li>
            <li><span class="label">Base Risk:</span> 100%</li>
            <li><span class="label">Base Model:</span> LinearModel</li>
          </ul>
        </div>
        
        <div class="info-card glass-panel">
          <h3>Defensive Logic</h3>
          <div class="logic-rule">
            <span class="emoji">🛑</span>
            <div>
              <strong>Valuation Bubble</strong>
              <p>PE Median > 60.0 → Clear Positions (0%)</p>
            </div>
          </div>
          <div class="logic-rule">
            <span class="emoji">🧊</span>
            <div>
              <strong>Extreme Panic</strong>
              <p>Limit Up < 10 → Clear Positions (0%)</p>
            </div>
          </div>
          <div class="logic-rule">
            <span class="emoji">📉</span>
            <div>
              <strong>Weak Sentiment</strong>
              <p>Sentiment < 30.0 → Reduce Risk by 50%</p>
            </div>
          </div>
        </div>

        <div class="metrics-grid">
          <div class="metric-item">
            <div class="m-label">Annualized Return</div>
            <div class="m-value" :class="{'positive': metrics.annualized_return > 0, 'negative': metrics.annualized_return < 0}">
              {{ (metrics.annualized_return * 100).toFixed(2) }}%
            </div>
          </div>
          <div class="metric-item">
            <div class="m-label">Information Ratio</div>
            <div class="m-value" :class="{'positive': metrics.information_ratio > 0, 'negative': metrics.information_ratio < 0}">
              {{ metrics.information_ratio.toFixed(2) }}
            </div>
          </div>
          <div class="metric-item">
            <div class="m-label">Max Drawdown</div>
            <div class="m-value negative">
              {{ (metrics.max_drawdown * 100).toFixed(2) }}%
            </div>
          </div>
        </div>

        <!-- Daily Timing Signals List -->
        <div class="info-card glass-panel daily-signals-card" style="display: flex; flex-direction: column; max-height: 350px;">
          <h3>Daily Timing Signals</h3>
          <div class="signals-scroll" style="overflow-y: auto; flex: 1; margin-top: 8px; padding-right: 4px;">
            <table class="signals-table" style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
              <thead>
                <tr style="text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); position: sticky; top: 0; background: rgba(30, 41, 59, 0.95); z-index: 10;">
                  <th style="padding: 6px 0; color: #9ca3af; font-weight: 500;">Date</th>
                  <th style="padding: 6px 0; color: #9ca3af; font-weight: 500; text-align: right;">Signal</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="d in reversedCurveData" :key="d.date" style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                  <td style="padding: 8px 0; color: #e5e7eb;">{{ d.date }}</td>
                  <td style="padding: 8px 0; text-align: right; font-weight: 600;">
                    <span v-if="d.timing_signal === 1.0" style="color: #ef4444;">看多 (BULL)</span>
                    <span v-else style="color: #10b981;">轻仓 (BEAR)</span>
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
import axios from 'axios'
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
          if (p.seriesName === 'Strategy Return') {
            strat = `<span style="color:#3b82f6;font-weight:bold;">${p.value}%</span>`;
          } else if (p.seriesName === 'Benchmark Return') {
            bench = `<span style="color:#9ca3af;">${p.value}%</span>`;
          } else if (p.seriesName === 'VIP Timing Signal') {
            signal = (p.value === '1.00' || p.value == 1.0) ? '<span style="color:#ef4444;font-weight:bold;">看多 (BULL)</span>' : '<span style="color:#10b981;font-weight:bold;">轻仓 (BEAR)</span>';
          } else if (p.seriesName === 'Sentiment Score') {
            sentiment = `<span style="color:#f59e0b;font-weight:bold;">${p.value}</span>`;
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
        { name: 'Strategy Return' },
        { name: 'Benchmark Return' },
        { name: 'Sentiment Score' },
        { name: 'VIP Timing Signal', itemStyle: { color: '#ef4444' } }
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
        name: 'Strategy Return',
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
        name: 'Benchmark Return',
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
        name: 'VIP Timing Signal',
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
      },
      {
        name: 'Sentiment Score',
        type: 'bar',
        data: sentimentSeries,
        xAxisIndex: 1,
        yAxisIndex: 2,
        itemStyle: { 
          color: (params) => {
            if (params.value < 30) return '#ef4444'; // Weak sentiment triggering defense
            if (params.value > 80) return '#10b981';
            return '#f59e0b';
          }
        }
      }
    ]
  }
})

const reversedCurveData = computed(() => {
  if (!curveData.value) return []
  return [...curveData.value].reverse()
})

const fetchResults = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await axios.get('http://localhost:8000/api/backtest/results')
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const runBacktest = () => {
  fetchResults()
}

onMounted(() => {
  fetchResults()
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
  width: 320px;
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
