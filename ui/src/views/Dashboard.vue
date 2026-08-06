<template>
  <div class="dashboard">
    <div class="plan-bar">
      <PlanSwitcher
        :model-value="planId"
        @update:model-value="planId = $event"
        @change="onPlanChange"
      />
    </div>

    <el-row :gutter="16" class="cards">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总市值</div>
          <div class="stat-value">¥ {{ money(totalMv) }}</div>
          <div class="stat-sub">权益市值 ¥{{ money(todayEquity) }} · 现金 ¥{{ money(cashBalance) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">总浮盈</div>
          <div class="stat-value" :class="totalPnl >= 0 ? 'up' : 'down'">
            {{ totalPnl >= 0 ? '+' : '' }}{{ money(totalPnl) }}
            <span class="pct">({{ pct(totalPnlPct) }})</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">累计投入 <span class="stat-sub">（季度预算累计）</span></div>
          <div class="stat-value">¥ {{ money(totalCost) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-label">现金占比</div>
          <div class="stat-value">
            {{ cashRatio == null ? '-' : cashRatio.toFixed(2) + '%' }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- XIRR 年化收益 -->
    <el-card shadow="never" class="xirr-card">
      <template #header>
        <div class="card-header">
          <span>年化收益（XIRR）</span>
          <span class="header-note">资金加权年化：全账户按季度预算到账时点，单基金按实际买卖现金流</span>
        </div>
      </template>
      <div class="xirr-body">
        <div class="xirr-account">
          <div class="stat-label">全账户</div>
          <div
            class="xirr-big"
            :class="xirrData.account.xirr != null && xirrData.account.xirr >= 0 ? 'up' : 'down'"
          >
            {{ fmtXirr(xirrData.account.xirr) }}
          </div>
          <div class="xirr-meta">
            投入 ¥{{ money(xirrData.account.invested) }}
            <span class="muted">→</span>
            现值 ¥{{ money(xirrData.account.current_value) }}
          </div>
          <div class="xirr-meta">
            收益
            <span :class="xirrData.account.gain >= 0 ? 'up' : 'down'">
              {{ signed(xirrData.account.gain) }}（{{ pct(xirrData.account.gain_pct) }}）
            </span>
            <span class="muted">· 首投 {{ xirrData.account.start_date || '—' }}</span>
          </div>
        </div>
        <div class="xirr-divider"></div>
        <div class="xirr-funds">
          <div class="xirr-fhead">
            <span>单基金</span>
            <span class="muted">年化</span>
            <span class="muted">投入</span>
            <span class="muted">现值</span>
          </div>
          <div v-for="f in xirrData.funds" :key="f.fund_id" class="xirr-frow">
            <span class="xirr-fname">{{ f.fund_code }} {{ f.fund_name }}</span>
            <span class="xirr-fval" :class="f.xirr != null && f.xirr >= 0 ? 'up' : 'down'">
              {{ fmtXirr(f.xirr) }}
            </span>
            <span class="xirr-fnum">{{ money(f.invested) }}</span>
            <span class="xirr-fnum">{{ money(f.current_mv) }}</span>
          </div>
          <div v-if="!xirrData.funds.length" class="muted">暂无基金数据</div>
        </div>
      </div>
    </el-card>

    <!-- 再平衡状态 -->
    <el-card shadow="never" class="rb-card">
      <template #header>
        <div class="card-header">
          <span>再平衡状态</span>
          <div class="header-right">
            <span class="header-note">当前市值占比 vs 目标占比（含现金）；超出判定阈值才提示，可调参数与计划</span>
            <el-button size="small" link type="primary" @click="router.push('/rebalance-check')">
              查看详情 →
            </el-button>
          </div>
        </div>
      </template>
      <div class="rb-body">
        <div v-for="row in rbRows" :key="row.fund_code || row.id" class="rb-row">
          <div class="rb-name">
            <span class="rb-code">{{ row.fund_code || '现金' }}</span>
            <span class="rb-name-text">{{ row.fund_name }}</span>
          </div>
          <div class="rb-track">
            <el-progress
              :percentage="rbPct(row)"
              :color="rbColor(row)"
              :stroke-width="10"
              :show-text="false"
            />
            <div
              v-if="row.target != null"
              class="rb-marker"
              :style="{ left: rbMarkerLeft(row) }"
              :title="`目标 ${Number(row.target).toFixed(1)}%`"
            ></div>
          </div>
          <div class="rb-text">
            <span>
              {{ row.real == null ? '—' : row.real.toFixed(1) + '%' }}
              <span class="muted">/ 目标 {{ row.target == null ? '—' : Number(row.target).toFixed(1) + '%' }}</span>
            </span>
            <span class="rb-dev" :class="row.status === 'normal' ? 'muted' : row.status === 'above' ? 'up' : 'down'">
              偏离 {{ signedPct(row.deviation) }}
              <span class="muted">（相对 {{ relDev(row) }}）</span>
            </span>
          </div>
          <el-tag size="small" effect="plain" :type="rbTagType(row)" :title="row.suggestion">
            {{ rbStatusText(row) }}
          </el-tag>
        </div>
        <div v-if="!rbRows.length" class="muted">暂无再平衡数据</div>
      </div>
    </el-card>

    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>总权益走势（日）</span>
          <span class="header-note">历史来自每日权益流水；今日按实时价 × 持有份额</span>
        </div>
      </template>
      <TotalEquityChart :today-equity="todayEquity" :quarters="quarters" />
    </el-card>

    <!-- 季度趋势：暂时注释掉，暂无用处
    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>季度趋势</span>
          <span class="header-note">市值统一按今天最新价估算（无历史行情）</span>
        </div>
      </template>
      <QuarterChart
        :quarters="quarters"
        :purchases="purchases"
        :prices="prices"
        :funds="summary.funds"
      />
    </el-card>
    -->

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>持仓汇总（按当前市值）</span>
          <div class="header-right">
            <span v-if="quoteTime" class="header-note">行情更新：{{ quoteTime }}</span>
            <el-button size="small" :loading="syncing" @click="syncAll">
              <el-icon style="margin-right: 4px"><Refresh /></el-icon>同步全部行情
            </el-button>
            <el-button size="small" type="primary" :loading="loadingQuote" @click="loadQuotes">
              获取最新价
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" stripe :summary-method="tableSummary" show-summary>
        <el-table-column prop="fund_code" label="代码" width="110" />
        <el-table-column prop="fund_name" label="名称" min-width="120" />
        <el-table-column prop="price" label="当前价" width="90" align="right">
          <template #default="{ row }">
            {{ row.price == null ? '-' : Number(row.price).toFixed(3) }}
          </template>
        </el-table-column>
        <el-table-column prop="shares" label="份额" width="100" align="right">
          <template #default="{ row }">
            {{ row.isCash || row.isFee ? '-' : formatShares(row.shares) }}
          </template>
        </el-table-column>
        <el-table-column prop="cost" label="累计投入" width="120" align="right">
          <template #default="{ row }">{{ `¥ ${money(row.cost)}` }}</template>
        </el-table-column>
        <el-table-column prop="mv" label="市值" width="120" align="right">
          <template #default="{ row }">
            {{ row.mv == null ? '-' : `¥ ${money(row.mv)}` }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="浮盈(率)" width="150" align="right">
          <template #default="{ row }">
            <span v-if="row.isFee" class="down">-{{ money(-row.pnl) }}</span>
            <span v-else-if="row.isCash || row.pnl == null" class="muted">-</span>
            <span v-else :class="row.pnl >= 0 ? 'up' : 'down'">
              {{ row.pnl >= 0 ? '+' : '' }}{{ money(row.pnl) }}
              <span class="pct">({{ pct(row.pnlPct) }})</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="realRatio" label="市值占比" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.realRatio == null" class="muted">-</span>
            <span v-else :class="['ratio-status', row.ratioStatus]" :title="ratioTitle(row)">
              <span v-if="row.ratioStatus === 'above'" class="ratio-arrow">↑</span>
              <span v-else-if="row.ratioStatus === 'below'" class="ratio-arrow">↓</span>
              {{ row.realRatio.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="target_ratio" label="规定比例" width="100" align="right">
          <template #default="{ row }">
            {{ row.target_ratio == null ? '-' : `${Number(row.target_ratio).toFixed(2)}%` }}
          </template>
        </el-table-column>
      </el-table>

      <div v-if="cashBreakdown" class="cash-note">
        现金余额 ¥{{ money(cashBreakdown.mv) }} ≈ 目标现金仓 ¥{{ money(cashBreakdown.targetMV) }}（{{ cashBreakdown.targetPct.toFixed(2) }}%）＋ 结余 ¥{{ signed(cashBreakdown.surplus) }}
        <span v-if="cashBreakdown.surplus > 0" class="muted">（结余＝买基金取整余款＋当季未投完的预算；结余越大说明资金还没配置完）</span>
        <span v-else class="muted">（结余为负说明现金低于 15% 目标：基金上涨或现金投入不足）</span>
      </div>

      <div v-if="!hasAnyTarget" class="tip">
        尚未设置任何基金的目标比例，去「基金管理」页为基金填写规定比例后，这里会展示市值占比与目标对比。
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import QuarterChart from '../components/QuarterChart.vue'
import TotalEquityChart from '../components/TotalEquityChart.vue'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import { fundsApi, purchasesApi, quartersApi, quotesApi, rebalanceApi, syncApi, xirrApi } from '../api'
import { judge, thresholdFor } from '../utils/rebalance'

const CASH_CODE = '000000'

// 当前选中的定投方案：切换后所有数据（summary/quarters/xirr/再平衡）按该方案过滤
const planId = ref(null)

const loading = ref(false)
const loadingQuote = ref(false)
const syncing = ref(false)
const quoteTime = ref(null)
const summary = ref({ funds: [], total_invested: 0, total_capital: null, cash_ratio: null })
const quarters = ref([]) // quarter 表：承载预算与现金
const prices = ref({}) // fund_code -> 最新价
const purchases = ref([]) // 购买记录（用于季度趋势图按份额累计市值）
const xirrData = ref({
  account: { xirr: null, invested: 0, current_value: 0, gain: 0, gain_pct: null, start_date: null },
  funds: [],
})
const rbData = ref(null) // 后端 /rebalance/check 的偏离分析（与「再平衡体检」页一致）
// 再平衡判定参数（默认与后端 config 一致，加载后覆盖）
const rebalanceParams = ref({ r_band: 15, min_abs: 1, max_abs: 3, amount_floor: 300 })
const router = useRouter()

// 现金余额 = Σ quarter.cash_amount；累计投入 = Σ quarter.budget
const cashBalance = computed(() =>
  quarters.value.reduce((s, q) => s + Number(q.cash_amount || 0), 0)
)
const totalBudget = computed(() =>
  quarters.value.reduce((s, q) => s + Number(q.budget || 0), 0)
)
const totalFee = computed(() =>
  quarters.value.reduce((s, q) => s + Number(q.total_fee || 0), 0)
)

// 现金目标比例：取现金基金 target_ratio；缺失时按 100 − Σ基金目标 兜底
const cashTargetRatio = computed(() => {
  const cashFund = (summary.value.funds || []).find((f) => f.fund_code === CASH_CODE)
  if (cashFund?.target_ratio != null) return Number(cashFund.target_ratio)
  const sum = (summary.value.funds || [])
    .filter((f) => f.fund_code !== CASH_CODE)
    .reduce((s, f) => s + (f.target_ratio != null ? Number(f.target_ratio) : 0), 0)
  return Math.max(0, 100 - sum)
})

// 持仓行：真实基金 + 现金行。市值占比以「基金市值 + 现金」为分母，
// 让每只基金的占比反映其在整体组合（含现金）中的权重；现金行不产生盈亏。
const rows = computed(() => {
  const fs = (summary.value.funds || []).filter((f) => f.fund_code !== CASH_CODE)
  const arr = fs.map((f) => {
    const price = prices.value[f.fund_code] ?? null
    const shares = Number(f.total_shares || 0)
    const cost = Number(f.total_cost || 0)
    const mv = price != null ? shares * price : null
    const pnl = mv != null ? mv - cost : null
    const pnlPct = cost > 0 && pnl != null ? (pnl / cost) * 100 : null
    return { ...f, isCash: false, price, shares, cost, mv, pnl, pnlPct, realRatio: null }
  })
  // 现金行：市值=现金余额，成本=现金余额（闲置现金不产生盈亏）
  arr.push({
    id: -1,
    fund_code: CASH_CODE,
    fund_name: '现金',
    isCash: true,
    target_ratio: cashTargetRatio.value,
    price: null,
    shares: 0,
    cost: cashBalance.value,
    mv: cashBalance.value,
    pnl: 0,
    pnlPct: null,
    realRatio: null,
  })
  // 手续费行：成本=总手续费，市值=0，浮盈=−总手续费（费用是成本，降低收益），让 权益+手续费+现金=预算 闭合
  arr.push({
    id: -2,
    fund_code: '',
    fund_name: '手续费',
    isFee: true,
    target_ratio: null,
    price: null,
    shares: 0,
    cost: totalFee.value,
    mv: null,
    pnl: -totalFee.value,
    pnlPct: null,
    realRatio: null,
  })
  const totalMv = arr.reduce((s, r) => s + (r.mv ?? 0), 0)
  arr.forEach((r) => {
    r.realRatio = r.mv != null && totalMv > 0 ? (r.mv / totalMv) * 100 : null
    r.ratioStatus = ratioStatusOf(r, totalMv)
  })
  return arr
})

// 今天实时总权益 = 各基金市值之和（用实时行情价 × 持有份额，不含现金/手续费）
const todayEquity = computed(() =>
  rows.value
    .filter((r) => !r.isCash && !r.isFee)
    .reduce((s, r) => s + (r.mv || 0), 0)
)

// 市值占比 vs 规定比例：超配(above)/低配(below)/正常(normal)。
// 判定用共享模块（相对带+底线+上限+金额底线），与「再平衡体检」页一致。
function ratioStatusOf(row, totalMvLocal) {
  if (row.realRatio == null || row.target_ratio == null) return 'normal'
  const dev = row.realRatio - Number(row.target_ratio)
  const threshold = thresholdFor(row.target_ratio, rebalanceParams.value)
  const devAmount = totalMvLocal != null ? (dev / 100) * totalMvLocal : null
  return judge(dev, threshold, rebalanceParams.value, devAmount)
}

function ratioTitle(row) {
  if (row.ratioStatus === 'above') {
    return `超配 ${(row.realRatio - Number(row.target_ratio)).toFixed(2)}%`
  }
  if (row.ratioStatus === 'below') {
    return `低配 ${(Number(row.target_ratio) - row.realRatio).toFixed(2)}%`
  }
  return '接近目标'
}

// 组合口径（表格行已含现金）：市值 / 成本 / 盈亏合计
const totalMv = computed(() => rows.value.reduce((s, r) => s + (r.mv ?? 0), 0))
const totalCost = computed(() => rows.value.reduce((s, r) => s + r.cost, 0))
const totalPnl = computed(() => rows.value.reduce((s, r) => s + (r.pnl ?? 0), 0))
const totalPnlPct = computed(() =>
  totalCost.value > 0 ? (totalPnl.value / totalCost.value) * 100 : null
)
const cashRatio = computed(() =>
  totalMv.value > 0 ? (cashBalance.value / totalMv.value) * 100 : null
)
const hasAnyTarget = computed(() =>
  (summary.value.funds || []).some((f) => f.target_ratio != null)
)

// 现金构成：余额 = 目标现金仓（现金目标% × 累计投入）＋ 结余（买基金取整余款＋未投完预算）
const cashBreakdown = computed(() => {
  if (totalBudget.value <= 0) return null
  const targetMV = (cashTargetRatio.value / 100) * totalBudget.value
  const surplus = cashBalance.value - targetMV
  return { mv: cashBalance.value, targetPct: cashTargetRatio.value, targetMV, surplus }
})

async function loadQuotes() {
  const codes = (summary.value.funds || [])
    .filter((f) => f.fund_code !== CASH_CODE)
    .map((f) => f.fund_code)
  if (codes.length === 0) return
  loadingQuote.value = true
  try {
    const data = await quotesApi.list(codes.join(','))
    prices.value = Object.fromEntries(
      (data.quotes || []).map((q) => [q.code, q.last])
    )
    const first = data.quotes && data.quotes[0]
    if (first && first.time) quoteTime.value = first.time
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    loadingQuote.value = false
  }
}

// 方案内参数：选中方案后各查询都带 plan_id（未选中时不传，兼容无方案场景）
function planParams() {
  return planId.value ? { plan_id: planId.value } : {}
}

async function loadData() {
  loading.value = true
  try {
    const pp = planParams()
    const [sumData, quarterData, purchaseData, xirr, rb] = await Promise.all([
      fundsApi.summary(pp),
      quartersApi.list(pp),
      purchasesApi.list({ page: 1, page_size: 100, ...pp }), // 含买卖，供趋势图累计份额
      xirrApi.get(pp).catch(() => xirrData.value),
      rebalanceApi.check(pp).catch(() => null),
    ])
    summary.value = sumData
    quarters.value = quarterData || []
    purchases.value = purchaseData?.items || []
    xirrData.value = xirr
    // 后端偏离分析：卡片展示用；其 params 同时供持仓表的判定用
    if (rb) {
      rbData.value = rb
      rebalanceParams.value = rb.params
    }
    await loadQuotes()
  } finally {
    loading.value = false
  }
}

// 方案切换：重新拉取该方案下全部数据
async function onPlanChange() {
  await loadData()
}

// 一键同步全部行情（增量补缺失日线 + 权益/现金流），完成后刷新页面数据
async function syncAll() {
  try {
    await ElMessageBox.confirm(
      '将同步所有基金缺失的历史日线，并增量生成每日权益流水与现金流量（只补缺失，不覆盖已有数据）。',
      '确认同步全部行情？',
      { type: 'warning', confirmButtonText: '确认同步', cancelButtonText: '取消' }
    )
  } catch {
    return // 用户取消
  }
  syncing.value = true
  try {
    const r = await syncApi.all()
    ElMessage.success(
      r && r.funds != null
        ? `已同步 ${r.funds} 只基金：新增日线 ${r.prices_inserted} 根、权益流水 ${r.holdings_generated} 天、现金流 ${r.cash_generated} 天`
        : '同步完成'
    )
    await loadData()
  } catch {
    // 失败提醒由 axios 拦截器统一弹出
  } finally {
    syncing.value = false
  }
}

// XIRR 显示：小数 → 百分比；null → —
function fmtXirr(v) {
  return v == null ? '—' : `${(v * 100).toFixed(2)}%`
}

// 再平衡卡片：用后端 /rebalance/check 的偏离分析（与「再平衡体检」页一致）
const rbRows = computed(() => {
  if (!rbData.value) return []
  const fundRows = (rbData.value.funds || []).map((f) => ({ ...f }))
  const c = rbData.value.cash
  if (c) fundRows.push({ ...c, fund_id: -1, fund_code: '000000', fund_name: '现金' })
  return fundRows
})
function rbPct(row) {
  if (row.real == null) return 0
  return Math.min(100, Math.max(0, row.real))
}
function rbMarkerLeft(row) {
  return `${Math.min(100, Number(row.target))}%`
}
function rbColor(row) {
  if (row.target == null) return '#c0c4cc'
  if (row.status === 'above') return '#f56c6c'
  if (row.status === 'below') return '#e6a23c'
  return '#409eff'
}
function rbTagType(row) {
  if (row.target == null) return 'info'
  if (row.status === 'above') return 'danger'
  if (row.status === 'below') return 'warning'
  return 'success'
}
function rbStatusText(row) {
  if (row.target == null) return '未设目标'
  if (row.fund_code === '000000') {
    if (row.status === 'above') return '现金偏多'
    if (row.status === 'below') return '现金偏低'
    return '达标'
  }
  if (row.status === 'above') return '超配'
  if (row.status === 'below') return '低配'
  return '达标'
}
function signedPct(v) {
  const n = Number(v || 0)
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}
// 相对偏离：|偏离| ÷ 目标（相对自身目标的真实跑偏幅度）
function relDev(row) {
  if (row.target == null || !row.target) return '-'
  return (Math.abs(row.deviation) / row.target * 100).toFixed(1) + '%'
}

function tableSummary({ columns }) {
  const sums = []
  columns.forEach((col, i) => {
    if (i === 0) {
      sums[i] = '合计'
    } else if (col.property === 'cost') {
      sums[i] = `¥ ${money(totalCost.value)}`
    } else if (col.property === 'mv') {
      sums[i] = `¥ ${money(totalMv.value)}`
    } else if (col.property === 'pnl') {
      sums[i] = `${totalPnl.value >= 0 ? '+' : ''}¥ ${money(totalPnl.value)}`
    } else if (col.property === 'realRatio') {
      sums[i] = totalMv.value > 0 ? '100.00%' : '-'
    } else {
      sums[i] = ''
    }
  })
  return sums
}

function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function pct(v) {
  if (v == null) return '-'
  return `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`
}

function formatShares(v) {
  return Number(v || 0).toLocaleString('zh-CN')
}

// 带正负号的金额：+28.00 / -775.00
function signed(v) {
  const n = Number(v || 0)
  const abs = Math.abs(n).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return (n >= 0 ? '+' : '-') + abs
}

</script>

<style scoped>
.plan-bar {
  margin-bottom: 16px;
}
.cards {
  margin-bottom: 16px;
}
.chart-card {
  margin-bottom: 16px;
}
.stat-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
.stat-sub {
  font-size: 11px;
  color: #c0c4cc;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
}
.pct {
  font-size: 13px;
  font-weight: 400;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-note {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
}
.up {
  color: #f56c6c; /* 涨红 */
}
.down {
  color: #67c23a; /* 跌绿 */
}
.ratio-status.above {
  color: #e6a23c; /* 超配：超过规定比例 */
  font-weight: 600;
}
.ratio-status.below {
  color: #409eff; /* 低配：低于规定比例 */
  font-weight: 600;
}
.ratio-arrow {
  margin-right: 2px;
}
.muted {
  color: #c0c4cc;
}
.cash-note {
  margin-top: 12px;
  color: #606266;
  font-size: 13px;
}
.tip {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
}
.xirr-card,
.rb-card,
.chart-card {
  margin-bottom: 16px;
}
.xirr-body {
  display: flex;
  gap: 24px;
  align-items: stretch;
}
.xirr-account {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-right: 24px;
}
.xirr-big {
  font-size: 34px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  margin-bottom: 8px;
}
.xirr-meta {
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}
.xirr-divider {
  width: 1px;
  background: #ebeef5;
  flex-shrink: 0;
}
.xirr-funds {
  flex: 1;
  min-width: 0;
}
.xirr-fhead,
.xirr-frow {
  display: grid;
  grid-template-columns: 1fr 90px 110px 110px;
  gap: 8px;
  align-items: center;
}
.xirr-fhead {
  color: #909399;
  font-size: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 4px;
}
.xirr-frow {
  padding: 6px 0;
  border-bottom: 1px solid #f5f7fa;
  font-size: 13px;
}
.xirr-frow:last-child {
  border-bottom: none;
}
.xirr-fname {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.xirr-fval {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.xirr-fnum {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.rb-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 6px 32px;
}
.rb-row {
  display: grid;
  grid-template-columns: 150px 1fr 190px 86px;
  align-items: center;
  gap: 12px;
  padding: 5px 0;
}
.rb-name {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.rb-code {
  color: #909399;
  font-size: 12px;
}
.rb-name-text {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.rb-track {
  position: relative;
}
.rb-track .el-progress {
  width: 100%;
}
.rb-marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #303133;
  border-radius: 1px;
  opacity: 0.55;
}
.rb-text {
  font-size: 12px;
  color: #606266;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  line-height: 1.5;
}
.rb-text .muted {
  color: #c0c4cc;
}
.rb-dev {
  display: block;
  font-size: 11px;
  margin-top: 2px;
}
.rb-row .el-tag {
  justify-self: end;
}
@media (max-width: 1100px) {
  .rb-row {
    grid-template-columns: 130px 1fr 150px 80px;
  }
}
</style>
