<template>
  <div class="layer-content grid-2-col">
    <div class="chart-panel glass-panel">
      <v-chart class="chart" :option="marginOption" autoresize />
    </div>
    <div class="chart-panel glass-panel">
      <v-chart class="chart" :option="fundFlowOption" autoresize />
    </div>
  </div>
</template>

<script setup>
defineProps({
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
