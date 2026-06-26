<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">Market Topics</h1>
        <p class="subtitle">Trending themes and their K-line trajectories.</p>
      </div>
      <div class="actions">
        <!-- Frequency stats (shown when searching) -->
        <div v-if="matchedStockStats.length > 0" class="freq-inline">
          <span v-for="s in matchedStockStats.slice(0, 3)" :key="s.name" class="freq-inline-item" :title="`${s.name} appears in ${s.topicCount} topics`">
            <span class="freq-inline-name">{{ s.name }}</span>
            <span class="freq-badge freq-topics">{{ s.topicCount }}</span>
          </span>
        </div>
        <button class="filter-btn" :class="{ 'active': showStarredOnly }" @click="showStarredOnly = !showStarredOnly" style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; height: 38px; border-radius: 8px;">
          <StarIcon class="icon-small" :fill="showStarredOnly ? 'currentColor' : 'none'" :class="{ 'text-yellow': showStarredOnly }" :style="{ color: showStarredOnly ? '#fbbf24' : 'inherit' }" />
          Starred
        </button>
        <div class="search-box">
          <SearchIcon class="search-icon" />
          <input type="text" v-model="searchQuery" placeholder="Search stock or topic..." class="search-input" />
          <button v-if="searchQuery" class="clear-btn" @click="searchQuery = ''"><XIcon class="icon-tiny" /></button>
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

    <div class="layout">
      <!-- Top Bar for topic list -->
      <div class="topic-top-bar glass-panel">
        <button class="scroll-btn" @click="scrollList(-1)" :disabled="!canScrollLeft" v-show="topicsList.length > 0">
          <ChevronLeftIcon class="icon-small" />
        </button>
        <div class="list-container-horizontal" ref="listContainer" @scroll="checkScroll">
          <div v-if="filteredTopics.length === 0" class="empty-state-small" style="width: 100%; color: #9ba1a6; padding: 12px 0;">
             No topics match "{{ searchQuery }}"
          </div>
          <div 
            v-for="topic in filteredTopics" 
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
          <div class="chart-panel glass-panel" style="position: relative; transition: height 0.3s;" :style="{ height: selectedStock ? '600px' : '350px' }">
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px 0 16px; position: absolute; top: 0; left: 0; right: 0; z-index: 10;">
              <h3 class="section-title" style="margin-bottom: 0;">Market Trend & Active Stocks</h3>
              
              <div style="display: flex; gap: 8px;" v-if="selectedStock && Object.keys(topicKlineOption).length > 0 && !stockLoading">
                <button class="btn-refresh" @click="toggleStockSelection(selectedStock)" style="padding: 4px 12px; font-size: 0.85rem; background: rgba(15, 23, 42, 0.8);">
                  <EyeOffIcon class="icon-tiny" /> Hide Stock
                </button>
                <button class="btn-refresh" @click="goToStockExplorer(selectedStock)" style="padding: 4px 12px; font-size: 0.85rem; background: rgba(15, 23, 42, 0.8);">
                  <ExternalLinkIcon class="icon-tiny" /> Open Explorer
                </button>
              </div>
            </div>

            <div v-if="stockLoading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 12px; color: #9ba1a6; background: rgba(15, 23, 42, 0.6); z-index: 20; border-radius: 12px;">
               <RefreshCwIcon class="icon spin" />
               <p>Fetching multi-grid data for {{ selectedStock }}...</p>
            </div>
            
            <div style="height: 100%; padding-top: 48px; box-sizing: border-box; position: relative;">
              <v-chart v-if="Object.keys(topicKlineOption).length > 0" class="chart" :option="topicKlineOption" @datazoom="handleDataZoom" autoresize style="height: 100%; width: 100%;" />
              <div v-else class="empty-state-small" style="height: 100%; display: flex; align-items: center; justify-content: center;">
                <p>No historical K-line data available for this topic from upstream API.</p>
              </div>
            </div>
          </div>

          <!-- Selected Stock Details Panel -->
          <div class="selected-stock-panel glass-panel" v-if="selectedStockDetails && selectedStockDetails.length > 0" style="margin-bottom: 16px;">
            <div class="section-header" style="margin-bottom: 8px; padding: 16px 20px 0 20px;">
              <h3 class="section-title" style="margin: 0; display: flex; align-items: center; gap: 12px;">
                <span style="color: #60a5fa; font-size: 1.2rem;">{{ selectedStockDetails[0]['个股'] }}</span>
                <span style="font-size: 0.85rem; color: #9ba1a6; font-weight: normal;" v-if="selectedStockDetails.length > 1">({{ selectedStockDetails.length }} items)</span>
              </h3>
              <button class="filter-btn" @click="toggleStockSelection(selectedStockDetails[0]['个股'])" style="display: flex; align-items: center; gap: 4px;">
                <XIcon class="icon-tiny" /> Clear
              </button>
            </div>
            
            <div v-for="(detail, idx) in selectedStockDetails" :key="idx" class="topic-description" :style="idx < selectedStockDetails.length - 1 ? 'border-bottom: 1px dashed rgba(255,255,255,0.1); margin-bottom: 8px;' : ''" style="background: transparent; padding-top: 0; padding-bottom: 16px; padding-left: 20px; padding-right: 20px;">
              <div style="margin-bottom: 12px; margin-top: 8px;">
                <span class="stock-badge" style="font-size: 0.85rem; font-weight: normal; background: rgba(255,255,255,0.1); padding: 4px 8px; border-radius: 6px;">
                  {{ detail['一级大类'] }}<span v-if="detail['二级小类']"> - {{ detail['二级小类'] }}</span>
                </span>
              </div>
              <div style="margin-bottom: 8px;">
                <span style="color: #9ba1a6; font-size: 0.85rem;">Logic & Relevance:</span>
                <div style="margin-top: 4px; line-height: 1.6; color: #f8fafc; font-size: 0.95rem;">{{ detail['相关性'] }}</div>
              </div>
              <div v-if="detail['信息源']" style="margin-top: 12px;">
                <span style="color: #9ba1a6; font-size: 0.85rem;">Source:</span>
                <span class="source-tag" style="margin-left: 8px; font-size: 0.8rem; background: rgba(16, 185, 129, 0.15); color: #6ee7b7; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(16, 185, 129, 0.2);">{{ detail['信息源'] }}</span>
              </div>
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
                  <button class="lb-action-btn" @click.stop="toggleStar(stock.name)" title="Toggle Star">
                    <StarIcon class="icon-tiny" :fill="starredStocks.includes(stock.name) ? 'currentColor' : 'none'" :style="{ color: starredStocks.includes(stock.name) ? '#fbbf24' : 'inherit' }" />
                  </button>
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

          <!-- Topic Description -->
          <div class="description-panel glass-panel" v-if="selectedTopic.content">
            <h3 class="section-title" style="padding: 16px 20px 0 20px; margin-bottom: 8px;">Topic Analysis & Logic</h3>
            <div class="topic-description" style="background: transparent; padding-top: 0;" v-html="formatContent(selectedTopic.content)"></div>
          </div>

          <!-- Related Stocks Table -->
          <div class="table-container glass-panel">
            <h3 class="section-title">Related Stocks ({{ filteredTopicRows ? filteredTopicRows.length : 0 }})</h3>
            <div class="table-scroll" v-if="filteredTopicRows && filteredTopicRows.length > 0">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width: 40px; text-align: center;">⭐</th>
                    <th>Category</th>
                    <th>Stock Name</th>
                    <th>Relevance / Logic</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, index) in filteredTopicRows" :key="index"
                      :class="{ 'highlighted-row': selectedStock === row['个股'] }"
                      @click="toggleStockSelection(row['个股'])">
                    <td @click.stop="toggleStar(row['个股'])" style="cursor: pointer; text-align: center;">
                      <StarIcon class="icon-small" :fill="starredStocks.includes(row['个股']) ? 'currentColor' : 'none'" :style="{ color: starredStocks.includes(row['个股']) ? '#fbbf24' : '#64748b', transition: 'all 0.2s' }" />
                    </td>
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
import { RefreshCwIcon, AlertTriangleIcon, HashIcon, ExternalLinkIcon, ChevronLeftIcon, ChevronRightIcon, EyeOffIcon, SearchIcon, XIcon, StarIcon } from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'
import { useChartFactory } from '../composables/useChartFactory'
import axios from 'axios'
import * as echarts from 'echarts/core'

