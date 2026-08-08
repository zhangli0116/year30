<template>
  <div class="strategy">
    <div class="plan-bar">
      <PlanSwitcher
        :model-value="planId"
        @update:model-value="planId = $event"
        @change="loadPlanDefaults"
      />
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>策略实验室</span>
          <span class="header-note">所有策略参数手动设置；动态金额因子：每期金额 = 基准金额 × 各因子乘数叠加（用前一日组合状态，无前视）</span>
        </div>
      </template>

      <!-- 基本 -->
      <div class="form-section">
        <div class="section-title">基本设置</div>
        <div class="controls">
          <div class="ctl">
            <span class="ctl-label">起始日</span>
            <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" style="width: 150px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">结束日</span>
            <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" style="width: 150px" placeholder="缺省今天" clearable />
          </div>
          <div class="ctl">
            <span class="ctl-label">基准金额</span>
            <el-input-number v-model="f.amount.base" :min="0" :step="500" :precision="0" :controls="false" style="width: 150px" placeholder="缺省用方案" />
          </div>
          <div class="ctl">
            <span class="ctl-label">每手份数</span>
            <el-input-number v-model="f.hands" :min="1" :step="100" style="width: 120px" />
          </div>
          <div class="ctl">
            <el-select v-model="f.unlisted_mode" style="width: 190px">
              <el-option label="未上市标的：现金停放" value="park" />
              <el-option label="未上市标的：比例重分配" value="redistribute" />
            </el-select>
          </div>
          <div class="ctl">
            <span class="ctl-label">水上窗口(日)</span>
            <el-input-number v-model="f.drawup_window" :min="1" :max="250" :step="5" size="small" style="width: 110px" title="水上曲线近 N 交易日滚动涨幅窗口" />
          </div>
          <div class="ctl bench-ctl">
            <span class="ctl-label">对比基准</span>
            <el-select v-model="benchmarks" multiple clearable placeholder="选择基准" style="width: 300px">
              <el-option v-for="b in benchmarkList" :key="b.symbol" :label="b.name" :value="b.symbol" />
            </el-select>
            <el-button :loading="syncing" :disabled="!benchmarks.length" size="small" @click="syncBenchmarks">同步所选基准</el-button>
          </div>
        </div>
      </div>

      <!-- 数据覆盖检查 -->
      <el-alert
        v-if="coverage && !coverage.ready"
        :type="actionableMissing.length ? 'warning' : 'info'"
        :closable="false"
        class="cov-alert"
        :title="coverageSummary"
      />
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

      <!-- 再平衡 -->
      <div class="form-section">
        <div class="section-title">再平衡</div>
        <div class="controls">
          <div class="ctl">
            <el-switch v-model="f.buy_rebalance" active-text="买入式再平衡" />
          </div>
          <div class="ctl">
            <el-switch v-model="f.sell_rebalance" active-text="卖出式再平衡" />
          </div>
          <div class="ctl">
            <span class="ctl-label">相对带%</span>
            <el-input-number v-model="f.rb.r_band" :min="0" :max="100" :step="1" style="width: 100px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">绝对底线%</span>
            <el-input-number v-model="f.rb.min_abs" :min="0" :max="100" :step="0.5" style="width: 100px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">绝对上限%</span>
            <el-input-number v-model="f.rb.max_abs" :min="0" :max="100" :step="0.5" style="width: 100px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">金额底线¥</span>
            <el-input-number v-model="f.rb.amount_floor" :min="0" :step="50" style="width: 110px" />
          </div>
          <span class="hint">年末卖出式判定阈值（本页调，不落库）</span>
        </div>
      </div>

      <!-- 撮合 -->
      <div class="form-section">
        <div class="section-title">撮合费用</div>
        <div class="controls">
          <div class="ctl">
            <span class="ctl-label">买入费率%</span>
            <el-input-number v-model="f.fees.buy_rate" :min="0" :max="100" :step="0.01" :precision="2" style="width: 110px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">卖出费率%</span>
            <el-input-number v-model="f.fees.sell_rate" :min="0" :max="100" :step="0.01" :precision="2" style="width: 110px" />
          </div>
          <div class="ctl">
            <span class="ctl-label">最低手续费¥</span>
            <el-input-number v-model="f.fees.min_fee" :min="0" :step="1" style="width: 110px" />
          </div>
        </div>
      </div>

      <!-- 动态金额因子 -->
      <div class="form-section">
        <div class="section-title">
          动态金额因子
          <span class="section-hint">每期金额 = 基准金额 × Σ因子乘数；水下=距峰值跌幅(超跌多投)，水上=近N日滚动涨幅(涨多回调少投)</span>
        </div>
        <div v-for="(fac, fi) in f.amount.factors" :key="fi" class="factor-card">
          <div class="factor-head">
            <el-input v-model="fac.id" placeholder="因子名" style="width: 140px" />
            <el-select v-model="fac.type" style="width: 130px">
              <el-option label="水下(距峰值)" value="drawdown" />
              <el-option label="水上(近N日涨幅)" value="drawup" />
            </el-select>
            <el-switch v-model="fac.enabled" active-text="启用" />
            <div v-if="fac.type === 'drawup'" class="ctl">
              <span class="ctl-label">窗口(日)</span>
              <el-input-number v-model="fac.window" :min="1" :max="250" :step="5" size="small" style="width: 100px" />
            </div>
            <el-button link type="danger" @click="removeFactor(fi)">删除因子</el-button>
          </div>
          <div class="bands">
            <div class="band-head">
              <span style="width: 120px">区间下限</span>
              <span style="width: 120px">区间上限</span>
              <span style="width: 100px">金额乘数</span>
              <span></span>
            </div>
            <div v-for="(b, bi) in fac.bands" :key="bi" class="band-row">
              <el-input-number v-model="b.min" :step="0.01" :precision="3" size="small" style="width: 120px" placeholder="—" />
              <el-input-number v-model="b.max" :step="0.01" :precision="3" size="small" style="width: 120px" placeholder="—" />
              <el-input-number v-model="b.mult" :min="0" :step="0.05" :precision="2" size="small" style="width: 100px" />
              <el-button link type="danger" @click="removeBand(fi, bi)">删</el-button>
            </div>
            <el-button size="small" plain @click="addBand(fi)">＋ 添加档位</el-button>
          </div>
        </div>
        <el-button size="small" type="primary" plain @click="addFactor">＋ 添加因子</el-button>
      </div>

      <div class="run-bar">
        <el-button :loading="checking" @click="runCoverage">数据覆盖检查</el-button>
        <el-button type="primary" :loading="loading" @click="runStrategy">运行回测</el-button>
        <span v-if="result" class="hint">共 {{ result.trades.length }} 笔成交；交易明细中的「金额缩放」列显示每期被因子调整的倍数</span>
      </div>
    </el-card>

    <BacktestCharts :result="result" :loading="loading" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import BacktestCharts from '../components/BacktestCharts.vue'
