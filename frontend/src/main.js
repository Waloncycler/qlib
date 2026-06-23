import { createApp } from 'vue'
import './styles/theme.css'
import App from './App.vue'
import router from './router'

import ECharts from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  BarChart,
  LineChart,
  CandlestickChart,
  PieChart,
  ScatterChart
} from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent
} from 'echarts/components'

// Register ECharts core components manually for smaller bundle size
use([
  CanvasRenderer,
  BarChart,
  LineChart,
  CandlestickChart,
  PieChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  VisualMapComponent
])

const app = createApp(App)

app.component('v-chart', ECharts)
app.use(router)
app.mount('#app')
