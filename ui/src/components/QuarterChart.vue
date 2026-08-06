<template>
  <div ref="chartEl" class="quarter-chart"></div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

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
      tooltip: { trigger: 'axis' },
      legend: { data: ['总投入', '总市值', '权益占比'], top: 0, left: 'center' }, // legend 置顶
      grid: { left: 70, right: 60, top: 40, bottom: 40 },
      xAxis: { type: 'category', data: s.labels, axisLabel: { fontSize: 12 } },
      yAxis: [
        { type: 'value', name: '金额（元）' },
        {
          type: 'value',
          name: '权益占比（%）',
          min: 0,
          max: 100,
          splitLine: { show: false },
        },
      ],
      series: [
        { name: '总投入', type: 'line', smooth: true, data: s.invested, itemStyle: { color: '#909399' } },
        { name: '总市值', type: 'line', smooth: true, data: s.marketValue, itemStyle: { color: '#409eff' } },
        {
          name: '权益占比',
          type: 'bar',
          yAxisIndex: 1,
          data: s.equityRatio,
          itemStyle: { color: '#e6a23c', opacity: 0.5 },
        },
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
  height: 360px;
}
</style>
