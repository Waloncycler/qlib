<template>
  <div class="report-dashboard">
    <!-- Header -->
    <header class="dashboard-header">
      <div class="header-content">
        <h1>AI Morning Reports</h1>
        <p class="subtitle">Daily AI market insights, summaries, and concepts</p>
      </div>
      <div class="header-actions" style="display: flex; align-items: center; gap: 10px;">
        <!-- Frequency stats (shown when searching) -->
        <div v-if="matchedStockStats.length > 0" class="freq-inline">
          <span v-for="s in matchedStockStats.slice(0, 3)" :key="s.symbol" class="freq-inline-item" :title="`${s.name} - 7d:${s.count7} 30d:${s.count30} Total:${s.total}`">
            <span class="freq-inline-name">{{ s.name }}</span>
            <span class="freq-badge freq-7">{{ s.count7 }}d</span>
            <span class="freq-badge freq-30">{{ s.count30 }}d</span>
            <span class="freq-badge freq-total">{{ s.total }}</span>
          </span>
        </div>
        <div class="search-box" style="position: relative; display: flex; align-items: center;">
          <SearchIcon style="position: absolute; left: 10px; width: 14px; height: 14px; opacity: 0.5;" />
          <input type="text" v-model="searchQuery" placeholder="Search stock or report..." style="padding: 6px 8px 6px 30px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; color: inherit; font-size: 13px; width: 220px;" />
          <button v-if="searchQuery" @click="searchQuery = ''" style="position: absolute; right: 6px; background: none; border: none; cursor: pointer; opacity: 0.5; padding: 2px; display: flex;"><XIcon style="width: 12px; height: 12px;" /></button>
        </div>
        <button class="refresh-btn" @click="handleRefresh" :disabled="loading || backendUpdating">
          <RefreshCcwIcon class="icon" :class="{ 'spinning': loading || backendUpdating }" />
          {{ backendUpdating ? 'Updating Backend...' : (loading ? 'Loading...' : 'Refresh') }}
        </button>
      </div>
    </header>

    <div v-if="error" class="error-banner">
      {{ error }}
    </div>

    <!-- Main Layout -->
    <div class="layout-container" v-if="!loading || reports.length > 0">
      <!-- Left Sidebar: Report List -->
      <div class="report-list-container glass-panel">

        <div class="report-list">
          <div 
            v-for="report in filteredReports" 
            :key="report.id"
            class="report-item"
            :class="{ 'active': selectedReport && selectedReport.id === report.id }"
            @click="selectReport(report)"
          >
            <div class="report-item-title">{{ report.title }}</div>
            <div class="report-item-date">{{ formatDate(report.created_time) }}</div>
            <div class="report-item-concepts" v-if="report.concepts && report.concepts.length > 0">
              <span class="concept-tag" v-for="(concept, idx) in report.concepts.slice(0, 2)" :key="idx">
                {{ formatConceptTitle(concept) }}
              </span>
            </div>
          </div>
          <div v-if="filteredReports.length === 0" style="padding: 20px; text-align: center; color: #9ca1a6; font-size: 13px;">
            No reports match "{{ searchQuery }}"
          </div>
        </div>
      </div>

      <!-- Right Panel: Report Detail -->
      <div class="report-detail-container glass-panel" v-if="selectedReport">

        
        <div class="detail-content-scroll">
          <!-- Stock Pool Section (Inside scroll area so it can be scrolled) -->
          <div class="stock-pool-section" v-if="selectedReport.stock_pool && selectedReport.stock_pool.length > 0">
            <div class="stock-pool-title">
              <TrendingUpIcon class="pool-icon" /> Daily Strategy Pool
              <span v-if="searchQuery.trim()" class="search-hint"> — filtered by "{{ searchQuery.trim() }}"</span>
            </div>

            <div class="stock-pool-groups">
              <div 
                class="stock-pool-group"
                v-for="(group, idx) in displayedStockPool"
                :key="idx"
              >
                <div class="group-concept-name">
                  {{ group.concept }}
                  <span class="new-badge" v-if="group.is_new">NEW</span>
                </div>
                
                <div class="stock-pool-tags" v-if="group.core_stocks && group.core_stocks.length > 0">
                  <div class="sub-label">核心股票</div>
                  <router-link 
                    v-for="stock in group.core_stocks" 
                    :key="stock.symbol"
                    :to="'/stock/' + stock.symbol"
                    class="stock-tag core-tag"
                    :class="{ 'stock-highlight': isStockMatched(stock) }"
                  >
                    <span class="stock-name">{{ stock.name }}</span>
                    <span class="stock-code">{{ stock.code }}</span>
                  </router-link>
                </div>
                
                <div class="stock-pool-tags" v-if="group.other_stocks && group.other_stocks.length > 0">
                  <div class="sub-label">其他股票</div>
                  <router-link 
                    v-for="stock in group.other_stocks" 
                    :key="stock.symbol"
                    :to="'/stock/' + stock.symbol"
                    class="stock-tag other-tag"
                    :class="{ 'stock-highlight': isStockMatched(stock) }"
                  >
                    <span class="stock-name">{{ stock.name }}</span>
                    <span class="stock-code">{{ stock.code }}</span>
                  </router-link>
                </div>
              </div>
              <div v-if="searchQuery.trim() && displayedStockPool.length === 0" style="padding: 20px; text-align: center; color: #9ca1a6; font-size: 13px;">
                No stocks match "{{ searchQuery }}" in this report
              </div>
            </div>
          </div>

          <div class="detail-content formatted-text" v-html="formattedContent"></div>
        </div>
      </div>
      
      <!-- Empty State -->
      <div class="report-detail-container glass-panel empty-state" v-else>
        <BookOpenIcon class="empty-icon" />
        <p>Select a report from the list to view its contents.</p>
      </div>
    </div>
    
    <!-- Loading State -->
    <div v-else-if="loading" class="loading-state">
      <div class="loader"></div>
      <p>Loading AI Morning Reports...</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { RefreshCcwIcon, BookOpenIcon, UserIcon, ClockIcon, TrendingUpIcon, SearchIcon, XIcon } from 'lucide-vue-next'
