<template>
  <div class="layer-content">
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
        <label class="toggle-label" title="涨跌停">
          <input type="checkbox" v-model="localChartToggles.showLimit" @change="emitUpdate" /> 涨跌停
        </label>
        <label class="toggle-label" title="20日新高">
          <input type="checkbox" v-model="localChartToggles.showHigh20" @change="emitUpdate" /> 20日新高
        </label>
        <label class="toggle-label" title="异动预警">
          <input type="checkbox" v-model="localChartToggles.showAbnormal" @change="emitUpdate" /> 异动预警
        </label>
        <label class="toggle-label" title="异动预测线">
          <input type="checkbox" v-model="localChartToggles.showPrediction" @change="emitUpdate" /> 异动预测线
        </label>
      </div>
      <v-chart class="chart" :option="klineOption" autoresize />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  dragonTiger: Object,
  lockupData: Object,
  klineOption: Object,
  chartToggles: Object
})

const emit = defineEmits(['update:chartToggles'])

const localChartToggles = ref({ ...props.chartToggles })

watch(() => props.chartToggles, (newVal) => {
  localChartToggles.value = { ...newVal }
}, { deep: true })

const emitUpdate = () => {
  emit('update:chartToggles', localChartToggles.value)
}
</script>

<style scoped>
.layer-content { display: flex; flex-direction: column; gap: 16px; flex: 1; }
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

@media (max-width: 768px) {
  .chart-panel {
    height: 300px;
    padding: 12px;
  }
}
</style>
