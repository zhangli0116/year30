<template>
  <div class="backtest">
    <div class="plan-bar">
      <PlanSwitcher
        :model-value="planId"
        @update:model-value="planId = $event"
        @change="onPlanChange"
      />
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>回测参数</span>
          <span class="header-note">买入式=每期低配补买、超配不卖；卖出式=年末超配卖出回现金；两开关可独立组合（都开/都关/单开）；整手=100份、买0.03%/卖0.07%、min ¥5</span>
        </div>
      </template>

      <div class="controls">
        <div class="ctl">
          <span class="ctl-label">起始日</span>
          <el-date-picker
            v-model="startDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="回测起始日"
            style="width: 150px"
          />
        </div>
        <div class="ctl">
          <span class="ctl-label">每期金额</span>
          <el-input-number
            v-model="amount"
            :min="0"
            :step="1000"
            :precision="0"
            :controls="false"
            style="width: 150px"
          />
        </div>
        <div class="ctl">
          <el-switch v-model="buyRebalance" active-text="买入式再平衡" />
        </div>
        <div class="ctl">
          <el-switch v-model="sellRebalance" active-text="卖出式再平衡" />
        </div>
        <div class="ctl">
          <el-select v-model="unlistedMode" style="width: 190px" title="方案内标的在回测起始时未上市（无历史价）时的处理">
            <el-option label="未上市标的：现金停放" value="park" />
            <el-option label="未上市标的：比例重分配" value="redistribute" />
          </el-select>
        </div>
        <div class="ctl bench-ctl">
          <span class="ctl-label">对比基准</span>
          <el-select v-model="benchmarks" multiple clearable placeholder="选择基准" style="width: 300px">
            <el-option v-for="b in benchmarkList" :key="b.symbol" :label="b.name" :value="b.symbol" />
          </el-select>
        </div>
        <div class="ctl-btns">
          <el-button :loading="syncing" :disabled="!benchmarks.length" @click="syncBenchmarks">
            同步所选基准
          </el-button>
          <el-button :loading="checking" @click="runCoverage">数据覆盖检查</el-button>
          <el-button type="primary" :loading="loading" @click="runBacktest">运行回测</el-button>
        </div>
      </div>

      <!-- 汇总横幅：覆盖不完整时必有提示 -->
      <el-alert
        v-if="coverage && !coverage.ready"
        :type="actionableMissing.length ? 'warning' : 'info'"
        :closable="false"
        class="cov-alert"
        :title="coverageSummary"
      />

      <!-- 可补的真实缺口：警告 + 去补历史 -->
      <el-alert
        v-if="actionableMissing.length"
        type="warning"
        :closable="false"
        class="cov-alert"
        title="以下标的存在缺失的交易日，回测结果可能不完整："
      >
        <div class="cov-body">
          <div class="cov-tags">
            <el-tag
              v-for="it in actionableMissing"
              :key="it.kind + it.code"
              size="small"
              :type="it.kind === 'fund' ? 'warning' : 'info'"
              class="cov-tag"
            >
              {{ it.name }}（{{ missingText(it) }}）
            </el-tag>
          </div>
          <div class="cov-actions">
            <el-button
              v-if="actionableMissing.some((i) => i.kind === 'fund')"
              size="small"
              link
              type="primary"
              @click="router.push('/prices')"
            >
              去基金价格页补历史 →
            </el-button>
            <el-button
              v-if="benchmarks.length && actionableMissing.some((i) => i.kind === 'benchmark')"
              size="small"
              link
              type="primary"
              :loading="syncing"
              @click="syncBenchmarks"
            >
              同步所选基准 →
            </el-button>
          </div>
        </div>
      </el-alert>

      <!-- 数据起点晚于起始日：仅信息提示（多为上市较晚，无需补历史） -->
      <el-alert
        v-if="lateStartItems.length"
        type="info"
        :closable="false"
        class="cov-alert"
        title="以下标的数据起点晚于回测起始日，此前区间它们不参与回测（多为上市较晚）："
      >
        <div class="cov-body">
          <div class="cov-tags">
            <el-tag
              v-for="it in lateStartItems"
              :key="it.kind + it.code"
              size="small"
              type="info"
              class="cov-tag"
            >
              {{ it.name }}（{{ it.first_date || '无数据' }} 起）
            </el-tag>
          </div>
        </div>
      </el-alert>

      <div v-if="warnings.length" class="warnings">
        <el-alert
          v-for="(w, i) in warnings"
          :key="i"
          :title="w"
          type="info"
          :closable="false"
          class="warn-item"
        />
      </div>

      <!-- 指标卡 -->
      <el-row v-if="result" :gutter="16" class="metrics">
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
      <div v-if="result" class="chart-card">
        <div class="chart-title">资产走势</div>
        <div ref="assetChartEl" class="chart-box" v-loading="loading"></div>
      </div>
      <div v-if="result" class="chart-card">
        <div class="chart-title">回撤水下曲线</div>
        <div ref="ddChartEl" class="chart-box" v-loading="loading"></div>
      </div>
      <div v-if="result" class="chart-card">
        <div class="chart-title">基准对比（净值，起点=1）</div>
        <div ref="benchChartEl" class="chart-box" v-loading="loading"></div>
      </div>
      <div v-if="result" class="chart-card">
        <div class="chart-title">持仓占比（各标的 + 现金）</div>
        <div ref="allocChartEl" class="chart-box" v-loading="loading"></div>
      </div>

      <!-- 交易明细 -->
      <div v-if="result" class="chart-card">
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
          <el-table-column label="原因" width="110">
            <template #default="{ row }">
              <span class="muted">{{ row.reason === 'period' ? '每期定投' : '年末再平衡' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import { backtestApi, benchmarksApi, planApi } from '../api'
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

const router = useRouter()

const planId = ref(null)
const startDate = ref('')
const amount = ref(null)
const buyRebalance = ref(true) // 买入式再平衡（每期低配补买）
const sellRebalance = ref(true) // 卖出式再平衡（年末超配卖出）
const unlistedMode = ref('park') // 未上市标的处理：park=现金停放 / redistribute=比例重分配
const benchmarks = ref([])
const benchmarkList = ref([])

const loading = ref(false)
const checking = ref(false)
const syncing = ref(false)
const result = ref(null)
const coverage = ref(null)
const warnings = ref([])

const assetChartEl = ref(null)
const ddChartEl = ref(null)
const benchChartEl = ref(null)
const allocChartEl = ref(null)
let assetChart = null
let ddChart = null
let benchChart = null
let allocChart = null

// ---- 派生 ----
// 覆盖不完整的项，按是否可补拆分：
//   actionable = 存在真实缺失交易日（需同步/补历史）→ 警告 + 去补入口
//   其余       = 仅数据起点晚于起始日（多为上市晚）→ 只做信息提示
const missingItems = computed(() =>
  coverage.value ? coverage.value.items.filter((i) => !i.covers_window) : []
)
const actionableMissing = computed(() => missingItems.value.filter((i) => i.actionable))
const lateStartItems = computed(() => missingItems.value.filter((i) => !i.actionable))
// 覆盖不完整汇总（供顶部横幅）：X 项可补历史、Y 项起点晚
const coverageSummary = computed(() => {
  const act = actionableMissing.value.length
  const late = lateStartItems.value.length
  const parts = []
  if (act) parts.push(`${act} 项存在缺失交易日（可补历史）`)
  if (late) parts.push(`${late} 项数据起点晚于起始日（多为上市较晚）`)
  return parts.length ? `数据覆盖不完整：${parts.join('、')}，详见下方` : ''
})
const m = computed(() => result.value?.metrics || null)
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
  const pts = result.value?.points || []
  return pts.length ? Number(pts[pts.length - 1].nav) : 0
})

