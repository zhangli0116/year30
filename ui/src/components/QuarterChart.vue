<template>
  <div ref="chartEl" class="quarter-chart"></div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import {
  barSeries,
  colors,
  fmtNum,
  legend,
  lineSeries,
  tooltip,
  xAxis,
  yAxis,
} from '../utils/chart'

// props：quarters(季度列表)、purchases(购买记录)、prices(fund_code->当前价)、funds(summary.funds)
const props = defineProps({
  quarters: { type: Array, default: () => [] },
  purchases: { type: Array, default: () => [] },
  prices: { type: Object, default: () => ({}) },
  funds: { type: Array, default: () => [] },
})

const chartEl = ref(null)
let chart = null

// 按季度序列化：总投入=Σ预算累计；市值=到该季度为止持有份额×当前价+累计现金；
// 权益占比=权益市值/总市值。因无历史价格，统一用「今天最新价」作市值基准。
const series = computed(() => {
  const qs = [...props.quarters].sort((a, b) => (a.start_date < b.start_date ? -1 : 1))
  const fundIdToCode = Object.fromEntries((props.funds || []).map((f) => [f.fund_id, f.fund_code]))
  const priceMap = props.prices || {}
  const sorted = [...(props.purchases || [])].sort((a, b) =>
    a.purchase_date < b.purchase_date ? -1 : 1
  )

  const labels = []
  const invested = []
  const marketValue = []
  const equityRatio = []
  const shares = {} // fund_id -> 累计份额（买+卖-）
  let pIdx = 0
  let cumBudget = 0
  let cumCash = 0

  for (const q of qs) {
    const endDate = q.end_date || '9999-12-31'
    while (pIdx < sorted.length && sorted[pIdx].purchase_date <= endDate) {
      const rec = sorted[pIdx]
      const sign = rec.type === 'sell' ? -1 : 1
      shares[rec.fund_id] = (shares[rec.fund_id] || 0) + sign * rec.hands * rec.shares_per_hand
      pIdx++
    }
    let mv = 0
    for (const [fid, sh] of Object.entries(shares)) {
      if (sh <= 0) continue
      const code = fundIdToCode[fid]
      const price = priceMap[code]
      if (price != null) mv += sh * price
    }
    cumBudget += Number(q.budget || 0)
    cumCash += Number(q.cash_amount || 0)
    const total = mv + cumCash
    labels.push(q.start_date || q.period)
    invested.push(cumBudget)
    marketValue.push(+total.toFixed(2))
    equityRatio.push(total > 0 ? +((mv / total) * 100).toFixed(2) : null)
  }
  return { labels, invested, marketValue, equityRatio }
})

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const s = series.value
  chart.setOption(
    {
      tooltip,
      legend: { ...legend, data: ['总投入', '总市值', '权益占比'] },
      // 上下两个窗格共享 x 轴（small multiples），避免双 y 轴误导比较
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 64, right: 24, top: 44, height: '52%' }, // 上：金额线
        { left: 64, right: 24, top: '68%', height: '22%' }, // 下：权益占比柱
      ],
      xAxis: [
        { ...xAxis(s.labels, { showLabel: false, boundaryGap: true }), gridIndex: 0 },
        { ...xAxis(s.labels, { boundaryGap: true }), gridIndex: 1 },
      ],
      yAxis: [
        yAxis('金额（元）', { formatter: (v) => fmtNum(v) }),
        {
          ...yAxis('权益占比（%）', {
            formatter: (v) => v + '%',
            min: 0,
            max: 100,
          }),
          gridIndex: 1,
        },
      ],
      series: [
        lineSeries('总投入', s.invested, colors.orange, {
          gradient: false,
          dashed: true,
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
        lineSeries('总市值', s.marketValue, colors.blue, {
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
        barSeries('权益占比', s.equityRatio, colors.violet, {
          xAxisIndex: 1,
          yAxisIndex: 1,
          tooltipFormatter: (v) => (v == null ? '-' : v + '%'),
        }),
      ],
    },
    true
  )
}

function onResize() {
  chart && chart.resize()
}

watch(series, render, { deep: true })

onMounted(() => {
  render()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})
</script>

<style scoped>
.quarter-chart {
  width: 100%;
  height: 400px;
}
</style>