import { useDataLoader } from '../composables/useDataLoader'

const { fetchReports, loading, triggerReportsRefresh, error } = useDataLoader()
const reports = ref([])
const selectedReport = ref(null)
const backendUpdating = ref(false)
const searchQuery = ref('')

const filteredReports = computed(() => {
  if (!searchQuery.value.trim()) return reports.value
  const query = searchQuery.value.trim().toLowerCase()
  const matched = reports.value.filter(report => {
    // Match report title
    if (report.title && report.title.toLowerCase().includes(query)) return true
    // Match concept names and stock code/name within stock_pool
    if (report.stock_pool && Array.isArray(report.stock_pool)) {
      return report.stock_pool.some(group => {
        if (group.concept && group.concept.toLowerCase().includes(query)) return true
        const core = group.core_stocks || []
        const other = group.other_stocks || []
        return [...core, ...other].some(s => {
          const name = (s.name || '').toLowerCase()
          const symbol = (s.symbol || '').toLowerCase()
          const code = (s.code || '').toLowerCase()
          return name.includes(query) || symbol.includes(query) || code.includes(query)
        })
      })
    }
    return false
  })
  return matched
})

// Auto-select first matching report when search changes
watch(filteredReports, (newVal) => {
  if (newVal.length > 0) {
    if (!selectedReport.value || !newVal.find(r => r.id === selectedReport.value.id)) {
      selectedReport.value = newVal[0]
    }
  }
})

const isStockMatched = (stock) => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return false
  const name = (stock.name || '').toLowerCase()
  const symbol = (stock.symbol || '').toLowerCase()
  const code = (stock.code || '').toLowerCase()
  return name.includes(query) || symbol.includes(query) || code.includes(query)
}

// When searching, only show concept groups that contain matching stocks
const displayedStockPool = computed(() => {
  const pool = selectedReport.value?.stock_pool
  if (!pool || !Array.isArray(pool)) return []
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return pool
  return pool.filter(group => {
    if (group.concept && group.concept.toLowerCase().includes(query)) return true
    const all = [...(group.core_stocks || []), ...(group.other_stocks || [])]
    return all.some(s => isStockMatched(s))
  })
})

