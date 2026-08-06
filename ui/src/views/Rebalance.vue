<template>
  <div class="rebalance">
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
          <span>卖出式再平衡</span>
          <div class="header-right">
            <span v-if="quoteTime" class="header-note">行情更新：{{ quoteTime }}</span>
            <el-button type="primary" size="small" :loading="loadingQuote" @click="fetchPrices">
              <el-icon style="margin-right: 4px"><Refresh /></el-icon>获取最新价格
            </el-button>
          </div>
        </div>
      </template>

      <div class="intro-note">
        拖动「目标占比」滑块（默认=规定比例），<b>超配的基金卖出、低配的买入</b>，卖出回笼并入现金池后统一分配，
        现金目标 = 100 − 权益总和；手续费 = max(5, 金额×费率)。用于买入式无法纠正的超配仓位。
      </div>

      <el-row :gutter="16" class="cards">
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-label">现有总市值</div>
            <div class="stat-value">¥ {{ money(plan.currentTotal) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-label">本季预算（元）</div>
            <el-input-number
              v-model="budget"
              :min="0"
              :step="100"
              :precision="0"
              :controls="false"
              style="width: 100%"
            />
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-label">手续费费率（%）</div>
            <div class="rate-line">
              <span class="rate-label">买入</span>
              <el-input-number
                v-model="buyFeeRate"
                :min="0"
                :step="0.01"
                :precision="4"
                :controls="false"
                style="width: 90px"
              />
            </div>
            <div class="rate-line">
              <span class="rate-label">卖出</span>
              <el-input-number
                v-model="sellFeeRate"
                :min="0"
                :step="0.01"
                :precision="4"
                :controls="false"
                style="width: 90px"
              />
            </div>
            <div class="fee-hint">手续费 = max(5, 金额×费率)</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover">
            <div class="stat-label">再平衡后现金池</div>
            <div class="stat-value" :class="plan.cashAfter < 0 ? 'down' : ''">
              ¥ {{ money(plan.cashAfter) }}
            </div>
            <div v-if="plan.cashPct != null" class="stat-sub">
              ≈ {{ plan.cashPct.toFixed(2) }}%（目标 {{ plan.cashTargetPct.toFixed(1) }}%）
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-table :data="plan.items" stripe class="main-table">
        <el-table-column label="基金" min-width="140">
          <template #default="{ row }">
            <div class="fund-name">
              <span class="code">{{ row.fund_code }}</span>
              <span>{{ row.fund_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前价" width="80" align="right">
          <template #default="{ row }">
            {{ row.price == null ? '-' : Number(row.price).toFixed(3) }}
          </template>
        </el-table-column>
        <el-table-column label="现有市值" width="110" align="right">
          <template #default="{ row }">{{ row.currentMV == null ? '-' : `¥ ${money(row.currentMV)}` }}</template>
        </el-table-column>
        <el-table-column label="现有占比" width="90" align="right">
          <template #default="{ row }">
            {{ row.currentPct == null ? '-' : row.currentPct.toFixed(2) + '%' }}
          </template>
        </el-table-column>
        <el-table-column label="目标占比（可滑动）" min-width="200" align="center">
          <template #default="{ row }">
            <div class="slider-cell">
              <el-slider
                v-model="row.targetPct"
                :min="0"
                :max="sliderMax(row)"
                :step="0.5"
                :show-tooltip="false"
                class="slider"
              />
              <span class="pct-text">{{ row.targetPct.toFixed(1) }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.action === 'sell'" type="danger" size="small">卖出 {{ row.actHands }}手</el-tag>
            <el-tag v-else-if="row.action === 'buy'" type="success" size="small">买入 {{ row.actHands }}手</el-tag>
            <span v-else class="muted">不动</span>
          </template>
        </el-table-column>
        <el-table-column label="操作金额" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.action === 'sell'" class="sell-amt">+¥{{ money(row.actPrincipal) }}</span>
            <span v-else-if="row.action === 'buy'" class="buy-amt">−¥{{ money(row.actPrincipal) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="手续费" width="80" align="right">
          <template #default="{ row }">
            {{ row.fee > 0 ? `¥${money(row.fee)}` : '-' }}
          </template>
        </el-table-column>
      </el-table>

      <div class="plan-summary">
        <span>卖出回笼 <b class="sell-amt">+¥{{ money(plan.sellProceeds) }}</b></span>
        <span>｜买入支出 <b class="buy-amt">−¥{{ money(plan.buyCost) }}</b></span>
        <span>｜手续费 <b>−¥{{ money(plan.totalFee) }}</b></span>
        <span>｜现金池 <b class="cash">¥{{ money(plan.cashAfter) }}</b></span>
      </div>

      <el-divider />

      <div class="submit-bar">
        <el-date-picker
          v-model="rebalanceDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="操作日期"
          style="width: 150px"
        />
        <el-button type="warning" size="large" :disabled="!hasAction" @click="openConfirm">
          执行卖出式再平衡
        </el-button>
        <span v-if="!hasAction" class="muted">（当前无需买卖，比例已达标）</span>
      </div>
    </el-card>

    <!-- 确认弹窗 -->
    <el-dialog
      v-model="confirmVisible"
      title="执行卖出式再平衡"
      width="560px"
      :close-on-click-modal="false"
    >
      <div class="entry-head">
        <div class="entry-head-item">
          <span class="entry-label">周期</span>
          <b class="entry-period">{{ periodFromDate(rebalanceDate) }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">操作日期</span>
          <b>{{ rebalanceDate }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">预算</span>
          <b>¥{{ money(budget) }}</b>
        </div>
      </div>

      <el-table :data="plan.items.filter(r => r.action !== 'hold')" size="small" stripe class="entry-table">
        <el-table-column label="基金" min-width="120">
          <template #default="{ row }">{{ row.fund_name }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <span :class="row.action === 'sell' ? 'sell-amt' : 'buy-amt'">
              {{ row.action === 'sell' ? '卖出' : '买入' }} {{ row.actHands }}手
            </span>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }">
            <span :class="row.action === 'sell' ? 'sell-amt' : 'buy-amt'">
              {{ row.action === 'sell' ? '+' : '-' }}¥{{ money(row.actPrincipal) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="手续费" width="80" align="right">
          <template #default="{ row }">¥{{ money(row.fee) }}</template>
        </el-table-column>
      </el-table>

      <div class="plan-summary">
        <span>卖出回笼 <b class="sell-amt">+¥{{ money(plan.sellProceeds) }}</b></span>
        <span>｜买入支出 <b class="buy-amt">−¥{{ money(plan.buyCost) }}</b></span>
        <span>｜手续费 <b>−¥{{ money(plan.totalFee) }}</b></span>
        <span>｜现金池 <b class="cash">¥{{ money(plan.cashAfter) }}</b></span>
      </div>
      <div class="entry-hint">确认后：卖出记录 type=sell、买入记录 type=buy 一并录入「{{ periodFromDate(rebalanceDate) }}」，季度权益/现金自动重算。</div>

      <template #footer>
        <el-button @click="confirmVisible = false">再想想</el-button>
        <el-button type="warning" :loading="submitting" @click="execute">确认执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import { fundsApi, planApi, purchasesApi, quartersApi, quotesApi } from '../api'

const router = useRouter()
const CASH_CODE = '000000'

// 当前选中的定投方案（本页的「方案」指卖出式再平衡计划 plan，注意区分）
const planId = ref(null)

const budget = ref(0)
const buyFeeRate = ref(0.03) // 买入费率（%）
const sellFeeRate = ref(0.07) // 卖出费率（%）
const loadingQuote = ref(false)
const quoteTime = ref(null)
const submitting = ref(false)
const rebalanceDate = ref(todayStr())
const fundRows = ref([])
const cashCurrent = ref(0)

const confirmVisible = ref(false)

function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function periodFromDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const q = Math.floor(d.getMonth() / 3) + 1
  return d.getFullYear() + 'Q' + q
}

// 滑块上限：单个滑块最大 = 100 − 其他基金目标之和，保证权益类总和 ≤ 100%（现金 ≥ 0）
function sliderMax(row) {
  const others = fundRows.value
    .filter((r) => r.fund_id !== row.fund_id)
    .reduce((s, r) => s + (r.targetPct || 0), 0)
  return Math.max(0, 100 - others)
}

// 再平衡方案：先卖超配（四舍五入到整手），买入受「现金池 − 目标现金」约束，
// 保证再平衡后现金回到目标比例（如 15%），而不是现金成剩余值。目标占比可滑动（默认=规定比例）。
// 派生值先在局部数组算/读（避免读写响应式行造成自依赖），最后回写源行供模板读取。
const plan = computed(() => {
  const rows = fundRows.value
  const currentTotal = rows.reduce((s, r) => s + (r.currentMV || 0), 0) + cashCurrent.value
  const finalTotal = currentTotal + budget.value
  const cashTargetPct = Math.max(0, 100 - rows.reduce((s, r) => s + Number(r.targetPct || 0), 0))
  const cashTargetValue = (finalTotal * cashTargetPct) / 100

  // 1) 派生值先算到局部数组（超配基金四舍五入到整手卖出）
  const derived = rows.map((r) => {
    const price = r.price
    const handPrice = r.handPrice
    const currentMV = r.currentMV || 0
    const targetPct = Number(r.targetPct || 0)
    const targetMV = (finalTotal * targetPct) / 100
    const diff = targetMV - currentMV
    const d = { row: r, price, handPrice, targetMV, diff, action: 'hold', actHands: 0, actPrincipal: 0, fee: 0 }
    if (price && diff < 0) {
      const targetShares = targetMV / price
      const excessShares = r.shares - targetShares
      const maxHands = Math.floor(r.shares / r.sharesPerHand)
      const sellHands = Math.max(0, Math.min(Math.round(excessShares / r.sharesPerHand), maxHands))
      if (sellHands > 0) {
        d.action = 'sell'
        d.actHands = sellHands
        d.actPrincipal = +(sellHands * handPrice).toFixed(2)
        d.fee = +Math.max(5, (d.actPrincipal * sellFeeRate.value) / 100).toFixed(2)
      }
    }
    return d
  })

  // 2) 现金池与可用于买入的额度（现金先保住目标比例）
  const sellProceeds = derived.reduce((s, d) => s + (d.action === 'sell' ? d.actPrincipal : 0), 0)
  const sellFee = derived.reduce((s, d) => s + (d.action === 'sell' ? d.fee : 0), 0)
  const pool = cashCurrent.value + budget.value + sellProceeds - sellFee
  const availableForBuy = pool - cashTargetValue

  // 3) 低配基金买入，额度受 availableForBuy 限制（按缺口比例分配）
  const under = derived.filter((d) => d.diff > 0 && d.price)
  const totalShortfall = under.reduce((s, d) => s + d.diff, 0)
  let buyScale = 1
  if (availableForBuy <= 0) {
    buyScale = 0 // 现金已低于目标，不买入
  } else if (totalShortfall > 0) {
    const principalCap = Math.max(0, availableForBuy - under.length * 5) // 本金上限 = 可用 − 手续费底线
    if (totalShortfall > principalCap) buyScale = principalCap / totalShortfall
  }
  under.forEach((d) => {
    const alloc = d.diff * buyScale
    const buyHands = d.handPrice ? Math.floor(alloc / d.handPrice) : 0
    if (buyHands > 0) {
      d.action = 'buy'
      d.actHands = buyHands
      d.actPrincipal = +(buyHands * d.handPrice).toFixed(2)
      d.fee = +Math.max(5, (d.actPrincipal * buyFeeRate.value) / 100).toFixed(2)
    }
  })

  const finalSell = derived.reduce((s, d) => s + (d.action === 'sell' ? d.actPrincipal : 0), 0)
  const finalBuy = derived.reduce((s, d) => s + (d.action === 'buy' ? d.actPrincipal : 0), 0)
  const finalFee = derived.reduce((s, d) => s + d.fee, 0)
  const cashAfter = pool - finalBuy - (derived.reduce((s, d) => s + (d.action === 'buy' ? d.fee : 0), 0))
  const totalAfter = finalTotal - finalFee
  const cashPct = totalAfter > 0 ? (cashAfter / totalAfter) * 100 : null

  // 4) 回写源行，供模板读取（滑块 v-model 直接作用在源行 targetPct 上驱动重算）
  derived.forEach((d) => {
    const r = d.row
    r.targetMV = d.targetMV
    r.diff = d.diff
    r.action = d.action
    r.actHands = d.actHands
    r.actPrincipal = d.actPrincipal
    r.fee = d.fee
  })

  return {
    items: rows, // 源行，滑块 v-model 直接作用其上，驱动重算
    currentTotal,
    finalTotal,
    totalAfter,
    sellProceeds: finalSell,
    buyCost: finalBuy,
    totalFee: finalFee,
    cashAfter,
    cashPct,
    cashTargetPct,
  }
})

const hasAction = computed(() => plan.value.items.some((r) => r.action !== 'hold'))

async function fetchPrices() {
  const codes = fundRows.value.map((r) => r.fund_code)
  if (!codes.length) return
  loadingQuote.value = true
  try {
    const data = await quotesApi.list(codes.join(','))
    const map = Object.fromEntries((data.quotes || []).map((q) => [q.code, q]))
    fundRows.value.forEach((r) => {
      const q = map[r.fund_code]
      if (!q) return
      const p = q.ask && q.ask[0] != null ? q.ask[0] : q.last
      r.price = p
      r.handPrice = +(p * 100).toFixed(2)
      r.currentMV = +(r.shares * p).toFixed(2)
      r.currentPct = null
    })
    const totalMv = fundRows.value.reduce((s, r) => s + (r.currentMV || 0), 0) + cashCurrent.value
    fundRows.value.forEach((r) => {
      r.currentPct = totalMv > 0 ? (r.currentMV / totalMv) * 100 : null
    })
    const first = data.quotes && data.quotes[0]
    if (first && first.time) quoteTime.value = first.time
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    loadingQuote.value = false
  }
}

function openConfirm() {
  if (!hasAction.value) {
    ElMessage.warning('当前无需买卖，比例已达标')
    return
  }
  if (!rebalanceDate.value) {
    ElMessage.warning('请选择操作日期')
    return
  }
  confirmVisible.value = true
}

async function execute() {
  submitting.value = true
  try {
    const period = periodFromDate(rebalanceDate.value)
    // 1) 建/取季度记录（带 plan_id）
    let quarter = null
    try {
      quarter = await quartersApi.create({
        period,
        start_date: rebalanceDate.value,
        budget: budget.value,
        note: period + ' 再平衡',
        plan_id: planId.value,
      })
    } catch {
      const all = await quartersApi.list({ plan_id: planId.value }).catch(() => [])
      quarter = (all || []).find((q) => q.period === period)
      if (!quarter) {
        ElMessage.error('创建季度记录失败')
        return
      }
    }
    const quarterId = quarter.id

    // 2) 批量记录 卖出 + 买入（带 plan_id）
    const records = plan.value.items
      .filter((r) => r.action !== 'hold')
      .map((r) => ({
        fund_id: r.fund_id,
        type: r.action,
        quarter_id: quarterId,
        plan_id: planId.value,
        purchase_date: rebalanceDate.value,
        price: r.price,
        hands: r.actHands,
        shares_per_hand: 100,
        total_amount: r.action === 'sell' ? r.actPrincipal : +(r.actPrincipal + r.fee).toFixed(2),
        fee: r.fee,
        note: period + ' 再平衡' + (r.action === 'sell' ? '·卖出' : '·买入'),
      }))
    if (!records.length) {
      ElMessage.warning('无可执行的买卖')
      return
    }
    await purchasesApi.batch(records)

    // 3) 回写季度
    await quartersApi.recalc(quarterId)
    ElMessage.success(`再平衡完成：${records.filter((r) => r.type === 'sell').length} 笔卖出，${records.filter((r) => r.type === 'buy').length} 笔买入`)
    confirmVisible.value = false
    router.push('/purchases')
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    submitting.value = false
  }
}

function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

// 加载当前方案：标的/占比取方案内 plan_fund，预算默认取方案 amount，
// 若当前周期该方案已有季度则取其预算；现有市值/现金取该方案 summary/quarters。
async function loadForPlan() {
  fundRows.value = []
  cashCurrent.value = 0
  if (!planId.value) return
  try {
    const [plans, fundData, sumData, quarterData] = await Promise.all([
      planApi.list(),
      fundsApi.list({ page: 1, page_size: 100 }),
      fundsApi.summary({ plan_id: planId.value }),
      quartersApi.list({ plan_id: planId.value }),
    ])
    const plan = (plans || []).find((p) => p.id === planId.value)
    const sumMap = Object.fromEntries((sumData.funds || []).map((f) => [f.fund_id, f]))
    // 基金元数据兜底（方案内 fund_code/fund_name 缺失时用）
    const metaById = Object.fromEntries(
      (fundData.items || [])
        .filter((f) => f.fund_code !== CASH_CODE)
        .map((f) => [f.id, f])
    )
    const planFunds = plan?.funds || []
    fundRows.value = planFunds
      .filter((pf) => pf.fund_code !== CASH_CODE)
      .map((pf) => {
        const s = sumMap[pf.fund_id] || {}
        const meta = metaById[pf.fund_id] || {}
        return {
          fund_id: pf.fund_id,
          fund_code: pf.fund_code,
          fund_name: pf.fund_name || meta.fund_name,
          target_ratio: pf.target_ratio != null ? Number(pf.target_ratio) : null,
          targetPct: pf.target_ratio != null ? Number(pf.target_ratio) : 0, // 滑块目标，默认=方案比例
          price: null,
          handPrice: null,
          shares: Number(s.total_shares || 0),
          sharesPerHand: 100,
          currentMV: 0,
          currentPct: null,
        }
      })
    cashCurrent.value = (quarterData || []).reduce((s, q) => s + Number(q.cash_amount || 0), 0)
    // 预算默认用方案每次投入金额；若当前周期已有季度，预算预填其预算
    budget.value = plan && plan.amount != null ? Number(plan.amount) : 0
    const period = periodFromDate(todayStr())
    const cur = (quarterData || []).find((q) => q.period === period)
    if (cur) budget.value = Number(cur.budget || 0)
    fetchPrices()
  } catch {
    // 接口错误在拦截器已展示
  }
}

// 方案切换：重新按该方案初始化标的/预算并拉行情
async function onPlanChange() {
  await loadForPlan()
}
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
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-note {
  color: #909399;
  font-size: 13px;
  font-weight: normal;
}
.intro-note {
  color: #606266;
  font-size: 13px;
  margin-bottom: 12px;
}
.cards {
  margin-bottom: 16px;
}
.stat-label {
  color: #909399;
  font-size: 13px;
  margin-bottom: 8px;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
}
.stat-sub {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.fee-hint {
  color: #c0c4cc;
  font-size: 11px;
  margin-top: 4px;
}
.rate-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.rate-label {
  color: #606266;
  font-size: 12px;
  width: 24px;
}
.main-table {
  margin-bottom: 12px;
}
.fund-name {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.fund-name .code {
  color: #909399;
  font-size: 12px;
}
.target-pct {
  color: #909399;
}
.slider-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.slider {
  flex: 1;
}
.pct-text {
  width: 44px;
  text-align: right;
  color: #606266;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.sell-amt {
  color: #67c23a;
  font-weight: 600;
}
.buy-amt {
  color: #f56c6c;
  font-weight: 600;
}
.cash {
  color: #409eff;
}
.muted {
  color: #909399;
}
.plan-summary {
  display: flex;
  gap: 18px;
  color: #606266;
  font-size: 13px;
  padding: 10px 14px;
  background: #f5f7fa;
  border-radius: 6px;
}
.submit-bar {
  display: flex;
  align-items: center;
  gap: 12px;
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
.entry-hint {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
  color: #c0c4cc;
  font-size: 12px;
}
</style>
