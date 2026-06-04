<template>
  <div class="layer-content">
    <div class="glass-panel p-6">
      <h3 class="section-title text-purple-400"><i class="fa-solid fa-building mr-2"></i> Core Financial Ratios</h3>
      <div class="table-scroll mt-4" v-if="financeData.length > 0">
        <table class="data-table">
          <thead>
            <tr>
              <th>Report Date</th>
              <th>EPS (摊薄)</th>
              <th>ROE% (净资产收益率)</th>
              <th>Gross Margin% (毛利率)</th>
              <th>Net Profit (净利润)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(fin, idx) in financeData" :key="idx">
              <td class="font-mono text-sky-400">{{ fin.date || fin.report_date || fin.updated_date }}</td>
              <td>{{ fin.eps || (fin.jinglirun && fin.zongguben ? (fin.jinglirun / fin.zongguben).toFixed(2) : '--') }}</td>
              <td>{{ fin.roe ? parseFloat(fin.roe).toFixed(2) : (fin.jinglirun && fin.jingzichan ? (fin.jinglirun / fin.jingzichan * 100).toFixed(2) : '--') }}</td>
              <td>{{ fin.gross_margin ? parseFloat(fin.gross_margin).toFixed(2) : '--' }}</td>
              <td class="text-emerald-400 font-bold">{{ fin.net_profit ? Number(fin.net_profit).toLocaleString() : (fin.jinglirun ? Number(fin.jinglirun).toLocaleString() : '--') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state-small">No fundamental financial data found.</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  financeData: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.layer-content { display: flex; flex-direction: column; gap: 16px; flex: 1; }
.section-title { font-size: 1rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.p-6 { padding: 24px; }
.table-scroll { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; }
.data-table td, .data-table th { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.data-table th { color: var(--text-secondary); font-size: 0.9rem; font-weight: 600; }
.data-table tr:hover td { background: rgba(255,255,255,0.02); }
.empty-state-small { padding: 20px; color: var(--text-secondary); text-align: center; font-style: italic; }
</style>
