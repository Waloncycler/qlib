const commonTheme = {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: 'Inter, sans-serif' },
  tooltip: {
    backgroundColor: 'rgba(22, 24, 30, 0.8)',
    borderColor: 'rgba(255,255,255,0.1)',
    textStyle: { color: '#f2f2f2' },
    backdropFilter: 'blur(10px)',
    padding: 12
  },
  grid: {
    top: 40,
    bottom: 30,
    left: 40,
    right: 20
  }
}

export function useChartFactory() {
  
  const createKlineOption = (title, data, options = {}) => {
    const {
      showLimit = true,
      showHigh20 = true,
      showAbnormal = true,
      showPrediction = true
    } = options
    
    // data: [{date, open, close, low, high, volume}]
    if (!data || !data.length) return {}
    
    const categoryData = []
    const values = []
    const volumes = []
    const markPointData = []
    
    const symbol = data[0]?.symbol || ''
    let limitPct = 9.8
    if (symbol.startsWith('SZ300') || symbol.startsWith('SH688')) limitPct = 19.8
    if (symbol.startsWith('BJ')) limitPct = 29.8
    
    data.forEach((item, index) => {
      categoryData.push(item.date || item.trade_date)
      
      let style = null
      let currentTopOffset = -15
      
      // 1. Calculate 20-day high (H)
      let is20DayHigh = false
      if (index >= 20) {
        let maxClose = 0
        for (let j = index - 20; j < index; j++) {
          if (data[j].close > maxClose) maxClose = data[j].close
        }
        if (item.close > maxClose) {
          is20DayHigh = true
        }
      }

      // 2. Calculate Abnormal Fluctuation (10-day 100%, 30-day 200%)
      let isYellow = false
      let isRed = false
      if (index >= 1) {
        const idx10 = Math.max(0, index - 10)
        const idx30 = Math.max(0, index - 30)
        const ret10 = (item.close / data[idx10].close) - 1
        const ret30 = (item.close / data[idx30].close) - 1
        
        if (ret10 >= 1.0 || ret30 >= 2.0) isRed = true
        else if (ret10 >= 0.8 || ret30 >= 1.7) isYellow = true
      }

      if (index > 0) {
        const prevClose = data[index - 1].close
        const pctChg = (item.close - prevClose) / prevClose * 100
        
        if (showLimit && pctChg >= limitPct) {
          // Limit Up
          markPointData.push({
            coord: [item.date || item.trade_date, item.high],
            symbolOffset: [0, currentTopOffset],
            value: '涨',
            symbol: 'roundRect',
            symbolSize: [18, 18],
            itemStyle: { color: '#ec4899' },
            label: { show: true, color: '#fff', fontSize: 10, formatter: '涨' }
          })
          currentTopOffset -= 20
          style = {
            color: '#ec4899', borderColor: '#ec4899', borderWidth: 2,
            shadowColor: 'rgba(236, 72, 153, 0.8)', shadowBlur: 10
          }
        } else if (showLimit && pctChg <= -limitPct) {
          // Limit Down
          markPointData.push({
            coord: [item.date || item.trade_date, item.low],
            symbolOffset: [0, 15],
            value: '跌',
            symbol: 'roundRect',
            symbolSize: [18, 18],
            itemStyle: { color: '#0ea5e9' },
            label: { show: true, color: '#fff', fontSize: 10, formatter: '跌' }
          })
          style = {
            color: '#0ea5e9', color0: '#0ea5e9', borderColor: '#0ea5e9', borderColor0: '#0ea5e9',
            borderWidth: 2, shadowColor: 'rgba(14, 165, 233, 0.8)', shadowBlur: 10
          }
        }
      }
      
      // Stack Markers
      if (showAbnormal && isRed) {
        markPointData.push({
          coord: [item.date || item.trade_date, item.high],
          symbolOffset: [0, currentTopOffset],
          value: '警',
          symbol: 'roundRect',
          symbolSize: [18, 18],
          itemStyle: { color: '#ef4444' },
          label: { show: true, color: '#fff', fontSize: 10, formatter: '警' }
        })
        currentTopOffset -= 20
      } else if (showAbnormal && isYellow) {
        markPointData.push({
          coord: [item.date || item.trade_date, item.high],
          symbolOffset: [0, currentTopOffset],
          value: '异',
          symbol: 'roundRect',
          symbolSize: [18, 18],
          itemStyle: { color: '#eab308' },
          label: { show: true, color: '#000', fontSize: 10, formatter: '异' }
        })
        currentTopOffset -= 20
      }
      
      if (showHigh20 && is20DayHigh) {
        markPointData.push({
          coord: [item.date || item.trade_date, item.high],
          symbolOffset: [0, currentTopOffset],
          value: 'H',
          symbol: 'circle',
          symbolSize: [18, 18],
          itemStyle: { color: '#8b5cf6', opacity: 0.9 },
          label: { show: true, color: '#fff', fontSize: 10, formatter: 'H' }
        })
        currentTopOffset -= 20
      }
      
      if (style) {
        values.push({
          value: [item.open, item.close, item.low, item.high],
          itemStyle: style
        })
      } else {
        values.push([item.open, item.close, item.low, item.high])
      }
      
      volumes.push([index, item.volume, item.close > item.open ? 1 : -1])
    })
    
    // Calculate prediction lines for the latest candle
    const markLineData = []
    if (showPrediction && data.length > 0) {
      const lastIndex = data.length - 1
      const lastItem = data[lastIndex]
      
      if (lastIndex >= 10) {
        const base10 = data[lastIndex - 10].close
        const limit10 = base10 * 2.0
        // Only show if it's within roughly 4 limit-ups to prevent crushing chart scale for flat stocks
        if (limit10 / lastItem.close <= 1.5) {
          markLineData.push({
            yAxis: parseFloat(limit10.toFixed(2)),
            lineStyle: { type: 'dashed', color: '#ef4444', width: 2 },
            label: { show: true, position: 'insideStartTop', formatter: '10日异动预测线: {c}', color: '#ef4444', fontSize: 11, fontWeight: 'bold' }
          })
        }
      }
      
      if (lastIndex >= 30) {
        const base30 = data[lastIndex - 30].close
        const limit30 = base30 * 3.0
        if (limit30 / lastItem.close <= 1.5) {
          markLineData.push({
            yAxis: parseFloat(limit30.toFixed(2)),
            lineStyle: { type: 'dashed', color: '#eab308', width: 2 },
            label: { show: true, position: 'insideStartBottom', formatter: '30日异动预测线: {c}', color: '#eab308', fontSize: 11, fontWeight: 'bold' }
          })
        }
      }
    }
    
    return {
      ...commonTheme,
      title: { text: title, left: 'center', top: 0, textStyle: { color: '#f2f2f2', fontSize: 16, fontWeight: 'bold' } },
      tooltip: {
        ...commonTheme.tooltip,
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: '#8b5cf6', type: 'dashed' } }
      },
      legend: { data: ['KLine', 'MA5', 'MA20'], textStyle: { color: '#9ba1a6' }, top: 0, right: '5%' },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: '5%', right: '5%', top: 75, height: '50%' },
        { left: '5%', right: '5%', top: '75%', height: '15%' }
      ],
      xAxis: [
        { type: 'category', data: categoryData, boundaryGap: false, axisLine: { lineStyle: { color: '#555' } }, axisLabel: { color: '#9ba1a6' } },
        { type: 'category', gridIndex: 1, data: categoryData, boundaryGap: false, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#555' } } }
      ],
      yAxis: [
        { scale: true, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ba1a6' } },
        { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
      ],
      dataZoom: [
        { 
          type: 'inside', xAxisIndex: [0, 1], 
          startValue: Math.max(0, categoryData.length - 30), 
          endValue: categoryData.length - 1 
        },
        { 
          show: true, xAxisIndex: [0, 1], type: 'slider', bottom: '2%', 
          startValue: Math.max(0, categoryData.length - 30), 
          endValue: categoryData.length - 1, 
          borderColor: 'rgba(255,255,255,0.05)', fillerColor: 'rgba(59, 130, 246, 0.2)' 
        }
      ],
      series: [
        {
          name: 'KLine',
          type: 'candlestick',
          data: values,
          itemStyle: {
            color: '#f7525f',
            color0: '#2ebd85',
            borderColor: '#f7525f',
            borderColor0: '#2ebd85'
          },
          markPoint: {
            data: markPointData
          },
          markLine: {
            symbol: ['none', 'none'],
            data: markLineData
          }
        },
        {
          name: 'MA5',
          type: 'line',
          data: data.map(d => parseFloat(d.ma5 ?? d.ma5avgprice)),
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1, color: '#facc15' }
        },
        {
          name: 'MA20',
          type: 'line',
          data: data.map(d => parseFloat(d.ma20 ?? d.ma20avgprice)),
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 1, color: '#c084fc' }
        },
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: {
            color: (params) => params.value[2] > 0 ? '#f7525f' : '#2ebd85'
          }
        }
      ]
    }
  }

  const createLineOption = (title, xAxisData, seriesArr) => {
    return {
      ...commonTheme,
      title: { text: title, textStyle: { color: '#f2f2f2', fontSize: 16 } },
      tooltip: { ...commonTheme.tooltip, trigger: 'axis' },
      legend: { textStyle: { color: '#9ba1a6' }, top: 0, right: 0 },
      xAxis: { type: 'category', data: xAxisData, axisLine: { lineStyle: { color: '#555' } }, axisLabel: { color: '#9ba1a6' } },
      yAxis: { type: 'value', scale: true, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ba1a6' } },
      series: seriesArr.map(s => ({
        ...s,
        type: 'line',
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2 },
      }))
    }
  }

  const createBarOption = (title, xAxisData, seriesArr) => {
    return {
      ...commonTheme,
      title: { text: title, textStyle: { color: '#f2f2f2', fontSize: 16 } },
      tooltip: { ...commonTheme.tooltip, trigger: 'axis' },
      legend: { textStyle: { color: '#9ba1a6' }, top: 0, right: 0 },
      xAxis: { type: 'category', data: xAxisData, axisLine: { lineStyle: { color: '#555' } }, axisLabel: { color: '#9ba1a6' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, axisLabel: { color: '#9ba1a6' } },
      series: seriesArr.map(s => ({
        ...s,
        type: 'bar',
      }))
    }
  }

  const createIntradayOption = (title, data) => {
    if (!data || !data.length) return {}
    
    const basePrice = data[0].price
    
    return {
      ...commonTheme,
      title: { text: title, textStyle: { color: '#f2f2f2', fontSize: 14 } },
      tooltip: { 
        ...commonTheme.tooltip, 
        trigger: 'axis',
        axisPointer: { type: 'cross', lineStyle: { color: '#8b5cf6', type: 'dashed' } },
        formatter: function (params) {
          let html = `${params[0].name}<br/>`
          params.forEach(p => {
            let val = p.value
            let color = p.color
            if (p.seriesName === 'Price') {
              let pct = ((val - basePrice) / basePrice * 100).toFixed(2)
              html += `<span style="color:${color}">Price: ${val.toFixed(2)} (${pct}%)</span><br/>`
            } else if (p.seriesName === 'Volume') {
              html += `<span style="color:${color}">Volume: ${val}</span><br/>`
            }
          })
          return html
        }
      },
      grid: [
        { left: '8%', right: '5%', top: 40, height: '55%' },
        { left: '8%', right: '5%', top: '70%', height: '20%' }
      ],
      xAxis: [
        { type: 'category', data: data.map(d => d.time), axisLine: { lineStyle: { color: '#555' } }, axisLabel: { color: '#9ba1a6' } },
        { type: 'category', gridIndex: 1, data: data.map(d => d.time), axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#555' } } }
      ],
      yAxis: [
        { 
          type: 'value', 
          scale: true, 
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }, 
          axisLabel: { 
            color: (value) => {
              if (value > basePrice) return '#f7525f'
              if (value < basePrice) return '#2ebd85'
              return '#9ba1a6'
            }
          } 
        },
        { type: 'value', gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } }
      ],
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      series: [
        {
          name: 'Price',
          type: 'line',
          data: data.map(d => d.price),
          smooth: false,
          symbol: 'none',
          lineStyle: { width: 1.5, color: '#38bdf8' },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(56, 189, 248, 0.3)' }, { offset: 1, color: 'rgba(56, 189, 248, 0)' }]
            }
          }
        },
        {
          name: 'Volume',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: data.map((d, i) => {
            let color = '#9ba1a6'
            if (i > 0) {
              color = d.price >= data[i-1].price ? '#f7525f' : '#2ebd85'
            }
            return { value: d.volume, itemStyle: { color } }
          })
        }
      ]
    }
  }

  return { createKlineOption, createLineOption, createBarOption, createIntradayOption }
}