// --- Stock frequency statistics across all reports ---
// Cache: { symbol -> { name, code, dates: Set of "YYYY-MM-DD" } }
const stockStats = computed(() => {
  const stats = {}
  const now = new Date()
  for (const report of reports.value) {
    // Extract date from title or created_time
    let dateStr = ''
    const m = (report.title || '').match(/(\d{4})(\d{2})(\d{2})/)
    if (m) {
      dateStr = `${m[1]}-${m[2]}-${m[3]}`
    } else if (report.created_time) {
      dateStr = report.created_time.split('T')[0]
    }
    if (!dateStr) continue

    const pool = report.stock_pool || []
    for (const group of pool) {
      for (const s of [...(group.core_stocks || []), ...(group.other_stocks || [])]) {
        if (!s.symbol) continue
        if (!stats[s.symbol]) {
          stats[s.symbol] = { name: s.name || '', code: s.code || '', dates: new Set() }
        }
        stats[s.symbol].dates.add(dateStr)
      }
    }
  }

  // Convert Sets to counts
  const result = []
  for (const [symbol, info] of Object.entries(stats)) {
    const dates = info.dates
    let count7 = 0, count30 = 0
    for (const d of dates) {
      const diff = (now - new Date(d)) / (1000 * 60 * 60 * 24)
      if (diff <= 7) count7++
      if (diff <= 30) count30++
    }
    result.push({ symbol, name: info.name, code: info.code, total: dates.size, count7, count30 })
  }
  // Sort by total appearances descending
  result.sort((a, b) => b.total - a.total)
  return result
})

// Stats for stocks matching the current search query
const matchedStockStats = computed(() => {
  if (!searchQuery.value.trim()) return []
  return stockStats.value.filter(s => isStockMatched(s))
})

const loadData = async () => {
  const data = await fetchReports()
  if (data && data.length > 0) {
    reports.value = data
    if (!selectedReport.value) {
      selectedReport.value = data[0]
    } else {
      const found = data.find(r => r.id === selectedReport.value.id)
      if (found) selectedReport.value = found
    }
  }
}

const handleRefresh = async () => {
  if (backendUpdating.value) return
  backendUpdating.value = true
  
  try {
    await triggerReportsRefresh()
    // Reports update once daily (trading day mornings); no need to poll.
    await new Promise(resolve => setTimeout(resolve, 8000))
  } finally {
    backendUpdating.value = false
    loadData()
  }
}

onMounted(() => {
  loadData()
})

const selectReport = (report) => {
  selectedReport.value = report
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', { 
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
  })
}

// Extract just the concept name before the dash for the tags
const formatConceptTitle = (conceptStr) => {
  if (!conceptStr) return ''
  const match = conceptStr.match(/^([^-——]+)/)
  if (match) return match[1].trim()
  return conceptStr.substring(0, 10) + '...'
}

const formattedContent = computed(() => {
  if (!selectedReport.value || !selectedReport.value.content) return ''
  
  let html = selectedReport.value.content
  
  // Highlight tags like 【新/顶级产业背书】
  html = html.replace(/(【.*?】)/g, '<span class="highlight-tag">$1</span>')
  
  // Highlight ticker symbols like [天孚通信(300394) +6.56%]
  html = html.replace(/(\[.*?\])/g, '<span class="highlight-ticker">$1</span>')
  
  // Style paragraph concepts
  html = html.replace(/(概念：)/g, '<br><span class="section-title">$1</span>')
  html = html.replace(/(核心逻辑：)/g, '<span class="section-subtitle">$1</span>')
  html = html.replace(/(催化事件：)/g, '<span class="section-subtitle">$1</span>')
  html = html.replace(/(核心股票:)/g, '<span class="section-subtitle">$1</span>')
  html = html.replace(/(其他股票:)/g, '<span class="section-subtitle">$1</span>')
  
  // Style bullet points if they start with number or hyphen
  html = html.replace(/(<br>\d+、.*?)(?=<br>|$)/g, '<div class="bullet-item">$1</div>')
  html = html.replace(/(<br>-.*?)(?=<br>|$)/g, '<div class="bullet-item">$1</div>')
  
  return html
})
</script>

<style scoped>
.report-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-bottom: 24px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 10px;
}

.dashboard-header h1 {
  font-size: 1.8rem;
  font-weight: 700;
  margin: 0 0 4px 0;
  background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.95rem;
  margin: 0;
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 500;
}

