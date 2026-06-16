<template>
  <div class="layer-content grid-2-col">
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
    <div class="glass-panel p-6 flex flex-col h-[600px]">
      <h3 class="section-title text-amber-500 mb-4"><i class="fa-solid fa-bolt mr-2"></i> CLS Telegraph (财联社电报)</h3>
      <div class="overflow-y-auto custom-scrollbar flex-1 space-y-4 pr-2">
        <div v-for="(news, idx) in clsTelegraphs" :key="idx" class="news-card">
          <p class="news-time"><i class="fa-regular fa-clock mr-1"></i>{{ formatTime(news.date || news.time || news.ctime) }}</p>
          <p class="news-content">{{ news.summary || news.content }}</p>
        </div>
        <div v-if="!clsTelegraphs.length" class="empty-state-small">No recent telegraphs.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  symbol: String,
  clsTelegraphs: {
    type: Array,
    default: () => []
  },
  eastmoneyNews: {
    type: Array,
    default: () => []
  }
})

const formatTime = (t) => {
  if (!t) return ''
  if (typeof t === 'number' && t > 100000000000) {
    const d = new Date(t)
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  }
  return t
}
</script>

<style scoped>
.layer-content { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.grid-2-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr)); gap: 16px; }
.section-title { font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.p-6 { padding: 24px; }
.news-card { padding: 16px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; transition: border-color 0.2s; }
.news-card:hover { border-color: rgba(255,255,255,0.2); }
.news-time { font-size: 0.8rem; color: #38bdf8; font-family: monospace; margin-bottom: 8px; }
.news-title { font-size: 1rem; font-weight: 600; color: #f2f2f2; line-height: 1.4; }
.news-content { font-size: 0.95rem; color: #cbd5e1; line-height: 1.6; }
.empty-state-small { padding: 20px; color: var(--text-secondary); text-align: center; font-style: italic; }

.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>
