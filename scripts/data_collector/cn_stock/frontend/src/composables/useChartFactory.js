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
    right: 20,
    containLabel: true
  }
}

export function useChartFactory() {
  
  const createKlineOption = (title, data) => {
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
      if (index > 0) {
        const prevClose = data[index - 1].close
        const pctChg = (item.close - prevClose) / prevClose * 100
        
        if (pctChg >= limitPct) {
          // Limit Up
          markPointData.push({
            coord: [item.date || item.trade_date, item.high],
            symbolOffset: [0, -15],
            value: '涨',
            symbol: 'roundRect',
            symbolSize: [18, 18],
            itemStyle: { color: '#ec4899' },
            label: { show: true, color: '#fff', fontSize: 10 }
          })
          style = {
            color: '#ec4899', // Pink/Magenta for limit up
            borderColor: '#ec4899',
            borderWidth: 2,
            shadowColor: 'rgba(236, 72, 153, 0.8)',
            shadowBlur: 10
          }
        } else if (pctChg <= -limitPct) {
          // Limit Down
          markPointData.push({
            coord: [item.date || item.trade_date, item.low],
            symbolOffset: [0, 15],
            value: '跌',
            symbol: 'roundRect',
            symbolSize: [18, 18],
            itemStyle: { color: '#0ea5e9' },
            label: { show: true, color: '#fff', fontSize: 10 }
          })
          style = {
            color: '#0ea5e9', // Sky blue/Cyan for limit down
            color0: '#0ea5e9',
            borderColor: '#0ea5e9',
            borderColor0: '#0ea5e9',
            borderWidth: 2,
            shadowColor: 'rgba(14, 165, 233, 0.8)',
            shadowBlur: 10
          }
        }
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
    
    return {
      ...commonTheme,
      title: { text: title, left: 'center', textStyle: { color: '#f2f2f2', fontSize: 16 } },
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

  return { createKlineOption, createLineOption, createBarOption }
}
