<template>
  <div class="layer-content">
    <div v-if="isLoading" class="glass-panel p-8 flex flex-col items-center justify-center h-[300px]">
      <i class="fa-solid fa-circle-notch fa-spin text-4xl text-sky-400 mb-4"></i>
      <p class="text-gray-400">Loading signals data...</p>
    </div>

    <div v-else-if="errorMessage" class="glass-panel p-8 flex flex-col items-center justify-center h-[300px] border-red-500/30">
      <i class="fa-solid fa-triangle-exclamation text-4xl text-red-400 mb-4"></i>
      <p class="text-red-300">{{ errorMessage }}</p>
    </div>

    <template v-else>
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
    </template>
  </div>
</template>

<script setup>
defineProps({
  isLoading: {
    type: Boolean,
    default: false
  },
  errorMessage: {
    type: String,
    default: ''
  },
  thsReasons: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.layer-content { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.section-title { font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.p-6 { padding: 24px; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; }
.data-table td, .data-table th { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.data-table th { color: var(--text-secondary); font-size: 0.9rem; font-weight: 600; }
.data-table tr:hover td { background: rgba(255,255,255,0.02); }
.empty-state-small { padding: 20px; color: var(--text-secondary); text-align: center; font-style: italic; }
</style>
