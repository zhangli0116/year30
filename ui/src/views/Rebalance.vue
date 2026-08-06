<template>
  <div class="rebalance">
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
        按「规定比例」目标，<b>超配的基金卖出、低配的买入</b>，卖出回笼并入现金池后统一分配；
        手续费 = max(5, 金额×费率)。用于买入式无法纠正的超配仓位。
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
        <el-table-column label="目标占比" width="90" align="right">
          <template #default="{ row }">
            <span class="target-pct">{{ row.target_ratio == null ? '-' : Number(row.target_ratio).toFixed(2) + '%' }}</span>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fundsApi, purchasesApi, quartersApi, quotesApi } from '../api'

const router = useRouter()
const CASH_CODE = '000000'

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

// 再平衡方案：超配卖出、低配买入，现金池 = 现有现金 + 预算 + 卖回笼 − 买支出 − 手续费
const plan = computed(() => {
  const rows = fundRows.value
  const currentTotal = rows.reduce((s, r) => s + (r.currentMV || 0), 0) + cashCurrent.value
  const finalTotal = currentTotal + budget.value

  const items = rows.map((r) => {
    const price = r.price
    const handPrice = r.handPrice
    const currentMV = r.currentMV || 0
    const targetPct = Number(r.target_ratio || 0)
    const targetMV = (finalTotal * targetPct) / 100
    const diff = targetMV - currentMV
    let action = 'hold'
    let actHands = 0
    let actPrincipal = 0
    let fee = 0

    if (price && diff > 0) {
      // 低配 → 买入到目标
      const buyHands = handPrice ? Math.floor(diff / handPrice) : 0
      if (buyHands > 0) {
        action = 'buy'
        actHands = buyHands
        actPrincipal = +(buyHands * handPrice).toFixed(2)
        fee = +Math.max(5, (actPrincipal * buyFeeRate.value) / 100).toFixed(2)
      }
    } else if (price && diff < 0) {
      // 超配 → 卖出超出部分到目标
      const targetShares = targetMV / price
      const excessShares = r.shares - targetShares
      const maxHands = Math.floor(r.shares / r.sharesPerHand)
      const sellHands = Math.max(0, Math.min(Math.floor(excessShares / r.sharesPerHand), maxHands))
      if (sellHands > 0) {
        action = 'sell'
        actHands = sellHands
        actPrincipal = +(sellHands * handPrice).toFixed(2)
        fee = +Math.max(5, (actPrincipal * sellFeeRate.value) / 100).toFixed(2)
      }
    }
    return { ...r, action, actHands, actPrincipal, fee, targetMV }
  })

  const sellProceeds = items.reduce((s, r) => s + (r.action === 'sell' ? r.actPrincipal : 0), 0)
  let buyCost = items.reduce((s, r) => s + (r.action === 'buy' ? r.actPrincipal : 0), 0)
  const buyRows = items.filter((r) => r.action === 'buy')
  const sellFee = items.reduce((s, r) => s + (r.action === 'sell' ? r.fee : 0), 0)
  const available = cashCurrent.value + budget.value + sellProceeds - sellFee

  if (available < 0) {
    // 现金池为负：不能买入，清空所有买入
    buyRows.forEach((r) => {
      r.action = 'hold'
      r.actHands = 0
      r.actPrincipal = 0
      r.fee = 0
    })
  } else if (buyRows.length) {
    let buyFee = buyRows.reduce((s, r) => s + r.fee, 0)
    if (buyCost + buyFee > available) {
      const scale = available / (buyCost + buyFee)
      buyRows.forEach((r) => {
        const newHands = Math.floor(r.actHands * scale)
        r.actHands = newHands
        r.actPrincipal = newHands * r.handPrice
        r.fee = newHands > 0 ? +Math.max(5, (r.actPrincipal * buyFeeRate.value) / 100).toFixed(2) : 0
        if (!newHands) r.action = 'hold'
      })
    }
  }

  const finalSell = items.reduce((s, r) => s + (r.action === 'sell' ? r.actPrincipal : 0), 0)
  const finalBuy = items.reduce((s, r) => s + (r.action === 'buy' ? r.actPrincipal : 0), 0)
  const finalFee = items.reduce((s, r) => s + r.fee, 0)
  const cashAfter = cashCurrent.value + budget.value + finalSell - finalBuy - finalFee

  return { items, currentTotal, finalTotal, sellProceeds: finalSell, buyCost: finalBuy, totalFee: finalFee, cashAfter }
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
    // 1) 建/取季度记录
    let quarter = null
    try {
      quarter = await quartersApi.create({
        period,
        start_date: rebalanceDate.value,
        budget: budget.value,
        note: period + ' 再平衡',
      })
    } catch {
      const all = await quartersApi.list().catch(() => [])
      quarter = (all || []).find((q) => q.period === period)
      if (!quarter) {
        ElMessage.error('创建季度记录失败')
        return
      }
    }
    const quarterId = quarter.id

    // 2) 批量记录 卖出 + 买入
    const records = plan.value.items
      .filter((r) => r.action !== 'hold')
      .map((r) => ({
        fund_id: r.fund_id,
        type: r.action,
        quarter_id: quarterId,
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

onMounted(async () => {
  try {
    const [sumData, fundData, quarterData] = await Promise.all([
      fundsApi.summary(),
      fundsApi.list({ page: 1, page_size: 20 }),
      quartersApi.list(),
    ])
    const all = fundData.items || []
    const sumMap = Object.fromEntries((sumData.funds || []).map((f) => [f.fund_id, f]))
    const funds = all.filter((f) => f.fund_code !== CASH_CODE)
    funds.sort((a, b) => (b.target_ratio || 0) - (a.target_ratio || 0))
    fundRows.value = funds.map((f) => {
      const s = sumMap[f.id] || {}
      return {
        fund_id: f.id,
        fund_code: f.fund_code,
        fund_name: f.fund_name,
        target_ratio: f.target_ratio != null ? Number(f.target_ratio) : null,
        price: null,
        handPrice: null,
        shares: Number(s.total_shares || 0),
        sharesPerHand: 100,
        currentMV: 0,
        currentPct: null,
      }
    })
    cashCurrent.value = (quarterData || []).reduce((s, q) => s + Number(q.cash_amount || 0), 0)
    // 若当前周期已有季度，预算预填其预算
    const period = periodFromDate(todayStr())
    const cur = (quarterData || []).find((q) => q.period === period)
    if (cur) budget.value = Number(cur.budget || 0)
    fetchPrices()
  } catch {
    // 接口错误在拦截器已展示
  }
})
</script>

<style scoped>
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
