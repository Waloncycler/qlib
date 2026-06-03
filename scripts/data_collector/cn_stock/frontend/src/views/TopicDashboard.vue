<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">Market Topics</h1>
        <p class="subtitle">Trending themes and their K-line trajectories.</p>
      </div>
      <div class="actions">
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

    <div class="layout">
      <!-- Top Bar for topic list -->
      <div class="topic-top-bar glass-panel">
        <button class="scroll-btn" @click="scrollList(-1)" :disabled="!canScrollLeft" v-show="topicsList.length > 0">
          <ChevronLeftIcon class="icon-small" />
        </button>
        <div class="list-container-horizontal" ref="listContainer" @scroll="checkScroll">
          <div 
            v-for="topic in topicsList" 
            :key="topic.id"
            class="topic-item-horizontal"
            :class="{ active: selectedTopic?.id === topic.id }"
            @click="selectTopic(topic)"
          >
            <div class="topic-name-row">
              <span class="topic-name" :title="topic.name">{{ topic.name }}</span>
              <span class="stock-badge">{{ topic.rows ? topic.rows.length : 0 }} stocks</span>
            </div>
            <div class="topic-meta">
              <span>{{ formatDate(topic.updated_time) }}</span>
              <span v-if="topic.is_top == 1" class="top-badge">TOP</span>
            </div>
          </div>
        </div>
        <button class="scroll-btn" @click="scrollList(1)" :disabled="!canScrollRight" v-show="topicsList.length > 0">
          <ChevronRightIcon class="icon-small" />
        </button>
      </div>

      <!-- Main chart & table area -->
      <div class="main-content">
        <div v-if="!selectedTopic" class="empty-state glass-panel">
          <HashIcon class="empty-icon" />
          <p>Select a topic to view details</p>
        </div>
        
        <template v-else>
          <div class="main-header glass-panel">
            <h2 class="main-title">{{ selectedTopic.name }}</h2>
            <div class="main-meta">
                <div class="meta-item"><span class="meta-icon">ID:</span> {{ selectedTopic.id }}</div>
                <div class="meta-item"><span class="meta-icon">Created:</span> {{ formatDate(selectedTopic.created_time) }}</div>
                <div class="meta-item text-accent"><span class="meta-icon">Updated:</span> {{ formatDate(selectedTopic.updated_time) }}</div>
            </div>
            <div class="topic-description" v-html="formatContent(selectedTopic.content)"></div>
          </div>

          <div class="chart-panel glass-panel">
            <h3 class="section-title">Market Trend & Active Stocks</h3>
            <v-chart v-if="Object.keys(topicKlineOption).length > 0" class="chart" :option="topicKlineOption" @datazoom="handleDataZoom" autoresize />
            <div v-else class="empty-state-small" style="height: 300px; display: flex; align-items: center; justify-content: center;">
              <p>No historical K-line data available for this topic from upstream API.</p>
            </div>
          </div>

          <!-- Leaderboard -->
          <div class="table-container glass-panel" v-if="activeStocksLeaderboard.length > 0">
            <div class="section-header">
              <h3 class="section-title">Active Stocks Leaderboard (Limit Up Count)</h3>
              <div class="filter-group">
                <input type="number" v-model.number="customDays" placeholder="Custom" class="filter-input" min="1" />
                <span class="filter-label">Days</span>
                <button class="filter-btn" :class="{active: leaderboardDays === 0}" @click="setCustomDays(0)">All</button>
                <button class="filter-btn" :class="{active: leaderboardDays === 5}" @click="setCustomDays(5)">5D</button>
                <button class="filter-btn" :class="{active: leaderboardDays === 10}" @click="setCustomDays(10)">10D</button>
              </div>
            </div>
            <div class="leaderboard-grid">
              <div v-for="stock in activeStocksLeaderboard" :key="stock.name" 
                   class="leaderboard-card"
                   :class="{'selected': selectedStock === stock.name}"
                   @click="toggleStockSelection(stock.name)">
                <div class="lb-header">
                  <div class="lb-name">{{ stock.name }}</div>
                  <button class="lb-action-btn" @click.stop="goToStockExplorer(stock.name)" title="Open in Stock Data Explorer">
                    <ExternalLinkIcon class="icon-tiny" />
                  </button>
                </div>
                <div class="lb-counts">
                  <span class="lb-up" v-if="stock.up > 0">🔥 {{ stock.up }}</span>
                  <span class="lb-down" v-if="stock.down > 0">❄ {{ stock.down }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Related Stocks Table -->
          <div class="table-container glass-panel">
            <h3 class="section-title">Related Stocks ({{ selectedTopic.rows ? selectedTopic.rows.length : 0 }})</h3>
            <div class="table-scroll" v-if="selectedTopic.rows && selectedTopic.rows.length > 0">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th>Stock Name</th>
                    <th>Relevance / Logic</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in selectedTopic.rows" :key="index"
                      :class="{ 'highlighted-row': selectedStock === row['个股'] }"
                      @click="toggleStockSelection(row['个股'])">
                    <td>
                      {{ row['一级大类'] }}
                      <div class="sub-category" v-if="row['二级小类']">{{ row['二级小类'] }}</div>
                    </td>
                    <td class="font-bold">{{ row['个股'] }}</td>
                    <td>{{ row['相关性'] }}</td>
                    <td><span class="source-tag" v-if="row['信息源']">{{ row['信息源'] }}</span><span v-else>-</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="empty-state-small">No individual stocks mapped to this topic yet.</div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, shallowRef, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { RefreshCwIcon, AlertTriangleIcon, HashIcon, ExternalLinkIcon, ChevronLeftIcon, ChevronRightIcon } from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'

const router = useRouter()
const { loading, error, fetchTopics, triggerBackendRefresh, checkRefreshStatus } = useDataLoader()

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

const topicsList = ref([])
const klinesMap = shallowRef({})
const selectedTopic = ref(null)
const selectedStock = ref(null)
const topicKlineOption = shallowRef({})

const listContainer = ref(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(true)

const checkScroll = () => {
  if (!listContainer.value) return
  const el = listContainer.value
  canScrollLeft.value = el.scrollLeft > 0
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
}

const scrollList = (direction) => {
  if (!listContainer.value) return
  const scrollAmount = 350 // pixels to scroll per click
  listContainer.value.scrollBy({ left: direction * scrollAmount, behavior: 'smooth' })
  setTimeout(checkScroll, 400)
}

watch(topicsList, () => {
  nextTick(() => {
    checkScroll()
  })
})

const leaderboardDays = ref(90)
const customDays = ref(90)
const zoomStartValue = ref(null)
const zoomEndValue = ref(null)

const handleDataZoom = (params) => {
  if (!selectedTopic.value) return
  const tid = String(selectedTopic.value.id)
  const kdata = klinesMap.value[tid]
  if (!kdata) return

  let zoom = params
  if (params.batch) zoom = params.batch[0]

  if (zoom.startValue !== undefined && zoom.endValue !== undefined) {
    zoomStartValue.value = zoom.startValue
    zoomEndValue.value = zoom.endValue
  } else if (zoom.start !== undefined && zoom.end !== undefined) {
    const total = kdata.length
    zoomStartValue.value = Math.floor((zoom.start / 100) * Math.max(0, total - 1))
    zoomEndValue.value = Math.ceil((zoom.end / 100) * Math.max(0, total - 1))
  }
  
  // Custom zoom overrides preset days filter
  leaderboardDays.value = -1 
  customDays.value = null
  
  buildLeaderboard()
}

const setCustomDays = (days) => {
  customDays.value = days === 0 ? null : days
  leaderboardDays.value = days
  zoomStartValue.value = null
  zoomEndValue.value = null
  buildLeaderboard()
  updateChartOption()
}

watch(customDays, (val) => {
  if (val !== null && val > 0) {
    leaderboardDays.value = val
    zoomStartValue.value = null
    zoomEndValue.value = null
    buildLeaderboard()
    updateChartOption()
  }
})

const activeStocksLeaderboard = ref([])

const toggleStockSelection = (stockName) => {
  selectedStock.value = selectedStock.value === stockName ? null : stockName
  updateChartOption()
}

const buildLeaderboard = () => {
  if (!selectedTopic.value || !klinesMap.value[String(selectedTopic.value.id)]) {
    activeStocksLeaderboard.value = []
    return
  }
  
  const tid = String(selectedTopic.value.id)
  const kdata = klinesMap.value[tid]
  let activeData = kdata
  if (leaderboardDays.value > 0) {
    activeData = kdata.slice(Math.max(kdata.length - leaderboardDays.value, 0))
  } else if (leaderboardDays.value === -1 && zoomStartValue.value !== null && zoomEndValue.value !== null) {
    activeData = kdata.slice(zoomStartValue.value, zoomEndValue.value + 1)
  }
  
  const counts = {}
  activeData.forEach(d => {
    try {
      const ups = JSON.parse(d.up_limit_stocks || "[]")
      ups.forEach(u => {
        if (!counts[u.name]) counts[u.name] = { up: 0, down: 0 }
        counts[u.name].up += 1
      })
      const downs = JSON.parse(d.down_limit_stocks || "[]")
      downs.forEach(u => {
        if (!counts[u.name]) counts[u.name] = { up: 0, down: 0 }
        counts[u.name].down += 1
      })
    } catch(e) {}
  })
  
  activeStocksLeaderboard.value = Object.keys(counts)
    .map(name => ({ name, up: counts[name].up, down: counts[name].down }))
    .sort((a, b) => b.up - a.up || b.down - a.down)
    .slice(0, 20) // show top 20
}

const goToStockExplorer = (stockName) => {
  router.push({ name: 'Stock', params: { symbol: stockName } })
}

const selectTopic = (topic) => {
  selectedTopic.value = topic
  selectedStock.value = null
  zoomStartValue.value = null
  zoomEndValue.value = null
  if (leaderboardDays.value === -1) {
    leaderboardDays.value = 90
    customDays.value = 90
  }
  buildLeaderboard()
  updateChartOption()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return dateStr.split(' ')[0]
}

const formatContent = (content) => {
  if (!content) return ''
  return content.replace(/\n/g, '<br>')
}

const updateChartOption = () => {
  if (!selectedTopic.value) return
  const tid = String(selectedTopic.value.id)
  const kdata = klinesMap.value[tid] || []
  
  if (kdata.length === 0) {
    topicKlineOption.value = {}
    return
  }

  const dates = kdata.map(d => d.trade_date)
  const values = kdata.map(d => [d.open, d.close, d.low, d.high])
  const upScatterData = []
  const downScatterData = []
  const hasSelected = !!selectedStock.value

  kdata.forEach((d, idx) => {
    try {
      const ups = JSON.parse(d.up_limit_stocks || "[]")
      if (hasSelected) {
        const selectedUp = ups.find(u => u.name === selectedStock.value)
        if (selectedUp) {
          upScatterData.push({
            value: [idx, d.high, `🔥 [${selectedUp.time}] ${selectedUp.name}`],
            symbolOffset: [0, -15],
            label: { show: true, position: 'top', formatter: p => p.value[2], backgroundColor: '#ea580c', color: '#fff', padding: [4,6], borderRadius: 3 }
          })
        }
      } else {
        const upText = ups.map(u => `[${u.time}] ${u.name}`).join('\n')
        if (upText) upScatterData.push({ value: [idx, d.high, upText], symbolOffset: [0, -15] })
      }

      const downs = JSON.parse(d.down_limit_stocks || "[]")
      if (hasSelected) {
        const selectedDown = downs.find(u => u.name === selectedStock.value)
        if (selectedDown) {
          downScatterData.push({
            value: [idx, d.low, `❄ [${selectedDown.time}] ${selectedDown.name}`],
            symbolOffset: [0, 15],
            label: { show: true, position: 'bottom', formatter: p => p.value[2], backgroundColor: '#059669', color: '#fff', padding: [4,6], borderRadius: 3 }
          })
        }
      } else {
        const downText = downs.map(u => `[${u.time}] ${u.name}`).join('\n')
        if (downText) downScatterData.push({ value: [idx, d.low, downText], symbolOffset: [0, 15] })
      }
    } catch(e) {}
  })

  let dzConfig = [
    { type: 'inside', start: 0, end: 100 },
    { type: 'slider', show: true, bottom: 0, textStyle: { color: '#9ba1a6' }, start: 0, end: 100 }
  ]

  if (leaderboardDays.value > 0) {
    const startValue = Math.max(kdata.length - leaderboardDays.value, 0)
    const endValue = Math.max(kdata.length - 1, 0)
    dzConfig = [
      { type: 'inside', startValue, endValue },
      { type: 'slider', show: true, bottom: 0, textStyle: { color: '#9ba1a6' }, startValue, endValue }
    ]
  } else if (leaderboardDays.value === -1 && zoomStartValue.value !== null && zoomEndValue.value !== null) {
    dzConfig = [
      { type: 'inside', startValue: zoomStartValue.value, endValue: zoomEndValue.value },
      { type: 'slider', show: true, bottom: 0, textStyle: { color: '#9ba1a6' }, startValue: zoomStartValue.value, endValue: zoomEndValue.value }
    ]
  }

  topicKlineOption.value = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: [{name: 'Topic Index'}, {name: 'Limit Up', itemStyle: {color: '#ef4444'}}, {name: 'Limit Down', itemStyle: {color: '#10b981'}}], textStyle: { color: '#9ba1a6' } },
    grid: { left: '3%', right: '3%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#9ba1a6' } },
    yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ba1a6' } },
    dataZoom: dzConfig,
    series: [
      {
        name: 'Topic Index', type: 'candlestick', data: values,
        itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }
      },
      {
        name: 'Limit Up', type: 'scatter', symbolSize: 0, data: upScatterData,
        label: { show: true, position: 'top', formatter: p => p.value[2], backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', padding: [2,4], borderRadius: 3, fontSize: 10 }, z: 10
      },
      {
        name: 'Limit Down', type: 'scatter', symbolSize: 0, data: downScatterData,
        label: { show: true, position: 'bottom', formatter: p => p.value[2], backgroundColor: 'rgba(16, 185, 129, 0.8)', color: '#fff', padding: [2,4], borderRadius: 3, fontSize: 10 }, z: 10
      }
    ]
  }
}

