<template>
  <div class="prices">
    <el-card shadow="never" class="prices-card">
      <template #header>
        <div class="card-header">
          <div class="card-title">
            <span class="title">基金价格</span>
            <span class="subtitle">K线 · 成交量 · 五档盘口</span>
          </div>
          <div class="header-right">
            <el-select v-model="fundId" placeholder="选择基金" style="width: 200px" @change="onFundChange">
              <el-option
                v-for="f in fundOptions"
                :key="f.id"
                :label="`${f.fund_code} ${f.fund_name}`"
                :value="f.id"
              />
            </el-select>
            <div class="date-inputs">
              <el-date-picker
                v-model="startDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                style="width: 140px"
                @change="onDateChange"
              />
              <span class="to">至</span>
              <el-date-picker
                v-model="endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                style="width: 140px"
                @change="onDateChange"
              />
            </div>
            <el-button type="primary" :loading="syncing" @click="doSync">
              同步缺失价格
            </el-button>
          </div>
        </div>
      </template>

      <!-- 行情概要条（场外基金无实时行情，隐藏） -->
      <div v-if="quote && !isOtc" class="quote-bar">
        <div class="qb-name">{{ fundLabel }}<span class="qb-code">{{ fundCode }}</span></div>
        <div class="qb-price" :class="isUp ? 'up' : 'down'">{{ fmtPrice(quote.last) }}</div>
        <div class="qb-change" :class="isUp ? 'up' : 'down'">
          {{ quote.change >= 0 ? '+' : '' }}{{ fmtPrice(quote.change) }}
          <span class="qb-pct">（{{ quote.change_pct >= 0 ? '+' : '' }}{{ quote.change_pct }}%）</span>
        </div>
        <div class="qb-meta">昨收 {{ fmtPrice(quote.prev_close) }} · 时间 {{ quote.time }}</div>
      </div>

      <el-alert v-if="syncResult" type="success" :closable="false" class="sync-result">
        {{ syncResult }}
      </el-alert>

      <div class="chart-wrap">
        <div class="kline-area">
          <div ref="chartEl" v-loading="chartLoading" class="kline-chart"></div>
          <div v-if="!bars.length && !chartLoading" class="empty-tip">
            该区间暂无价格数据，点「同步缺失价格」从所选数据源拉取。
          </div>
        </div>

        <!-- 右侧五档盘口（场外基金无盘口，隐藏） -->
        <div class="quote-panel" v-if="quote && !isOtc">
          <div class="qp-title">五档盘口</div>
          <div class="qp-group sell">
            <div
              v-for="i in [4, 3, 2, 1, 0]"
              :key="'a' + i"
              class="qp-row"
              :class="{ active: quote.ask[i] === quote.last }"
            >
              <span class="qp-lvl">卖{{ i + 1 }}</span>
              <div class="qp-main">
                <div class="qp-depth sell" :style="{ width: depthPct(quote.ask_vol[i]) }"></div>
                <span class="qp-price sell">{{ fmtPrice(quote.ask[i]) }}</span>
                <span class="qp-vol">{{ fmtVol(quote.ask_vol[i]) }}</span>
              </div>
            </div>
          </div>

          <div class="qp-last">
            <span class="qp-lvl">最新</span>
            <span class="qp-last-val" :class="isUp ? 'up' : 'down'">{{ fmtPrice(quote.last) }}</span>
            <span class="qp-change" :class="isUp ? 'up' : 'down'">
              {{ quote.change >= 0 ? '+' : '' }}{{ quote.change_pct }}%
            </span>
          </div>

          <div class="qp-group buy">
            <div
              v-for="i in [0, 1, 2, 3, 4]"
              :key="'b' + i"
              class="qp-row"
              :class="{ active: quote.bid[i] === quote.last }"
            >
              <span class="qp-lvl">买{{ i + 1 }}</span>
              <div class="qp-main">
                <div class="qp-depth buy" :style="{ width: depthPct(quote.bid_vol[i]) }"></div>
                <span class="qp-price buy">{{ fmtPrice(quote.bid[i]) }}</span>
                <span class="qp-vol">{{ fmtVol(quote.bid_vol[i]) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 同步缺失价格确认弹窗 -->
    <el-dialog
      v-model="syncConfirmVisible"
      title="同步缺失价格"
      width="560px"
      :close-on-click-modal="false"
    >
      <div class="entry-head">
        <div class="entry-head-item">
          <span class="entry-label">基金</span>
          <b class="entry-period">{{ fundLabel }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">日期</span>
          <b>{{ startDate }} 至 {{ endDate }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">数据源</span>
          <b>{{ sourceLabel }}</b>
        </div>
        <div v-if="sourceTip" class="entry-head-item">
          <span class="entry-label">提示</span>
          <b class="muted">{{ sourceTip }}</b>
        </div>
      </div>

      <el-table :data="segList" size="small" stripe class="entry-table">
        <el-table-column prop="start" label="缺失开始日期" />
        <el-table-column prop="end" label="缺失结束日期" />
      </el-table>

      <div class="entry-foot">
        将同步缺失 <b>{{ syncCheck ? syncCheck.missing_days : 0 }}</b> 个工作日（{{ segList.length }} 段）
      </div>
      <div class="entry-hint">含节假日（无行情数据，实际新增以数据源返回为准）。</div>

      <template #footer>
        <el-button @click="syncConfirmVisible = false">取消</el-button>
        <el-button type="primary" :loading="syncing" @click="confirmSync">确认同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { datasourceApi, fundsApi, pricesApi, quotesApi } from '../api'

const fundOptions = ref([])
const fundId = ref(null)
// 数据源配置（设置页按 fund_type 分别配置）；当前基金类型对应的数据源动态取
const dsTypes = ref([])
const currentTypeConfig = computed(() => {
  const ft = fundOptions.value.find((f) => f.id === fundId.value)?.fund_type || 'etf'
  return dsTypes.value.find((t) => t.fund_type === ft)
})
const currentSourceName = computed(() => currentTypeConfig.value?.current || 'tencent')
const currentSourceLabel = computed(() => {
  const t = currentTypeConfig.value
  return (t?.options || []).find((p) => p.name === t?.current)?.label || t?.current || '腾讯行情'
})
const startDate = ref('')
const endDate = ref('')
const syncing = ref(false)
const chartLoading = ref(false)
const syncResult = ref(null)
const bars = ref([]) // [{trade_date, open, high, low, close, volume}]
const quote = ref(null) // 实时五档 {last, bid, ask, bid_vol, ask_vol, time}

// 同步确认弹窗
const syncConfirmVisible = ref(false)
const syncCheck = ref(null) // {missing_days, segments}
const segList = ref([])
const fundLabel = computed(
  () => fundOptions.value.find((f) => f.id === fundId.value)?.fund_name || ''
)
const fundCode = computed(
  () => fundOptions.value.find((f) => f.id === fundId.value)?.fund_code || ''
)
// 场外基金：无 OHLC/五档盘口，价格页改用单位净值折线
const isOtc = computed(
  () => fundOptions.value.find((f) => f.id === fundId.value)?.fund_type === 'otc'
)
const isUp = computed(() => (quote.value ? (quote.value.change_pct ?? 0) >= 0 : true))
const maxVol = computed(() => {
  if (!quote.value) return 1
  const vols = [...(quote.value.bid_vol || []), ...(quote.value.ask_vol || [])]
  return Math.max(1, ...vols.map((v) => Number(v) || 0))
})
function depthPct(v) {
  const n = Number(v) || 0
  return Math.min(100, (n / maxVol.value) * 100) + '%'
}

const chartEl = ref(null)
let chart = null
// 最近一次渲染的数据源 key（基金+日期区间）；变化时重置缩放，仅刷新时保留
let lastRenderKey = ''

function defaultRange() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1)
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return [fmt(start), fmt(now)]
}

function onDateChange() {
  // 校验开始 ≤ 结束
  if (startDate.value && endDate.value && startDate.value > endDate.value) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return
  }
  loadKline()
}

async function loadKline() {
  if (!fundId.value || !startDate.value || !endDate.value) return
  chartLoading.value = true
  try {
    const data = await pricesApi.list({
      fund_id: fundId.value,
      start_date: startDate.value,
      end_date: endDate.value,
    })
    bars.value = data || []
    render()
  } catch {
    // 拦截器已提示
  } finally {
    chartLoading.value = false
  }
}

// 拉取实时五档（含买卖挂单量）；场外基金无盘口，跳过
async function loadQuote() {
  if (isOtc.value) {
    quote.value = null
    return
  }
  const fund = fundOptions.value.find((f) => f.id === fundId.value)
  if (!fund) return
  try {
    const data = await quotesApi.list(fund.fund_code)
    quote.value = data.quotes && data.quotes[0]
  } catch {
    quote.value = null
  }
  // 五档面板出现会让 K线 容器变窄，等 DOM 更新后重算图表尺寸，避免重叠
  await nextTick()
  chart && chart.resize()
}

function fmtPrice(v) {
  return v == null ? '-' : Number(v).toFixed(3)
}

// 成交量/挂单量格式：万手缩略
function fmtVol(v) {
  if (v == null) return '-'
  const n = Number(v)
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  return String(Math.round(n))
}

// 成交量轴刻度/悬停：取整到万（<10000 显示原值），与轴单位"万"保持一致
function fmtVolShort(v) {
  if (v == null) return '-'
  const n = Number(v)
  if (n >= 10000) return Math.round(n / 10000) + '万'
  return String(Math.round(n))
}

function onFundChange() {
  loadKline()
  loadQuote()
}

const sourceLabel = computed(() => currentSourceLabel.value)
const sourceTip = computed(() => {
  const name = currentSourceName.value
  if (name === 'akshare')
    return 'AKShare 非官方数据源，有 1~2s 限流与重试，实时行情较慢'
  if (isOtc.value) return '场外基金无 K 线/盘口，仅同步净值'
  if (name === 'sina')
    return '新浪日线仅支持最近约 4 年，更早历史需切换其他数据源同步'
  return ''
})

// 先检查缺失时间段 → 弹窗确认 → 确认后才实际同步
async function doSync() {
  if (!fundId.value || !startDate.value || !endDate.value) {
    ElMessage.warning('请选择基金和日期范围')
    return
  }
  syncing.value = true
  syncResult.value = null
  try {
    const payload = {
      fund_id: fundId.value,
      start_date: startDate.value,
      end_date: endDate.value,
    }
    // 1) 后端先确认缺失时间段
    const check = await pricesApi.check(payload)
    if (!check.missing_days) {
      syncResult.value = '该区间已全部覆盖，无缺失数据，无需同步。'
      return
    }
    // 2) 弹出自定义确认弹窗
    syncCheck.value = check
    segList.value = check.segments
    syncConfirmVisible.value = true
  } catch {
    // 拦截器已提示
  } finally {
    syncing.value = false
  }
}

// 确认后实际同步
async function confirmSync() {
  if (!syncCheck.value) return
  syncing.value = true
  syncConfirmVisible.value = false
  try {
    const payload = {
      fund_id: fundId.value,
      start_date: startDate.value,
      end_date: endDate.value,
    }
    const r = await pricesApi.sync(payload)
    syncResult.value =
      `数据源「${r.source}」：拉取 ${r.fetched} 条，新增 ${r.inserted} 条，已存在 ${r.existing} 条` +
      (r.inserted > 0 ? '，已刷新图表。' : '。')
    await loadKline()
  } catch {
    // 拦截器已提示
  } finally {
    syncing.value = false
  }
}

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const dates = bars.value.map((b) => b.trade_date)
  // 数据源变化（换基金/改日期区间）→ 重置缩放；仅刷新（如同步后重绘）→ 保留用户缩放
  const key = `${fundId.value}|${startDate.value}|${endDate.value}`
  const forceReset = key !== lastRenderKey || bars.value.length === 0
  lastRenderKey = key
  let zoomStart = 0
  let zoomEnd = 100
  if (!forceReset) {
    const cur = chart.getOption().dataZoom
    const dz = Array.isArray(cur) ? cur[0] : cur
    if (dz && typeof dz.start === 'number' && typeof dz.end === 'number') {
      zoomStart = dz.start
      zoomEnd = dz.end
    }
  }

  // 场外基金：无 OHLC，绘单位净值折线
  if (isOtc.value) {
    const navData = bars.value.map((b) => Number(b.close_price))
    chart.setOption(
      {
        tooltip: { trigger: 'axis' },
        legend: { data: ['累计净值'], top: 0, left: 'center' },
        grid: [{ left: 70, right: 20, top: 40, bottom: 60 }],
        xAxis: [
          {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLabel: { fontSize: 11, hideOverlap: true },
          },
        ],
        yAxis: [{ type: 'value', scale: true }],
        dataZoom: [
          { type: 'inside', xAxisIndex: 0, start: zoomStart, end: zoomEnd },
          { type: 'slider', xAxisIndex: 0, start: zoomStart, end: zoomEnd, height: 20 },
        ],
        series: [
          {
            name: '累计净值',
            type: 'line',
            data: navData,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2, color: '#409eff' },
            itemStyle: { color: '#409eff' },
            areaStyle: { opacity: 0.08 },
          },
        ],
      },
      forceReset
    )
    return
  }

  // ECharts candlestick 数据格式：[open, close, low, high]
  const data = []
  const volData = []
  bars.value.forEach((b) => {
    const o = Number(b.open_price)
    const c = Number(b.close_price)
    const l = Number(b.low_price)
    const h = Number(b.high_price)
    if (!o || !c || !l || !h) {
      // 任一 OHLC 无效（null/0）→ 跳过该 bar（push null，ECharts 断开该段）
      data.push(null)
      volData.push(null)
      return
    }
    data.push([o, c, l, h])
    // 成交量柱：阳线红、阴线绿
    volData.push({
      value: Number(b.volume || 0),
      itemStyle: { color: c >= o ? '#f56c6c' : '#67c23a' },
    })
  })
  chart.setOption(
    {
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: ['日K', '成交量'], top: 0, left: 'center' },
      axisPointer: { link: [{ xAxisIndex: 'all' }] },
      grid: [
        { left: 70, right: 20, top: 40, height: '56%' }, // 主图：K线
        { left: 70, right: 20, top: '72%', height: '14%' }, // 副图：成交量
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          boundaryGap: true,
          axisLabel: { show: false },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: true,
          axisLabel: { fontSize: 11, interval: 'auto', hideOverlap: true },
        },
      ],
      yAxis: [
        { type: 'value', scale: true },
        {
          type: 'value',
          gridIndex: 1,
          scale: true,
          splitLine: { show: false },
          axisLabel: {
            fontSize: 10,
            formatter: fmtVolShort,
          },
        },
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: zoomStart, end: zoomEnd },
        { type: 'slider', xAxisIndex: [0, 1], start: zoomStart, end: zoomEnd, height: 20 },
      ],
      series: [
        {
          name: '日K',
          type: 'candlestick',
          data,
          itemStyle: {
            color: '#f56c6c', // 阳线（涨）
            color0: '#67c23a', // 阴线（跌）
            borderColor: '#f56c6c',
            borderColor0: '#67c23a',
          },
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volData,
          tooltip: { valueFormatter: fmtVolShort },
        },
      ],
    },
    forceReset
  )
}

