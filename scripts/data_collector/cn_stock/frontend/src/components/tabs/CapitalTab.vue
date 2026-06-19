<template>
  <div class="layer-content grid-2-col">
    <div v-if="isLoading" class="glass-panel p-8 flex flex-col items-center justify-center h-[450px] col-span-full">
      <i class="fa-solid fa-circle-notch fa-spin text-4xl text-sky-400 mb-4"></i>
      <p class="text-gray-400">Loading capital data...</p>
    </div>

    <div v-else-if="errorMessage" class="glass-panel p-8 flex flex-col items-center justify-center h-[450px] border-red-500/30 col-span-full">
      <i class="fa-solid fa-triangle-exclamation text-4xl text-red-400 mb-4"></i>
      <p class="text-red-300">{{ errorMessage }}</p>
    </div>

    <template v-else>
      <div class="chart-panel glass-panel">
        <v-chart class="chart" :option="marginOption" autoresize />
      </div>
      <div class="chart-panel glass-panel">
        <v-chart class="chart" :option="fundFlowOption" autoresize />
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
  marginOption: Object,
  fundFlowOption: Object
})
</script>

<style scoped>
.layer-content { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.grid-2-col { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 500px), 1fr)); gap: 16px; }
.chart-panel { padding: 16px; height: 450px; position: relative; }
.chart { width: 100%; height: 100%; }
</style>
