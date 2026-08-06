<template>
  <div class="calculator">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>季度再平衡计算器</span>
          <div class="header-right">
            <span v-if="quoteTime" class="header-note">行情更新：{{ quoteTime }}</span>
            <el-button type="primary" size="small" :loading="loadingQuote" @click="fetchPrices">
              <el-icon style="margin-right: 4px"><Refresh /></el-icon>获取最新价格
            </el-button>
          </div>
        </div>
      </template>

      <div class="intro-note">
        拖动「目标占比」滑块，实时查看 <b>现有持仓 + 本季买入</b> 后的整体比例；手数可手动覆盖，滑块会自动回算。
      </div>

      <el-row :gutter="16" class="cards">
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">现有总市值</div>
            <div class="stat-value">¥ {{ money(view.currentTotal) }}</div>
          </el-card>
        </el-col>
        <el-col :span="8">
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
            <div class="stat-label fee-label">手续费费率（%）</div>
            <el-input-number
              v-model="feeRate"
              :min="0"
              :step="0.01"
              :precision="4"
              :controls="false"
              style="width: 100%"
            />
            <div class="fee-hint">手续费 = max(5, 本金×费率)，不足 5 元按 5 元</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <div class="stat-label">录入后总资产</div>
            <div class="stat-value">¥ {{ money(view.finalTotal) }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-table :data="view.arr" stripe class="main-table">
        <el-table-column label="基金" min-width="150">
          <template #default="{ row }">
            <div class="fund-name">
              <span class="code">{{ row.fund_code }}</span>
              <span>{{ row.fund_name }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="当前价" width="170">
          <template #default="{ row }">
            <div class="price-cell">
              <el-popover placement="bottom" trigger="click" width="170" :disabled="!row.quote">
                <template #reference>
                  <el-button size="small" :disabled="!row.quote">选价</el-button>
                </template>
                <div v-if="row.quote" class="quote-list">
                  <div class="quote-group-title">最新</div>
                  <div class="quote-item" @click="pickPrice(row, row.quote.last, '最新')">
                    最新　{{ fmtPrice(row.quote.last) }}
                  </div>
                  <div class="quote-group-title">卖盘（默认卖1）</div>
                  <div
                    v-for="(p, i) in row.quote.ask"
                    :key="'a' + i"
                    class="quote-item"
                    @click="pickPrice(row, p, '卖' + (i + 1))"
                  >
                    卖{{ i + 1 }}　{{ fmtPrice(p) }}
                  </div>
                  <div class="quote-group-title">买盘</div>
                  <div
                    v-for="(p, i) in row.quote.bid"
                    :key="'b' + i"
                    class="quote-item"
                    @click="pickPrice(row, p, '买' + (i + 1))"
                  >
                    买{{ i + 1 }}　{{ fmtPrice(p) }}
                  </div>
                </div>
              </el-popover>
              <span class="price-val">{{ row.price == null ? '-' : Number(row.price).toFixed(3) }}</span>
              <el-tag v-if="row.priceSource" size="small" type="info" effect="plain">
                {{ row.priceSource }}
              </el-tag>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="现有市值" width="110" align="right">
          <template #default="{ row }">
            {{ row.currentMV == null ? '-' : `¥ ${money(row.currentMV)}` }}
          </template>
        </el-table-column>
        <el-table-column label="现有占比" width="90" align="right">
          <template #default="{ row }">
            {{ row.currentPct == null ? '-' : row.currentPct.toFixed(1) + '%' }}
          </template>
        </el-table-column>

        <el-table-column label="目标占比" min-width="200" align="center">
          <template #default="{ row }">
            <div class="slider-cell">
              <el-slider
                v-model="row.targetPct"
                :min="0"
                :max="sliderMax(row)"
                :step="0.5"
                :show-tooltip="false"
                class="slider"
                @input="onSlider(row)"
                @change="onSlider(row)"
              />
              <span class="pct-text">{{ row.targetPct.toFixed(1) }}%</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="本季手数" width="110" align="center">
          <template #default="{ row }">
            <el-input-number
              v-model="row.hands"
              :min="0"
              :step="1"
              :precision="0"
              :controls="false"
              size="small"
              style="width: 80px"
              @change="onHandsChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="本季金额" width="100" align="right">
          <template #default="{ row }">¥ {{ money(row.amount) }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="80" align="right">
          <template #default="{ row }">
            <span class="fee-cell">{{ row.fee > 0 ? `¥ ${money(row.fee)}` : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="录入后市值" width="110" align="right">
          <template #default="{ row }">¥ {{ money(row.finalMV) }}</template>
        </el-table-column>
        <el-table-column label="录入后占比" width="110" align="right">
          <template #default="{ row }">
            <span :class="{ 'ratio-warn': isDeviating(row) }">
              {{ row.finalPct == null ? '-' : row.finalPct.toFixed(2) + '%' }}
            </span>
          </template>
        </el-table-column>
      </el-table>

      <el-alert
        type="info"
        :closable="false"
        class="cash-line"
        title="现金"
      >
        <div class="cash-flow">
          现有现金 ¥{{ money(cashCurrent) }} ＋ 本季现金 ¥{{ money(view.cashNew) }}
          ＝ 录入后现金 ¥{{ money(view.cashFinal) }}
          （<b>录入后占比 {{ view.cashPct == null ? '-' : view.cashPct.toFixed(2) + '%' }}</b>
          ，目标 {{ view.cashTargetPct.toFixed(1) }}%）
        </div>
        <div class="cash-breakdown">
          本季构成：目标现金 ¥{{ money(view.cashTargetAmount) }}（{{ view.cashTargetPct.toFixed(1) }}%）＋ 结余 ¥{{ signedMoney(view.cashSurplus) }}
          <span v-if="view.cashSurplus > 0" class="cash-hint">（基金少投，预算未投完）</span>
          <span v-else-if="view.cashSurplus < 0" class="cash-hint">（基金超投，动用了现金仓）</span>
        </div>
      </el-alert>

      <el-divider />

      <div class="submit-bar">
        <el-date-picker
          v-model="quarterDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="买入日期"
          style="width: 150px"
        />
        <el-input
          v-model="quarterNote"
          placeholder="备注，如 2026Q3 定投"
          style="width: 180px"
        />
        <el-button type="success" size="large" @click="submitQuarter">
          一键录入本季度
        </el-button>
      </div>
    </el-card>

    <!-- 一键录入确认弹窗 -->
    <el-dialog
      v-model="confirmVisible"
      title="一键录入本季度"
      width="560px"
      class="entry-dialog"
      :close-on-click-modal="false"
    >
      <div class="entry-head">
        <div class="entry-head-item">
          <span class="entry-label">周期</span>
          <b class="entry-period">{{ confirmData.period }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">预算</span>
          <b>¥{{ money(confirmData.budget) }}</b>
        </div>
        <div class="entry-head-item">
          <span class="entry-label">买入日期</span>
          <b>{{ quarterDate }}</b>
        </div>
      </div>

      <el-table :data="confirmData.rows" size="small" stripe class="entry-table">
        <el-table-column label="基金" min-width="140">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column prop="hands" label="手数" width="60" align="right" />
        <el-table-column label="本金" width="96" align="right">
          <template #default="{ row }">¥{{ money(row.principal) }}</template>
        </el-table-column>
        <el-table-column label="手续费" width="88" align="right">
          <template #default="{ row }"><span class="entry-fee">¥{{ money(row.fee) }}</span></template>
        </el-table-column>
        <el-table-column label="金额" width="96" align="right">
          <template #default="{ row }"><b>¥{{ money(row.amount) }}</b></template>
        </el-table-column>
      </el-table>

      <div class="entry-foot">
        <span>手续费合计 <b>¥{{ money(confirmData.totalFee) }}</b></span>
        <span class="entry-divider">｜</span>
        <span>现金 <b class="entry-cash">¥{{ money(confirmData.cashAmount) }}</b></span>
      </div>
      <div class="entry-hint">
        确认后录入「{{ confirmData.period }}」：本季权益 / 手续费 / 剩余现金将自动重算。
      </div>

      <template #footer>
        <el-button @click="confirmVisible = false">再想想</el-button>
        <el-button type="success" :loading="submitting" @click="doSubmitQuarter">确认录入</el-button>
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

const budget = ref(12500)
const feeRate = ref(0.03) // 手续费费率（%），默认 0.03
const loadingQuote = ref(false)
const quoteTime = ref(null)
const submitting = ref(false)
const cashCurrent = ref(0) // 现有现金 = Σ quarter.cash_amount
const quarterDate = ref(todayStr())
const quarterNote = ref(defaultNote())
const fundRows = ref([])

// 一键录入确认弹窗
const confirmVisible = ref(false)
const confirmData = reactive({
  period: '',
  budget: 0,
  rows: [],
  totalFee: 0,
  cashAmount: 0,
})

function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function defaultNote() {
  const now = new Date()
  const q = Math.floor(now.getMonth() / 3) + 1
  return `${now.getFullYear()}Q${q} 定投`
}

// ---- 派生视图：现有市值 / 目标 / 手数金额 / 录入后整体占比 ----
// 注意：模板行直接复用 fundRows 里的响应式行（不再浅拷贝），派生字段算好后回写上去，
// 这样滑块/手数/选价的改动会作用到响应式源，view 才会重算、金额与现金行才联动。
const view = computed(() => {
  const rows = fundRows.value
  const currentTotal =
    rows.reduce((s, r) => s + (r.price ? r.currentShares * r.price : 0), 0) +
    cashCurrent.value

  // 派生值先算到局部数组，避免从响应式行读回刚写过的字段造成自依赖
  const derived = []
  let fundAmount = 0
  let totalFee = 0
  rows.forEach((r) => {
    const handPrice = r.price ? +(r.price * 100).toFixed(2) : null
    const currentMV = r.price ? r.currentShares * r.price : null
    const currentPct =
      currentTotal > 0 && currentMV != null ? (currentMV / currentTotal) * 100 : null
    // 本金 = 手数×一手价；手续费 = max(5, 本金×费率)；本季金额 = 本金 + 手续费
    const principal = r.hands && handPrice ? +(r.hands * handPrice).toFixed(2) : 0
    const fee = principal > 0 ? +Math.max(5, (principal * feeRate.value) / 100).toFixed(2) : 0
    const amount = +(principal + fee).toFixed(2)
    derived.push({ handPrice, currentMV, currentPct, principal, fee, amount })
    fundAmount += amount
    totalFee += fee
  })

  const cashNew = Math.max(0, budget.value - fundAmount)
  const cashFinal = cashCurrent.value + cashNew
  const cashTargetPct = Math.max(
    0,
    100 - rows.reduce((s, r) => s + (r.targetPct || 0), 0)
  )
  const cashTargetAmount = (cashTargetPct / 100) * budget.value
  const cashSurplus = cashNew - cashTargetAmount
  // 录入后总资产 = 现有总市值 + 预算 − 手续费（手续费是纯成本，不成为资产）
  const finalTotal = currentTotal + budget.value - totalFee
  const finalTotalCheck =
    derived.reduce((s, d) => s + (d.currentMV ?? 0) + d.principal, 0) + cashFinal

  derived.forEach((d) => {
    // 录入后市值 = 现有市值 + 本金（手续费不增加市值）
    const finalMV = (d.currentMV ?? 0) + d.principal
    d.finalMV = finalMV
    d.finalPct = finalTotalCheck > 0 ? (finalMV / finalTotalCheck) * 100 : null
  })

  // 回写派生字段到响应式行，供模板直接读取
  rows.forEach((r, i) => {
    const d = derived[i]
    r.handPrice = d.handPrice
    r.currentMV = d.currentMV
    r.currentPct = d.currentPct
    r.principal = d.principal
    r.fee = d.fee
    r.amount = d.amount
    r.finalMV = d.finalMV
    r.finalPct = d.finalPct
  })

  return {
    arr: rows,
    currentTotal,
    finalTotal,
    fundAmount,
    totalFee,
    cashNew,
    cashFinal,
    cashTargetAmount,
    cashSurplus,
    cashPct: finalTotalCheck > 0 ? (cashFinal / finalTotalCheck) * 100 : null,
    cashTargetPct,
  }
})

// 滑块上限：单个滑块最大 = 100 − 其他基金目标之和，保证权益类总和 ≤ 100%
function sliderMax(row) {
  const others = fundRows.value
    .filter((r) => r.fund_id !== row.fund_id)
    .reduce((s, r) => s + (r.targetPct || 0), 0)
  return Math.max(0, 100 - others)
}

// ---- 滑块 → 手数（全局重算 + 预算上限）----
// 每只基金按目标占比反推需买本金；若总缺口超过本季预算，则按缺口比例缩放，
// 保证「本金 + 手续费」总投入 ≤ 预算，不会超支。
function onSlider(changedRow) {
  changedRow._manual = false
  const rows = fundRows.value
  const manual = rows.filter((r) => r._manual)
  const auto = rows.filter((r) => !r._manual)
  const finalTotal = view.value.finalTotal

  // 手动行占用的金额（本金+手续费）先从预算里扣
  const manualAmount = manual.reduce((s, r) => s + (r.amount || 0), 0)
  const budgetForAuto = Math.max(0, budget.value - manualAmount)

  // 每个自动行的目标缺口（本金）
  const needs = auto.map((r) => {
    const handPrice = r.price ? +(r.price * 100).toFixed(2) : null
    const currentMV = r.price ? r.currentShares * r.price : 0
    const targetMV = (finalTotal * (r.targetPct || 0)) / 100
    const need = Math.max(0, targetMV - currentMV)
    return { row: r, handPrice, need }
  })
  const totalNeed = needs.reduce((s, x) => s + x.need, 0)
  // 本金上限 = 预算 − 手动行 − 手续费底线（每自动行至少 5 元）
  const principalCap = Math.max(0, budgetForAuto - auto.length * 5)
  const scale = totalNeed > 0 && totalNeed > principalCap ? principalCap / totalNeed : 1
  needs.forEach(({ row, handPrice, need }) => {
    const alloc = need * scale
    row.hands = handPrice && handPrice > 0 ? Math.floor(alloc / handPrice) : 0
  })
}

// ---- 手数 → 滑块（回算隐含占比）----
function onHandsChange(row) {
  row._manual = true
  const handPrice = row.price ? +(row.price * 100).toFixed(2) : null
  const currentMV = row.price ? row.currentShares * row.price : 0
  const finalMV = currentMV + (row.hands || 0) * (handPrice || 0)
  row.targetPct =
    view.value.finalTotal > 0
      ? +(finalMV / view.value.finalTotal) * 100
      : 0
}

function pickPrice(row, price, label) {
  if (price == null) return
  row.price = price
  row.handPrice = +(price * 100).toFixed(2)
  row.priceSource = label
  if (!row._manual) onSlider(row)
}

function isDeviating(row) {
  if (row.finalPct == null || row.targetPct == null) return false
  return Math.abs(row.finalPct - row.targetPct) > 1
}

// ---- 获取最新行情（含五档），默认填卖1 ----
async function fetchPrices() {
  const codes = fundRows.value.map((r) => r.fund_code)
  if (!codes.length) return
  loadingQuote.value = true
  try {
    const data = await quotesApi.list(codes.join(','))
    const map = Object.fromEntries((data.quotes || []).map((q) => [q.code, q]))
    // 先把所有行的价格设完，再统一算手数——否则 onSlider 读 currentTotal
    // 时后面的行 price 还是 null，会低估 total 导致手数偏少
    fundRows.value.forEach((r) => {
      const q = map[r.fund_code]
      if (!q) return
      const defaultPrice = q.ask && q.ask[0] != null ? q.ask[0] : q.last
      r.quote = q
      r.price = defaultPrice
      r.handPrice = +(defaultPrice * 100).toFixed(2)
    })
    fundRows.value.forEach((r) => {
      if (r.price && !r._manual) onSlider(r)
    })
    const first = data.quotes && data.quotes[0]
    if (first && first.time) quoteTime.value = first.time
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    loadingQuote.value = false
  }
}

// ---- 一键录入本季度 ----
// 流程：建 quarter → 批量带 quarter_id 建购买记录 → recalc quarter
function periodFromDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const q = Math.floor(d.getMonth() / 3) + 1
  return d.getFullYear() + 'Q' + q
}

// 一键录入：先弹确认摘要，确认后再走 建 quarter → 批量记录 → recalc
function submitQuarter() {
  const rowsWithHands = view.value.arr.filter((r) => r.hands > 0)
  const missingPrice = rowsWithHands.some((r) => r.price == null || r.price <= 0)
  if (rowsWithHands.length === 0 || missingPrice) {
    ElMessage.warning('请先获取价格并确认每行的手数')
    return
  }
  if (!quarterDate.value) {
    ElMessage.warning('请选择买入日期')
    return
  }

  confirmData.period = periodFromDate(quarterDate.value)
  confirmData.budget = budget.value
  confirmData.rows = rowsWithHands.map((r) => ({
    name: r.fund_name,
    hands: r.hands,
    principal: r.principal || 0,
    fee: r.fee || 0,
    amount: r.amount || 0,
  }))
  confirmData.totalFee = view.value.totalFee || 0
  confirmData.cashAmount = view.value.cashNew || 0
  confirmVisible.value = true
}

async function doSubmitQuarter() {
  submitting.value = true
  try {
    const period = confirmData.period
    const rowsWithHands = view.value.arr.filter((r) => r.hands > 0)

    // 1) 先建/取季度记录（避免取消时留下空季度）
    let quarter = null
    try {
      quarter = await quartersApi.create({
        period,
        start_date: quarterDate.value,
        budget: budget.value,
        note: quarterNote.value || null,
      })
    } catch {
      // period 重复：匹配已有
      const all = await quartersApi.list().catch(() => [])
      quarter = (all || []).find((q) => q.period === period)
      if (!quarter) {
        ElMessage.error('创建季度记录失败')
        return
      }
    }
    const quarterId = quarter.id

    // 2) 批量建购买记录（带 quarter_id）
    const records = rowsWithHands.map((r) => ({
      fund_id: r.fund_id,
      quarter_id: quarterId,
      purchase_date: quarterDate.value,
      price: r.price,
      hands: r.hands,
      shares_per_hand: 100,
      total_amount: r.amount, // 本金 + 手续费
      fee: r.fee,
      note: quarterNote.value || null,
    }))
    await purchasesApi.batch(records)

    // 3) 回写 equity_amount / cash_amount
    await quartersApi.recalc(quarterId)
    ElMessage.success(`已录入 ${records.length} 条记录（${period}）`)
    confirmVisible.value = false
    router.push('/purchases')
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    submitting.value = false
  }
}

function fmtPrice(v) {
  return v == null ? '-' : Number(v).toFixed(3)
}

function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

// 带正负号的金额：+1,875.00 / -775.00
function signedMoney(v) {
  const n = Number(v || 0)
  const abs = Math.abs(n).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return (n >= 0 ? '+' : '-') + abs
}

onMounted(async () => {
  try {
    const [sumData, fundData, quarterData] = await Promise.all([
      fundsApi.summary(),
      fundsApi.list({ page: 1, page_size: 20 }),
      quartersApi.list(),
    ])
    const all = fundData.items || []
    const sumMap = Object.fromEntries(
      (sumData.funds || []).map((f) => [f.fund_id, f])
    )
    const funds = all.filter((f) => f.fund_code !== CASH_CODE)
    funds.sort((a, b) => (b.target_ratio || 0) - (a.target_ratio || 0))
    fundRows.value = funds.map((f) => {
      const s = sumMap[f.id] || {}
      return {
        fund_id: f.id,
        fund_code: f.fund_code,
        fund_name: f.fund_name,
        target_ratio: Number(f.target_ratio || 0),
        targetPct: Number(f.target_ratio || 0),
        price: null,
        handPrice: null,
        priceSource: null,
        quote: null,
        currentShares: Number(s.total_shares || 0),
        currentCost: Number(s.total_cost || 0),
        hands: 0,
        _manual: false,
      }
    })
    // 现有现金 = 各季度剩余现金之和（quarter.cash_amount）
    cashCurrent.value = (quarterData || []).reduce(
      (s, q) => s + Number(q.cash_amount || 0),
      0
    )
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
.fee-label {
  margin-top: 10px;
}
.fee-hint {
  color: #c0c4cc;
  font-size: 11px;
  margin-top: 4px;
  line-height: 1.4;
}
.fee-cell {
  color: #909399;
  font-variant-numeric: tabular-nums;
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
.price-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.price-val {
  font-variant-numeric: tabular-nums;
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
.quote-group-title {
  font-size: 12px;
  color: #909399;
  margin: 6px 0 2px;
}
.quote-item {
  padding: 5px 8px;
  font-size: 13px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
}
.quote-item:hover {
  background: #ecf5ff;
  color: #409eff;
}
.ratio-warn {
  color: #f56c6c;
  font-weight: 600;
}
.cash-line {
  margin-bottom: 8px;
}
.cash-breakdown {
  margin-top: 2px;
  color: #909399;
  font-size: 13px;
}
.cash-hint {
  color: #e6a23c;
}
.submit-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.entry-head {
  display: flex;
  gap: 28px;
  margin-bottom: 14px;
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
  font-size: 16px;
  color: #409eff;
}
.entry-table {
  margin-bottom: 12px;
}
.entry-fee {
  color: #e6a23c;
}
.entry-foot {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #606266;
}
.entry-cash {
  color: #409eff;
}
.entry-divider {
  color: #dcdfe6;
}
.entry-hint {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
  color: #c0c4cc;
  font-size: 12px;
}
</style>
