<template>
  <div ref="chartEl" class="total-equity-chart"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { cashApi, holdingsApi } from '../api'
import {
  colors,
  dataZoom,
  fmtNum,
  grid,
  legend,
  lineSeries,
  tooltip,
  xAxis,
  yAxis,
} from '../utils/chart'

// 3 条走势（按日）：
//   总权益：历史来自 fund_holding_daily（跨基金求和），今日用实时价×份额覆盖
//   总资产：总权益 + 当日现金（fund_cash_daily.cash_amount）
//   累积投入：各季度 budget 的累计（quarter.start_date 入账）
const props = defineProps({
  todayEquity: { type: Number, default: null },
  quarters: { type: Array, default: () => [] },
  planId: { type: [Number, String], default: null },
})

const chartEl = ref(null)
let chart = null
const series = ref({ dates: [], equity: [], asset: [], invested: [] })

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function load() {
  // planId 未定时不发请求：不带 plan_id 的 /holdings/total 会汇总全部方案、
  // /cash 会回退到第一个方案，两者口径不一致，等 planId 有值再加载
  if (props.planId == null) {
    series.value = { dates: [], equity: [], asset: [], invested: [] }
    render()
    return
  }
  const end = todayStr()
  const params = { start_date: '2024-01-01', end_date: end, plan_id: props.planId } // 走势随方案
  try {
    const [holdData, cashData] = await Promise.all([
      holdingsApi.total(params),
      cashApi.list(params),
    ])
    const equityMap = Object.fromEntries((holdData || []).map((r) => [r.trade_date, Number(r.total_equity)]))
    const cashMap = Object.fromEntries((cashData || []).map((r) => [r.trade_date, Number(r.cash_amount)]))
    const budgetEvents = (props.quarters || [])
      .filter((q) => q.start_date && Number(q.budget))
      .map((q) => [q.start_date, Number(q.budget)])
      .sort((a, b) => (a[0] < b[0] ? -1 : 1))

    // 日期轴 = 交易日（以权益流水为准）∪ 预算入账日 ∪ 今天
    // 现金虽逐日历日产生，但并入交易日轴、按交易日取值/前值填充，
    // 避免周末/节假日进入 x 轴造成权益/资产线出现平直台阶
    const dateSet = new Set([...Object.keys(equityMap), ...budgetEvents.map((e) => e[0])])
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
      // 今日实时权益覆盖（3 点前未收盘）；null 或 0（行情失败）时沿用 DB 历史值，不坠 0
      if (d === end && props.todayEquity != null && props.todayEquity > 0) lastEquity = props.todayEquity
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
      tooltip,
      legend: { ...legend, data: ['总权益', '总资产（权益+现金）', '累积投入'] },
      grid,
      xAxis: xAxis(series.value.dates),
      yAxis: yAxis('金额（元）', { formatter: (v) => fmtNum(v) }),
      dataZoom,
      series: [
        lineSeries('总权益', series.value.equity, colors.blue, { tooltipFormatter: (v) => fmtNum(v, 2) }),
        lineSeries('总资产（权益+现金）', series.value.asset, colors.green, {
          gradient: false,
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
        lineSeries('累积投入', series.value.invested, colors.orange, {
          gradient: false,
          dashed: true,
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
      ],
    },
    true
  )
}

function onResize() {
  chart && chart.resize()
}

watch(() => [props.todayEquity, props.quarters, props.planId], load)

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