const router = useRouter()
const { loading, error, fetchTopics, triggerTopicsRefresh, fetchCsv, triggerRealtimeFetch } = useDataLoader()

const backendUpdating = ref(false)
const showStarredOnly = ref(false)
const starredStocks = ref([])

const loadStarredStocks = async () => {
  try {
    const res = await axios.get('/api/user/starred_stocks')
    if (res.data && res.data.starred) {
      starredStocks.value = res.data.starred
    }
  } catch (err) {
    console.error("Failed to load starred stocks:", err)
  }
}

const toggleStar = async (stockName) => {
  try {
    const res = await axios.post('/api/user/starred_stocks/toggle', { symbol: stockName })
    if (res.data && res.data.starred) {
      starredStocks.value = res.data.starred
    }
  } catch (err) {
    console.error("Failed to toggle starred stock:", err)
  }
}

const handleRefresh = async () => {
  if (backendUpdating.value) return
  backendUpdating.value = true
  
  try {
    await triggerTopicsRefresh()
    // Topics update once daily; no need to poll. Wait briefly for backend to finish writing, then reload.
    await new Promise(resolve => setTimeout(resolve, 8000))
  } finally {
    backendUpdating.value = false
    loadData()
  }
}

const topicsList = ref([])
const searchQuery = ref('')
const filteredTopics = computed(() => {
  let list = topicsList.value

  if (showStarredOnly.value) {
    list = list.filter(topic => {
      if (!topic.rows) return false
      return topic.rows.some(row => starredStocks.value.includes(row['个股']))
    })
  }

  if (!searchQuery.value.trim()) return list

  const query = searchQuery.value.trim().toLowerCase()
  return list.filter(topic => {
    if (topic.name && topic.name.toLowerCase().includes(query)) return true
    if (topic.rows && Array.isArray(topic.rows) && topic.rows.some(row => row && row['个股'] && String(row['个股']).toLowerCase().includes(query))) return true
    return false
  })
})

