// 统一的 ECharts 样式工具：各图表复用，保证风格一致
import * as echarts from 'echarts'

// 调色板：与 Element Plus 主色一致，多系列图表按语义取色
export const colors = {
  blue: '#409eff', // 主色：权益 / 市值
  green: '#67c23a', // 成功：资产 / 现金
  orange: '#e6a23c', // 警告：投入 / 成本
  red: '#f56c6c', // 危险：涨 / 亏损
  violet: '#7b61ff', // 辅助：比例类（与蓝色在 CVD 下可区分）
  gray: '#909399', // 中性
}

// hex 转 rgba
export function rgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

// 面积渐变（线下方淡出）
export function areaGradient(color, opacity = 0.22) {
  return {
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: rgba(color, opacity) },
        { offset: 1, color: rgba(color, 0) },
      ]),
    },
  }
}

// 通用折线 series
export function lineSeries(name, data, color, { gradient = true, dashed = false, width = 2, tooltipFormatter } = {}) {
  return {
    name,
    type: 'line',
    smooth: true,
    showSymbol: false,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { width, color, ...(dashed ? { type: 'dashed' } : {}) },
    itemStyle: { color },
    emphasis: { focus: 'series' },
    data,
    ...(gradient ? areaGradient(color) : {}),
    ...(tooltipFormatter ? { tooltip: { valueFormatter: tooltipFormatter } } : {}),
  }
}

// 通用柱 series：半透明 + 顶部圆角
export function barSeries(name, data, color, opts = {}) {
  const { tooltipFormatter, ...rest } = opts
  return {
    name,
    type: 'bar',
    data,
    barMaxWidth: 16,
    itemStyle: { color: rgba(color, 0.55), borderRadius: [4, 4, 0, 0] },
    emphasis: { focus: 'series' },
    ...(tooltipFormatter ? { tooltip: { valueFormatter: tooltipFormatter } } : {}),
    ...rest,
  }
}

// 均值虚线（markLine）
export function averageMarkLine() {
  return {
    symbol: 'none',
    lineStyle: { color: '#c0c4cc', type: 'dashed', width: 1 },
    label: { color: '#909399', fontSize: 11, formatter: '平均 {c}' },
    data: [{ type: 'average', name: '平均' }],
  }
}

// 金额千分位；decimals 控制小数位（轴刻度用 0，tooltip 用 2）
export function fmtNum(v, decimals = 0) {
  if (v == null || isNaN(v)) return '-'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: decimals })
}

// 通用配置：有图例时用 grid，单系列无图例用 gridSlim（顶部更紧凑）
export const grid = { left: 64, right: 24, top: 48, bottom: 58 }
export const gridSlim = { left: 64, right: 24, top: 24, bottom: 58 }

export const legend = {
  top: 0,
  left: 'center',
  itemWidth: 16,
  itemHeight: 8,
  icon: 'roundRect',
  textStyle: { color: '#606266', fontSize: 12 },
}

export const tooltip = {
  trigger: 'axis',
  confine: true,
  backgroundColor: 'rgba(255,255,255,0.96)',
  borderColor: '#e4e7ed',
  borderWidth: 1,
  padding: [8, 12],
  textStyle: { color: '#303133', fontSize: 12 },
  axisPointer: { type: 'line', lineStyle: { color: '#c0c4cc', type: 'dashed' } },
}

export const dataZoom = [
  { type: 'inside', start: 0, end: 100 },
  {
    type: 'slider',
    start: 0,
    end: 100,
    height: 18,
    bottom: 8,
    borderColor: '#e4e7ed',
    fillerColor: 'rgba(64,158,255,0.12)',
    handleStyle: { color: '#409eff' },
    textStyle: { color: '#909399', fontSize: 10 },
  },
]

export function xAxis(dates, { showLabel = true, boundaryGap = false } = {}) {
  return {
    type: 'category',
    data: dates,
    boundaryGap,
    axisLine: { lineStyle: { color: '#dcdfe6' } },
    axisTick: { show: false },
    axisLabel: showLabel
      ? { color: '#909399', fontSize: 11, interval: 'auto', hideOverlap: true }
      : { show: false },
  }
}

export function yAxis(name, { formatter, min, max, showSplitLine = true } = {}) {
  return {
    type: 'value',
    name,
    nameTextStyle: { color: '#909399', fontSize: 11 },
    scale: true,
    axisLabel: {
      color: '#909399',
      fontSize: 11,
      ...(formatter ? { formatter } : {}),
    },
    ...(showSplitLine
      ? { splitLine: { lineStyle: { color: '#f0f2f5' } } }
      : { splitLine: { show: false } }),
    ...(min != null ? { min } : {}),
    ...(max != null ? { max } : {}),
  }
}
