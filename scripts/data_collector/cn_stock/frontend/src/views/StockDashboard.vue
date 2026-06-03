<template>
  <div class="dashboard">
    <header class="header">
      <div class="header-left">
        <h1 class="title">Stock Data Explorer</h1>
        <span v-if="hasData" class="ymos-tag">
          <i class="fa-solid fa-user-secret mr-1"></i> YMOS 首席风控官 & 逻辑校准官
        </span>
        <p class="subtitle">Deep dive into multi-dimensional stock data.</p>
      </div>
      
      <div class="header-actions">
        <div class="search-section-inline glass-panel">
          <input 
            type="text" 
            v-model="symbol" 
            placeholder="Symbol (e.g. SH600519)" 
            class="search-input-inline"
            @keyup.enter="handleSearch"
          />
          <button class="btn-search-inline" @click="handleSearch" :disabled="loading">
            <SearchIcon v-if="!loading" class="icon-small" />
            <RefreshCwIcon v-else class="icon-small spin" />
            Fetch
          </button>
        </div>
        
        <button 
          v-if="hasData"
          @click="runYmosAudit" 
          class="btn-ymos"
          :disabled="isAuditing || isBackgroundFetching"
          :title="isBackgroundFetching ? 'Waiting for background data sync...' : ''"
        >
          <i class="fa-solid fa-microchip mr-2" :class="{'fa-spin': isAuditing}"></i> 
          {{ isAuditing ? 'Auditing...' : (isBackgroundFetching ? 'Syncing Data...' : 'Run Deep Risk Audit') }}
        </button>
      </div>
    </header>
    <!-- Floating Toast Notifications -->
    <div class="toast-container">
      <transition name="toast-fade">
        <div v-if="successMsg" class="toast toast-success glass-panel">
          <CheckCircleIcon class="icon success-icon" />
          <p>{{ successMsg }}</p>
        </div>
      </transition>
      
      <transition name="toast-fade">
        <div v-if="error" class="toast toast-error glass-panel">
          <AlertTriangleIcon class="icon error-icon" />
          <p>{{ error }}</p>
        </div>
      </transition>
    </div>

    <div v-if="hasData" class="tabs-container glass-panel">
      <button class="tab-btn" :class="{active: activeTab === 'market'}" @click="activeTab = 'market'">
        <i class="fa-solid fa-candlestick-chart tab-icon text-sky-400"></i> Market
      </button>
      <button class="tab-btn" :class="{active: activeTab === 'signals'}" @click="activeTab = 'signals'">
        <i class="fa-solid fa-bolt tab-icon text-yellow-400"></i> Signals
      </button>
      <button class="tab-btn" :class="{active: activeTab === 'capital'}" @click="activeTab = 'capital'">
        <i class="fa-solid fa-coins tab-icon text-emerald-400"></i> Capital
      </button>
      <button class="tab-btn" :class="{active: activeTab === 'fundamentals'}" @click="activeTab = 'fundamentals'">
        <i class="fa-solid fa-file-invoice-dollar tab-icon text-purple-400"></i> Fundamentals
      </button>
      <button class="tab-btn" :class="{active: activeTab === 'news'}" @click="activeTab = 'news'">
        <i class="fa-solid fa-newspaper tab-icon text-rose-400"></i> News
      </button>
    </div>

    <!-- YMOS Risk Audit Result Panel (Global) -->
    <div v-if="hasData && (auditResult || isAuditing)" class="glass-panel ymos-result-panel">
      <div v-if="auditResult" class="audit-result custom-scrollbar">
        <div class="markdown-body" v-html="parsedAuditResult"></div>
      </div>
      <div v-else class="ymos-loading-text">
        Auditing in progress...
      </div>
    </div>

    <!-- 1. Market Layer -->
    <div v-if="hasData && activeTab === 'market'" class="layer-content">
      <div class="grid-cards mb-4">
        <div class="stat-card glass-panel" v-if="dragonTiger">
          <div class="stat-label">LHB Net Buy (龙虎榜净买)</div>
          <div class="stat-value" :class="dragonTiger.NET_BUY_AMT > 0 ? 'up' : 'down'">
            {{ (dragonTiger.NET_BUY_AMT / 10000).toFixed(2) }} 万
          </div>
        </div>
        <div class="stat-card glass-panel" v-if="lockupData">
          <div class="stat-label">Next Lockup Expiry</div>
          <div class="stat-value">{{ lockupData.date }}</div>
          <div class="stat-subtext">{{ lockupData.ratio }}%</div>
        </div>
      </div>
      <div class="chart-panel glass-panel">
        <div class="chart-toggles-floating">
          <label class="toggle-label" title="涨跌停"><input type="checkbox" v-model="chartToggles.showLimit" /> 涨跌停</label>
          <label class="toggle-label" title="20日新高"><input type="checkbox" v-model="chartToggles.showHigh20" /> 20日新高</label>
          <label class="toggle-label" title="异动预警"><input type="checkbox" v-model="chartToggles.showAbnormal" /> 异动预警</label>
          <label class="toggle-label" title="异动预测线"><input type="checkbox" v-model="chartToggles.showPrediction" /> 异动预测线</label>
        </div>
        <v-chart class="chart" :option="klineOption" autoresize />
      </div>
    </div>

    <!-- 2. Signals Layer -->
    <div v-if="hasData && activeTab === 'signals'" class="layer-content">
      <div class="glass-panel p-6">
        <h3 class="section-title text-yellow-400"><i class="fa-solid fa-fire mr-2"></i> THS Concept / Hot Reasons</h3>
        <table class="data-table mt-4" v-if="thsReasons.length > 0">
          <thead>
            <tr><th>Concept Name</th><th>Reasoning</th></tr>
          </thead>
          <tbody>
            <tr v-for="(reason, idx) in thsReasons" :key="idx">
              <td class="font-bold text-emerald-400 whitespace-nowrap">{{ reason.name }}</td>
              <td class="text-slate-300">{{ reason.reason || reason.reason_tags }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty-state-small">No concept reasons found for this symbol.</div>
      </div>

    </div>

    <!-- 3. Capital Layer -->
    <div v-if="hasData && activeTab === 'capital'" class="layer-content grid-2-col">
      <div class="chart-panel glass-panel">
        <v-chart class="chart" :option="marginOption" autoresize />
      </div>
      <div class="chart-panel glass-panel">
        <v-chart class="chart" :option="fundFlowOption" autoresize />
      </div>
    </div>

    <!-- 4. Fundamentals Layer -->
    <div v-if="hasData && activeTab === 'fundamentals'" class="layer-content">
      <div class="glass-panel p-6">
        <h3 class="section-title text-purple-400"><i class="fa-solid fa-building mr-2"></i> Core Financial Ratios</h3>
        <div class="table-scroll mt-4" v-if="financeData.length > 0">
          <table class="data-table">
            <thead>
              <tr>
                <th>Report Date</th>
                <th>EPS (摊薄)</th>
                <th>ROE% (净资产收益率)</th>
                <th>Gross Margin% (毛利率)</th>
                <th>Net Profit (净利润)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(fin, idx) in financeData" :key="idx">
                <td class="font-mono text-sky-400">{{ fin.date || fin.report_date || fin.updated_date }}</td>
                <td>{{ fin.eps || (fin.jinglirun && fin.zongguben ? (fin.jinglirun / fin.zongguben).toFixed(2) : '--') }}</td>
                <td>{{ fin.roe ? parseFloat(fin.roe).toFixed(2) : (fin.jinglirun && fin.jingzichan ? (fin.jinglirun / fin.jingzichan * 100).toFixed(2) : '--') }}</td>
                <td>{{ fin.gross_margin ? parseFloat(fin.gross_margin).toFixed(2) : '--' }}</td>
                <td class="text-emerald-400 font-bold">{{ fin.net_profit ? Number(fin.net_profit).toLocaleString() : (fin.jinglirun ? Number(fin.jinglirun).toLocaleString() : '--') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state-small">No fundamental financial data found.</div>
      </div>
    </div>

    <!-- 5. News Layer -->
    <div v-if="hasData && activeTab === 'news'" class="layer-content grid-2-col">
      <div class="glass-panel p-6 flex flex-col h-[600px]">
        <h3 class="section-title text-amber-500 mb-4"><i class="fa-solid fa-bolt mr-2"></i> CLS Telegraph (财联社电报)</h3>
        <div class="overflow-y-auto custom-scrollbar flex-1 space-y-4 pr-2">
          <div v-for="(news, idx) in clsTelegraphs" :key="idx" class="news-card">
            <p class="news-time"><i class="fa-regular fa-clock mr-1"></i>{{ news.time || news.ctime }}</p>
            <p class="news-content">{{ news.content }}</p>
          </div>
          <div v-if="!clsTelegraphs.length" class="empty-state-small">No recent telegraphs.</div>
        </div>
      </div>
      <div class="glass-panel p-6 flex flex-col h-[600px]">
        <h3 class="section-title text-rose-500 mb-4"><i class="fa-solid fa-newspaper mr-2"></i> Company News ({{ symbol }})</h3>
        <div class="overflow-y-auto custom-scrollbar flex-1 space-y-4 pr-2">
          <div v-for="(news, idx) in eastmoneyNews" :key="idx" class="news-card">
            <h4 class="news-title">{{ news.title }}</h4>
            <p class="news-time mt-2"><i class="fa-regular fa-calendar mr-1"></i>{{ formatTime(news.time || news.publish_time || news.date) }}</p>
          </div>
          <div v-if="!eastmoneyNews.length" class="empty-state-small">No company news found.</div>
        </div>
      </div>
    </div>
    
    <div v-if="!hasData && !loading && !error" class="empty-state glass-panel">
      <TrendingUpIcon class="empty-icon" />
      <p>Enter a symbol and fetch its real-time hierarchical data layers</p>
    </div>
  </div>
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { SearchIcon, RefreshCwIcon, AlertTriangleIcon, TrendingUpIcon, CheckCircleIcon } from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'
import { useChartFactory } from '../composables/useChartFactory'
import { marked } from 'marked'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const { loading, error, fetchCsv, fetchJson, triggerRealtimeFetch, triggerRiskAudit } = useDataLoader()
const symbol = ref(route.params.symbol || 'SH600519')
const successMsg = ref('')
const hasData = ref(false)
const activeTab = ref('market')
const isBackgroundFetching = ref(false)
const { createKlineOption, createLineOption, createBarOption } = useChartFactory()

let toastTimer = null

watch(error, (newVal) => {
  if (newVal) {
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { error.value = null }, 4000)
  }
})

const showSuccess = (msg) => {
  successMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { successMsg.value = '' }, 3000)
}

// Market Layer
const klineOption = shallowRef({})
let klineRawData = []
let stockNameCache = ''
const chartToggles = ref({
  showLimit: true,
  showHigh20: true,
  showAbnormal: true,
  showPrediction: true
})

watch(chartToggles, () => {
  if (klineRawData.length) {
    klineOption.value = createKlineOption(stockNameCache, klineRawData, chartToggles.value)
  }
}, { deep: true })

const dragonTiger = ref(null)
const lockupData = ref(null)

// Signals Layer
const thsReasons = ref([])
const isAuditing = ref(false)
const auditResult = ref('')
const parsedAuditResult = computed(() => {
  if (!auditResult.value) return ''
  return marked.parse(auditResult.value)
})

// Capital Layer
const marginOption = shallowRef({})
const fundFlowOption = shallowRef({})

// Fundamentals Layer
const financeData = ref([])

// News Layer
const clsTelegraphs = ref([])
const eastmoneyNews = ref([])

const formatTime = (t) => {
  if (!t) return ''
  if (typeof t === 'number' && t > 100000000000) {
    const d = new Date(t)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  }
  return t
}

const runYmosAudit = async () => {
  if (!symbol.value) return
  isAuditing.value = true
  auditResult.value = ''
  try {
    const res = await triggerRiskAudit(symbol.value)
    if (res && res.status === 'success') {
      auditResult.value = res.report
    } else {
      auditResult.value = `Error generating audit: ${res?.message || 'Unknown error'}`
    }
  } catch (err) {
    auditResult.value = `Error: ${err.message}`
  } finally {
    isAuditing.value = false
  }
}

const handleSearch = async () => {
  if (!symbol.value) return
  const rawQuery = symbol.value.trim()
  
  // Set loading state early so UI shows reaction
  loading.value = true
  
  // Resolve Chinese name or loose symbol to exact code
  try {
    const res = await axios.get(`/api/resolve_symbol/${encodeURIComponent(rawQuery)}`)
    if (res.data && res.data.symbol) {
      symbol.value = res.data.symbol
    }
  } catch (err) {
    loading.value = false
    error.value = `Could not resolve stock: ${err.response?.data?.detail || err.message}`
    return
  }
  
  loading.value = false
  const s = symbol.value.toUpperCase()
  
  router.push({ params: { symbol: s } })
  successMsg.value = ''
  hasData.value = false
  
  // Reset data
  dragonTiger.value = null
  lockupData.value = null
  thsReasons.value = []
  isAuditing.value = false
  auditResult.value = ''
  financeData.value = []
  clsTelegraphs.value = []
  eastmoneyNews.value = []
  
  // 1. Trigger real-time fetch for MARKET layer FIRST
  const triggerRes = await triggerRealtimeFetch(s, 'market')
  if (!triggerRes || triggerRes.status !== 'success') {
    return
  }
  
  showSuccess(`Fetching market data for ${s}...`)
  
  // Render Market Layer instantly
  let stockName = s;
  try {
    const quotesData = await fetchJson('market', `${s}_tencent_quotes.json`)
    if (quotesData && typeof quotesData === 'object') {
      const keys = Object.keys(quotesData);
      if (keys.length > 0 && quotesData[keys[0]] && quotesData[keys[0]].name) {
        stockName = `${quotesData[keys[0]].name} (${s})`
      }
    }
  } catch(e) {
    console.warn("Could not fetch stock name", e);
  }

  const klineData = await fetchCsv('market', `${s}_tencent_sina_kline.csv`)
  if (klineData && klineData.length) {
    klineRawData = klineData
    stockNameCache = stockName
    klineOption.value = createKlineOption(stockName, klineData, chartToggles.value)
    hasData.value = true
  }
  
  // 2. LAZY LOAD the rest of the layers in the background
  isBackgroundFetching.value = true
  Promise.all([
    triggerRealtimeFetch(s, 'signals'),
    triggerRealtimeFetch(s, 'capital'),
    triggerRealtimeFetch(s, 'fundamentals'),
    triggerRealtimeFetch(s, 'news')
  ]).then(async () => {
    showSuccess(`Background data synchronized for ${s}`)
    
    const dtJson = await fetchJson('signals', `${s}_dragon_tiger.json`)
    if (dtJson && dtJson.length) dragonTiger.value = dtJson[0]
    
    const lockupJson = await fetchJson('signals', `${s}_lockup_expiry.json`)
    if (lockupJson && lockupJson.length) lockupData.value = lockupJson[0]

    const allThs = await fetchCsv('signals', 'ths_hot_reasons.csv')
    if (allThs && allThs.length) {
      const rawCode = s.replace(/[A-Za-z]/g, '')
      thsReasons.value = allThs.filter(r => r.code && String(r.code).includes(rawCode))
    }

    const marginData = await fetchCsv('capital', `${s}_margin_trading.csv`)
    if (marginData && marginData.length) {
      const dates = marginData.map(d => String(d.date))
      marginOption.value = createLineOption('Margin Trading Balance (融资余额)', dates, [{
        name: 'Balance', data: marginData.map(d => d.margin_balance || d['融资余额']),
        itemStyle: { color: '#38bdf8' }, areaStyle: { color: 'rgba(56, 189, 248, 0.1)' }
      }])
    } else {
      marginOption.value = createLineOption('Margin Trading Balance (融资余额)', [], [])
    }

    const flowData = await fetchCsv('capital', `${s}_fund_flow_120d.csv`)
    if (flowData && flowData.length) {
      const dates = flowData.map(d => String(d.date))
      fundFlowOption.value = createBarOption('120-Day Capital Inflow Trend', dates, [{
        name: 'Net Flow', data: flowData.map(d => d.net_inflow || d.main_net_flow),
        itemStyle: { color: (p) => p.value > 0 ? '#f7525f' : '#2ebd85' }
      }])
    } else {
      fundFlowOption.value = createBarOption('120-Day Capital Inflow Trend', [], [])
    }

    const finData = await fetchCsv('fundamentals', `${s}_mootdx_finance.csv`)
    if (finData && finData.length) {
      financeData.value = finData.slice(0, 15)
    }

    const cls = await fetchJson('news', 'cls_telegraph.json')
    if (cls && cls.length) clsTelegraphs.value = cls
    
    const emNews = await fetchJson('news', `${s}_eastmoney_news.json`)
    if (emNews && emNews.length) eastmoneyNews.value = emNews
  }).catch(err => {
    console.error("Error fetching background layers", err)
  }).finally(() => {
    isBackgroundFetching.value = false
  })
}

if (route.params.symbol) {
  handleSearch()
}
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 12px; padding-bottom: 24px; }.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  width: 100%;
}
.header-left {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.title { font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #e0f2fe, #38bdf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; display: inline-block;}
.subtitle { color: var(--text-secondary); margin: 4px 0 0 0; }

.ymos-tag {
  display: inline-flex;
  align-items: center;
  font-size: 0.85rem;
  font-weight: bold;
  color: #a78bfa;
  background: rgba(139, 92, 246, 0.1);
  border: 1px solid rgba(139, 92, 246, 0.3);
  padding: 4px 12px;
  border-radius: 9999px;
  margin-top: 8px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.search-section-inline { 
  display: flex; 
  align-items: center; 
  padding: 4px; 
  border-radius: 8px; 
  gap: 8px;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.1);
}
.search-input-inline { 
  background: transparent; 
  border: none; 
  color: white; 
  padding: 6px 12px; 
  width: 160px; 
  font-size: 0.9rem; 
  outline: none; 
}
.btn-search-inline { 
  display: flex; 
  align-items: center; 
  gap: 6px; 
  background: var(--accent-color); 
  color: white; 
  border: none; 
  padding: 6px 16px; 
  border-radius: 6px; 
  cursor: pointer; 
  font-weight: 600; 
  font-size: 0.9rem;
  transition: all 0.2s; 
}
.btn-search-inline:hover:not(:disabled) { 
  background: #2563eb; 
  box-shadow: 0 0 8px var(--accent-glow); 
}
.icon-small { width: 16px; height: 16px; }

.btn-ymos {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #7c3aed;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: bold;
  font-size: 0.9rem;
  transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
}
.btn-ymos:hover:not(:disabled) {
  background: #6d28d9;
  box-shadow: 0 0 16px rgba(124, 58, 237, 0.6);
}

.icon.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* YMOS Result Panel */
.ymos-result-panel {
  padding: 20px;
  margin-bottom: 20px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 12px;
}
.ymos-result-title {
  font-size: 1rem;
  font-weight: 700;
  color: #a78bfa;
  margin: 0 0 12px 0;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.ymos-loading-text {
  font-size: 0.9rem;
  color: #94a3b8;
  font-style: italic;
}
.audit-result {
  max-height: 400px;
  overflow-y: auto;
}

/* Toast Notifications */
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 1000;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  font-weight: 500;
  pointer-events: auto;
  min-width: 300px;
}

.toast-success {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.toast-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.toast p { margin: 0; }

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.tabs-container { display: flex; gap: 8px; padding: 8px !important; border-radius: 12px; margin-bottom: 0; flex-wrap: wrap; flex-shrink: 0; }
.tab-btn {
  padding: 10px 20px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
  white-space: nowrap;
}
.tab-btn:hover { background: rgba(255,255,255,0.05); color: #fff; }
.tab-btn.active { background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.3); color: #38bdf8; }

.layer-content {
  display: flex; flex-direction: column; gap: 16px; flex: 1;
}

.ymos-result-panel {
  padding: 16px !important;
}

.grid-2-col {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 16px;
}

.grid-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.stat-card { padding: 20px; display: flex; flex-direction: column; gap: 8px; }
.stat-label { color: var(--text-secondary); font-size: 0.9rem; font-weight: 500; }
.stat-value { font-size: 1.8rem; font-weight: 700; }
.stat-subtext { font-size: 0.85rem; color: var(--text-secondary); }
.up { color: var(--danger); }
.down { color: var(--success); }

.chart-panel { padding: 16px; height: 450px; position: relative; }
.chart { width: 100%; height: 100%; }
.chart-toggles-floating { 
  position: absolute; 
  top: 12px; 
  left: 20px; 
  display: flex; 
  gap: 12px; 
  z-index: 10; 
  background: rgba(15, 23, 42, 0.7); 
  padding: 4px 10px; 
  border-radius: 6px; 
  border: 1px solid rgba(255,255,255,0.05);
  backdrop-filter: blur(4px);
}
.toggle-label { font-size: 0.8rem; color: #cbd5e1; display: flex; align-items: center; gap: 4px; cursor: pointer; user-select: none; }
.toggle-label input { accent-color: #38bdf8; cursor: pointer; margin: 0; }

.markdown-body {
  max-height: 500px;
  overflow-y: auto;
  color: #cbd5e1;
  font-size: 0.85rem;
  line-height: 1.5;
}
.markdown-body h2 {
  font-size: 1.05rem;
  font-weight: bold;
  margin-top: 0.5rem;
  margin-bottom: 0.25rem;
  color: #a78bfa;
}
.markdown-body h3 {
  font-size: 0.95rem;
  font-weight: bold;
  margin-top: 0.5rem;
  margin-bottom: 0.25rem;
}
.markdown-body p {
  margin-bottom: 0.25rem;
}
.markdown-body ul {
  list-style-type: disc;
  padding-left: 1.5rem;
  margin-bottom: 0.25rem;
}
.markdown-body li {
  margin-bottom: 0.15rem;
}
.markdown-body strong {
  color: #fcd34d;
  font-weight: bold;
}

.section-title { font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.p-6 { padding: 24px; }

.data-table { width: 100%; border-collapse: collapse; text-align: left; }
.data-table td { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.data-table tr:hover td { background: rgba(255,255,255,0.02); }

.news-card { padding: 16px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; transition: border-color 0.2s; }
.news-card:hover { border-color: rgba(255,255,255,0.2); }
.news-time { font-size: 0.8rem; color: #38bdf8; font-family: monospace; margin-bottom: 8px; }
.news-title { font-size: 1rem; font-weight: 600; color: #f2f2f2; line-height: 1.4; }
.news-content { font-size: 0.95rem; color: #cbd5e1; line-height: 1.6; }

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; color: var(--text-secondary); opacity: 0.7; flex: 1; }
.empty-state-small { padding: 20px; color: var(--text-secondary); text-align: center; font-style: italic; }
.empty-icon { width: 48px; height: 48px; margin-bottom: 16px; }

.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>