// --- Stock frequency stats: how many topics each stock appears in ---
const matchedStockStats = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return []

  const stats = {}  // { stockName: Set of topic names }
  for (const topic of topicsList.value) {
    if (!topic.rows) continue
    for (const row of topic.rows) {
      const name = row['个股']
      if (!name) continue
      if (!stats[name]) stats[name] = new Set()
      stats[name].add(topic.name)
    }
  }

  const result = []
  for (const [name, topicSet] of Object.entries(stats)) {
    if (!name.toLowerCase().includes(query)) continue
    result.push({ name, topicCount: topicSet.size })
  }
  result.sort((a, b) => b.topicCount - a.topicCount)
  return result
})

const filteredTopicRows = computed(() => {
  if (!selectedTopic.value || !selectedTopic.value.rows) return []
  if (showStarredOnly.value) {
    return selectedTopic.value.rows.filter(r => starredStocks.value.includes(r['个股']))
  }
  return selectedTopic.value.rows
})

const klinesMap = shallowRef({})
const selectedTopic = ref(null)
const selectedStock = ref(null)
const stockLoading = ref(false)
const topicKlineOption = shallowRef({})

const selectedStockDetails = computed(() => {
  if (!selectedStock.value || !selectedTopic.value || !selectedTopic.value.rows) return []
  return selectedTopic.value.rows.filter(r => r['个股'] === selectedStock.value)
})

const stockKlineOption = shallowRef({})
const { createKlineOption } = useChartFactory()

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

watch(filteredTopics, (newVal) => {
  nextTick(() => {
    checkScroll()
  })
  
  // If the currently selected topic is filtered out, select the first one available
  if (newVal.length > 0) {
    if (!selectedTopic.value || !newVal.find(t => t.id === selectedTopic.value.id)) {
      selectTopic(newVal[0])
    }
  } else {
    selectedTopic.value = null
    selectedStock.value = null
    topicKlineOption.value = {}
  }
})

