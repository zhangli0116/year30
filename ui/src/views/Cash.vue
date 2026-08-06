<template>
  <div class="cash-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>每日现金流量</span>
          <div class="header-right">
            <div class="date-inputs">
              <el-date-picker
                v-model="startDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始日期"
                style="width: 150px"
                @change="loadCash"
              />
              <span class="to">至</span>
              <el-date-picker
                v-model="endDate"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束日期"
                style="width: 150px"
                @change="loadCash"
              />
            </div>
            <el-button type="success" :loading="generating" @click="generateCash">
              生成现金流量
            </el-button>
            <span v-if="note" class="header-note">{{ note }}</span>
          </div>
        </div>
      </template>

      <div ref="chartEl" v-loading="loading" class="cash-chart"></div>
      <div v-if="!rows.length && !loading" class="empty-tip">
        暂无现金流量，点「生成现金流量」按日期范围生成（每日增量 = 预算 − 买入支出 + 卖出回笼 − 手续费）。
      </div>
    </el-card>

    <!-- 生成现金流量确认弹窗 -->
    <el-dialog
      v-model="genConfirmVisible"
      title="生成现金流量"
      width="480px"
      :close-on-click-modal="false"
    >
      <div class="entry-head">
        <div class="entry-head-item">
          <span class="entry-label">日期</span>
          <b>{{ startDate }} 至 {{ endDate }}</b>
        </div>
      </div>
      <div class="entry-foot" v-if="genCheck">
        将生成缺失的 <b>{{ genCheck.missing_days }}</b> 个日历日
        <span v-if="genCheck.missing_start">（{{ genCheck.missing_start }} ~ {{ genCheck.missing_end }}）</span>
      </div>
      <div class="entry-hint">
        按日历日累计：预算入账 + 卖出回笼 − 买入支出 − 手续费；最终余额应等于季度现金合计。
      </div>
      <template #footer>
        <el-button @click="genConfirmVisible = false">取消</el-button>
        <el-button type="success" :loading="generating" @click="confirmGenerate">确认生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { cashApi } from '../api'

const startDate = ref('')
const endDate = ref('')
const generating = ref(false)
const loading = ref(false)
const note = ref('')
const rows = ref([]) // [{trade_date, increment, cash_amount}]
const genConfirmVisible = ref(false)
const genCheck = ref(null) // {missing_days, missing_start, missing_end}

const chartEl = ref(null)
let chart = null

function defaultRange() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1)
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return [fmt(start), fmt(now)]
}

async function generateCash() {
  if (!startDate.value || !endDate.value) {
    ElMessage.warning('请选择日期范围')
    return
  }
  // 先检查缺失的日历日
  const check = await cashApi.check({
    start_date: startDate.value,
    end_date: endDate.value,
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
    const r = await cashApi.generate({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    note.value = `已生成 ${r.generated} 天的现金流`
    await loadCash()
  } catch {
    // 拦截器已提示
  } finally {
    generating.value = false
  }
}

async function loadCash() {
  if (!startDate.value || !endDate.value) return
  loading.value = true
  try {
    rows.value = (await cashApi.list({ start_date: startDate.value, end_date: endDate.value })) || []
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
  render()
}

function render() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const dates = rows.value.map((r) => r.trade_date)
  const cash = rows.value.map((r) => Number(r.cash_amount))
  chart.setOption(
    {
      tooltip: { trigger: 'axis' },
      grid: { left: 70, right: 30, top: 30, bottom: 60 },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLabel: { fontSize: 11, interval: 'auto', hideOverlap: true },
      },
      yAxis: { type: 'value', name: '现金（元）', scale: true },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', start: 0, end: 100, height: 22, bottom: 12 },
      ],
      series: [
        {
          name: '现金余额',
          type: 'line',
          smooth: true,
          data: cash,
          areaStyle: { opacity: 0.12 },
          itemStyle: { color: '#409eff' },
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
  const [sd, ed] = defaultRange()
  startDate.value = sd
  endDate.value = ed
  render()
  await loadCash()
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
.cash-chart {
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
