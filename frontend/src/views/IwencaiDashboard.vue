<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">Market Pulse</h1>
        <p class="subtitle">市场体检 · DeepSeek 结构化分析</p>
      </div>
      <div class="actions">
        <button class="btn-refresh" @click="triggerScan" :disabled="scanning">
          <LoaderIcon v-if="scanning" class="icon spin" />
          <ZapIcon v-else class="icon" />
          {{ scanning ? '分析中...' : '手动扫描' }}
        </button>
        <button class="btn-refresh" @click="loadPulse" :disabled="loadingPulse">
          <RefreshCwIcon class="icon" :class="{ 'spin': loadingPulse }" />
          刷新
        </button>
      </div>
    </header>

    <!-- Error -->
    <div v-if="pulseError" class="error-panel glass-panel">
      <AlertTriangleIcon class="icon error-icon" />
      <p>{{ pulseError }}</p>
    </div>

    <!-- Main Content -->
    <div v-if="pulseData" class="pulse-scroll custom-scrollbar">
      <!-- Date -->
      <div class="pulse-meta glass-panel">
        <CalendarIcon class="icon-sm" />
        <span>{{ pulseData.date }}</span>
        <span class="dot">·</span>
        <ClockIcon class="icon-sm" />
        <span>{{ formatTime(pulseData.timestamp) }}</span>
        <span v-if="pulseData.structured?.sentiment?.sentiment_label" class="dot">·</span>
        <span v-if="pulseData.structured?.sentiment?.sentiment_label" class="sentiment-tag" :class="sentimentClass">
          {{ pulseData.structured.sentiment.sentiment_label }}
        </span>
      </div>

      <!-- Metrics Row: 涨跌分布 + 情绪 -->
      <div v-if="pulseData.structured?.market_breadth" class="metrics-row">
        <div class="metric-card glass-panel" v-for="m in breadthMetrics" :key="m.label">
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-value" :class="m.cls">{{ m.value }}</div>
        </div>
      </div>

      <!-- Sentiment & Capital -->
      <div class="two-col" v-if="hasSentimentOrCapital">
        <!-- Sentiment -->
        <div v-if="pulseData.structured?.sentiment" class="chart-card glass-panel">
          <h4 class="card-title">打板情绪</h4>
          <div class="sentiment-grid">
            <div class="sent-item" v-for="s in sentimentItems" :key="s.label">
              <div class="sent-num" :class="s.cls">{{ s.value }}</div>
              <div class="sent-label">{{ s.label }}</div>
            </div>
          </div>
          <div v-if="pulseData.structured.sentiment.sentiment_score != null" class="score-bar-wrapper">
            <div class="score-bar-label">情绪评分</div>
            <div class="score-bar">
              <div class="score-bar-fill" :style="{ width: pulseData.structured.sentiment.sentiment_score + '%' }" :class="sentimentClass"></div>
              <span class="score-num">{{ pulseData.structured.sentiment.sentiment_score }}</span>
            </div>
          </div>
        </div>

        <!-- Capital Flow -->
        <div v-if="hasCapital" class="chart-card glass-panel">
          <h4 class="card-title">资金面</h4>
          <div class="capital-grid">
            <div class="cap-item" v-for="c in capitalItems" :key="c.label">
              <div class="cap-label">{{ c.label }}</div>
              <div class="cap-value" :class="c.cls">{{ c.value }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sector & Concept Charts -->
      <div class="two-col" v-if="hasCharts">
        <!-- Top Sectors Bar Chart -->
        <div v-if="pulseData.structured?.top_sectors?.length" class="chart-card glass-panel">
          <h4 class="card-title">行业板块涨幅 Top 10</h4>
          <v-chart class="bar-chart" :option="sectorBarOption" autoresize />
        </div>

        <!-- Top Concepts Bar Chart -->
        <div v-if="pulseData.structured?.top_concepts?.length" class="chart-card glass-panel">
          <h4 class="card-title">概念题材涨幅 Top 10</h4>
          <v-chart class="bar-chart" :option="conceptBarOption" autoresize />
        </div>
      </div>

      <!-- Finance -->
      <div v-if="hasFinance" class="chart-card glass-panel">
        <h4 class="card-title">大金融板块追踪</h4>
        <v-chart class="finance-chart" :option="financeBarOption" autoresize />
      </div>

      <!-- AI Strategy Report -->
      <div v-if="pulseData.report" class="report-panel glass-panel">
        <div class="report-header">
          <SparklesIcon class="icon-accent" />
          <h3>每日市场策略简报</h3>
        </div>
        <div class="report-content" v-html="renderMarkdown(pulseData.report)"></div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="!loadingPulse && !pulseError" class="empty-panel glass-panel">
      <div class="empty-content">
        <ActivityIcon class="icon-large" />
        <h3>暂无体检数据</h3>
        <p>点击「手动扫描」生成今日市场体检</p>
      </div>
    </div>

    <!-- Divider -->
    <div class="section-divider">
      <span class="divider-line"></span>
      <span class="divider-text">手动搜索</span>
      <span class="divider-line"></span>
    </div>

    <!-- Search Section -->
    <div class="search-panel glass-panel">
      <div class="search-input-wrapper">
        <BotIcon class="search-icon" />
        <input v-model="query" type="text"
          placeholder="Try: 今日涨停，所属概念包含算力，市盈率小于30"
          @keyup.enter="search" :disabled="loading" />
        <button class="btn-search" @click="search" :disabled="loading || !query.trim()">
          <LoaderIcon v-if="loading" class="icon spin" />
          <SearchIcon v-else class="icon" /> Search
        </button>
      </div>
    </div>

    <div v-if="error" class="error-panel glass-panel">
      <AlertTriangleIcon class="icon error-icon" />
      <p>{{ error }}</p>
    </div>

    <div class="results-container glass-panel" v-if="results.length > 0">
      <div class="table-header"><h3>{{ results.length }} Results Found</h3></div>
      <div class="table-scroll custom-scrollbar">
        <table class="data-table">
          <thead><tr><th v-for="col in columns" :key="col">{{ col }}</th></tr></thead>
          <tbody>
            <tr v-for="(row, idx) in results" :key="idx">
              <td v-for="col in columns" :key="col">{{ formatCell(row[col]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-else-if="searched && !loading && !error" class="empty-panel glass-panel">
      <div class="empty-content">
        <DatabaseIcon class="icon-large" />
        <h3>No Results Found</h3>
        <p>Try adjusting your natural language query.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  BotIcon, SearchIcon, LoaderIcon, AlertTriangleIcon, DatabaseIcon,
  ZapIcon, RefreshCwIcon, CalendarIcon, ClockIcon, SparklesIcon, ActivityIcon
} from 'lucide-vue-next'

// ===== Market Pulse =====
const pulseData = ref(null)
const loadingPulse = ref(false)
const pulseError = ref(null)
const scanning = ref(false)

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

// ===== Computed: 市场宽度指标卡 =====
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

// ===== Computed: 打板情绪 =====
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

const hasSentimentOrCapital = computed(() => {
  return pulseData.value?.structured?.sentiment || hasCapital.value
})

// ===== Computed: 资金面 =====
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

// ===== Sentiment tag =====
const sentimentClass = computed(() => {
  const label = pulseData.value?.structured?.sentiment?.sentiment_label || ''
  const score = pulseData.value?.structured?.sentiment?.sentiment_score
  if (label.includes('亢奋') || label.includes('高涨')) return 'tag-hot'
  if (label.includes('低迷') || label.includes('冰点')) return 'tag-cold'
  if (score != null && score >= 70) return 'tag-hot'
  if (score != null && score <= 30) return 'tag-cold'
  return 'tag-neutral'
})

// ===== Computed: 板块/概念柱状图 =====
const hasCharts = computed(() => {
  return pulseData.value?.structured?.top_sectors?.length > 0 || pulseData.value?.structured?.top_concepts?.length > 0
})

const buildHorizontalBar = (data, valueKey, label) => {
  if (!data?.length) return {}
  const sorted = [...data].sort((a, b) => (b[valueKey] ?? -999) - (a[valueKey] ?? -999))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(22,24,30,0.9)', borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f2f2f2', fontSize: 12 }, trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>${label}: <strong style="color:${p.color}">${p.value?.toFixed(2)}%</strong>`
      }
    },
    grid: { top: 8, bottom: 8, left: 8, right: 40, containLabel: true },
    xAxis: {
      type: 'value', axisLabel: { color: '#9ba1a6', fontSize: 10, formatter: (v) => v + '%' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    yAxis: {
      type: 'category', data: sorted.map(d => d.name),
      inverse: true,
      axisLabel: { color: '#cbd5e1', fontSize: 11 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: sorted.map(d => ({
        value: d[valueKey] ?? 0,
        itemStyle: {
          color: (d[valueKey] ?? 0) > 0 ? '#ef4444' : '#22c55e',
          borderRadius: [0, 3, 3, 0],
        }
      })),
      barWidth: '55%',
      label: {
        show: true, position: 'right', color: '#9ba1a6', fontSize: 10,
        formatter: (p) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%'
      }
    }]
  }
}

const sectorBarOption = computed(() => buildHorizontalBar(pulseData.value?.structured?.top_sectors, 'change_pct', '涨跌幅'))
const conceptBarOption = computed(() => buildHorizontalBar(pulseData.value?.structured?.top_concepts, 'change_pct', '涨跌幅'))

// ===== Computed: 大金融 =====
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
        let html = `${item.name}板块<br/>`
        html += `涨跌幅: <strong style="color:${item.change_pct >= 0 ? '#ef4444' : '#22c55e'}">${item.change_pct?.toFixed(2)}%</strong><br/>`
        if (item.turnover != null) html += `成交额: ${item.turnover?.toFixed(0)}亿<br/>`
        if (item.inflow != null) html += `主力净流入: <span style="color:${item.inflow >= 0 ? '#ef4444' : '#22c55e'}">${item.inflow?.toFixed(1)}亿</span>`
        return html
      }
    },
    grid: { top: 8, bottom: 8, left: 8, right: 50, containLabel: true },
    xAxis: {
      type: 'value', axisLabel: { color: '#9ba1a6', fontSize: 10, formatter: (v) => v + '%' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
    },
    yAxis: {
      type: 'category', data: items.map(i => i.name),
      axisLabel: { color: '#cbd5e1', fontSize: 13, fontWeight: 600 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }, axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: items.map(i => ({
        value: i.change_pct,
        itemStyle: { color: i.change_pct >= 0 ? '#ef4444' : '#22c55e', borderRadius: [0, 4, 4, 0] }
      })),
      barWidth: '40%',
      label: {
        show: true, position: 'right', color: '#9ba1a6', fontSize: 12, fontWeight: 600,
        formatter: (p) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%'
      }
    }]
  }
})

// ===== Markdown renderer =====
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

onMounted(() => { loadPulse() })

// ===== Search =====
const query = ref('')
const loading = ref(false)
const error = ref(null)
const results = ref([])
const searched = ref(false)

const columns = computed(() => results.value.length === 0 ? [] : Object.keys(results.value[0]))

const formatCell = (val) => {
  if (val === null || val === undefined || val === '') return '--'
  if (typeof val === 'object') return JSON.stringify(val)
  if (typeof val === 'number' && val % 1 !== 0) return val > 1e9 ? val : val.toFixed(2)
  return val
}

const search = async () => {
  if (!query.value.trim() || loading.value) return
  loading.value = true; error.value = null; searched.value = true; results.value = []
  try {
    const res = await fetch('/api/iwencai/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query.value })
    })
    if (!res.ok) throw new Error(`Server returned ${res.status}`)
    const data = await res.json()
    if (data.status === 'success') results.value = data.data
    else throw new Error(data.message || 'Error')
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}
</script>

<style scoped>
.dashboard { padding: 24px; height: 100%; display: flex; flex-direction: column; gap: 16px; overflow: hidden; }
.header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; flex-shrink: 0; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }
.actions { display: flex; gap: 8px; }

.btn-refresh {
  display: flex; align-items: center; gap: 6px;
  background: rgba(56, 189, 248, 0.15); color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
  padding: 8px 16px; border-radius: 6px; cursor: pointer;
  font-size: 0.85rem; font-weight: 600; transition: all 0.2s;
}
.btn-refresh:hover:not(:disabled) { background: rgba(56, 189, 248, 0.25); border-color: #38bdf8; }
.btn-refresh:disabled { opacity: 0.4; cursor: not-allowed; }
.icon-sm { width: 14px; height: 14px; opacity: 0.7; }
.icon-accent { width: 18px; height: 18px; color: #facc15; }
.icon-large { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }

.pulse-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }

.pulse-meta {
  display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 8px;
  font-size: 0.8rem; color: var(--text-secondary); flex-shrink: 0;
}
.pulse-meta .dot { opacity: 0.4; }
.sentiment-tag { font-weight: 600; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.tag-hot { background: rgba(239,68,68,0.2); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); }
.tag-cold { background: rgba(34,197,94,0.2); color: #22c55e; border: 1px solid rgba(34,197,94,0.3); }
.tag-neutral { background: rgba(250,204,21,0.15); color: #facc15; border: 1px solid rgba(250,204,21,0.3); }

/* Metrics Row */
.metrics-row { display: flex; gap: 8px; flex-shrink: 0; }
.metric-card {
  flex: 1; padding: 12px 16px; border-radius: 8px; text-align: center;
}
.metric-label { font-size: 0.7rem; color: rgba(255,255,255,0.4); margin-bottom: 4px; }
.metric-value { font-size: 1.4rem; font-weight: 800; }

/* Two Column */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex-shrink: 0; }
@media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }

.chart-card { padding: 14px 16px; border-radius: 10px; }
.card-title { font-size: 0.85rem; color: var(--text-secondary); margin: 0 0 8px 0; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.06); }

/* Sentiment Grid */
.sentiment-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.sent-item { text-align: center; background: rgba(15,23,42,0.3); border-radius: 6px; padding: 8px 4px; }
.sent-num { font-size: 1.2rem; font-weight: 800; }
.sent-label { font-size: 0.68rem; color: rgba(255,255,255,0.4); margin-top: 2px; }

.score-bar-wrapper { margin-top: 10px; }
.score-bar-label { font-size: 0.7rem; color: rgba(255,255,255,0.4); margin-bottom: 4px; }
.score-bar {
  position: relative; height: 20px; background: rgba(15,23,42,0.5); border-radius: 10px; overflow: hidden;
}
.score-bar-fill { height: 100%; border-radius: 10px; transition: width 0.5s ease; }
.score-bar-fill.tag-hot { background: linear-gradient(90deg, rgba(239,68,68,0.3), #ef4444); }
.score-bar-fill.tag-cold { background: linear-gradient(90deg, rgba(34,197,94,0.3), #22c55e); }
.score-bar-fill.tag-neutral { background: linear-gradient(90deg, rgba(250,204,21,0.3), #facc15); }
.score-num { position: absolute; right: 8px; top: 0; line-height: 20px; font-size: 0.72rem; font-weight: 700; color: #fff; }

/* Capital Grid */
.capital-grid { display: flex; flex-direction: column; gap: 6px; }
.cap-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: rgba(15,23,42,0.3); border-radius: 6px; }
.cap-label { font-size: 0.75rem; color: rgba(255,255,255,0.5); }
.cap-value { font-size: 1rem; font-weight: 700; }

/* Bar charts */
.bar-chart { width: 100%; height: 280px; }
.finance-chart { width: 100%; height: 180px; }

/* Report */
.report-panel { padding: 20px 24px; border-radius: 12px; flex-shrink: 0; }
.report-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.report-header h3 { margin: 0; font-size: 1.05rem; color: #facc15; }
.report-content { font-size: 0.85rem; line-height: 1.8; color: var(--text-primary); }
.report-content :deep(h3) { font-size: 0.95rem; color: #38bdf8; margin: 16px 0 8px; font-weight: 600; }
.report-content :deep(h4) { font-size: 0.88rem; color: #7dd3fc; margin: 12px 0 6px; font-weight: 600; }
.report-content :deep(h5) { font-size: 0.82rem; color: #7dd3fc; margin: 8px 0 4px; font-weight: 500; }
.report-content :deep(strong) { color: #fff; }
.report-content :deep(code) { background: rgba(56,189,248,0.15); color: #7dd3fc; padding: 1px 4px; border-radius: 3px; font-size: 0.8rem; }
.report-content :deep(ul) { padding-left: 20px; margin: 6px 0; }
.report-content :deep(li) { margin: 4px 0; }
.report-content :deep(hr) { border: none; border-top: 1px solid rgba(255,255,255,0.1); margin: 12px 0; }
.report-content :deep(p) { margin: 0; }

.val-up { color: #ef4444; }
.val-down { color: #22c55e; }

/* Divider */
.section-divider { display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.divider-line { flex: 1; height: 1px; background: rgba(255,255,255,0.1); }
.divider-text { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 1px; }

/* Search */
.search-panel { padding: 16px; border-radius: 12px; flex-shrink: 0; }
.search-input-wrapper {
  display: flex; align-items: center; background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 4px; gap: 12px;
}
.search-icon { margin-left: 12px; color: #38bdf8; }
.search-input-wrapper input { flex: 1; background: transparent; border: none; color: #fff; font-size: 1rem; padding: 12px 0; outline: none; }
.search-input-wrapper input::placeholder { color: rgba(255, 255, 255, 0.3); }
.btn-search {
  display: flex; align-items: center; gap: 8px; background: #38bdf8; color: #0f172a; border: none;
  padding: 10px 24px; border-radius: 6px; cursor: pointer; font-weight: 700; transition: all 0.2s; margin-right: 4px;
}
.btn-search:hover:not(:disabled) { background: #7dd3fc; box-shadow: 0 0 12px rgba(56, 189, 248, 0.5); }
.btn-search:disabled { opacity: 0.5; cursor: not-allowed; }

.error-panel { padding: 16px; border-radius: 12px; display: flex; align-items: center; gap: 12px; color: #f87171; flex-shrink: 0; }
.error-panel .error-icon { width: 20px; height: 20px; flex-shrink: 0; }

.results-container { flex: 1; display: flex; flex-direction: column; overflow: hidden; border-radius: 12px; min-height: 0; }
.table-header { padding: 16px 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
.table-header h3 { margin: 0; font-size: 1.1rem; color: var(--text-primary); }
.table-scroll { overflow: auto; flex: 1; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; white-space: nowrap; }
.data-table th, .data-table td { padding: 12px 16px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
.data-table th { position: sticky; top: 0; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(8px); color: var(--text-secondary); font-weight: 600; z-index: 10; border-bottom: 2px solid rgba(255,255,255,0.1); }
.data-table tr:hover td { background: rgba(255, 255, 255, 0.03); }

.empty-panel { flex: 1; display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.empty-content { text-align: center; color: var(--text-secondary); }
.empty-content h3 { margin: 0 0 8px 0; color: var(--text-primary); }
.empty-content p { margin: 0; }

.icon.spin { animation: spin 1s linear infinite; }
.custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

@keyframes spin { 100% { transform: rotate(360deg); } }
</style>