import { backtestApi, benchmarksApi, planApi } from '../api'

const router = useRouter()

const planId = ref(null)
const startDate = ref('')
const endDate = ref(null)
const loading = ref(false)
const checking = ref(false)
const syncing = ref(false)
const result = ref(null)
const coverage = ref(null)
const benchmarks = ref([])
const benchmarkList = ref([])

const defaultFactors = () => [
  {
    id: '水下超跌',
    type: 'drawdown',
    enabled: true,
    window: 20,
    bands: [
      { min: null, max: -0.15, mult: 1.2 },
      { min: -0.15, max: -0.08, mult: 1.1 },
      { min: -0.08, max: 0, mult: 1.0 },
    ],
  },
  {
    id: '水上回调',
    type: 'drawup',
    enabled: true,
    window: 20,
    bands: [
      { min: 0.08, max: null, mult: 0.85 },
      { min: 0.04, max: 0.08, mult: 0.9 },
      { min: 0, max: 0.04, mult: 1.0 },
    ],
  },
]

const f = reactive({
  buy_rebalance: true,
  sell_rebalance: true,
  unlisted_mode: 'park',
  hands: 100,
  drawup_window: 20,
  fees: { buy_rate: 0.03, sell_rate: 0.07, min_fee: 5 },
  rb: { r_band: 15, min_abs: 1, max_abs: 3, amount_floor: 300 },
  amount: { base: null, factors: defaultFactors() },
})

