<template>
  <div class="prices">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>基金价格</span>
          <div class="header-right">
            <el-select v-model="fundId" placeholder="选择基金" style="width: 200px" @change="loadKline">
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
                style="width: 150px"
                @change="onDateChange"
              />
              <span class="to">至</span>
              <el-date-picker
                v-model="endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                style="width: 150px"
                @change="onDateChange"
              />
            </div>
            <el-select v-model="source" placeholder="数据源" style="width: 170px">
              <el-option
                v-for="s in sources"
                :key="s.name"
                :label="s.label"
                :value="s.name"
              />
            </el-select>
            <el-button type="primary" :loading="syncing" @click="doSync">
              同步缺失价格
            </el-button>
          </div>
        </div>
      </template>

      <el-alert v-if="syncResult" type="success" :closable="false" class="sync-result">
        {{ syncResult }}
      </el-alert>

      <div ref="chartEl" v-loading="chartLoading" class="kline-chart"></div>
      <div v-if="!bars.length && !chartLoading" class="empty-tip">
        该区间暂无价格数据，点「同步缺失价格」从所选数据源拉取。
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { fundsApi, pricesApi } from '../api'

const fundOptions = ref([])
const sources = ref([])
const fundId = ref(null)
const source = ref('tencent')
const startDate = ref('')
const endDate = ref('')
const syncing = ref(false)
const chartLoading = ref(false)
const syncResult = ref(null)
const bars = ref([]) // [{trade_date, open, high, low, close}]

// 同步确认弹窗
const syncConfirmVisible = ref(false)
const syncCheck = ref(null) // {missing_days, segments}
const segList = ref([])
const fundLabel = computed(
  () => fundOptions.value.find((f) => f.id === fundId.value)?.fund_name || ''
)

const chartEl = ref(null)
let chart = null

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

const sourceLabel = computed(
  () => sources.value.find((s) => s.name === source.value)?.label || source.value
)

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
      source: source.value,
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
      source: source.value,
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
  // ECharts candlestick 数据格式：[open, close, low, high]
  const data = bars.value.map((b) => [
    Number(b.open_price),
    Number(b.close_price),
    Number(b.low_price),
    Number(b.high_price),
  ])
  chart.setOption(
    {
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: ['日K'], top: 0, left: 'center' }, // legend 置顶，避免被底部滑块挡住
      grid: { left: 70, right: 20, top: 40, bottom: 60 },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLabel: { fontSize: 11, interval: 'auto', hideOverlap: true },
      },
      yAxis: { type: 'value', scale: true },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 20 },
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
      ],
    },
    true
  )
}

function onResize() {
  chart && chart.resize()
}

onMounted(async () => {
  try {
    const [fundData, sourceData] = await Promise.all([
      fundsApi.list({ page: 1, page_size: 100 }),
      pricesApi.sources(),
    ])
    const real = (fundData.items || []).filter((f) => f.fund_code !== '000000')
    fundOptions.value = real
    sources.value = sourceData || []
    if (real.length) fundId.value = real[0].id
    const [sd, ed] = defaultRange()
    startDate.value = sd
    endDate.value = ed
    render()
    await loadKline()
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
.kline-chart {
  width: 100%;
  height: 520px;
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
