<template>
  <div class="dashboard">
    <header class="header">
      <div>
        <h1 class="title">AI Wencai</h1>
        <p class="subtitle">Natural Language Stock Screening</p>
      </div>
    </header>

    <!-- Search Section -->
    <div class="search-panel glass-panel">
      <div class="search-input-wrapper">
        <BotIcon class="search-icon" />
        <input 
          v-model="query" 
          type="text" 
          placeholder="Try: 今日涨停，所属概念包含算力，市盈率小于30" 
          @keyup.enter="search"
          :disabled="loading"
        />
        <button class="btn-search" @click="search" :disabled="loading || !query.trim()">
          <LoaderIcon v-if="loading" class="icon spin" />
          <SearchIcon v-else class="icon" />
          Search
        </button>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-panel glass-panel">
      <AlertTriangleIcon class="icon error-icon" />
      <p>{{ error }}</p>
    </div>

    <!-- Results Section -->
    <div class="results-container glass-panel" v-if="results.length > 0">
      <div class="table-header">
        <h3>{{ results.length }} Results Found</h3>
      </div>
      <div class="table-scroll custom-scrollbar">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in results" :key="idx">
              <td v-for="col in columns" :key="col">{{ formatCell(row[col]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Empty State -->
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
import { ref, computed } from 'vue'
import { BotIcon, SearchIcon, LoaderIcon, AlertTriangleIcon, DatabaseIcon } from 'lucide-vue-next'

const query = ref('')
const loading = ref(false)
const error = ref(null)
const results = ref([])
const searched = ref(false)

const columns = computed(() => {
  if (results.value.length === 0) return []
  return Object.keys(results.value[0])
})

const formatCell = (val) => {
  if (val === null || val === undefined || val === '') return '--'
  // Handle objects/arrays recursively or stringify
  if (typeof val === 'object') return JSON.stringify(val)
  // Format floats
  if (typeof val === 'number' && val % 1 !== 0) {
    // Basic heuristic to not overly format large IDs if any
    if (val > 1000000000) return val
    return val.toFixed(2)
  }
  return val
}

const search = async () => {
  if (!query.value.trim() || loading.value) return
  
  loading.value = true
  error.value = null
  searched.value = true
  results.value = []

  try {
    const res = await fetch('/api/iwencai/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query: query.value })
    })
    
    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`)
    }
    
    const data = await res.json()
    if (data.status === 'success') {
      results.value = data.data
    } else {
      throw new Error(data.message || 'Unknown error occurred')
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dashboard {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow: hidden;
}

.header { display: flex; justify-content: space-between; align-items: flex-start; flex-shrink: 0; }
.title { font-size: 1.8rem; margin-bottom: 4px; background: linear-gradient(to right, #fff, #9ba1a6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { color: var(--text-secondary); margin: 0; }

.search-panel {
  padding: 16px;
  border-radius: 12px;
  flex-shrink: 0;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 4px;
  gap: 12px;
}

.search-icon {
  margin-left: 12px;
  color: #38bdf8;
}

.search-input-wrapper input {
  flex: 1;
  background: transparent;
  border: none;
  color: #fff;
  font-size: 1rem;
  padding: 12px 0;
  outline: none;
}

.search-input-wrapper input::placeholder {
  color: rgba(255, 255, 255, 0.3);
}

.btn-search {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #38bdf8;
  color: #0f172a;
  border: none;
  padding: 10px 24px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 700;
  transition: all 0.2s;
  margin-right: 4px;
}

.btn-search:hover:not(:disabled) {
  background: #7dd3fc;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
}

.btn-search:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.icon.spin {
  animation: spin 1s linear infinite;
}

.results-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 12px;
}

.table-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.table-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: var(--text-primary);
}

.table-scroll {
  overflow: auto;
  flex: 1;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.85rem;
  white-space: nowrap;
}

.data-table th, .data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table th {
  position: sticky;
  top: 0;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(8px);
  color: var(--text-secondary);
  font-weight: 600;
  z-index: 10;
  border-bottom: 2px solid rgba(255,255,255,0.1);
}

.data-table tr:hover td {
  background: rgba(255, 255, 255, 0.03);
}

.empty-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.empty-content {
  text-align: center;
  color: var(--text-secondary);
}

.icon-large {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-content h3 {
  margin: 0 0 8px 0;
  color: var(--text-primary);
}

.empty-content p {
  margin: 0;
}

.custom-scrollbar::-webkit-scrollbar { width: 8px; height: 8px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }

@keyframes spin { 100% { transform: rotate(360deg); } }
</style>