function addFactor() {
  f.amount.factors.push({
    id: '',
    type: 'drawdown',
    enabled: true,
    window: 20,
    bands: [{ min: null, max: 0, mult: 1.0 }],
  })
}
function removeFactor(i) {
  f.amount.factors.splice(i, 1)
}
function addBand(fi) {
  f.amount.factors[fi].bands.push({ min: null, max: null, mult: 1.0 })
}
function removeBand(fi, bi) {
  f.amount.factors[fi].bands.splice(bi, 1)
}

function threeYearsAgo() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 3)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function loadPlanDefaults(pid) {
  if (!pid) return
  try {
    const list = await planApi.list()
    const plan = (list || []).find((p) => p.id === pid)
    if (plan) {
      if (f.amount.base == null && plan.amount != null) f.amount.base = Number(plan.amount)
      if (plan.start_date) startDate.value = plan.start_date
      else if (!startDate.value) startDate.value = threeYearsAgo()
    }
  } catch {
    // 拦截器已提示
  }
}

// ---- 数据覆盖检查 ----
const missingItems = computed(() =>
  coverage.value ? coverage.value.items.filter((i) => !i.covers_window) : []
)
const actionableMissing = computed(() => missingItems.value.filter((i) => i.actionable))
const lateStartItems = computed(() => missingItems.value.filter((i) => !i.actionable))
const coverageSummary = computed(() => {
  const act = actionableMissing.value.length
  const late = lateStartItems.value.length
  const parts = []
  if (act) parts.push(`${act} 项存在缺失交易日（可补历史）`)
  if (late) parts.push(`${late} 项数据起点晚于起始日（多为上市较晚）`)
  return parts.length ? `数据覆盖不完整：${parts.join('、')}，详见下方` : ''
})

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

function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
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

async function syncBenchmarks() {
  if (!startDate.value || !benchmarks.value.length) return
  syncing.value = true
  try {
    const end = endDate.value || todayStr()
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
  if (!planId.value || !startDate.value) return
  checking.value = true
  try {
    coverage.value = await backtestApi.coverage({
      plan_id: planId.value,
      start_date: startDate.value,
      end_date: endDate.value || todayStr(),
      ...(benchmarks.value.length ? { benchmarks: benchmarks.value.join(',') } : {}),
    })
  } catch {
    // 拦截器已提示
  } finally {
    checking.value = false
  }
}

async function runStrategy() {
  if (!planId.value || !startDate.value) {
    ElMessage.warning('请选择方案和起始日期')
    return
  }
  loading.value = true
  result.value = null
  try {
    const payload = {
      plan_id: planId.value,
      start_date: startDate.value,
      end_date: endDate.value || null,
      benchmarks: benchmarks.value,
      strategy: JSON.parse(JSON.stringify(f)),
    }
    result.value = await backtestApi.runStrategy(payload)
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const list = await planApi.list()
    if (list?.length) {
      planId.value = list[0].id
      await loadPlanDefaults(planId.value)
    }
  } catch {
    // 拦截器已提示
  }
  await loadBenchmarks()
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
.form-section {
  margin-bottom: 20px;
}
.form-section:last-child {
  margin-bottom: 12px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #409eff;
}
.section-hint {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
  margin-left: 8px;
}
.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.ctl {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ctl-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}
.hint {
  color: #c0c4cc;
  font-size: 12px;
}
.factor-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
  background: #fafbfc;
}
.factor-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.bands {
  border-top: 1px dashed #e4e7ed;
  padding-top: 10px;
}
.band-head,
.band-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.band-head {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.band-row {
  margin-bottom: 6px;
}
.run-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
}
.cov-alert {
  margin-bottom: 12px;
}
.cov-body {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.cov-tags {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cov-actions {
  flex-shrink: 0;
  display: flex;
  gap: 8px;
}
</style>
