<template>
  <div class="backtest-container">
    <div class="top-control-bar glass-panel">
      <div class="controls-left">
        <div class="control-item">
          <i class="fa-solid fa-calendar-days" style="color: #94a3b8;" title="Trading Day"></i>
          <select v-model="poolDate" class="mini-input" @change="fetchPool">
            <option v-for="d in validDates" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
        <div class="control-item window-control" style="display: flex; gap: 4px; padding: 2px 8px;">
          <div class="dual-range" style="gap: 4px;">
            <span class="range-hint" style="font-size: 0.7rem;">Pre</span>
            <input type="range" v-model="rangePre" min="0" max="5" step="1" class="mini-slider" style="width: 40px;" />
            <span class="range-val" style="font-size: 0.7rem; width: 8px;">{{ rangePre }}</span>
            <span class="range-hint" style="margin-left: 4px; font-size: 0.7rem;">Post</span>
            <input type="range" v-model="rangePost" min="0" max="5" step="1" class="mini-slider" style="width: 40px;" :disabled="isLatestDate" />
            <span class="range-val" style="font-size: 0.7rem; width: 8px;">{{ isLatestDate ? 0 : rangePost }}</span>
          </div>
        </div>
        <div class="control-item" style="display: flex; align-items: center; gap: 4px; cursor: pointer; margin-left: 8px; white-space: nowrap;" @click="showPool = !showPool">
          <span style="font-size: 0.75rem; font-weight: bold; transition: color 0.3s; white-space: nowrap; flex-shrink: 0;" :style="{ color: showPool ? '#38bdf8' : '#94a3b8' }">Show Pool</span>
          <div style="position: relative; display: inline-flex; height: 16px; width: 32px; border-radius: 9999px; align-items: center; padding: 0 2px; transition: all 0.3s;"
               :style="{ background: showPool ? '#0ea5e9' : '#334155', border: showPool ? 'none' : '1px solid #475569', boxShadow: showPool ? '0 0 8px rgba(14,165,233,0.5)' : 'none' }">
            <div style="height: 12px; width: 12px; border-radius: 9999px; background-color: white; transition: transform 0.3s;"
                 :style="{ transform: showPool ? 'translateX(16px)' : 'translateX(0)' }"></div>
          </div>
        </div>
      </div>

      <div class="controls-right" style="display: flex; align-items: center; gap: 8px;">
        <div v-if="enableMlFilter" class="control-item" style="display: flex; align-items: center; gap: 4px;">
          <span style="font-size: 0.75rem; color: #94a3b8; font-weight: bold;">TopK:</span>
          <input type="number" v-model="topK" @change="fetchResults" min="1" max="50" style="background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 4px; font-size: 0.75rem; padding: 2px; width: 35px; outline: none; text-align: center;" />
        </div>
        <div v-if="enableMlFilter" class="control-item">
          <select v-model="selectedModelVersion" @change="fetchResults" class="model-select" style="background: #1e293b; color: #38bdf8; border: 1px solid #0ea5e9; border-radius: 4px; font-size: 0.7rem; padding: 2px 4px; outline: none; cursor: pointer; max-width: 100px;">
            <option value="v3_open2close">V3</option>
          </select>
        </div>
        <div class="control-item" style="margin-right: 8px; display: flex; align-items: center; gap: 4px; cursor: pointer; white-space: nowrap;" @click="enableMlFilter = !enableMlFilter; fetchResults()">
          <span style="font-size: 0.75rem; font-weight: bold; transition: color 0.3s; white-space: nowrap; flex-shrink: 0;" :style="{ color: enableMlFilter ? '#38bdf8' : '#94a3b8' }">ML</span>
          <div style="position: relative; display: inline-flex; height: 14px; width: 28px; border-radius: 9999px; align-items: center; padding: 0 2px; transition: all 0.3s;"
               :style="{ background: enableMlFilter ? '#0ea5e9' : '#334155', border: enableMlFilter ? 'none' : '1px solid #475569', boxShadow: enableMlFilter ? '0 0 8px rgba(14,165,233,0.5)' : 'none' }">
            <div style="height: 10px; width: 10px; border-radius: 9999px; background-color: white; transition: transform 0.3s;"
                 :style="{ transform: enableMlFilter ? 'translateX(14px)' : 'translateX(0)' }"></div>
          </div>
        </div>
        <div v-if="enableMlFilter" class="control-item" style="margin-right: 8px; display: flex; align-items: center; gap: 4px; cursor: pointer; white-space: nowrap;" @click="enableMarketTiming = !enableMarketTiming; fetchResults()" title="大盘均线择时：跌破20日线时降仓">
          <span style="font-size: 0.75rem; font-weight: bold; transition: color 0.3s; white-space: nowrap; flex-shrink: 0;" :style="{ color: enableMarketTiming ? '#fbbf24' : '#94a3b8' }">择时</span>
          <div style="position: relative; display: inline-flex; height: 14px; width: 28px; border-radius: 9999px; align-items: center; padding: 0 2px; transition: all 0.3s;"
               :style="{ background: enableMarketTiming ? '#f59e0b' : '#334155', border: enableMarketTiming ? 'none' : '1px solid #475569', boxShadow: enableMarketTiming ? '0 0 8px rgba(245,158,11,0.5)' : 'none' }">
            <div style="height: 10px; width: 10px; border-radius: 9999px; background-color: white; transition: transform 0.3s;"
                 :style="{ transform: enableMarketTiming ? 'translateX(14px)' : 'translateX(0)' }"></div>
          </div>
        </div>
        <button class="mini-btn" @click="downloadData" :disabled="downloading" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 10px; font-size: 0.75rem; white-space: nowrap; font-weight: bold;" title="Download Data">
          <i class="fa-solid fa-download"></i>
          <span style="margin-left: 6px;">{{ downloading ? '...' : 'Data' }}</span>
        </button>
        <button class="mini-btn" @click="openLeaderboard" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); padding: 4px 10px; font-size: 0.75rem; white-space: nowrap; font-weight: bold;" title="Leaderboard">
          <i class="fa-solid fa-trophy"></i>
          <span style="margin-left: 6px;">Rank</span>
        </button>

        <button class="mini-btn" @click="runIntelligentBacktest" :disabled="loading" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 10px; font-size: 0.75rem; white-space: nowrap; font-weight: bold;" title="Run Backtest">
          <i class="fa-solid fa-play"></i>
          <span style="margin-left: 6px;">{{ loading ? '...' : 'Run' }}</span>
        </button>
      </div>
    </div>

    <transition name="slide">
      <div v-if="showPool" class="top-pool-section glass-panel">
        <div class="pool-content">
          <!-- AI Reports Row -->
          <div class="pool-row">
            <div class="row-label">AI</div>
            <div class="horizontal-scroll">
              <div v-for="(theme, idx) in poolData?.sources?.ai_reports" :key="'ai-'+idx" 
                   class="theme-chip" :class="{'active-chip': selectedTheme?.concept === theme.concept && isComparisonMode}"
                   @click="selectTheme(theme)">
                {{ theme.concept }}
                <span v-if="theme.is_new" class="new-dot"></span>
              </div>
            </div>
          </div>
          <!-- Market Topics Row -->
          <div class="pool-row">
            <div class="row-label">Topics</div>
            <div class="horizontal-scroll">
              <div v-for="(theme, idx) in poolData?.sources?.market_topics" :key="'top-'+idx" 
                   class="theme-chip" :class="{'active-chip': selectedTheme?.concept === theme.concept && isComparisonMode}"
                   @click="selectTheme(theme)">
                {{ theme.concept }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>

    <div class="content-wrapper" v-show="!loading">
      
      <!-- Chart Area (Full Width) -->
      <div class="chart-container glass-panel" style="position: relative; flex: 1;">
        <div v-if="comparisonLoading" class="comparison-overlay">
          <div class="spinner"></div>
          <p>Comparing {{ selectedTheme?.concept }}...</p>
        </div>
        <button v-if="isComparisonMode" @click="isComparisonMode = false" class="close-comparison-btn">
          ✕ Return to Backtest
        </button>
        <button v-if="compareCurves && compareCurves.length > 0" @click="compareCurves = null" class="close-comparison-btn" style="background: rgba(34,197,94,0.2); color: #4ade80; border-color: rgba(34,197,94,0.3);">
          ✕ Exit Compare
        </button>
        <div v-if="compareCurves && compareCurves.length > 0" class="compare-strategy-tabs">
          <button v-for="(c, i) in compareCurves" :key="i" @click="selectCompareStrategy(i)"
            class="compare-tab" :class="{ active: compareSelectedIndex === i }"
            :style="{ borderColor: compareSelectedIndex === i ? c.color : 'transparent' }">
            <span class="dot" :style="{ background: c.color }"></span>
            {{ c.label }}
          </button>
        </div>
        <v-chart ref="chartRef" class="chart" :option="chartOption" :update-options="{ notMerge: true }" autoresize @click="onChartClick" />
      </div>

      <!-- Analysis Side Panel -->
      <div class="side-panel-right" v-if="!isComparisonMode">
        <div class="glass-panel p-4 info-card" style="height: 100%; display: flex; flex-direction: column; overflow-y: auto;">
          <h4 class="text-sky-400 font-bold">Signal Backtest Metrics</h4>
          
          <div class="metrics-row mb-3" v-if="metrics && metrics.total_return !== undefined">
            <div class="mini-metric">
              <span class="l">Total Return</span>
              <span class="v" :class="metrics.total_return >= 0 ? 'text-emerald-400' : 'text-red-400'">{{ (metrics.total_return * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Ann. Return</span>
              <span class="v" :class="metrics.annualized_return >= 0 ? 'text-emerald-400' : 'text-red-400'">{{ (metrics.annualized_return * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Max Drawdown</span>
              <span class="v text-red-400">{{ (metrics.max_drawdown * 100).toFixed(2) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">Sharpe</span>
              <span class="v text-blue-400">{{ metrics.sharpe_ratio?.toFixed(3) || 'N/A' }}</span>
            </div>
            <div class="mini-metric">
              <span class="l">Hit Rate</span>
              <span class="v text-amber-400">{{ ((metrics.hit_rate || 0) * 100).toFixed(1) }}%</span>
            </div>
            <div class="mini-metric">
              <span class="l">P/L Ratio</span>
              <span class="v text-purple-400">{{ metrics.profit_loss_ratio?.toFixed(2) || 'N/A' }}</span>
            </div>
            <div class="mini-metric" style="grid-column: span 2;">
              <span class="l">Benchmark Return</span>
              <span class="v text-gray-400">{{ ((metrics.benchmark_total_return || 0) * 100).toFixed(2) }}%</span>
            </div>
          </div>
          <div v-else-if="metrics && metrics.annualized_return !== undefined" class="metrics-row mb-3">
            <div class="mini-metric"><span class="l">Ann. Return</span><span class="v text-emerald-400">{{ (metrics.annualized_return * 100).toFixed(2) }}%</span></div>
            <div class="mini-metric"><span class="l">Max Drawdown</span><span class="v text-red-400">{{ (metrics.max_drawdown * 100).toFixed(2) }}%</span></div>
          </div>
          <div v-else class="text-sm text-gray-400 text-center py-4">Run backtest to see metrics</div>

          <!-- Concept Attribution -->
          <h4 class="text-sky-400 font-bold mt-3 mb-2" style="cursor: pointer; display: flex; align-items: center; justify-content: space-between;" @click="showTopConcepts = !showTopConcepts">
            <div>Top Concepts</div>
            <i class="fa-solid" :class="showTopConcepts ? 'fa-chevron-down' : 'fa-chevron-right'" style="font-size: 0.75rem; color: #64748b;"></i>
          </h4>
          <div class="signals-scroll" v-show="showTopConcepts">
            <div v-if="conceptAttribution && conceptAttribution.length > 0">
              <div v-for="(c, idx) in conceptAttribution.slice(0, 15)" :key="idx" 
                   class="mb-2 p-2 rounded border" 
                   :style="{ background: c.total_return > 0 ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)', border: '1px solid ' + (c.total_return > 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)') }">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
                  <span style="color: #e2e8f0; font-size: 0.75rem; font-weight: 500; display: inline-block; flex: 1; padding-right: 8px; line-height: 1.2;" :title="c.concept">
                    {{ c.concept }}
                  </span>
                  <span style="font-family: monospace; font-size: 0.75rem; font-weight: bold; white-space: nowrap;" :style="{ color: c.total_return > 0 ? '#34d399' : '#f87171' }">
                    {{ c.total_return > 0 ? '+' : '' }}{{ (c.total_return * 100).toFixed(1) }}%
                  </span>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.65rem;">
                  <span style="color: #64748b;">{{ c.days_active }}d Active</span>
                  <span style="color: #7dd3fc;">Hit {{ (c.hit_rate * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 text-center py-2">No concept data</div>
          </div>

          <!-- Today's ML Top Picks (Chip Style, matching Daily Trades) -->
          <div v-if="todaysPicks" class="mb-2 p-2 bg-slate-800/50 rounded border border-slate-700/50">
            <div class="text-xs text-gray-400 font-bold mb-1" style="display: flex; justify-content: space-between; align-items: center;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span>Today's Top Picks · {{ todaysPicks.date }}</span>
                <button 
                  @click="() => { useCompositePicks = !useCompositePicks; fetchTodaysPicks(); }"
                  class="transition-colors"
                  style="background: transparent; border: none; padding: 0; outline: none; cursor: pointer; font-size: 0.8rem;"
                  :style="{ color: useCompositePicks ? '#38bdf8' : '#64748b' }"
                  :title="useCompositePicks ? '复合打分模式已开启 (包含人气与LLM过滤)' : '纯净模式已开启 (原始模型得分)'"
                >
                  <i class="fa-solid fa-wand-magic-sparkles"></i>
                </button>
              </div>
              <button 
                @click="runPremarketSelection"
                :disabled="isRefreshingPicks"
                class="transition-colors ml-2"
                style="background: transparent; border: none; padding: 0; outline: none; cursor: pointer; font-size: 1rem; color: #34d399;"
                title="手动拉取最新早盘研报并生成金股"
              >
                <i class="fa-solid" :class="isRefreshingPicks ? 'fa-spinner fa-spin' : 'fa-rotate'"></i>
              </button>
            </div>
            <div class="flex flex-wrap gap-1">
              <span v-for="(pick, idx) in todaysPicks.top_picks" :key="idx" class="stock-tag" 
                    style="padding: 1px 5px; font-size: 0.65rem; border: 1px solid rgba(59,130,246,0.3);"
                    :style="{ background: pick.score > 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.1)', color: pick.score > 0 ? '#34d399' : '#f87171' }">
                {{ pick.name }}
                <span class="text-sky-400/60 ml-1" style="font-size: 0.55rem;">{{ pick.theme ? pick.theme.split('/')[0] : '' }}</span>
                <span v-if="liveQuotes[pick.symbol]" class="ml-1 font-mono font-bold animate-pulse" :class="liveQuotes[pick.symbol].pct_change >= 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ liveQuotes[pick.symbol].pct_change >= 0 ? '+' : '' }}{{ liveQuotes[pick.symbol].pct_change.toFixed(2) }}%
                </span>
                <span v-else class="ml-1 font-mono" :class="pick.score > 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ pick.score > 0 ? '+' : '' }}{{ pick.score }}
                </span>
              </span>
            </div>
          </div>

          <!-- Daily Holdings -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; margin-bottom: 8px; width: 100%;">
            <div style="color: #38bdf8; font-weight: bold; font-size: 1rem; text-transform: uppercase;">
              Daily Trades
            </div>
            <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 12px; height: 12px; margin-left: 8px;" :title="isMarketOpenRef ? (isLiveSyncing ? 'Syncing...' : 'Market Open - Auto Sync Active') : 'Market Closed'">
              <template v-if="isMarketOpenRef">
                <span class="animate-ping" style="position: absolute; display: inline-flex; height: 10px; width: 10px; border-radius: 9999px; background-color: #34d399; opacity: 0.75;"></span>
                <span style="position: relative; display: inline-flex; border-radius: 9999px; height: 8px; width: 8px; background-color: #10b981;"></span>
              </template>
              <template v-else>
                <span style="position: relative; display: inline-flex; border-radius: 9999px; height: 8px; width: 8px; background-color: #ef4444;"></span>
              </template>
            </div>
          </div>
          <div class="signals-scroll">
            <div v-if="holdings && holdings.length > 0">
              <div v-for="(h, idx) in reversedHoldings" :key="idx" 
                   :id="'trade-card-' + h.date"
                   class="mb-2 p-2 rounded border transition-all duration-500"
                   :class="activeDate === h.date ? 'bg-sky-900/40 border-sky-400/80 shadow-[0_0_15px_rgba(56,189,248,0.2)] ring-1 ring-sky-400 scale-[1.02]' : 'bg-slate-800/50 border-slate-700/50'">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: nowrap; white-space: nowrap; width: 100%; margin-bottom: 4px; font-size: 0.75rem; font-weight: bold; transition: color 0.5s;" :class="activeDate === h.date ? 'text-sky-300' : 'text-gray-400'">
                  <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    {{ h.date }} <span style="color: #4b5563;">· {{ (h.entries?.length || 0) + (h.holds?.length || 0) }} held</span>
                  </div>
                  <span style="white-space: nowrap; flex-shrink: 0; margin-left: 8px;" :class="getLiveDailyReturn(h) > 0 ? 'text-emerald-400' : (getLiveDailyReturn(h) < 0 ? 'text-red-400' : 'text-slate-500')">
                    <span v-if="holdings && holdings.length > 0 && h.date === holdings[holdings.length-1].date && Object.keys(liveQuotes).length > 0" style="font-size: 0.6rem; color: #38bdf8; margin-right: 4px; font-weight: normal;" class="animate-pulse">LIVE</span>
                    {{ getLiveDailyReturn(h) > 0 ? '+' : '' }}{{ (getLiveDailyReturn(h) * 100).toFixed(2) }}%
                  </span>
                </div>
                
                <!-- Entries -->
                <div v-if="h.entries && h.entries.length" class="flex flex-wrap gap-1 mb-1">
                  <span v-for="sym in h.entries" :key="'e'+sym" class="stock-tag" style="padding: 1px 5px; font-size: 0.65rem; background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.3);">
                    ▲ {{ getName(h.holdings, sym) || sym }} 
                    <span v-if="getWeight(h.holdings, sym) > 0" class="text-sky-300 ml-1">({{ (getWeight(h.holdings, sym) * 100).toFixed(1) }}%)</span>
                    <span v-if="liveQuotes[sym] && getLivePnL(sym, 'entry', h.date) !== null" class="ml-1 font-mono font-bold animate-pulse" :class="getLivePnL(sym, 'entry', h.date) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                      PnL: {{ getLivePnL(sym, 'entry', h.date) >= 0 ? '+' : '' }}{{ getLivePnL(sym, 'entry', h.date).toFixed(2) }}%
                    </span>
                    <span v-else-if="getReturn(h.holdings, sym) !== undefined && getReturn(h.holdings, sym) !== null" class="ml-1" :class="getReturn(h.holdings, sym) > 0 ? 'text-emerald-400' : (getReturn(h.holdings, sym) < 0 ? 'text-red-400' : 'text-gray-500')">
                      {{ getReturn(h.holdings, sym) > 0 ? '+' : '' }}{{ (getReturn(h.holdings, sym) * 100).toFixed(2) }}%
                    </span>
                  </span>
                </div>
                
                <!-- Holds -->
                <div v-if="h.holds && h.holds.length" class="flex flex-wrap gap-1 mb-1">
                  <span v-for="sym in h.holds" :key="'h'+sym" class="stock-tag" style="padding: 1px 5px; font-size: 0.65rem; background: rgba(100,116,139,0.2); color: #94a3b8; border: 1px solid rgba(100,116,139,0.3);">
                    ● {{ getName(h.holdings, sym) || sym }} 
                    <span v-if="getWeight(h.holdings, sym) > 0" class="text-sky-300/70 ml-1">({{ (getWeight(h.holdings, sym) * 100).toFixed(1) }}%)</span>
                    <span v-if="liveQuotes[sym] && getLivePnL(sym, 'hold', h.date) !== null" class="ml-1 font-mono font-bold animate-pulse" :class="getLivePnL(sym, 'hold', h.date) >= 0 ? 'text-emerald-400' : 'text-red-400'">
                      PnL: {{ getLivePnL(sym, 'hold', h.date) >= 0 ? '+' : '' }}{{ getLivePnL(sym, 'hold', h.date).toFixed(2) }}%
                    </span>
                    <span v-else-if="getReturn(h.holdings, sym) !== undefined && getReturn(h.holdings, sym) !== null" class="ml-1" :class="getReturn(h.holdings, sym) > 0 ? 'text-emerald-400' : (getReturn(h.holdings, sym) < 0 ? 'text-red-400' : 'text-gray-500')">
                      {{ getReturn(h.holdings, sym) > 0 ? '+' : '' }}{{ (getReturn(h.holdings, sym) * 100).toFixed(2) }}%
                    </span>
                  </span>
                </div>

                <!-- Exits -->
                <div v-if="h.exits && h.exits.length" class="flex flex-wrap gap-1 mb-1">
                  <span v-for="sym in h.exits" :key="'x'+sym" class="stock-tag" style="padding: 1px 5px; font-size: 0.65rem; background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3);">
                    ▼ {{ getName(h.holdings, sym) || sym }}
                    <span v-if="getReturn(h.holdings, sym) !== undefined && getReturn(h.holdings, sym) !== null" class="ml-1 font-bold" :class="getReturn(h.holdings, sym) > 0 ? 'text-emerald-400' : (getReturn(h.holdings, sym) < 0 ? 'text-red-400' : 'text-gray-500')">
                      Settled: {{ getReturn(h.holdings, sym) > 0 ? '+' : '' }}{{ (getReturn(h.holdings, sym) * 100).toFixed(2) }}%
                    </span>
                  </span>
                </div>
                
                <!-- Detailed Trades (交割单) -->
                <div v-if="h.trades && h.trades.length" class="mt-2 text-[0.7rem] border-t border-slate-700/50 pt-1">
                  <div class="text-gray-500 mb-1" style="cursor: pointer; display: flex; align-items: center; justify-content: space-between;" @click="expandedTrades[h.date] = !expandedTrades[h.date]">
                    <span>Transaction Details (交割单)</span>
                    <i class="fa-solid" :class="expandedTrades[h.date] ? 'fa-chevron-down' : 'fa-chevron-right'" style="font-size: 0.75rem; color: #64748b;"></i>
                  </div>
                  <table v-show="expandedTrades[h.date]" class="w-full text-left border-collapse" style="color: #9ca3af;">
                    <thead>
                      <tr>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Symbol</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Action</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Price</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Shares</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Amount</th>
                        <th class="font-normal pb-1 border-b border-slate-700/50">Fee</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(t, i) in h.trades" :key="'t'+i" class="border-b border-slate-800/50 hover:bg-slate-800">
                        <td class="py-1">{{ t.symbol }}</td>
                        <td class="py-1">
                          <span :class="t.action === 'buy' ? 'text-emerald-400' : 'text-red-400'">{{ t.action.toUpperCase() }}</span>
                          <span class="text-[0.6rem] text-gray-600 ml-1">({{ t.reason }})</span>
                        </td>
                        <td class="py-1">{{ t.price }}</td>
                        <td class="py-1">{{ t.shares }}</td>
                        <td class="py-1">{{ t.amount }}</td>
                        <td class="py-1">{{ t.fee }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                
                <!-- If neither entries nor exits nor trades, just show held count -->
                <div v-if="(!h.entries || !h.entries.length) && (!h.exits || !h.exits.length) && (!h.trades || !h.trades.length) && h.holdings && h.holdings.length" class="text-xs text-gray-500 mt-1">
                  No trades. Holding {{ h.holdings.length }} symbols.
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 text-center py-4">No holdings data</div>
          </div>
        </div>
      </div>


    </div>

    <!-- Global Loading State -->
    <div v-if="loading" class="global-loading-panel">
      <div class="spinner"></div>
      <p>{{ loadingMsg }}</p>
    </div>

    <!-- Error State -->
    <div v-if="error" class="error-panel">
      <p>{{ error }}</p>
    </div>
    
    <!-- Leaderboard Modal -->
    <div v-if="showLeaderboard" class="modal-overlay" @click.self="showLeaderboard = false">
      <div class="leaderboard-modal glass-panel">
        <div class="modal-header">
          <h3><i class="fa-solid fa-trophy" style="color: #facc15; margin-right: 8px;"></i> Strategy Leaderboard</h3>
          <button class="close-btn" @click="showLeaderboard = false"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="modal-body">
          <div v-if="leaderboardLoading" class="loading-state">
            <div class="spinner"></div>
            <span>Loading leaderboard...</span>
          </div>
          <table v-else class="leaderboard-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th @click="handleSort('label')" class="sortable">Label <i v-if="sortKey === 'label'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th @click="handleSort('model')" class="sortable">Model <i v-if="sortKey === 'model'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th @click="handleSort('K')" class="sortable">K <i v-if="sortKey === 'K'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th>Filters</th>
                <th @click="handleSort('annual')" class="sortable">Annual Return <i v-if="sortKey === 'annual'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th @click="handleSort('drawdown')" class="sortable">Max Drawdown <i v-if="sortKey === 'drawdown'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th @click="handleSort('sharpe')" class="sortable">Sharpe <i v-if="sortKey === 'sharpe'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
                <th @click="handleSort('win_rate')" class="sortable">Win Rate <i v-if="sortKey === 'win_rate'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i><i v-else class="fa-solid fa-sort sort-icon-dim"></i></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in sortedLeaderboardData" :key="item.id" :class="{'top-3': index < 3, 'clickable-row': true}" @click="loadStrategy(item)">
                <td>
                  <span v-if="index === 0" style="color: #facc15;">1</span>
                  <span v-else-if="index === 1" style="color: #94a3b8;">2</span>
                  <span v-else-if="index === 2" style="color: #b45309;">3</span>
                  <span v-else>{{ index + 1 }}</span>
                </td>
                <td style="font-weight: 600; color: #e0f2fe;">{{ item.label }}</td>
                <td style="color: #cbd5e1;">{{ item.model }}</td>
                <td style="color: #38bdf8;">{{ item.K }}</td>
                <td style="font-size: 0.75rem;">
                  <span v-if="item.vol" class="badge badge-vol">量能</span>
                  <span v-if="item.timing" class="badge badge-timing">择时</span>
                  <span v-if="item.crash" class="badge badge-crash">防暴跌</span>
                  <span v-if="item.boost" class="badge badge-boost">连板</span>
                  <span v-if="!item.vol && !item.timing && !item.crash && !item.boost" style="color: #475569;">无</span>
                </td>
                <td :style="{color: parseFloat(item.annual) > 0 ? '#34d399' : '#f87171', fontWeight: 'bold'}">{{ item.annual }}%</td>
                <td style="color: #f87171;">{{ item.drawdown }}%</td>
                <td style="color: #a78bfa;">{{ item.sharpe }}</td>
                <td style="color: #60a5fa;">{{ item.win_rate }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Compare Strategies Modal -->
    <div v-if="showCompareModal" class="modal-overlay" @click.self="showCompareModal = false">
      <div class="leaderboard-modal glass-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h3 style="color: #4ade80; font-weight: bold;">Compare Strategies</h3>
          <button @click="showCompareModal = false" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 1.2rem;">✕</button>
        </div>
        <p style="color: #94a3b8; font-size: 0.8rem; margin-bottom: 12px;">Select strategies to overlay on the chart (including current).</p>
        <div style="max-height: 400px; overflow-y: auto;">
          <table class="leaderboard-table" style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="border-bottom: 1px solid #334155;">
                <th style="padding: 8px; text-align: left; color: #94a3b8; font-size: 0.75rem;"></th>
                <th @click="handleSort('label')" class="sortable" style="padding: 8px; text-align: left; color: #94a3b8; font-size: 0.75rem;">Label <i v-if="sortKey === 'label'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
                <th @click="handleSort('model')" class="sortable" style="padding: 8px; text-align: left; color: #94a3b8; font-size: 0.75rem;">Model <i v-if="sortKey === 'model'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
                <th @click="handleSort('K')" class="sortable" style="padding: 8px; text-align: left; color: #94a3b8; font-size: 0.75rem;">K <i v-if="sortKey === 'K'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
                <th style="padding: 8px; text-align: left; color: #94a3b8; font-size: 0.75rem;">Filters</th>
                <th @click="handleSort('annual')" class="sortable" style="padding: 8px; text-align: right; color: #94a3b8; font-size: 0.75rem;">Annual <i v-if="sortKey === 'annual'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
                <th @click="handleSort('drawdown')" class="sortable" style="padding: 8px; text-align: right; color: #94a3b8; font-size: 0.75rem;">Drawdown <i v-if="sortKey === 'drawdown'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
                <th @click="handleSort('sharpe')" class="sortable" style="padding: 8px; text-align: right; color: #94a3b8; font-size: 0.75rem;">Sharpe <i v-if="sortKey === 'sharpe'" :class="['fa-solid', sortOrder === 'asc' ? 'fa-sort-up' : 'fa-sort-down']"></i></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in sortedLeaderboardData" :key="item.id" style="border-bottom: 1px solid rgba(51,65,85,0.5); cursor: pointer;" @click="toggleCompareItem(item)">
                <td style="padding: 8px;">
                  <input type="checkbox" :checked="isCompareSelected(item)" @click.stop="toggleCompareItem(item)" style="accent-color: #22c55e; cursor: pointer;" />
                </td>
                <td style="padding: 8px; color: #e0f2fe; font-weight: 600;">{{ item.label }}</td>
                <td style="padding: 8px; color: #cbd5e1;">{{ item.model }}</td>
                <td style="padding: 8px; color: #38bdf8;">{{ item.K }}</td>
                <td style="padding: 8px; font-size: 0.75rem;">
                  <span v-if="item.vol" class="badge badge-vol">量能</span>
                  <span v-if="item.timing" class="badge badge-timing">择时</span>
                  <span v-if="item.crash" class="badge badge-crash">防暴跌</span>
                  <span v-if="item.boost" class="badge badge-boost">连板</span>
                  <span v-if="!item.vol && !item.timing && !item.crash && !item.boost" style="color: #475569;">无</span>
                </td>
                <td style="padding: 8px; text-align: right; color: #34d399; font-weight: bold;">{{ item.annual }}%</td>
                <td style="padding: 8px; text-align: right; color: #f87171;">{{ item.drawdown }}%</td>
                <td style="padding: 8px; text-align: right; color: #a78bfa;">{{ item.sharpe }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div style="margin-top: 12px; display: flex; justify-content: flex-end; gap: 8px;">
          <button @click="showCompareModal = false" style="background: rgba(100,116,139,0.2); color: #94a3b8; border: 1px solid #475569; padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.8rem;">Cancel</button>
          <button @click="executeCompare" :disabled="compareSelected.length === 0" style="background: rgba(34,197,94,0.2); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: bold;" :style="{ opacity: compareSelected.length === 0 ? 0.5 : 1 }">Compare ({{ compareSelected.length }})</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
import VChart, { THEME_KEY } from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  AxisPointerComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  AxisPointerComponent
])

const loading = ref(false)
const enableMlFilter = ref(true)
const selectedModelVersion = ref('v3_binary')
const topK = ref(10)
const enableMarketTiming = ref(true)
const enableTurnoverFilter = ref(true)
const enableCrashFilter = ref(false)
const enableSelectionBoost = ref(false)
const showLeaderboard = ref(false)
const showCompareModal = ref(false)
const compareSelected = ref([])
const compareCurves = ref(null) // [{label, curve, color}]
const compareSelectedIndex = ref(-1)
const chartRef = ref(null)
const leaderboardLoading = ref(false)
const leaderboardData = ref([])

const sortKey = ref('sharpe')
const sortOrder = ref('desc')

const sortedLeaderboardData = computed(() => {
  const data = [...leaderboardData.value]
  if (!sortKey.value) return data

  data.sort((a, b) => {
    let valA = a[sortKey.value]
    let valB = b[sortKey.value]

    // Handle percentage strings
    if (typeof valA === 'string' && valA.endsWith('%')) valA = parseFloat(valA.replace('%', ''))
    if (typeof valB === 'string' && valB.endsWith('%')) valB = parseFloat(valB.replace('%', ''))
    
    // Handle falsy or missing values gracefully
    if (valA === undefined || valA === null) valA = 0
    if (valB === undefined || valB === null) valB = 0

    if (valA < valB) return sortOrder.value === 'asc' ? -1 : 1
    if (valA > valB) return sortOrder.value === 'asc' ? 1 : -1
    return 0
  })
  
  return data
})

const handleSort = (key) => {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'desc'
  }
}
const showTopConcepts = ref(false)
const expandedTrades = ref({})
const todaysPicks = ref(null)
const loadingMsg = ref('Loading...')
const downloading = ref(false)
const error = ref(null)
const metrics = ref(null)
const curveData = ref(null)
const holdings = ref([])
const conceptAttribution = ref([])
const reversedHoldings = computed(() => {
  return [...holdings.value].reverse()
})

// Pool State
const poolDate = ref('')
const validDates = ref([])
const poolData = ref(null)
const poolLoading = ref(false)
const openSource = ref('ai')

// Comparison Mode State
const selectedTheme = ref(null)
const themeStocksData = ref({}) // symbol -> { name, data }
const isComparisonMode = ref(false)
const comparisonLoading = ref(false)
const showPool = ref(true)
const rangePre = ref(1)
const rangePost = ref(1)
const isLatestDate = ref(false)

const selectTheme = async (theme) => {
  selectedTheme.value = theme
  isComparisonMode.value = true
  comparisonLoading.value = true
  themeStocksData.value = {}
  
  const stocks = [
    ...(theme.core_stocks || []),
    ...(theme.other_stocks || [])
  ].slice(0, 15) // Limit to 15 stocks to avoid overcrowding
  
  const date = poolDate.value
  const pre = parseInt(rangePre.value) || 0
  const post = isLatestDate.value ? 0 : (parseInt(rangePost.value) || 0)

  let targetDates = [date]
  if (pre > 0 || post > 0) {
    try {
      const res = await axios.get(`/api/market/trading_days?date=${date}&pre_n=${pre}&post_n=${post}`)
      if (res.data.status === 'success') {
        targetDates = res.data.data
        isLatestDate.value = res.data.is_latest
      }
    } catch (e) {
      console.warn("Failed to fetch trading days", e)
    }
  }

  // Define standard 5-minute intervals for a trading day (uniform width)
  const generateDayGrid = (d) => {
    const grid = []
    // Morning: 09:35 to 11:30
    for (let h = 9; h <= 11; h++) {
      for (let m = 0; m < 60; m += 5) {
        if (h === 9 && m <= 30) continue
        if (h === 11 && m > 30) continue
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
        grid.push(`${d} ${timeStr}`)
      }
    }
    // Afternoon: 13:05 to 15:00
    for (let h = 13; h <= 15; h++) {
      for (let m = 0; m < 60; m += 5) {
        if (h === 13 && m === 0) continue
        if (h === 15 && m > 0) continue
        const timeStr = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}`
        grid.push(`${d} ${timeStr}`)
      }
    }
    return grid
  }

  const allTargetTimes = []
  targetDates.forEach(d => {
    allTargetTimes.push(...generateDayGrid(d))
  })

  const promises = stocks.map(async (s) => {
    let symbol = s.symbol
    if (!symbol && s.name) {
      try {
        const res = await axios.get(`/api/resolve_symbol/${s.name}`)
        symbol = res.data.symbol
      } catch (e) {
        console.warn(`Failed to resolve symbol for ${s.name}`)
      }
    }
    
    if (symbol) {
      try {
        const stockAllData = []
        for (const d of targetDates) {
          const res = await axios.get(`/api/stock/${symbol}/intraday/${d}`)
          if (res.data.status === 'success' && res.data.data) {
            // Filter and downsample/map to 5-min if needed
            // But for now, we just collect and we will map to the grid in getComparisonOption
            const formatted = res.data.data
              .filter(item => item.time <= '15:00')
              .map(item => ({
                ...item,
                time: `${d} ${item.time}`
              }))
            stockAllData.push(...formatted)
          }
        }
        
        if (stockAllData.length > 0) {
          themeStocksData.value[symbol] = {
            name: s.name,
            data: stockAllData,
            grid: allTargetTimes // Attach the grid to keep it consistent
          }
        }
      } catch (err) {
        console.error(`Failed to fetch data for ${symbol}`, err)
      }
    }
  })
  
  await Promise.all(promises)
  comparisonLoading.value = false
}

const activeDate = ref(null)
const hoveredDate = ref(null)

const onChartClick = (params) => {
  // 对比模式下：点击曲线选中对应策略
  if (compareCurves.value && compareCurves.value.length > 0) {
    console.log('[Compare] chart click:', params)
    if (params && params.seriesIndex !== undefined) {
      selectCompareStrategy(params.seriesIndex)
    }
    return
  }

  if (params && params.name) {
    const date = params.name
    activeDate.value = date

    // Clear the active highlight after 2.5 seconds
    setTimeout(() => {
      if (activeDate.value === date) {
        activeDate.value = null
      }
    }, 2500)

    // Scroll to the card
    setTimeout(() => {
      const el = document.getElementById('trade-card-' + date)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }, 50)
  }
}

const toggleSource = (src) => {
  if (openSource.value === src) {
    openSource.value = null
  } else {
    openSource.value = src
  }
}

const goToStock = (symbol) => {
  if (symbol) {
    router.push(`/stock/${symbol}`)
  }
}

const isST = (name) => {
  return name && (name.toUpperCase().includes('ST'))
}

const fetchValidDates = async () => {
  try {
    const res = await axios.get('/api/backtest/pool/dates')
    if (res.data.dates) {
      validDates.value = res.data.dates
      if (validDates.value.length > 0 && !poolDate.value) {
        poolDate.value = validDates.value[0]
        fetchPool()
      }
    }
  } catch (err) {
    if (err.response && err.response.status === 502) {
      // Suppress 502 during hot-reload
    } else {
      console.error("Failed to fetch valid dates:", err)
    }
  }
}

const fetchPool = async () => {
  if (!poolDate.value) return
  poolLoading.value = true
  try {
    const res = await axios.get(`/api/backtest/pool?date=${poolDate.value}`)
    poolData.value = res.data
  } catch (err) {
    console.error("Failed to fetch pool data:", err)
  } finally {
    poolLoading.value = false
  }
}

const form = ref({
  symbol: 'SH600519',
  startDate: '2024-01-01',
  endDate: '2024-12-31'
})

const isLiveSyncing = ref(false)
const liveQuotes = ref({})

const syncLiveQuotes = async () => {
  if (isLiveSyncing.value) return
  isLiveSyncing.value = true
  
  try {
    const symbols = new Set()
    
    // 1. Add Today's Top Picks
    if (todaysPicks.value && todaysPicks.value.top_picks) {
      todaysPicks.value.top_picks.forEach(p => symbols.add(p.symbol))
    }
    
    // 2. Add currently selected Daily Trades (if available)
    const activeDateStr = activeDate.value
    if (activeDateStr && holdings.value) {
      const activeH = holdings.value.find(h => h.date === activeDateStr)
      if (activeH) {
        if (activeH.entries) activeH.entries.forEach(s => symbols.add(s))
        if (activeH.holds) activeH.holds.forEach(s => symbols.add(s))
        if (activeH.exits) activeH.exits.forEach(s => symbols.add(s))
      }
    }
    
    const symArr = Array.from(symbols)
    if (symArr.length === 0) return
    
    const res = await axios.post('/api/backtest/live-quotes', { symbols: symArr })
    if (res.data.status === 'success') {
      liveQuotes.value = { ...liveQuotes.value, ...res.data.data }
    }
  } catch (err) {
    console.error("Failed to sync live quotes:", err)
  } finally {
    isLiveSyncing.value = false
  }
}

const getLivePnL = (sym, type, dateStr) => {
  const quote = liveQuotes.value[sym]
  if (!quote) return null
  
  let isLatest = false
  if (holdings.value && holdings.value.length > 0) {
    isLatest = dateStr === holdings.value[holdings.value.length - 1].date
  }
  
  let pnl = quote.pct_change
  
  if (isLatest) {
    if (type === 'entry' && quote.open_price > 0) {
      pnl = (quote.price - quote.open_price) / quote.open_price * 100
    } else if (type === 'exit' && quote.yesterday_close > 0) {
      pnl = (quote.open_price - quote.yesterday_close) / quote.yesterday_close * 100
    }
  }
  
  return isNaN(pnl) ? 0 : pnl
}

const getLiveDailyReturn = (h) => {
  let isLatest = false
  if (holdings.value && holdings.value.length > 0) {
    isLatest = h.date === holdings.value[holdings.value.length - 1].date
  }
  
  if (isLatest && Object.keys(liveQuotes.value).length > 0) {
    let totalPnL = 0
    let count = 0
    
    if (h.entries) {
      h.entries.forEach(sym => {
        const pnl = getLivePnL(sym, 'entry', h.date)
        if (pnl !== null) {
          totalPnL += pnl
          count++
        }
      })
    }
    
    if (h.holds) {
      h.holds.forEach(sym => {
        const pnl = getLivePnL(sym, 'hold', h.date)
        if (pnl !== null) {
          totalPnL += pnl
          count++
        }
      })
    }
    
    if (h.exits) {
      h.exits.forEach(sym => {
        const ret = getReturn(h.holdings, sym)
        if (ret !== undefined && ret !== null) {
          totalPnL += (ret * 100)
          count++
        }
      })
    }
    
    // The divisor is the number of active components originally held (holds + exits). 
    // Since it's a substitution strategy, count/2 roughly equals the portfolio size if entries == exits.
    // To be precise for equal weight, the base capital was spread across (holds + exits).
    let baseCount = (h.holds ? h.holds.length : 0) + (h.exits ? h.exits.length : 0)
    if (baseCount === 0 && count > 0) baseCount = count // fallback
    
    if (baseCount > 0) {
      return totalPnL / baseCount / 100.0
    }
  }
  
  return h.daily_return
}

const getCompareChartOption = () => {
  const curves = compareCurves.value
  if (!curves || curves.length === 0) return {}

  // 收集所有日期（取并集）
  const allDates = new Set()
  curves.forEach(c => {
    c.curve.forEach(d => allDates.add(d.date))
  })
  const sortedDates = [...allDates].sort()

  // 为每条曲线构建日期→收益率的映射
  const series = curves.map(c => {
    const dateMap = {}
    c.curve.forEach(d => {
      dateMap[d.date] = (d.strategy || 0) * 100
    })
    return {
      name: c.label,
      type: 'line',
      data: sortedDates.map(d => dateMap[d] !== undefined ? dateMap[d].toFixed(2) : null),
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: c.color },
      itemStyle: { color: c.color },
      connectNulls: true
    }
  })

  return {
    title: {
      text: 'Strategy Comparison — Click a curve to view details',
      left: 'center',
      top: 5,
      textStyle: { color: '#4ade80', fontSize: 14, fontWeight: 'bold' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(56, 189, 248, 0.4)',
      textStyle: { color: '#e2e8f0' },
      formatter: function(params) {
        if (!params || params.length === 0) return ''
        const date = params[0].name
        let html = `<div style="font-weight:bold;margin-bottom:4px;color:#38bdf8;">${date}</div>`
        params.forEach(p => {
          if (p.value === null || p.value === undefined) return
          const val = Number(p.value)
          const color = val >= 0 ? '#ef4444' : '#10b981'
          html += `<div style="display:flex;justify-content:space-between;gap:12px;margin-top:3px;">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="font-family:monospace;font-weight:bold;color:${color}">${val > 0 ? '+' : ''}${val.toFixed(2)}%</span>
          </div>`
        })
        return html
      }
    },
    grid: { left: '5%', right: '4%', top: '12%', bottom: '15%' },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: sortedDates,
      axisLabel: { color: '#9ca3af', fontSize: 10 },
      axisLine: { lineStyle: { color: '#374151' } }
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', formatter: '{value} %' },
      splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { show: true, type: 'slider', bottom: '3%', start: 0, end: 100 }
    ],
    series
  }
}

const getComparisonOption = () => {
  const allData = themeStocksData.value
  const series = []
  const symbols = Object.keys(allData)
  
  const baseOption = {
    title: { 
      textStyle: { color: '#e5e7eb', fontSize: 16 },
      left: 'center',
      top: 5
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#f8fafc' }
    },
    legend: {
      textStyle: { color: '#e5e7eb' },
      bottom: 25,
      type: 'scroll'
    },
    grid: {
      top: '12%',
      bottom: '15%',
      left: '5%',
      right: '5%'
    },
    xAxis: {
      type: 'category',
      axisLabel: { color: '#9ca3af' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
      data: []
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', formatter: '{value}%' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } }
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { show: true, type: 'slider', bottom: 5, start: 0, end: 100, height: 15 }
    ],
    series: []
  }

  if (symbols.length === 0) {
    return {
      ...baseOption,
      title: { 
        ...baseOption.title,
        text: comparisonLoading.value ? 'Fetching data...' : 'No intraday data found for this theme', 
        textStyle: { color: comparisonLoading.value ? '#9ca3af' : '#ef4444', fontSize: 14 }, 
        top: 'center' 
      },
      legend: { show: false }
    }
  }

  // Use the grid from the first stock (all stocks share the same grid)
  const sortedTimes = allData[symbols[0]].grid || []
  baseOption.xAxis.data = sortedTimes
  
  const pre = parseInt(rangePre.value) || 0
  const post = isLatestDate.value ? 0 : (parseInt(rangePost.value) || 0)

  baseOption.xAxis.axisLabel.interval = (index, value) => {
    if (pre > 0 || post > 0) {
      return value.includes(' 09:30')
    }
    return index % 60 === 0
  }
  baseOption.xAxis.axisLabel.formatter = (value) => {
    const parts = value.split(' ')
    if (pre > 0 || post > 0) {
      return parts[0]
    }
    return parts[1] || parts[0]
  }

  // Boundary markers for each day (at 15:00)
  const markLines = []
  sortedTimes.forEach((t, idx) => {
    if (t.endsWith(' 15:00') && idx < sortedTimes.length - 1) {
      markLines.push({
        xAxis: idx,
        lineStyle: { color: 'rgba(255, 255, 255, 0.3)', type: 'dashed', width: 1 },
        label: { show: false }
      })
    }
  })

  symbols.forEach(s => {
    const stock = allData[s]
    const dataPoints = stock.data
    if (!dataPoints || dataPoints.length === 0) return

    const basePrice = dataPoints[0].pre_close || dataPoints[0].price
    if (!basePrice) return
    
    const relativeData = sortedTimes.map(t => {
      const point = dataPoints.find(p => p.time === t)
      if (point) {
        return ((point.price - basePrice) / basePrice * 100).toFixed(2)
      }
      return null
    })
    
    if (relativeData.some(v => v !== null)) {
      series.push({
        name: stock.name,
        type: 'line',
        data: relativeData,
        showSymbol: false,
        smooth: true,
        connectNulls: true,
        lineStyle: { width: 2 },
        markLine: markLines.length > 0 ? {
          symbol: ['none', 'none'],
          data: markLines
        } : undefined
      })
    }
  })
  
  const title = selectedTheme.value?.concept || 'Theme'

  return {
    ...baseOption,
    title: { ...baseOption.title, text: title },
    tooltip: {
      ...baseOption.tooltip,
      formatter: (params) => {
        if (!params || params.length === 0) return ''
        let res = `<div style="font-weight:bold;margin-bottom:4px;color:#9ca3af;">${params[0].name}</div>`
        const validParams = params.filter(p => p.value !== null && p.value !== undefined && !isNaN(p.value))
        const sortedParams = validParams.sort((a, b) => Number(b.value) - Number(a.value))
        
        sortedParams.forEach(p => {
          const val = Number(p.value)
          const color = val >= 0 ? '#ef4444' : '#10b981'
          const displayVal = val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)
          res += `<div style="display:flex;justify-content:space-between;gap:20px;">
            <span>${p.marker} ${p.seriesName}</span>
            <span style="font-weight:bold;color:${color};">${displayVal}%</span>
          </div>`
        })
        return res
      }
    },
    legend: { ...baseOption.legend, data: series.map(s => s.name) },
    series: series
  }
}

const chartOption = computed(() => {
  if (compareCurves.value && compareCurves.value.length > 0) {
    return getCompareChartOption()
  }
  if (isComparisonMode.value) {
    return getComparisonOption()
  }

  // Define default series names to ensure legend matches
  const seriesNames = [
    'AI Strategy Return',
    'Stock Buy&Hold'
  ]

  const baseBacktestOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.9)',
      borderColor: 'rgba(56, 189, 248, 0.4)',
      textStyle: { color: '#e2e8f0' },
      formatter: function(params) {
        if (params && params.length > 0) {
          const date = params[0].name
          
          setTimeout(() => {
            if (hoveredDate.value !== date) {
              hoveredDate.value = date
            }
          }, 0)

          let tooltipHtml = `<div style="font-weight:bold;margin-bottom:4px;color:#38bdf8;">${date}</div>`
          params.forEach(p => {
            const val = p.value !== undefined && p.value !== null ? Number(p.value) : 0
            const color = val >= 0 ? '#ef4444' : '#10b981' // Red for positive, Green for negative
            tooltipHtml += `<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:4px;">
                              <span>${p.marker} ${p.seriesName}</span>
                              <span style="font-family:monospace; font-weight:bold; color:${color}">${val > 0 ? '+' : ''}${val.toFixed(2)}%</span>
                            </div>`
          })
          return tooltipHtml
        }
        return ''
      }
    },
    legend: {
      data: seriesNames,
      textStyle: { color: '#e5e7eb' },
      top: 5
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }]
    },
    grid: [
      { left: '5%', right: '4%', top: '10%', height: '65%' },
      { left: '5%', right: '4%', top: '80%', height: '15%' }
    ],
    xAxis: [
      { type: 'category', gridIndex: 0, boundaryGap: false, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#374151' } }, data: [] },
      { type: 'category', gridIndex: 1, boundaryGap: true, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } }, data: [] }
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, axisLabel: { color: '#9ca3af', formatter: '{value} %' }, splitLine: { lineStyle: { color: '#374151', type: 'dashed' } } },
      { type: 'value', gridIndex: 1, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { show: true, type: 'slider', xAxisIndex: [0, 1], bottom: '1%', start: 0, end: 100 }
    ],
    series: []
  }

  if (!curveData.value || curveData.value.length === 0) {
    return {
      ...baseBacktestOption,
      title: { text: loading.value ? 'Running backtest...' : 'No backtest data', left: 'center', top: 'center', textStyle: { color: '#9ca3af' } },
      series: [
        ...seriesNames.map(name => ({ name, type: 'line', data: [] })),
        { name: 'Daily Return', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: [] }
      ]
    }
  }

  let activeData = curveData.value
  
  // Find the first index where the strategy actually has a position or non-zero return
  const firstActiveIdx = activeData.findIndex(d => (d.holdings_count && d.holdings_count > 0) || Math.abs(d.daily_return || 0) > 0.000001 || Math.abs(d.strategy || 0) > 0.000001)
  
  if (firstActiveIdx > 0) {
    // Keep one day before the first active day so the curve starts exactly at 0
    const startIdx = Math.max(0, firstActiveIdx - 1)
    activeData = activeData.slice(startIdx)
    
    // Re-baseline benchmark so it starts at 0%
    const baseBench = activeData[0].benchmark || 0
    activeData = activeData.map(d => ({
      ...d,
      benchmark: (1 + (d.benchmark || 0)) / (1 + baseBench) - 1
    }))
  }

  const dates = activeData.map(d => d.date)
  const strategySeries = activeData.map(d => ((d.strategy || 0) * 100).toFixed(2))
  const benchSeries = activeData.map(d => ((d.benchmark || 0) * 100).toFixed(2))
  const dailyReturns = activeData.map(d => ((d.daily_return || 0) * 100).toFixed(2))

  // Inject LIVE data into the last data point if applicable
  if (holdings.value && holdings.value.length > 0 && curveData.value.length > 0) {
    const lastHolding = holdings.value[holdings.value.length - 1]
    if (dates[dates.length - 1] === lastHolding.date && Object.keys(liveQuotes.value).length > 0) {
      const liveDailyRet = getLiveDailyReturn(lastHolding)
      dailyReturns[dailyReturns.length - 1] = (liveDailyRet * 100).toFixed(2)
      
      if (curveData.value.length > 1) {
        const prevCumulative = curveData.value[curveData.value.length - 2].strategy
        const newCumulative = (1 + prevCumulative) * (1 + liveDailyRet) - 1
        strategySeries[strategySeries.length - 1] = (newCumulative * 100).toFixed(2)
      } else {
        strategySeries[strategySeries.length - 1] = (liveDailyRet * 100).toFixed(2)
      }
    }
  }

  baseBacktestOption.xAxis[0].data = dates
  baseBacktestOption.xAxis[1].data = dates

  const strategySeriesObj = {
    name: 'AI Strategy Return',
    type: 'line',
    xAxisIndex: 0,
    yAxisIndex: 0,
    data: strategySeries,
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 3, color: '#3b82f6' },
    itemStyle: { color: '#3b82f6' }
  }

  if (metrics.value && metrics.value.drawdown_periods && metrics.value.drawdown_periods.length > 0) {
    strategySeriesObj.markArea = {
      silent: true,
      itemStyle: {
        color: 'rgba(239, 68, 68, 0.15)',
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.5)',
        borderType: 'dashed'
      },
      data: metrics.value.drawdown_periods.map(dd => [
        {
          name: `回撤 ${(dd.drawdown * 100).toFixed(2)}%`,
          xAxis: dd.start,
          label: {
            show: true,
            position: 'insideTop',
            color: '#f87171',
            fontSize: 12
          }
        },
        { xAxis: dd.end }
      ])
    }
  } else if (metrics.value && metrics.value.max_drawdown_start && metrics.value.max_drawdown_end) {
    strategySeriesObj.markArea = {
      silent: true,
      itemStyle: {
        color: 'rgba(239, 68, 68, 0.15)',
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.5)',
        borderType: 'dashed'
      },
      label: {
        position: 'insideTop',
        color: '#f87171',
        fontSize: 12,
        formatter: `回撤 ${(metrics.value.max_drawdown * 100).toFixed(2)}%`
      },
      data: [
        [
          { xAxis: metrics.value.max_drawdown_start },
          { xAxis: metrics.value.max_drawdown_end }
        ]
      ]
    }
  }

  return {
    ...baseBacktestOption,
    series: [
      strategySeriesObj,
      {
        name: 'Stock Buy&Hold',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: benchSeries,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, type: 'dashed', color: '#64748b' },
        itemStyle: { color: '#64748b' }
      },
      {
        name: 'Daily Return',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: dailyReturns,
        itemStyle: {
          color: function(params) {
            return params.value >= 0 ? '#ef4444' : '#10b981' // Red for positive (China style), Green for negative
          }
        }
      }
    ]
  }
})

const reversedCurveData = computed(() => {
  if (!curveData.value) return []
  return [...curveData.value].reverse()
})

const runSingleBacktest = async () => {
  if (!form.value.symbol) {
    error.value = "Please enter a stock symbol."
    return
  }

  isComparisonMode.value = false
  loading.value = true
  error.value = null
  try {
    const res = await axios.post('/api/backtest/single', {
      symbol: form.value.symbol,
      start_date: form.value.startDate,
      end_date: form.value.endDate
    })
    
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
    } else {
      error.value = res.data.message || 'Unknown error occurred.'
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const fetchResults = async () => {
  compareCurves.value = []
  isComparisonMode.value = false
  loading.value = true
  loadingMsg.value = 'Loading cached results...'
  error.value = null
  try {
    const res = await axios.get(`/api/backtest/results?enable_ml_filter=${enableMlFilter.value}&model_version=${selectedModelVersion.value}&top_k=${topK.value}&enable_market_timing=${enableMarketTiming.value}&vol=${enableTurnoverFilter.value}&crash=${enableCrashFilter.value}&boost=${enableSelectionBoost.value}`)
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics || null
      curveData.value = res.data.data.curve || null
      holdings.value = res.data.data.holdings || []
      conceptAttribution.value = res.data.data.concept_attribution || []
    }
    // Refresh today's picks with matching parameters
    await fetchTodaysPicks()
  } catch (err) {
    if (err.response && err.response.status === 502) {
      // Suppress 502 during hot-reload
    } else {
      console.error("Failed to fetch backtest results:", err)
    }
  } finally {
    loading.value = false
  }
}

const downloadData = async () => {
  downloading.value = true
  error.value = null
  try {
    const res = await axios.post('/api/backtest/download-data', {}, { timeout: 1800000 })
    if (res.data.status === 'success') {
      alert(`Downloaded ${res.data.downloaded} stocks (${res.data.failed} failed)`)
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    downloading.value = false
  }
}

const runIntelligentBacktest = async () => {
  compareCurves.value = []
  isComparisonMode.value = false
  loading.value = true
  loadingMsg.value = enableMlFilter.value ? 'Running ML Hybrid Backtest...' : 'Running Signal Backtest...'
  error.value = null
  try {
    const res = await axios.post(`/api/backtest/intelligent?enable_ml_filter=${enableMlFilter.value}&model_version=${selectedModelVersion.value}&top_k=${topK.value}&enable_market_timing=${enableMarketTiming.value}&vol=${enableTurnoverFilter.value}&crash=${enableCrashFilter.value}&boost=${enableSelectionBoost.value}`, {}, { timeout: 600000 })
    if (res.data.status === 'success') {
      metrics.value = res.data.data.metrics
      curveData.value = res.data.data.curve
      holdings.value = res.data.data.holdings || []
      conceptAttribution.value = res.data.data.concept_attribution || []
      await fetchTodaysPicks()
    } else {
      error.value = res.data.message || 'Unknown error occurred.'
    }
  } catch (err) {
    console.error(err)
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

const openLeaderboard = async () => {
  showLeaderboard.value = true
  leaderboardLoading.value = true
  try {
    const res = await axios.get('/api/backtest/strategy-compare')
    if (res.data && res.data.status === 'success') {
      leaderboardData.value = res.data.data
    } else {
      console.error("Leaderboard fetch failed:", res.data)
      leaderboardData.value = []
    }
  } catch (err) {
    console.error("Failed to load leaderboard:", err)
    leaderboardData.value = []
  } finally {
    leaderboardLoading.value = false
  }
}

const loadStrategy = (item) => {
  // 同步所有控制变量，确保加载的数据与 leaderboard 行完全一致
  enableMlFilter.value = item.model !== 'factor_rank' && item.model !== 'pure_signal'
  selectedModelVersion.value = item.model
  topK.value = item.K
  enableMarketTiming.value = item.timing || false
  enableTurnoverFilter.value = item.vol || false
  enableCrashFilter.value = item.crash || false
  enableSelectionBoost.value = item.boost || false

  // 关闭 leaderboard 弹窗
  showLeaderboard.value = false

  // 加载对应的回测数据
  fetchResults()
}

// === Strategy Compare ===
const compareColors = ['#38bdf8', '#fbbf24', '#a78bfa', '#34d399', '#f87171', '#fb923c', '#22d3ee', '#e879f9']

const openCompareModal = async () => {
  // 确保 leaderboard 数据已加载
  if (leaderboardData.value.length === 0) {
    leaderboardLoading.value = true
    try {
      const res = await axios.get('/api/backtest/strategy-compare')
      leaderboardData.value = res.data.data || []
    } catch (e) {
      console.error('Failed to load leaderboard', e)
    }
    leaderboardLoading.value = false
  }
  // 默认选中当前策略
  compareSelected.value = [{
    id: 'current',
    label: 'Current Settings',
    model: selectedModelVersion.value,
    K: topK.value,
    timing: enableMarketTiming.value
  }]
  showCompareModal.value = true
}

const compareItemKey = (item) => item.id || `${item.model}_${item.K}_${item.timing}`

const isCompareSelected = (item) => {
  return compareSelected.value.some(s => compareItemKey(s) === compareItemKey(item))
}

const toggleCompareItem = (item) => {
  const key = compareItemKey(item)
  const idx = compareSelected.value.findIndex(s => compareItemKey(s) === key)
  if (idx >= 0) {
    compareSelected.value.splice(idx, 1)
  } else {
    compareSelected.value.push(item)
  }
}

const executeCompare = async () => {
  showCompareModal.value = false
  if (compareSelected.value.length === 0) return

  loading.value = true
  compareCurves.value = []
  compareSelectedIndex.value = -1

  for (let i = 0; i < compareSelected.value.length; i++) {
    const item = compareSelected.value[i]
    const timing = item.timing || false
    try {
      const res = await axios.get(`/api/backtest/results?enable_ml_filter=true&model_version=${item.model}&top_k=${item.K}&enable_market_timing=${timing}`)
      const data = res.data.data || {}
      const curve = data.curve || []
      const label = item.label || `${item.model} K=${item.K} ${timing ? '择时' : '无择时'}`
      compareCurves.value.push({
        label,
        curve,
        color: compareColors[i % compareColors.length],
        metrics: data.metrics || null,
        holdings: data.holdings || []
      })
    } catch (e) {
      console.error(`Failed to load ${item.model_version} K=${item.top_k}`, e)
    }
  }

  // 默认选中第一条曲线
  if (compareCurves.value.length > 0) {
    selectCompareStrategy(0)
  }

  loading.value = false
}

const selectCompareStrategy = (index) => {
  if (!compareCurves.value || index < 0 || index >= compareCurves.value.length) return
  compareSelectedIndex.value = index
  const s = compareCurves.value[index]
  // 直接替换主面板数据，让右侧指标和底部交割单同步更新
  metrics.value = s.metrics
  holdings.value = s.holdings
}

const getWeight = (holdingsList, symbol) => {
  if (!holdingsList) return 0;
  const item = holdingsList.find(h => h.symbol === symbol);
  return item && item.weight !== undefined ? item.weight : 0;
}

const getReturn = (holdingsList, symbol) => {
  if (!holdingsList) return null;
  const item = holdingsList.find(h => h.symbol === symbol);
  return item && item.ret !== undefined ? item.ret : null;
}

const getName = (holdingsList, symbol) => {
  // 1. Try Live Quotes
  if (liveQuotes.value && liveQuotes.value[symbol] && liveQuotes.value[symbol].name) {
    return liveQuotes.value[symbol].name;
  }
  
  // 2. Try Today's Picks
  if (todaysPicks.value && todaysPicks.value.top_picks) {
    const pick = todaysPicks.value.top_picks.find(p => p.symbol === symbol);
    if (pick && pick.name) return pick.name;
  }

  // 3. Try Holdings List
  if (holdingsList) {
    const item = holdingsList.find(h => h.symbol === symbol);
    if (item && item.name && item.name !== symbol) return item.name;
  }
  
  return symbol;
}

const useCompositePicks = ref(true)

const fetchTodaysPicks = async () => {
  try {
    const res = await axios.get(`/api/backtest/todays-picks?model_version=${selectedModelVersion.value}&top_k=${topK.value}&use_composite=${useCompositePicks.value}`)
    if (res.data && res.data.status === 'success') {
      todaysPicks.value = res.data
    } else {
      todaysPicks.value = null
    }
  } catch (err) {
    console.error("Failed to fetch todays picks:", err)
    todaysPicks.value = null
  }
}

const todayStr = computed(() => {
  const d = new Date()
  const offset = d.getTimezoneOffset() * 60000
  return (new Date(d.getTime() - offset)).toISOString().split('T')[0]
})

const canRefreshPicks = computed(() => {
  if (!todaysPicks.value || !todaysPicks.value.date) return true
  return todaysPicks.value.date !== todayStr.value
})

const isRefreshingPicks = ref(false)

const runPremarketSelection = async () => {
  if (isRefreshingPicks.value) return;
  
  if (!canRefreshPicks.value) {
    const confirmForce = confirm("今日金股已经生成，确认要强制重新拉取最新研报吗？");
    if (!confirmForce) return;
  }
  
  isRefreshingPicks.value = true;
  try {
    const res = await axios.post('/api/refresh/reports');
    if (res.data.status !== 'started' && res.data.status !== 'success' && res.data.status !== 'busy') {
      alert(res.data.message || 'Failed to start selection');
      isRefreshingPicks.value = false;
      return;
    }
    
    let attempts = 0;
    const oldDate = todaysPicks.value?.date;
    
    const poll = async () => {
      attempts++;
      if (attempts > 30) {
        alert("请求超时，请稍后再试");
        isRefreshingPicks.value = false;
        return;
      }
      
      const statusRes = await axios.get('/api/refresh/reports/status');
      if (statusRes.data.running) {
        setTimeout(poll, 2000);
      } else {
        await fetchTodaysPicks();
        if (todaysPicks.value?.date === oldDate) {
          alert("上游数据源尚未发布今日最新的盘前研报数据，请稍后重试！");
        }
        isRefreshingPicks.value = false;
      }
    };
    
    setTimeout(poll, 2000);
  } catch (err) {
    console.error(err);
    alert('请求错误: ' + (err.response?.data?.detail || err.message));
    isRefreshingPicks.value = false;
  }
}

const isMarketOpen = () => {
  const now = new Date()
  const hours = now.getHours()
  const minutes = now.getMinutes()
  const time = hours * 100 + minutes
  // 09:30 to 11:30 and 13:00 to 15:00
  return (time >= 930 && time <= 1130) || (time >= 1300 && time <= 1500)
}

const isMarketOpenRef = ref(isMarketOpen())
let syncInterval = null

// --- Watchers: auto-sync data when parameters change ---

// rangePre / rangePost: re-trigger theme comparison when slider changes
watch([rangePre, rangePost], () => {
  if (isComparisonMode.value && selectedTheme.value) {
    selectTheme(selectedTheme.value)
  }
})

onMounted(() => {
  fetchResults()
  fetchValidDates()

  syncInterval = setInterval(() => {
    isMarketOpenRef.value = isMarketOpen()
    if (isMarketOpenRef.value && !isLiveSyncing.value) {
      syncLiveQuotes()
    }
  }, 30000)

  if (isMarketOpenRef.value) {
    syncLiveQuotes()
  }
})

onUnmounted(() => {
  if (syncInterval) clearInterval(syncInterval)
})
</script>

<style scoped>
.backtest-container {
  padding: 12px;
  height: calc(100vh - 24px);
  display: flex;
  flex-direction: column;
  color: var(--text-primary);
  gap: 12px;
}

.top-control-bar {
  padding: 6px 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  border-radius: 8px;
  overflow-x: auto;
}

.top-control-bar::-webkit-scrollbar {
  height: 4px;
}
.top-control-bar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}

.controls-left, .controls-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.controls-right {
  justify-content: flex-end;
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #9ca3af;
}

.window-control {
  margin-left: 12px;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.dual-range {
  display: flex;
  align-items: center;
  gap: 6px;
}

.range-hint {
  font-size: 0.75rem;
  color: #64748b;
  text-transform: uppercase;
  font-weight: 600;
}

.range-val {
  font-size: 0.85rem;
  color: #60a5fa;
  font-weight: 700;
  min-width: 12px;
  text-align: center;
}

.mini-slider {
  width: 60px;
  accent-color: #3b82f6;
  cursor: pointer;
  height: 4px;
}

.mini-slider:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.mini-input {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255,255,255,0.1);
  color: #f8fafc;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  outline: none;
}

.icon-btn, .mini-btn {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover, .mini-btn:hover {
  background: rgba(59, 130, 246, 0.3);
}

.top-pool-section {
  padding: 12px;
  border-radius: 12px;
  overflow: hidden;
}

.pool-settings {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.setting-label {
  font-size: 0.85rem;
  color: #9ca3af;
}

.range-slider {
  width: 150px;
  accent-color: #3b82f6;
  cursor: pointer;
}

.range-value {
  font-size: 0.85rem;
  color: #60a5fa;
  font-weight: 600;
  min-width: 100px;
}

.pool-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.pool-row:last-child {
  margin-bottom: 0;
}

.row-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: #9ca3af;
  width: 60px;
  text-transform: uppercase;
}

.horizontal-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  flex: 1;
}

.horizontal-scroll::-webkit-scrollbar {
  height: 4px;
}
.horizontal-scroll::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
}

.theme-chip {
  background: rgba(255,255,255,0.05);
  color: #e5e7eb;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 0.85rem;
  white-space: nowrap;
  cursor: pointer;
  border: 1px solid rgba(255,255,255,0.1);
  transition: all 0.2s;
  position: relative;
}

.theme-chip:hover {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
}

.active-chip {
  background: rgba(59, 130, 246, 0.3) !important;
  color: #60a5fa !important;
  border-color: #3b82f6 !important;
}

.new-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
}

.content-wrapper {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.side-panel-right {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.info-card h4 {
  margin: 0 0 8px 0;
  font-size: 0.85rem;
  color: #9ca3af;
  text-transform: uppercase;
}

.form-group-mini {
  display: flex;
  gap: 4px;
}

.mini-run-btn {
  background: #3b82f6;
  border: none;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
}

.metrics-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mini-metric {
  background: rgba(255,255,255,0.05);
  padding: 8px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-metric .l { font-size: 0.7rem; color: #9ca3af; }
.mini-metric .v { font-size: 1rem; font-weight: 700; }

.signals-scroll {
  font-size: 0.75rem;
}

.signals-table {
  width: 100%;
}

.signals-table td {
  padding: 4px 0;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.hold { color: #ef4444; font-weight: 700; }
.empty { color: #10b981; font-weight: 700; }

.slide-enter-active, .slide-leave-active {
  transition: all 0.3s ease;
  max-height: 200px;
}
.slide-enter-from, .slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
  margin-top: 0;
}

.global-loading-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
  gap: 16px;
}

.chart-container {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  min-width: 0;
}

.chart {
  height: 100%;
  width: 100%;
}

.stock-tag {
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.core-tag {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.other-tag {
  background: rgba(255, 255, 255, 0.05);
  color: #9ca3af;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.topic-tag {
  background: rgba(59, 130, 246, 0.1);
  color: #cbd5e1;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.st-stock {
  border-color: rgba(245, 158, 11, 0.5) !important;
  background: rgba(245, 158, 11, 0.1) !important;
  color: #f59e0b !important;
}

.st-badge {
  background: #f59e0b;
  color: #000;
  font-size: 0.65rem;
  font-weight: 800;
  padding: 1px 3px;
  border-radius: 3px;
  line-height: 1;
}

.clickable-theme {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e5e7eb;
  margin-bottom: 6px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
  display: inline-block;
}

.clickable-theme:hover {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.active-theme {
  background: rgba(59, 130, 246, 0.3);
  color: #3b82f6;
  border-left: 3px solid #3b82f6;
}

.close-comparison-btn {
  position: absolute;
  top: 15px;
  right: 15px;
  z-index: 100;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #9ca3af;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.close-comparison-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}

.compare-strategy-tabs {
  position: absolute;
  top: 50px;
  left: 15px;
  z-index: 99;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 70%;
}

.compare-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(15, 23, 42, 0.8);
  border: 2px solid transparent;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.7rem;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
  backdrop-filter: blur(8px);
}

.compare-tab:hover {
  background: rgba(30, 41, 59, 0.9);
  color: #e2e8f0;
}

.compare-tab.active {
  color: #f1f5f9;
  font-weight: bold;
}

.compare-tab .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.comparison-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(4px);
  z-index: 50;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #e5e7eb;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(59, 130, 246, 0.3);
  border-radius: 50%;
  border-top-color: #3b82f6;
  animation: spin 1s ease-in-out infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.leaderboard-modal {
  width: 90%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header {
  padding: 16px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.5);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: #f8fafc;
}

.close-btn {
  background: transparent;
  border: none;
  color: #9ca3af;
  font-size: 1.25rem;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #ef4444;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.leaderboard-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.leaderboard-table th {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.05);
  color: #9ca3af;
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
  border-bottom: 2px solid rgba(255, 255, 255, 0.1);
}

.leaderboard-table td {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 0.95rem;
}

.leaderboard-table tr:hover td {
  background: rgba(255, 255, 255, 0.02);
}

.top-3 td {
  background: rgba(250, 204, 21, 0.05);
}

.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s;
}

.clickable-row:hover td {
  background: rgba(59, 130, 246, 0.15) !important;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: #9ca3af;
}

.badge {
  padding: 2px 6px;
  border-radius: 4px;
  margin-right: 4px;
  white-space: nowrap;
}
.badge-vol {
  background: rgba(56, 189, 248, 0.2);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}
.badge-timing {
  background: rgba(251, 191, 36, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.3);
}
.badge-crash {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}
.badge-boost {
  background: rgba(167, 139, 250, 0.2);
  color: #a78bfa;
  border: 1px solid rgba(167, 139, 250, 0.3);
}

.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}
.sortable:hover {
  color: #f8fafc !important;
}
.sort-icon-dim {
  color: rgba(255,255,255,0.2);
  margin-left: 4px;
}
</style>
