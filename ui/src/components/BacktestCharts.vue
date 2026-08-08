<template>
  <div v-if="result">
    <!-- 指标卡 -->
    <el-row :gutter="16" class="metrics">
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">
            <el-tooltip content="资金加权年化收益率：把每期投入按实际时间点折算，衡量『这些投入到现在，年化回报多少』。持有期短时会被放大，需结合天数看。" placement="top">
              <span>XIRR 年化</span>
            </el-tooltip>
          </div>
          <div class="m-big" :class="numOr(xirr, 0) >= 0 ? 'up' : 'down'">{{ fmtXirr(xirr) }}</div>
          <div class="m-sub">资金加权 · 基于 {{ result.metrics.span_days }} 天</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">
            <el-tooltip content="时间加权收益率（期间，非年化）：剥离投入时点的影响，衡量策略本身的累计涨跌，短中期波动真实、不会被年化放大。" placement="top">
              <span>TWR 期间</span>
            </el-tooltip>
          </div>
          <div class="m-big" :class="numOr(twr, 0) >= 0 ? 'up' : 'down'">{{ fmtPct(twr) }}</div>
          <div class="m-sub">年化 {{ fmtPct(twrAnnualized) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">最大回撤</div>
          <div class="m-big down">{{ fmtPct(maxDD) }}</div>
          <div class="m-sub">{{ ddRange }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">累计投入</div>
          <div class="m-big">{{ money(invested) }}</div>
          <div class="m-sub">{{ result.metrics.deposit_count }} 期</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">当前市值</div>
          <div class="m-big">{{ money(currentValue) }}</div>
          <div class="m-sub">净值 {{ navLast.toFixed(3) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="m-card">
          <div class="m-label">累计收益</div>
          <div class="m-big" :class="numOr(gain, 0) >= 0 ? 'up' : 'down'">{{ signedMoney(gain) }}</div>
          <div class="m-sub">{{ fmtGainPct(gainPct) }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表 -->
    <div class="chart-card">
      <div class="chart-title">资产走势</div>
      <div ref="assetChartEl" class="chart-box" v-loading="loading"></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">回撤水下曲线（距峰值跌幅）</div>
      <div ref="ddChartEl" class="chart-box" v-loading="loading"></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">水上曲线（近 1 月涨幅 · 回调风险）</div>
      <div ref="duChartEl" class="chart-box" v-loading="loading"></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">基准对比（净值，起点=1）</div>
      <div ref="benchChartEl" class="chart-box" v-loading="loading"></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">持仓占比（各标的 + 现金）</div>
      <div ref="allocChartEl" class="chart-box" v-loading="loading"></div>
    </div>

    <!-- 交易明细 -->
    <div class="chart-card">
      <div class="chart-title">交易明细（{{ result.trades.length }} 笔）</div>
      <el-table :data="result.trades" size="small" stripe max-height="320">
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="fund_code" label="代码" width="90" />
        <el-table-column prop="fund_name" label="名称" min-width="120" />
        <el-table-column label="方向" width="70">
          <template #default="{ row }">
            <el-tag size="small" :type="row.side === 'buy' ? 'success' : 'danger'" effect="plain">
              {{ row.side === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="hands" label="手数" width="70" align="right" />
        <el-table-column label="单价" width="90" align="right">
          <template #default="{ row }">{{ Number(row.price).toFixed(3) }}</template>
        </el-table-column>
        <el-table-column label="本金" width="110" align="right">
          <template #default="{ row }">¥{{ money(row.principal) }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="90" align="right">
          <template #default="{ row }">¥{{ money(row.fee) }}</template>
        </el-table-column>
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }">¥{{ money(row.total_amount) }}</template>
        </el-table-column>
        <el-table-column label="金额缩放" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.amount_mult != null && row.amount_mult !== 1" :class="row.amount_mult > 1 ? 'up' : 'down'">
              ×{{ Number(row.amount_mult).toFixed(2) }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="原因" width="110">
          <template #default="{ row }">
            <span class="muted">{{ row.reason === 'period' ? '每期定投' : '年末再平衡' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import {
  colors,
  dataZoom,
  fmtNum,
  grid,
  legend,
  lineSeries,
  signedArea,
  tooltip,
  xAxis,
  yAxis,
} from '../utils/chart'

const props = defineProps({
  result: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  // 基金代码 → 名称映射（持仓占比图用名称展示；缺省回退代码）
  fundNameMap: { type: Object, default: () => ({}) },
})

// ---- 指标卡派生 ----
const m = computed(() => props.result?.metrics || null)
const xirr = computed(() => (m.value ? m.value.xirr : null))
const twr = computed(() => (m.value ? m.value.twr : null))
const twrAnnualized = computed(() => (m.value ? m.value.twr_annualized : null))
const maxDD = computed(() => (m.value ? m.value.max_drawdown : null))
const ddRange = computed(() => {
  if (!m.value) return ''
  const { max_drawdown_start: s, max_drawdown_end: e } = m.value
  return s && e ? `${s} ~ ${e}` : '—'
})
const invested = computed(() => (m.value ? m.value.invested : 0))
const currentValue = computed(() => (m.value ? m.value.current_value : 0))
const gain = computed(() => (m.value ? m.value.gain : 0))
const gainPct = computed(() => (m.value ? m.value.gain_pct : null))
const navLast = computed(() => {
  const pts = props.result?.points || []
  return pts.length ? Number(pts[pts.length - 1].nav) : 0
})

// ---- 图表 ----
const assetChartEl = ref(null)
const ddChartEl = ref(null)
const duChartEl = ref(null)
const benchChartEl = ref(null)
const allocChartEl = ref(null)
let assetChart = null
let ddChart = null
let duChart = null
let benchChart = null
let allocChart = null

function dates() {
  return (props.result?.points || []).map((p) => p.date)
}

function renderAssetChart() {
  if (!assetChartEl.value) return
  if (!assetChart) assetChart = echarts.init(assetChartEl.value)
  const pts = props.result.points || []
  const ds = dates()
  assetChart.setOption(
    {
      tooltip,
      legend: { ...legend, data: ['总资产', '累计投入'] },
      grid,
      xAxis: xAxis(ds),
      yAxis: yAxis('金额（元）', { formatter: (v) => fmtNum(v) }),
      dataZoom,
      series: [
        lineSeries('总资产', pts.map((p) => Number(p.asset)), colors.blue, {
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
        lineSeries('累计投入', pts.map((p) => Number(p.invested)), colors.orange, {
          gradient: false,
          dashed: true,
          tooltipFormatter: (v) => fmtNum(v, 2),
        }),
      ],
    },
    true
  )
}

function renderDDChart() {
  if (!ddChartEl.value) return
  if (!ddChart) ddChart = echarts.init(ddChartEl.value)
  const ds = dates()
  const dd = (props.result.points || []).map((p) => p.drawdown)
  const pct = (v) => `${(v * 100).toFixed(1)}%`
  ddChart.setOption(
    {
      tooltip: { ...tooltip, valueFormatter: (v) => (v == null ? '-' : pct(v)) },
      legend: { ...legend, data: ['回撤'] },
      grid,
      xAxis: xAxis(ds),
      yAxis: yAxis('回撤', { formatter: pct }),
      dataZoom,
      series: signedArea('回撤', dd),
    },
    true
  )
}

function renderDUChart() {
  if (!duChartEl.value) return
  if (!duChart) duChart = echarts.init(duChartEl.value)
  const ds = dates()
  const du = (props.result.points || []).map((p) => p.drawup)
  const pct = (v) => `${(v * 100).toFixed(1)}%`
  duChart.setOption(
    {
      tooltip: { ...tooltip, valueFormatter: (v) => (v == null ? '-' : pct(v)) },
      legend: { ...legend, data: ['水上'] },
      grid,
      xAxis: xAxis(ds),
      yAxis: yAxis('水上', { formatter: pct }),
      dataZoom,
      series: signedArea('水上', du),
    },
    true
  )
}

function renderBenchChart() {
  if (!benchChartEl.value) return
  if (!benchChart) benchChart = echarts.init(benchChartEl.value)
  const ds = dates()
  const navSeries = (props.result.points || []).map((p) => Number(p.nav))
  const pool = [colors.green, colors.orange, colors.red, colors.violet]
  const benchSeries = (props.result.benchmarks || []).map((b, i) =>
    lineSeries(b.name, b.nav_series.map((n) => n.nav), pool[i % pool.length], {
      gradient: false,
      width: 1.5,
      tooltipFormatter: (v) => (v == null ? '-' : v.toFixed(3)),
    })
  )
  benchChart.setOption(
    {
      tooltip: {
        ...tooltip,
        valueFormatter: (v) => (v == null ? '-' : v.toFixed(3)),
      },
      legend: {
        ...legend,
        data: ['本方案', ...(props.result.benchmarks || []).map((b) => b.name)],
      },
      grid,
      xAxis: xAxis(ds),
      yAxis: yAxis('净值（起点=1）', { formatter: (v) => v.toFixed(2) }),
      dataZoom,
      series: [
        lineSeries('本方案', navSeries, colors.blue, {
          gradient: false,
          width: 2.5,
          tooltipFormatter: (v) => v.toFixed(3),
        }),
        ...benchSeries,
      ],
    },
    true
  )
}

// 持仓占比 stacked area：现金置底，各标的按代码排序，逐日占比合计 100%
function renderAllocChart() {
  if (!allocChartEl.value) return
  if (!allocChart) allocChart = echarts.init(allocChartEl.value)
  const pts = props.result.points || []
  const ds = dates()
  const fundKeys = Object.keys(pts[0]?.allocations || {})
    .filter((k) => k !== '000000')
    .sort()
  const keys = ['000000', ...fundKeys]
  // 现金固定灰色；基金用不含 gray 的独立色池循环（≥8 只才可能彼此重复，永不与现金撞色）
  const fundPool = [
    colors.blue,
    colors.green,
    colors.orange,
    colors.red,
    colors.violet,
    '#00bcd4', // cyan
    '#9c27b0', // magenta
    '#8d6e63', // brown
  ]
  const series = keys.map((k, idx) => {
    const color = k === '000000' ? colors.gray : fundPool[(idx - 1) % fundPool.length]
    return {
      name: k === '000000' ? '现金' : (props.fundNameMap[k] || k),
      type: 'line',
      stack: 'all',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 0 },
      itemStyle: { color },
      areaStyle: { color, opacity: 0.72 },
      emphasis: { focus: 'series' },
      data: pts.map((p) => Number(p.allocations?.[k] ?? 0)),
    }
  })
  const pct = (v) => (v == null ? '-' : `${v}%`)
  allocChart.setOption(
    {
      tooltip: { ...tooltip, valueFormatter: (v) => (v == null ? '-' : pct(v)) },
      legend: { ...legend, data: series.map((s) => s.name) },
      grid,
      xAxis: xAxis(ds),
      yAxis: yAxis('占比（%）', { formatter: pct, min: 0, max: 100 }),
      dataZoom,
      series,
    },
    true
  )
}

function renderAll() {
  renderAssetChart()
  renderDDChart()
  renderDUChart()
  renderBenchChart()
  renderAllocChart()
}

function disposeCharts() {
  ;[assetChart, ddChart, duChart, benchChart, allocChart].forEach((c) => c && c.dispose())
  assetChart = ddChart = duChart = benchChart = allocChart = null
}

function onResize() {
  assetChart && assetChart.resize()
  ddChart && ddChart.resize()
  duChart && duChart.resize()
  benchChart && benchChart.resize()
  allocChart && allocChart.resize()
}

watch(
  () => props.result,
  async () => {
    if (!props.result) return
    disposeCharts() // 释放旧实例，等 DOM 更新后重建
    await nextTick()
    renderAll()
  },
  { immediate: true }
)

onMounted(() => {
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})

// ---- 格式化 ----
function numOr(v, d) {
  return v == null ? d : Number(v)
}
function fmtXirr(v) {
  return v == null ? '—' : `${(v * 100).toFixed(2)}%`
}
function fmtPct(v) {
  if (v == null) return '—'
  const n = Number(v)
  return `${(n >= 0 ? '+' : '')}${(n * 100).toFixed(2)}%`
}
// gain_pct 后端返回的已是百分比数值（如 13.46 表示 13.46%），直接显示不再乘 100
function fmtGainPct(v) {
  if (v == null) return '—'
  const n = Number(v)
  return `${(n >= 0 ? '+' : '')}${n.toFixed(2)}%`
}
function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}
function signedMoney(v) {
  const n = Number(v || 0)
  const abs = Math.abs(n).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return `${n >= 0 ? '+' : '-'}${abs}`
}
</script>

<style scoped>
.metrics {
  margin-bottom: 8px;
}
.m-card :deep(.el-card__body) {
  padding: 14px 16px;
}
.m-label {
  color: #909399;
  font-size: 12px;
  margin-bottom: 6px;
}
.m-big {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.m-sub {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.up {
  color: #f56c6c;
}
.down {
  color: #67c23a;
}
.chart-card {
  margin-bottom: 16px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #409eff;
}
.chart-box {
  width: 100%;
  height: 380px;
}
.muted {
  color: #c0c4cc;
}
</style>