const loadData = async () => {
  const data = await fetchTopics()
  if (data && data.topics) {
    topicsList.value = data.topics.sort((a, b) => {
      if (a.is_top !== b.is_top) return (b.is_top || 0) - (a.is_top || 0)
      return new Date(b.updated_time) - new Date(a.updated_time)
    })
    klinesMap.value = data.klines
    if (topicsList.value.length > 0 && !selectedTopic.value) {
      selectTopic(topicsList.value[0])
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 24px; height: 100%; }
.header { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }
.btn-refresh { display: flex; align-items: center; gap: 8px; background: rgba(59, 130, 246, 0.15); color: var(--accent-color); border: 1px solid rgba(59, 130, 246, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
.btn-refresh:hover:not(:disabled) { background: rgba(59, 130, 246, 0.25); box-shadow: 0 0 12px var(--accent-glow); }
.icon.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

.layout { display: flex; flex-direction: column; gap: 16px; flex: 1; min-height: 0; overflow: hidden; }
.topic-top-bar { display: flex; align-items: center; padding: 12px 16px; gap: 12px; overflow: hidden; flex-shrink: 0; border-radius: 12px; }

.scroll-btn { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary); width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s; flex-shrink: 0; }
.scroll-btn:hover:not(:disabled) { background: rgba(59, 130, 246, 0.15); color: var(--accent-color); border-color: rgba(59, 130, 246, 0.3); }
.scroll-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.icon-small { width: 18px; height: 18px; }

.list-container-horizontal { flex: 1; display: flex; overflow-x: auto; gap: 10px; padding-bottom: 4px; align-items: center; scrollbar-width: none; scroll-behavior: smooth; }
.list-container-horizontal::-webkit-scrollbar { display: none; }

.topic-item-horizontal { display: flex; flex-direction: column; padding: 8px 12px; border-radius: 8px; cursor: pointer; transition: all 0.2s; min-width: 160px; max-width: 220px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); flex-shrink: 0; }
.topic-item-horizontal:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.15); transform: translateY(-1px); }
.topic-item-horizontal.active { background: rgba(59, 130, 246, 0.15); border-color: var(--accent-color); box-shadow: 0 0 10px rgba(59, 130, 246, 0.1); }

