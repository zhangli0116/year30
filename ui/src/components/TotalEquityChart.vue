<template>
  <div ref="chartEl" class="total-equity-chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { cashApi, holdingsApi } from '../api'

// 3 条走势（按日）：
//   总权益：历史来自 fund_holding_daily（跨基金求和），今日用实时价×份额覆盖
//   总资产：总权益 + 当日现金（fund_cash_daily.cash_amount）
//   累积投入：各季度 budget 的累计（quarter.start_date 入账）
const props = defineProps({
  todayEquity: { type: Number, default: null },
  quarters: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chart = null
const series = ref({ dates: [], equity: [], asset: [], invested: [] })

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function load() {
  const end = todayStr()
  try {
    const [holdData, cashData] = await Promise.all([
      holdingsApi.total({ start_date: '2024-01-01', end_date: end }),
      cashApi.list({ start_date: '2024-01-01', end_date: end }),
    ])
    const equityMap = Object.fromEntries((holdData || []).map((r) => [r.trade_date, Number(r.total_equity)]))
    const cashMap = Object.fromEntries((cashData || []).map((r) => [r.trade_date, Number(r.cash_amount)]))
    const budgetEvents = (props.quarters || [])
      .filter((q) => q.start_date && Number(q.budget))
      .map((q) => [q.start_date, Number(q.budget)])
      .sort((a, b) => (a[0] < b[0] ? -1 : 1))

    // 日期轴 = 权益日期 ∪ 现金日期 ∪ 预算日期 ∪ 今天
    const dateSet = new Set([...Object.keys(equityMap), ...Object.keys(cashMap), ...budgetEvents.map((e) => e[0])])
    if (props.todayEquity != null) dateSet.add(end)
    const sortedDates = [...dateSet].sort((a, b) => (a < b ? -1 : 1))

    // 逐日推进：权益/现金按最近值填充，投入按预算累计
    let lastEquity = 0
    let lastCash = 0
    let invested = 0
    let bIdx = 0
    const equityLine = []
    const assetLine = []
    const investedLine = []
    for (const d of sortedDates) {
      if (d in equityMap) lastEquity = equityMap[d]
      if (d in cashMap) lastCash = cashMap[d]
      while (bIdx < budgetEvents.length && budgetEvents[bIdx][0] <= d) {
        invested += budgetEvents[bIdx][1]
        bIdx += 1
      }
      // 今日实时权益覆盖（3 点前未收盘）
      if (d === end && props.todayEquity != null) lastEquity = props.todayEquity
      equityLine.push(lastEquity)
      assetLine.push(lastEquity + lastCash)
      investedLine.push(invested)
    }
    series.value = { dates: sortedDates, equity: equityLine, asset: assetLine, invested: investedLine }
    render()
  } catch {
    // 拦截器已提示
  }
}

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: { data: ['总权益', '总资产（权益+现金）', '累积投入'], top: 0, left: 'center' },
      grid: { left: 70, right: 30, top: 40, bottom: 60 },
      xAxis: {
        type: 'category',
        data: series.value.dates,
        boundaryGap: false,
        axisLabel: { fontSize: 11, interval: 'auto', hideOverlap: true },
      },
      yAxis: { type: 'value', name: '金额（元）', scale: true },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 22, bottom: 12 },
      ],
      series: [
        { name: '总权益', type: 'line', smooth: true, data: series.value.equity, areaStyle: { opacity: 0.1 }, itemStyle: { color: '#409eff' } },
        { name: '总资产（权益+现金）', type: 'line', smooth: true, data: series.value.asset, itemStyle: { color: '#67c23a' } },
        { name: '累积投入', type: 'line', smooth: true, data: series.value.invested, itemStyle: { color: '#e6a23c' } },
      ],
    },
    true
  )
}

function onResize() {
  chart && chart.resize()
}

watch(() => [props.todayEquity, props.quarters], load)

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})
</script>

<style scoped>
.total-equity-chart {
  width: 100%;
  height: 380px;
}
</style>
