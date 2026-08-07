<template>
  <div class="holdings">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>每日权益流水</span>
          <div class="header-right">
            <PlanSwitcher
              :model-value="planId"
              @update:model-value="planId = $event"
              @change="onPlanChange"
            />
            <el-select v-model="fundId" placeholder="选择基金" style="width: 200px" @change="loadHoldings">
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
                @change="loadHoldings"
              />
              <span class="to">至</span>
              <el-date-picker
                v-model="endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                style="width: 150px"
                @change="loadHoldings"
              />
            </div>
            <el-button type="success" :loading="generating" @click="generateHoldings">
              生成权益流水
            </el-button>
            <span v-if="note" class="header-note">{{ note }}</span>
          </div>
        </div>
      </template>

      <div ref="chartEl" v-loading="loading" class="equity-chart"></div>
      <div v-if="!holdings.length && !loading" class="empty-tip">
        暂无权益流水，点「生成权益流水」按所选基金与日期范围生成（需先有历史价格）。
      </div>
    </el-card>

    <!-- 生成权益流水确认弹窗 -->
    <el-dialog
      v-model="genConfirmVisible"
      title="生成权益流水"
      width="480px"
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
      </div>
      <div class="entry-foot" v-if="genCheck">
        将生成缺失的 <b>{{ genCheck.missing_days }}</b> 个交易日
        <span v-if="genCheck.missing_start">（{{ genCheck.missing_start }} ~ {{ genCheck.missing_end }}）</span>
      </div>
      <div class="entry-hint">
        每日权益流水需先有历史价格，仅交易日生成；已有日期会更新。
      </div>
      <template #footer>
        <el-button @click="genConfirmVisible = false">取消</el-button>
        <el-button type="success" :loading="generating" @click="confirmGenerate">确认生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { fundsApi, holdingsApi } from '../api'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import {
  averageMarkLine,
  colors,
  dataZoom,
  fmtNum,
  gridSlim,
  lineSeries,
  tooltip,
  xAxis,
  yAxis,
} from '../utils/chart'

const planId = ref(null)
const fundOptions = ref([])
const fundId = ref(null)
const startDate = ref('')
const endDate = ref('')
// 按当前方案过滤（缺省不带 plan_id 时后端回退默认方案）
const planParams = () => (planId.value ? { plan_id: planId.value } : {})
const generating = ref(false)
const loading = ref(false)
const note = ref('')
const holdings = ref([]) // [{trade_date, total_hands, total_shares, price, equity_amount}]
const genConfirmVisible = ref(false)
const genCheck = ref(null) // {missing_days, missing_start, missing_end}
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

async function generateHoldings() {
  if (!fundId.value || !startDate.value || !endDate.value) {
    return
  }
  // 先检查缺失的交易日
  const check = await holdingsApi.check({
    fund_id: fundId.value,
    start_date: startDate.value,
    end_date: endDate.value,
    ...planParams(),
  })
  if (!check.missing_days) {
    note.value = '该区间已全部生成，无缺失。'
    return
  }
  genCheck.value = check
  genConfirmVisible.value = true
}

async function confirmGenerate() {
  genConfirmVisible.value = false
  generating.value = true
  try {
    const r = await holdingsApi.generate({
      fund_id: fundId.value,
      start_date: startDate.value,
      end_date: endDate.value,
      ...planParams(),
    })
    note.value = `已生成 ${r.generated} 个交易日的权益流水`
    await loadHoldings()
  } catch {
    // 拦截器已提示
  } finally {
    generating.value = false
  }
}

async function loadHoldings() {
  if (!fundId.value || !startDate.value || !endDate.value) return
  loading.value = true
  try {
    holdings.value =
      (await holdingsApi.list({
        fund_id: fundId.value,
        start_date: startDate.value,
        end_date: endDate.value,
        ...planParams(),
      })) || []
  } catch {
    holdings.value = []
  } finally {
    loading.value = false
  }
  render()
}

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const dates = holdings.value.map((h) => h.trade_date)
  const values = holdings.value.map((h) => Number(h.equity_amount))
  chart.setOption(
    {
      tooltip,
      grid: gridSlim,
      xAxis: xAxis(dates),
      yAxis: yAxis('权益金额（元）', { formatter: (v) => fmtNum(v) }),
      dataZoom,
      series: [
        {
          ...lineSeries('权益市值', values, colors.blue, {
            tooltipFormatter: (v) => fmtNum(v, 2),
          }),
          markLine: averageMarkLine(),
        },
      ],
    },
    true
  )
}

function onResize() {
  chart && chart.resize()
}

// 方案切换：按新方案重拉权益流水
function onPlanChange() {
  loadHoldings()
}

onMounted(async () => {
  try {
    const data = await fundsApi.list({ page: 1, page_size: 100 })
    const real = (data.items || []).filter((f) => f.fund_code !== '000000')
    fundOptions.value = real
    if (real.length) fundId.value = real[0].id
    const [sd, ed] = defaultRange()
    startDate.value = sd
    endDate.value = ed
    render()
    await loadHoldings()
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
.header-note {
  color: #909399;
  font-size: 12px;
}
.equity-chart {
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
