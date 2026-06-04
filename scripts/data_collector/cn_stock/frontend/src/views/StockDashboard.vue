<template>
  <div class="dashboard">
    <header class="header">
      <div class="header-left">
        <h1 class="title">Stock Data Explorer</h1>
      </div>
    </header>
    
    <div class="header-controls">
      <div v-if="hasData" class="tabs-container-center glass-panel">
        <button class="tab-btn-center" :class="{active: activeTab === 'market'}" @click="activeTab = 'market'">
          <i class="fa-solid fa-candlestick-chart tab-icon-center text-sky-400"></i> Market
        </button>
        <button class="tab-btn-center" :class="{active: activeTab === 'signals'}" @click="activeTab = 'signals'">
          <i class="fa-solid fa-bolt tab-icon-center text-yellow-400"></i> Signals
        </button>
        <button class="tab-btn-center" :class="{active: activeTab === 'capital'}" @click="activeTab = 'capital'">
          <i class="fa-solid fa-coins tab-icon-center text-emerald-400"></i> Capital
        </button>
        <button class="tab-btn-center" :class="{active: activeTab === 'fundamentals'}" @click="activeTab = 'fundamentals'">
          <i class="fa-solid fa-file-invoice-dollar tab-icon-center text-purple-400"></i> Fundamentals
        </button>
        <button class="tab-btn-center" :class="{active: activeTab === 'news'}" @click="activeTab = 'news'">
          <i class="fa-solid fa-newspaper tab-icon-center text-rose-400"></i> News
        </button>
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
    </div>
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
    <MarketTab v-if="hasData && activeTab === 'market'" 
      :dragonTiger="dragonTiger"
      :lockupData="lockupData"
      :klineOption="klineOption"
      v-model:chartToggles="chartToggles"
    />

    <!-- 2. Signals Layer -->
    <SignalsTab v-if="hasData && activeTab === 'signals'"
      :thsReasons="thsReasons"
    />

    <!-- 3. Capital Layer -->
    <CapitalTab v-if="hasData && activeTab === 'capital'"
      :marginOption="marginOption"
      :fundFlowOption="fundFlowOption"
    />

    <!-- 4. Fundamentals Layer -->
    <FundamentalsTab v-if="hasData && activeTab === 'fundamentals'"
      :financeData="financeData"
    />

    <!-- 5. News Layer -->
    <NewsTab v-if="hasData && activeTab === 'news'"
      :symbol="symbol"
      :clsTelegraphs="clsTelegraphs"
      :eastmoneyNews="eastmoneyNews"
    />
    
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

import MarketTab from '../components/tabs/MarketTab.vue'
import SignalsTab from '../components/tabs/SignalsTab.vue'
import CapitalTab from '../components/tabs/CapitalTab.vue'
import FundamentalsTab from '../components/tabs/FundamentalsTab.vue'
import NewsTab from '../components/tabs/NewsTab.vue'

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
.dashboard { display: flex; flex-direction: column; gap: 12px; padding-bottom: 24px; }
.header {
  margin-bottom: 4px;
}
.header-left {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.title { font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #e0f2fe, #38bdf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0; display: inline-block; white-space: nowrap;}

.header-controls {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  flex-wrap: nowrap;
  gap: 16px;
  width: 100%;
  overflow-x: auto;
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.header-controls::-webkit-scrollbar { 
  display: none; 
}

.header-actions-wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: nowrap;
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
  font-weight: 600;
  transition: all 0.2s;
  white-space: nowrap;
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

.tabs-container-center {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  padding: 6px 8px !important;
  border-radius: 12px;
  margin: 0;
  width: fit-content;
  background: rgba(0,0,0,0.25);
  border: 1px solid rgba(255,255,255,0.08);
}
.tab-btn-center {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
}
.tab-btn-center:hover { 
  background: rgba(255,255,255,0.06); 
  color: #f8fafc; 
}
.tab-btn-center.active { 
  background: rgba(56, 189, 248, 0.15); 
  border-color: rgba(56, 189, 248, 0.3); 
  color: #38bdf8; 
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.1);
}
.tab-icon-center { font-size: 1rem; }

.layer-content {
  display: flex; flex-direction: column; gap: 16px; flex: 1;
}

.ymos-result-panel {
  padding: 16px !important;
}

.markdown-body strong {
  color: #fcd34d;
  font-weight: bold;
}

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px; color: var(--text-secondary); opacity: 0.7; flex: 1; }
.empty-state-small { padding: 20px; color: var(--text-secondary); text-align: center; font-style: italic; }
.empty-icon { width: 48px; height: 48px; margin-bottom: 16px; }

.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

/* Responsive Shrinking (Keeps it on one line but shrinks elements to fit) */
@media (max-width: 1200px) {
  .header-controls { gap: 8px; }
  .tab-btn-center { padding: 6px 10px; font-size: 0.85rem; gap: 6px; }
  .search-input-inline { width: 120px; font-size: 0.85rem; }
  .btn-search-inline { padding: 6px 12px; font-size: 0.85rem; }
  .btn-ymos { padding: 6px 12px; font-size: 0.85rem; }
}

@media (max-width: 900px) {
  .header-controls { gap: 4px; }
  .tab-btn-center { padding: 4px 6px; font-size: 0.75rem; gap: 4px; }
  .tab-icon-center { font-size: 0.8rem; }
  .header-actions { gap: 6px; }
  .search-section-inline { gap: 4px; padding: 2px; }
  .search-input-inline { width: 80px; padding: 4px 8px; font-size: 0.75rem; }
  .btn-search-inline { padding: 4px 8px; font-size: 0.75rem; gap: 4px; }
  .btn-ymos { padding: 4px 8px; font-size: 0.75rem; gap: 4px; }
  .icon-small { width: 12px; height: 12px; }
}
</style>