.topic-name-row { display: flex; justify-content: space-between; margin-bottom: 6px; align-items: center; gap: 8px; }
.topic-name { font-weight: 600; font-size: 0.95rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stock-badge { font-size: 0.75rem; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; flex-shrink: 0; }
.topic-meta { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-secondary); }
.top-badge { color: var(--danger); font-weight: bold; background: rgba(239, 68, 68, 0.1); padding: 0 6px; border-radius: 4px; margin-left: auto; }

.main-content { flex: 1; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; padding-right: 8px; }
.main-header { padding: 20px; }
.main-title { font-size: 1.5rem; margin-bottom: 12px; }
.main-meta { display: flex; gap: 16px; font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px; }
.meta-item { display: flex; align-items: center; gap: 4px; }
.text-accent { color: var(--accent-color); }
.topic-description { font-size: 0.95rem; line-height: 1.6; color: rgba(255,255,255,0.8); background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; }

.chart-panel { padding: 16px; height: auto; display: flex; flex-direction: column; }
.chart { width: 100%; height: 450px; min-height: 450px; }
.section-title { font-size: 1.1rem; margin-bottom: 16px; font-weight: 600; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }

.filter-group { display: flex; align-items: center; gap: 8px; }
.filter-input { width: 60px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; }
.filter-label { font-size: 0.85rem; color: var(--text-secondary); }
.filter-btn { background: rgba(255,255,255,0.1); color: white; border: none; padding: 4px 10px; border-radius: 4px; font-size: 0.85rem; cursor: pointer; }
.filter-btn.active { background: var(--accent-color); }

