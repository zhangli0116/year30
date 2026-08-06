<template>
  <div class="dashboard">
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
import { computed, onMounted, ref } from 'vue'
import QuarterChart from '../components/QuarterChart.vue'
import TotalEquityChart from '../components/TotalEquityChart.vue'
import { fundsApi, purchasesApi, quartersApi, quotesApi } from '../api'

const CASH_CODE = '000000'

const loading = ref(false)
const loadingQuote = ref(false)
const quoteTime = ref(null)
const summary = ref({ funds: [], total_invested: 0, total_capital: null, cash_ratio: null })
const quarters = ref([]) // quarter 表：承载预算与现金
const prices = ref({}) // fund_code -> 最新价
const purchases = ref([]) // 购买记录（用于季度趋势图按份额累计市值）

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
    r.ratioStatus = ratioStatusOf(r)
  })
  return arr
})

// 今天实时总权益 = 各基金市值之和（用实时行情价 × 持有份额，不含现金/手续费）
const todayEquity = computed(() =>
  rows.value
    .filter((r) => !r.isCash && !r.isFee)
    .reduce((s, r) => s + (r.mv || 0), 0)
)

// 市值占比 vs 规定比例：超配(above)/低配(below)/正常(normal)，±1 个百分点内视为正常
function ratioStatusOf(row) {
  if (row.realRatio == null || row.target_ratio == null) return 'normal'
  const diff = row.realRatio - Number(row.target_ratio)
  if (diff > 1) return 'above'
  if (diff < -1) return 'below'
  return 'normal'
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

async function loadData() {
  loading.value = true
  try {
    const [sumData, quarterData, purchaseData] = await Promise.all([
      fundsApi.summary(),
      quartersApi.list(),
      purchasesApi.list({ page: 1, page_size: 100 }), // 含买卖，供趋势图累计份额
    ])
    summary.value = sumData
    quarters.value = quarterData || []
    purchases.value = purchaseData?.items || []
    await loadQuotes()
  } finally {
    loading.value = false
  }
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

onMounted(loadData)
</script>

<style scoped>
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
</style>