function onResize() {
  chart && chart.resize()
}

onMounted(async () => {
  try {
    const [fundData, ds] = await Promise.all([
      fundsApi.list({ page: 1, page_size: 100 }),
      datasourceApi.get(),
    ])
    const real = (fundData.items || []).filter((f) => f.fund_code !== '000000')
    fundOptions.value = real
    dsTypes.value = ds.types || []
    if (real.length) fundId.value = real[0].id
    const [sd, ed] = defaultRange()
    startDate.value = sd
    endDate.value = ed
    render()
    await loadKline()
    await loadQuote()
  } catch {
    // 拦截器已提示
  }
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart && chart.dispose()
  chart = null
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.date-inputs {
  display: flex;
  align-items: center;
  gap: 6px;
}
.date-inputs .to {
  color: #909399;
  font-size: 13px;
}
.sync-result {
  margin-bottom: 12px;
}
.chart-wrap {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.kline-area {
  flex: 1;
  min-width: 0;
}
.kline-chart {
  width: 100%;
  height: 560px;
}
.card-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.card-title .title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.card-title .subtitle {
  color: #909399;
  font-size: 12px;
}
.quote-bar {
  display: flex;
  align-items: baseline;
  gap: 16px;
  padding: 12px 16px;
  margin-bottom: 12px;
  background: linear-gradient(90deg, #f5f7fa, #eef3fb);
  border-radius: 8px;
  flex-wrap: wrap;
}
.qb-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.qb-code {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}
.qb-price {
  font-size: 26px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.qb-change {
  font-size: 14px;
  font-weight: 500;
}
.qb-pct {
  font-size: 13px;
}
.qb-meta {
  color: #909399;
  font-size: 12px;
}
.up {
  color: #f56c6c; /* 涨红 */
}
.down {
  color: #67c23a; /* 跌绿 */
}
.quote-panel {
  width: 250px;
  flex-shrink: 0;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  padding: 10px 12px;
  font-size: 13px;
}
.qp-title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.qp-group + .qp-group {
  margin-top: 4px;
}
.qp-row {
  position: relative;
  display: flex;
  align-items: center;
  padding: 3px 0;
}
.qp-row.active {
  outline: 1px solid #409eff;
  outline-offset: -1px;
  border-radius: 3px;
}
.qp-lvl {
  width: 40px;
  color: #909399;
  flex-shrink: 0;
}
.qp-main {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}
.qp-depth {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 2px;
}
.qp-depth.sell {
  right: 0;
  background: rgba(103, 194, 58, 0.18); /* 卖盘绿淡 */
}
.qp-depth.buy {
  left: 0;
  background: rgba(245, 108, 108, 0.18); /* 买盘红淡 */
}
.qp-price {
  flex: 1;
  text-align: right;
  font-variant-numeric: tabular-nums;
  z-index: 1;
}
.qp-price.sell {
  color: #67c23a;
}
.qp-price.buy {
  color: #f56c6c;
}
.qp-vol {
  width: 52px;
  text-align: right;
  color: #909399;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  z-index: 1;
}
.qp-last {
  display: flex;
  align-items: baseline;
  margin: 8px 0;
  padding: 8px 10px;
  background: #f5f7fa;
  border-radius: 6px;
}
.qp-last .qp-lvl {
  width: 40px;
  color: #909399;
}
.qp-last-val {
  flex: 1;
  font-weight: 700;
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}
.qp-change {
  font-size: 13px;
  font-weight: 500;
}
.entry-head {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 6px;
}
.entry-head-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.entry-label {
  color: #909399;
  font-size: 13px;
}
.entry-period {
  font-size: 15px;
  color: #409eff;
}
.entry-table {
  margin-bottom: 12px;
}
.entry-foot {
  font-size: 13px;
  color: #606266;
}
.entry-hint {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
  color: #c0c4cc;
  font-size: 12px;
}
.empty-tip {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 30px 0;
}
</style>
