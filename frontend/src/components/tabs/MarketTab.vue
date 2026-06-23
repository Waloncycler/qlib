<template>
  <div class="layer-content">
    <div v-if="isLoading" class="glass-panel p-8 flex flex-col items-center justify-center h-[500px]">
      <i class="fa-solid fa-circle-notch fa-spin text-4xl text-sky-400 mb-4"></i>
      <p class="text-gray-400">Loading market data...</p>
    </div>

    <div v-else-if="errorMessage" class="glass-panel p-8 flex flex-col items-center justify-center h-[500px] border-red-500/30">
      <i class="fa-solid fa-triangle-exclamation text-4xl text-red-400 mb-4"></i>
      <p class="text-red-300">{{ errorMessage }}</p>
    </div>

    <template v-else>
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
          <div class="toggle-label ml-2" v-if="loadingIntraday">
            <i class="fa-solid fa-circle-notch fa-spin text-sky-400"></i> Loading Intraday...
          </div>
        </div>
        <v-chart class="chart" :option="klineOption" autoresize @click="onChartClick" />
      </div>

      <!-- Intraday Panel -->
      <div v-if="intradayOption && Object.keys(intradayOption).length" class="chart-panel glass-panel mt-4 relative">
        <button class="close-btn" @click="intradayOption = null"><i class="fa-solid fa-xmark"></i></button>
        <v-chart class="chart" :option="intradayOption" autoresize />
      </div>
      <div v-else-if="intradayOption && Object.keys(intradayOption).length === 0 && !loadingIntraday" class="glass-panel p-4 mt-4 text-center text-gray-400">
        No intraday data available for {{ intradayDate }}
        <button class="ml-4 text-rose-400 hover:text-rose-300" @click="intradayOption = null">Close</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { useChartFactory } from '../../composables/useChartFactory'

const props = defineProps({
  isLoading: {
    type: Boolean,
    default: false
  },
  errorMessage: {
    type: String,
    default: ''
  },
  dragonTiger: Object,
  lockupData: Object,
  klineOption: Object,
  chartToggles: Object,
  symbol: String
})

const emit = defineEmits(['update:chartToggles'])

const localChartToggles = ref({ ...props.chartToggles })

watch(() => props.chartToggles, (newVal) => {
  localChartToggles.value = { ...newVal }
}, { deep: true })

const emitUpdate = () => {
  emit('update:chartToggles', localChartToggles.value)
}

const { createIntradayOption } = useChartFactory()
const intradayOption = ref(null)
const intradayDate = ref('')
const loadingIntraday = ref(false)

const onChartClick = async (params) => {
  if (params.componentType === 'series' && params.seriesName === 'KLine') {
    const date = params.name // xAxis value
    if (date) {
      await fetchIntraday(date)
    }
  }
}

const fetchIntraday = async (date) => {
  if (!props.symbol) return
  intradayDate.value = date
  loadingIntraday.value = true
  intradayOption.value = null
  try {
    const res = await axios.get(`/api/stock/${props.symbol}/intraday/${date}`)
    if (res.data && res.data.status === 'success' && res.data.data.length > 0) {
      intradayOption.value = createIntradayOption(`Intraday Curve ${date}`, res.data.data)
    } else {
      intradayOption.value = {}
    }
  } catch (err) {
    console.error('Failed to fetch intraday', err)
    intradayOption.value = {}
  } finally {
    loadingIntraday.value = false
  }
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
.close-btn { position: absolute; top: 12px; right: 16px; background: transparent; border: none; color: #94a3b8; cursor: pointer; font-size: 1.2rem; z-index: 10; transition: color 0.2s; }
.close-btn:hover { color: #f87171; }

@media (max-width: 768px) {
  .chart-panel {
    height: 300px;
    padding: 12px;
  }
}
</style>