// 缺失描述：无数据 / 缺 N 个交易日（首个缺口区间）
function missingText(it) {
  if (!it.missing_days) return '无可用数据'
  const segs = it.segments || []
  if (segs.length) {
    const s = segs[0]
    const range = s.start === s.end ? s.start : `${s.start} ~ ${s.end}`
    return `缺 ${it.missing_days} 个交易日（${range}）`
  }
  return `缺 ${it.missing_days} 个交易日`
}

function threeYearsAgo() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 3)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mm}-${dd}`
}

async function loadPlanDefaults(pid) {
  if (!pid) return
  try {
    const list = await planApi.list()
    const plan = (list || []).find((p) => p.id === pid)
    if (plan) {
      if (plan.amount != null) amount.value = Number(plan.amount)
      if (plan.start_date) startDate.value = plan.start_date
      else if (!startDate.value) startDate.value = threeYearsAgo()
    }
  } catch {
    // 拦截器已提示
  }
}

async function loadBenchmarks() {
  try {
    benchmarkList.value = (await benchmarksApi.list()) || []
    if (!benchmarks.value.length && benchmarkList.value.length) {
      benchmarks.value = [benchmarkList.value[0].symbol] // 默认沪深300
    }
  } catch {
    // 拦截器已提示
  }
}

function onPlanChange() {
  loadPlanDefaults(planId.value)
}

function backtestParams() {
  return {
    plan_id: planId.value,
    start_date: startDate.value,
    end_date: todayStr(),
    ...(amount.value ? { amount: amount.value } : {}),
    ...(benchmarks.value.length ? { benchmarks: benchmarks.value.join(',') } : {}),
    buy_rebalance: buyRebalance.value,
    sell_rebalance: sellRebalance.value,
    unlisted_mode: unlistedMode.value,
  }
}

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 同步所选基准在 [起始日, 今天] 的历史日线，完成后刷新覆盖检查
async function syncBenchmarks() {
  if (!startDate.value || !benchmarks.value.length) return
  syncing.value = true
  try {
    const end = todayStr()
    let total = 0
    for (const symbol of benchmarks.value) {
      const r = await benchmarksApi.sync({ symbol, start_date: startDate.value, end_date: end })
      total += r?.inserted || 0
    }
    ElMessage.success(`已同步 ${benchmarks.value.length} 个基准，新增 ${total} 条日线`)
    await runCoverage()
  } catch {
    // 拦截器已提示
  } finally {
    syncing.value = false
  }
}

async function runCoverage() {
  if (!planId.value || !startDate.value) {
    return
  }
  checking.value = true
  try {
    const params = {
      plan_id: planId.value,
      start_date: startDate.value,
      end_date: todayStr(),
      ...(benchmarks.value.length ? { benchmarks: benchmarks.value.join(',') } : {}),
    }
    coverage.value = await backtestApi.coverage(params)
  } catch {
    // 拦截器已提示
  } finally {
    checking.value = false
  }
}

async function runBacktest() {
  if (!planId.value) return
  if (!startDate.value) {
    return
  }
  loading.value = true
  result.value = null
  warnings.value = []
  disposeCharts() // 释放旧实例：v-if 移除图表 DOM 后实例会挂到脱离元素上
  try {
    const data = await backtestApi.run(backtestParams())
    result.value = data
    warnings.value = data.warnings || []
    await nextTick() // 等 v-if 渲染出图表容器再 init/setOption，否则 chartEl 为 null
    renderAll()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

function disposeCharts() {
  ;[assetChart, ddChart, benchChart, allocChart].forEach((c) => c && c.dispose())
  assetChart = ddChart = benchChart = allocChart = null
}

// ---- 图表 ----
function dates() {
  return (result.value?.points || []).map((p) => p.date)
}

function renderAssetChart() {
  if (!assetChartEl.value) return
  if (!assetChart) assetChart = echarts.init(assetChartEl.value)
  const pts = result.value.points || []
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
  const dd = (result.value.points || []).map((p) => p.drawdown)
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

function renderBenchChart() {
  if (!benchChartEl.value) return
  if (!benchChart) benchChart = echarts.init(benchChartEl.value)
  const ds = dates()
  const navSeries = (result.value.points || []).map((p) => Number(p.nav))
  const pool = [colors.green, colors.orange, colors.red, colors.violet]
  const benchSeries = (result.value.benchmarks || []).map((b, i) =>
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
        data: ['本方案', ...(result.value.benchmarks || []).map((b) => b.name)],
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
  const pts = result.value.points || []
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
      name: k === '000000' ? '现金' : k,
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
  renderBenchChart()
  renderAllocChart()
}

function onResize() {
  assetChart && assetChart.resize()
  ddChart && ddChart.resize()
  benchChart && benchChart.resize()
  allocChart && allocChart.resize()
}

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

onMounted(async () => {
  await loadBenchmarks()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<style scoped>
.plan-bar {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-note {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
.ctl {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ctl-label {
  color: #606266;
  font-size: 13px;
}
.ctl-btns {
  display: flex;
  gap: 8px;
  margin-left: auto;
}
.cov-alert {
  margin-bottom: 12px;
}
.cov-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cov-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cov-actions {
  display: flex;
  gap: 12px;
}
.warnings {
  margin-bottom: 12px;
}
.warn-item {
  margin-bottom: 6px;
}
.metrics {
  margin-bottom: 16px;
}
.m-card {
  text-align: center;
}
.m-label {
  color: #909399;
  font-size: 12px;
  margin-bottom: 8px;
}
.m-big {
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.m-sub {
  color: #c0c4cc;
  font-size: 11px;
  margin-top: 6px;
}
.chart-card {
  margin-bottom: 16px;
}
.chart-title {
  color: #606266;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
}
.chart-box {
  width: 100%;
  height: 360px;
}
.up {
  color: #f56c6c;
}
.down {
  color: #67c23a;
}
.muted {
  color: #c0c4cc;
}
</style>