.leaderboard-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.leaderboard-card { background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); padding: 6px 10px; border-radius: 6px; cursor: pointer; transition: all 0.2s; min-width: 100px; display: flex; flex-direction: column; gap: 2px; }
.leaderboard-card:hover { border-color: rgba(255,255,255,0.2); background: rgba(255,255,255,0.05); }
.leaderboard-card.selected { border-color: var(--accent-color); background: rgba(59, 130, 246, 0.15); }
.lb-header { display: flex; justify-content: space-between; align-items: center; }
.lb-name { font-weight: 600; font-size: 0.9rem; }
.lb-action-btn { background: transparent; color: var(--text-secondary); border: none; cursor: pointer; padding: 2px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s; margin-left: 8px; }
.lb-action-btn:hover { color: var(--accent-color); background: rgba(255,255,255,0.1); }
.icon-tiny { width: 13px; height: 13px; }
.lb-counts { display: flex; gap: 6px; font-size: 0.8rem; font-weight: bold; }
.lb-up { color: var(--danger); }
.lb-down { color: var(--success); }

.table-container { padding: 20px; }
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; }
.data-table th { color: var(--text-secondary); font-weight: 500; font-size: 0.85rem; padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); }
.data-table td { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; }
.data-table tr:hover td { background: rgba(255,255,255,0.02); }
.data-table tr.highlighted-row td { background: rgba(59, 130, 246, 0.1); }
.font-bold { font-weight: 600; color: #fff; }
.sub-category { font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px; }
.source-tag { background: rgba(255,255,255,0.1); padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }

.empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: var(--text-secondary); }
.empty-icon { width: 48px; height: 48px; margin-bottom: 16px; opacity: 0.5; }
.empty-state-small { padding: 24px; text-align: center; color: var(--text-secondary); }
</style>