watch(searchQuery, (newVal) => {
  if (!newVal.trim() || !selectedTopic.value) return
  
  const query = newVal.trim().toLowerCase()
  const matchedRow = selectedTopic.value.rows?.find(r => r['个股'] && String(r['个股']).toLowerCase().includes(query))
  
  if (matchedRow && selectedStock.value !== matchedRow['个股']) {
    setTimeout(() => {
      if (selectedStock.value !== matchedRow['个股']) {
        toggleStockSelection(matchedRow['个股'])
      }
    }, 50)
  }
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

const toggleStockSelection = async (stockName) => {
  if (selectedStock.value === stockName) {
    selectedStock.value = null
    stockKlineOption.value = {}
  } else {
    selectedStock.value = stockName
    await loadStockKline(stockName)
  }
  updateChartOption()
}

const loadStockKline = async (stockName) => {
  stockKlineOption.value = {}
  stockLoading.value = true
  try {
    const res = await axios.get(`/api/resolve_symbol/${encodeURIComponent(stockName)}`)
    if (res.data && res.data.symbol) {
      const symbol = res.data.symbol.toUpperCase()
      
      // Trigger real-time fetch to ensure K-line data is completely up to date
      await triggerRealtimeFetch(symbol, 'market')
      
      const klineData = await fetchCsv('market', `${symbol}_tencent_sina_kline.csv`)
      
      if (klineData && klineData.length) {
        const tid = String(selectedTopic.value.id)
        const topicKData = klinesMap.value[tid] || []
        const topicDates = topicKData.map(d => d.trade_date)
        
        let alignedKlineData = klineData
        if (topicDates.length > 0) {
          const klineMap = {}
          klineData.forEach(d => { klineMap[d.date || d.trade_date] = d })
          
          let lastValidRow = null
          alignedKlineData = topicDates.map(tdate => {
            if (klineMap[tdate]) {
              lastValidRow = { ...klineMap[tdate], date: tdate, trade_date: tdate }
              return lastValidRow
            } else {
              if (lastValidRow) {
                return { ...lastValidRow, date: tdate, trade_date: tdate, volume: 0 }
              } else {
                // If missing before first data point, return a 0 row
                return { date: tdate, trade_date: tdate, open: 0, close: 0, high: 0, low: 0, volume: 0 }
              }
            }
          })
        }

        // Toggles default to showing all indicators to match Stock Data Explorer
        const toggles = { showLimit: true, showHigh20: true, showAbnormal: true, showPrediction: true }
        stockKlineOption.value = createKlineOption(`${stockName} (${symbol})`, alignedKlineData, toggles)
      }
    }
  } catch (err) {
    console.error("Failed to load individual stock kline:", err)
  } finally {
    stockLoading.value = false
  }
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
  
  let allCounts = Object.keys(counts)
    .map(name => ({ name, up: counts[name].up, down: counts[name].down }))
    .sort((a, b) => b.up - a.up || b.down - a.down)
    
  if (showStarredOnly.value) {
    allCounts = allCounts.filter(s => starredStocks.value.includes(s.name))
  }
  
  activeStocksLeaderboard.value = allCounts.slice(0, 20) // show top 20
}

watch([showStarredOnly, starredStocks], () => {
  buildLeaderboard()
}, { deep: true })

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

  // Auto-select stock if searching
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.trim().toLowerCase()
    const matchedRow = topic.rows?.find(r => r['个股'] && r['个股'].toLowerCase().includes(query))
    if (matchedRow) {
      // Small timeout to allow UI update before loading heavy charts
      setTimeout(() => {
        toggleStockSelection(matchedRow['个股'])
      }, 50)
    }
  }
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
        let upText = ''
        if (ups.length > 0) {
          const names = ups.map(u => u.name)
          if (names.length <= 2) {
            upText = names.join('\n')
          } else {
            upText = names.slice(0, 2).join('\n') + `\n...共${names.length}只`
          }
        }
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
        let downText = ''
        if (downs.length > 0) {
          const names = downs.map(u => u.name)
          if (names.length <= 2) {
            downText = names.join('\n')
          } else {
            downText = names.slice(0, 2).join('\n') + `\n...共${names.length}只`
          }
        }
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

  let option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: 'rgba(148,163,184,0.3)' } },
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: '#f2f2f2', fontSize: 12 },
      padding: [8, 12],
      formatter: (params) => {
        if (!params || !params.length) return ''
        const dateIdx = params[0].dataIndex
        const d = kdata[dateIdx]
        if (!d) return ''
        let html = `<div style="font-weight:600;margin-bottom:4px;color:#94a3b8">${d.trade_date}</div>`
        // Candlestick OHLC
        const candleParam = params.find(p => p.seriesName === 'Topic Index')
        if (candleParam) {
          const [open, close, low, high] = candleParam.data?.value || candleParam.data || []
          html += `<div>Open: <b>${open}</b>  Close: <b>${close}</b></div>`
          html += `<div>High: <b>${high}</b>  Low: <b>${low}</b></div>`
        }
        // Limit Up stocks
        try {
          const ups = JSON.parse(d.up_limit_stocks || '[]')
          if (ups.length > 0) {
            html += `<div style="margin-top:6px;color:#ef4444;font-weight:600">🔥 Limit Up (${ups.length})</div>`
            ups.slice(0, 8).forEach(u => {
              const highlight = hasSelected && u.name === selectedStock.value
              html += `<div style="padding-left:8px;${highlight ? 'color:#facc15;font-weight:700' : 'color:#fca5a5'}">[${u.time}] ${u.name}</div>`
            })
            if (ups.length > 8) html += `<div style="padding-left:8px;color:#9ba1a6">...+${ups.length - 8} more</div>`
          }
        } catch(e) {}
        // Limit Down stocks
        try {
          const downs = JSON.parse(d.down_limit_stocks || '[]')
          if (downs.length > 0) {
            html += `<div style="margin-top:6px;color:#10b981;font-weight:600">❄ Limit Down (${downs.length})</div>`
            downs.slice(0, 8).forEach(u => {
              const highlight = hasSelected && u.name === selectedStock.value
              html += `<div style="padding-left:8px;${highlight ? 'color:#facc15;font-weight:700' : 'color:#6ee7b7'}">[${u.time}] ${u.name}</div>`
            })
            if (downs.length > 8) html += `<div style="padding-left:8px;color:#9ba1a6">...+${downs.length - 8} more</div>`
          }
        } catch(e) {}
        return html
      }
    },
    legend: { 
      data: [{name: 'Topic Index'}, {name: 'Limit Up', itemStyle: {color: '#ef4444'}}, {name: 'Limit Down', itemStyle: {color: '#10b981'}}], 
      textStyle: { color: '#9ba1a6', fontSize: 11 },
      top: 4,
      left: 'center',
      itemGap: 16,
      itemWidth: 14,
      itemHeight: 10
    },
    grid: [{ left: '2%', right: '2%', bottom: '15%', top: 36 }],
    xAxis: [{ type: 'category', data: dates, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#9ba1a6' } }],
    yAxis: [{ type: 'value', scale: true, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ba1a6' } }],
    dataZoom: dzConfig,
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    series: [
      {
        name: 'Topic Index', type: 'candlestick', data: values,
        itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }
      },
      {
        name: 'Limit Up', type: 'scatter', data: upScatterData,
        symbolSize: 0,
        itemStyle: { color: 'rgba(239, 68, 68, 0.85)', borderColor: '#fff', borderWidth: 0.5 },
        label: {
          show: true,
          position: 'top',
          formatter: p => {
            const text = p.value[2] || ''
            if (hasSelected) {
              const match = text.match(/\[([^\]]+)\]\s*(.+)/)
              if (match) return match[2]
            }
            return text
          },
          backgroundColor: 'rgba(239, 68, 68, 0.9)',
          color: '#fff',
          padding: [3, 6],
          borderRadius: 3,
          fontSize: 10,
          distance: 8
        },
        labelLayout: { moveOverlap: 'shiftY' },
        z: 10
      },
      {
        name: 'Limit Down', type: 'scatter', data: downScatterData,
        symbolSize: 0,
        itemStyle: { color: 'rgba(16, 185, 129, 0.85)', borderColor: '#fff', borderWidth: 0.5 },
        label: {
          show: true,
          position: 'bottom',
          formatter: p => {
            const text = p.value[2] || ''
            if (hasSelected) {
              const match = text.match(/\[([^\]]+)\]\s*(.+)/)
              if (match) return match[2]
            }
            return text
          },
          backgroundColor: 'rgba(16, 185, 129, 0.9)',
          color: '#fff',
          padding: [3, 6],
          borderRadius: 3,
          fontSize: 10,
          distance: 8
        },
        labelLayout: { moveOverlap: 'shiftY' },
        z: 10
      }
    ]
  }

  if (hasSelected && Object.keys(stockKlineOption.value).length > 0) {
    const stockOpt = stockKlineOption.value
    
    // Top grid for Topic Index - leave room for legend row
    option.grid[0].top = 36
    option.grid[0].height = '30%'
    option.grid[0].bottom = 'auto'
    option.xAxis[0].axisLabel = { show: false }
    option.xAxis[0].axisTick = { show: false }
    
    // Bottom grids for Stock Kline and Volume
    option.grid.push(
      { left: '2%', right: '2%', top: '42%', height: '35%' }, 
      { left: '2%', right: '2%', top: '80%', height: '10%' }
    )
    
    option.xAxis.push(
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: false, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', gridIndex: 2, data: dates, boundaryGap: false, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#9ba1a6' } }
    )
    
    if (stockOpt.yAxis && stockOpt.yAxis.length > 1) {
      option.yAxis.push(
        { ...stockOpt.yAxis[0], gridIndex: 1 },
        { ...stockOpt.yAxis[1], gridIndex: 2 }
      )
    }
    
    if (stockOpt.series) {
      const stockSeries = stockOpt.series.map(s => {
        const newXIndex = (s.xAxisIndex || 0) + 1
        const newYIndex = (s.yAxisIndex || 0) + 1
        return { ...s, xAxisIndex: newXIndex, yAxisIndex: newYIndex }
      })
      option.series = [...option.series, ...stockSeries]
    }
    
    // Merge legend data and use two-row layout to avoid horizontal overflow
    if (stockOpt.legend && stockOpt.legend.data) {
      option.legend.data = [...option.legend.data, ...stockOpt.legend.data]
    }
    option.legend.type = 'scroll'
    option.legend.width = '80%'
    
    dzConfig.forEach(z => {
      z.xAxisIndex = [0, 1, 2]
    })
    option.dataZoom = dzConfig
  }

  topicKlineOption.value = option
}