.refresh-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--accent-color);
}

.refresh-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.error-banner {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
}

.layout-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0; /* Important for nested scrolling */
}

/* Top List */
.report-list-container {
  flex-shrink: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
  overflow: hidden;
  padding: 10px;
}



.report-list {
  flex: 1;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 10px;
  display: flex;
  flex-direction: row;
  gap: 12px;
}

.report-list::-webkit-scrollbar {
  height: 6px;
}

.report-list::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.report-item {
  flex-shrink: 0;
  width: 200px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.2s;
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
}

.report-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.2);
}

.report-item.active {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.4);
}

.report-item-title {
  font-weight: 500;
  color: #f1f5f9;
  margin-bottom: 4px;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.report-item-date {
  font-size: 0.7rem;
  color: #94a3b8;
  margin-bottom: 6px;
}

.report-item-concepts {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  overflow: hidden;
}

.concept-tag {
  flex-shrink: 0;
  font-size: 0.7rem;
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  color: #cbd5e1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 90px;
}

/* Detail Panel */
.report-detail-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}


/* Stock Pool Section */
.stock-pool-section {
  padding: 0 0 24px 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.stock-pool-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1rem;
  font-weight: 700;
  color: #10b981;
  margin-bottom: 16px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.pool-icon {
  width: 20px;
  height: 20px;
}

.stock-pool-groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stock-pool-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(255, 255, 255, 0.02);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.group-concept-name {
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
  border-left: 3px solid #3b82f6;
  padding-left: 10px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.new-badge {
  font-size: 0.7rem;
  background: linear-gradient(135deg, #ef4444, #f43f5e);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 800;
  letter-spacing: 0.5px;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.4);
}

.stock-pool-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.sub-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  width: 60px;
}

.stock-tag {
  display: flex;
  align-items: center;
  border-radius: 6px;
  padding: 6px 12px;
  text-decoration: none;
  transition: all 0.2s;
  cursor: pointer;
}

.core-tag {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
.core-tag:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
  transform: translateY(-1px);
}
.core-tag .stock-name {
  color: #fca5a5;
}

.other-tag {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}
.other-tag:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}
.other-tag .stock-name {
  color: var(--text-primary);
}

.stock-name {
  font-weight: 600;
  font-size: 0.9rem;
  margin-right: 6px;
}

.stock-code {
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-family: monospace;
}

/* Search highlight */
.stock-highlight {
  background: rgba(250, 204, 21, 0.15) !important;
  border-color: rgba(250, 204, 21, 0.5) !important;
  box-shadow: 0 0 8px rgba(250, 204, 21, 0.2);
}
.search-hint {
  color: #facc15;
  font-size: 0.85rem;
  font-weight: 400;
}

/* Frequency statistics (inline in header) */
.freq-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}
.freq-inline-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.freq-inline-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
}
.freq-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 600;
  font-family: monospace;
}
.freq-7 {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}
.freq-30 {
  background: rgba(250, 204, 21, 0.15);
  color: #facc15;
}
.freq-total {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.detail-content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.detail-content-scroll::-webkit-scrollbar {
  width: 8px;
}

.detail-content-scroll::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}

/* Formatted Text Typography */
.formatted-text {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--text-secondary);
  max-width: 900px;
}

.formatted-text :deep(br) {
  content: "";
  display: block;
  margin-bottom: 8px;
}

.formatted-text :deep(.highlight-tag) {
  color: #f59e0b;
  font-weight: 600;
  background: rgba(245, 158, 11, 0.1);
  padding: 0 4px;
  border-radius: 4px;
}

.formatted-text :deep(.highlight-ticker) {
  color: #3b82f6;
  font-weight: 600;
  cursor: pointer;
  background: rgba(59, 130, 246, 0.1);
  padding: 0 4px;
  border-radius: 4px;
}

.formatted-text :deep(.section-title) {
  display: block;
  font-size: 1.3rem;
  font-weight: 700;
  color: #fff;
  margin-top: 16px;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  padding-bottom: 8px;
}

.formatted-text :deep(.section-subtitle) {
  font-weight: 700;
  color: #e2e8f0;
}

.formatted-text :deep(.bullet-item) {
  padding-left: 20px;
  position: relative;
}

.empty-state {
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--text-secondary);
}
</style>