const loadData = async () => {
  const data = await fetchTopics()
  if (data && data.topics) {
    topicsList.value = data.topics.sort((a, b) => {
      if (a.is_top !== b.is_top) return (b.is_top || 0) - (a.is_top || 0)
      return new Date(b.updated_time) - new Date(a.updated_time)
    })
    klinesMap.value = data.klines
    if (filteredTopics.value.length > 0 && !selectedTopic.value) {
      selectTopic(filteredTopics.value[0])
    }
  }
}

onMounted(() => {
  loadStarredStocks()
  loadData()
})
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 24px; height: 100%; }
.header { display: flex; justify-content: space-between; align-items: flex-start; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }
.actions { display: flex; align-items: center; gap: 16px; }

/* Frequency stats (inline in header) */
.freq-inline { display: flex; align-items: center; gap: 8px; }
.freq-inline-item { display: inline-flex; align-items: center; gap: 4px; }
.freq-inline-name { font-size: 0.8rem; font-weight: 600; color: var(--text-primary, #f8fafc); }
.freq-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 0.7rem; font-weight: 600; font-family: monospace; }
.freq-topics { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }

.search-box { position: relative; display: flex; align-items: center; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 4px 12px; transition: border-color 0.2s; height: 38px; box-sizing: border-box; }
.search-box:focus-within { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2); }
.search-icon { width: 16px; height: 16px; color: #9ca3af; margin-right: 8px; flex-shrink: 0; }
.search-input { background: transparent; border: none; color: #f8fafc; font-size: 0.9rem; outline: none; width: 200px; padding: 0; }
.search-input::placeholder { color: #64748b; }
.clear-btn { background: transparent; border: none; color: #9ca3af; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 2px; margin-left: 4px; border-radius: 50%; transition: all 0.2s; }
.clear-btn:hover { color: #f8fafc; background: rgba(255,255,255,0.1); }
.btn-refresh { display: flex; align-items: center; gap: 8px; background: rgba(59, 130, 246, 0.15); color: var(--accent-color); border: 1px solid rgba(59, 130, 246, 0.3); padding: 8px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s; height: 38px; box-sizing: border-box; }
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

.topic-item-horizontal { display: flex; flex-direction: column; padding: 8px 12px; border-radius: 8px; cursor: pointer; transition: all 0.2s; min-width: 160px; max-width: 320px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.05); flex-shrink: 0; }
.topic-item-horizontal:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.15); transform: translateY(-1px); }
.topic-item-horizontal.active { background: rgba(59, 130, 246, 0.15); border-color: var(--accent-color); box-shadow: 0 0 10px rgba(59, 130, 246, 0.1); }

.topic-name-row { display: flex; justify-content: space-between; margin-bottom: 6px; align-items: center; gap: 8px; }
.topic-name { font-weight: 600; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stock-badge { font-size: 0.7rem; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; flex-shrink: 0; }
.topic-meta { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-secondary); }
.top-badge { color: var(--danger); font-weight: bold; background: rgba(239, 68, 68, 0.1); padding: 0 6px; border-radius: 4px; margin-left: auto; }

.main-content { flex: 1; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; padding-right: 8px; }
.topic-description { font-size: 0.95rem; line-height: 1.6; color: rgba(255,255,255,0.8); background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; }

.chart-panel { padding: 0; position: relative; overflow: hidden; flex-shrink: 0; min-height: 350px; }
.chart { width: 100%; height: 100%; }
.section-title { font-size: 1.1rem; margin-bottom: 16px; font-weight: 600; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }

.filter-group { display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.2); padding: 4px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); }
.filter-input { width: 60px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 4px 8px; border-radius: 6px; font-size: 0.8rem; text-align: center; outline: none; transition: border-color 0.2s; }
.filter-input:focus { border-color: rgba(59, 130, 246, 0.5); }
.filter-label { font-size: 0.8rem; color: var(--text-secondary); margin: 0 4px; }
.filter-btn { background: transparent; color: var(--text-secondary); border: 1px solid transparent; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; cursor: pointer; transition: all 0.2s; font-weight: 500; }
.filter-btn:hover { background: rgba(255,255,255,0.05); color: #fff; }
.filter-btn.active { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border-color: rgba(59, 130, 246, 0.3); }

.leaderboard-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.leaderboard-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); padding: 6px 10px 6px 12px; border-radius: 8px; cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); display: flex; flex-direction: row; align-items: center; gap: 8px; width: auto; }
.leaderboard-card:hover { border-color: rgba(255,255,255,0.15); background: rgba(255,255,255,0.04); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
.leaderboard-card.selected { border-color: rgba(59, 130, 246, 0.5); background: rgba(59, 130, 246, 0.1); box-shadow: 0 0 15px rgba(59, 130, 246, 0.15); }
.lb-header { display: flex; align-items: center; gap: 4px; }
.lb-name { font-weight: 500; font-size: 0.9rem; color: #f8fafc; white-space: nowrap; }
.lb-action-btn { background: transparent; color: #64748b; border: none; cursor: pointer; padding: 2px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s; margin-left: 2px; }
.lb-action-btn:hover { color: #38bdf8; background: rgba(56, 189, 248, 0.1); }
.icon-tiny { width: 14px; height: 14px; }
.lb-counts { display: flex; gap: 8px; }
.lb-up { background: rgba(239, 68, 68, 0.15); color: #fca5a5; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; border: 1px solid rgba(239, 68, 68, 0.2); display: flex; align-items: center; gap: 4px; }
.lb-down { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.2); display: flex; align-items: center; gap: 4px; }

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
