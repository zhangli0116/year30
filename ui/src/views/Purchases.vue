<template>
  <el-card shadow="never">
    <template #header>
      <div class="header">
        <div class="header-left">
          <span>购买记录</span>
          <PlanSwitcher
            :model-value="planId"
            @update:model-value="planId = $event"
            @change="onPlanChange"
          />
        </div>
        <div class="header-right">
          <el-select
            v-model="filterFundId"
            placeholder="全部基金"
            clearable
            style="width: 200px"
          >
            <el-option
              v-for="f in fundOptions"
              :key="f.id"
              :label="`${f.fund_code} ${f.fund_name}`"
              :value="f.id"
            />
          </el-select>
          <el-button :loading="loading" @click="load">刷新</el-button>
        </div>
      </div>
    </template>

    <div v-loading="loading">
      <!-- 按周期分组 -->
      <div v-for="q in quarterViews" :key="q.id" class="quarter-card">
        <div class="quarter-header">
          <div class="q-left" @click="toggle(q.id)">
            <el-icon class="q-arrow">
              <ArrowDown v-if="isExpanded(q.id)" />
              <ArrowRight v-else />
            </el-icon>
            <span class="q-period">{{ q.period }}</span>
            <span v-if="q.start_date && q.end_date" class="q-meta">{{ q.start_date }} ~ {{ q.end_date }}</span>
            <span v-else-if="q.start_date" class="q-meta">{{ q.start_date }} 起</span>
          </div>
          <div class="q-stats">
            <span class="q-stat">
              预算
              <el-input-number
                v-model="q.budget"
                :min="0"
                :step="100"
                :precision="2"
                :controls="false"
                size="small"
                style="width: 110px"
                @change="saveBudget(q)"
              />
            </span>
            <span class="q-stat">权益 <b>¥{{ money(q.equityAmount) }}</b></span>
            <span class="q-stat">手续费 <b>¥{{ money(q.totalFee) }}</b></span>
            <span class="q-stat">剩余现金 <b class="cash-val">¥{{ money(q.cashAmount) }}</b></span>
            <span class="q-stat">{{ countFor(q) }} 条记录</span>
          </div>
        </div>

        <el-collapse-transition>
          <div v-show="isExpanded(q.id)" class="q-body">
            <el-table :data="filteredRecords(q)" stripe size="small">
              <el-table-column label="基金" min-width="170">
                <template #default="{ row }">
                  <div class="fund-cell">
                    <el-tag v-if="row.type === 'sell'" type="danger" size="small" effect="plain">卖</el-tag>
                    <el-tag v-else type="success" size="small" effect="plain">买</el-tag>
                    <span>{{ fundName(row.fund_id) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="purchase_date" label="交易日期" width="120" />
              <el-table-column label="单价" width="100" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(4) }}</template>
              </el-table-column>
              <el-table-column prop="hands" label="手数" width="70" align="right" />
              <el-table-column label="份数" width="100" align="right">
                <template #default="{ row }">
                  {{ (row.hands * row.shares_per_hand).toLocaleString('zh-CN') }}
                </template>
              </el-table-column>
              <el-table-column label="金额" width="120" align="right">
                <template #default="{ row }">¥ {{ Number(row.total_amount).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="手续费" width="80" align="right">
                <template #default="{ row }">¥ {{ Number(row.fee || 0).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="note" label="备注" min-width="110" show-overflow-tooltip />
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                  <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="q-actions">
              <el-button type="primary" size="small" @click="openCreate(q.id)">
                ＋ 新增记录
              </el-button>
            </div>
          </div>
        </el-collapse-transition>
      </div>

      <!-- 未归类记录（不在任何周期内） -->
      <div v-if="orphanRecords.length" class="quarter-card orphan-card">
        <div class="quarter-header">
          <div class="q-left" @click="orphanExpanded = !orphanExpanded">
            <el-icon class="q-arrow">
              <ArrowDown v-if="orphanExpanded" />
              <ArrowRight v-else />
            </el-icon>
            <span class="q-period">未归类记录</span>
            <span class="q-meta">（未关联周期）</span>
          </div>
          <div class="q-stats"><span class="q-stat">{{ orphanRecords.length }} 条记录</span></div>
        </div>
        <el-collapse-transition>
          <div v-show="orphanExpanded" class="q-body">
            <el-table :data="orphanRecords" stripe size="small">
              <el-table-column label="基金" min-width="170">
                <template #default="{ row }">
                  <div class="fund-cell">
                    <el-tag v-if="row.type === 'sell'" type="danger" size="small" effect="plain">卖</el-tag>
                    <el-tag v-else type="success" size="small" effect="plain">买</el-tag>
                    <span>{{ fundName(row.fund_id) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="purchase_date" label="交易日期" width="120" />
              <el-table-column label="单价" width="100" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(4) }}</template>
              </el-table-column>
              <el-table-column prop="hands" label="手数" width="70" align="right" />
              <el-table-column label="份数" width="100" align="right">
                <template #default="{ row }">
                  {{ (row.hands * row.shares_per_hand).toLocaleString('zh-CN') }}
                </template>
              </el-table-column>
              <el-table-column label="金额" width="120" align="right">
                <template #default="{ row }">¥ {{ Number(row.total_amount).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column label="手续费" width="80" align="right">
                <template #default="{ row }">¥ {{ Number(row.fee || 0).toFixed(2) }}</template>
              </el-table-column>
              <el-table-column prop="note" label="备注" min-width="110" show-overflow-tooltip />
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                  <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-transition>
      </div>

      <el-empty
        v-if="!quarterViews.length && !orphanRecords.length"
        description="暂无记录，去「季度计算器」一键录入本季度"
      />
    </div>

    <!-- 新增 / 编辑弹窗（保留：选价五档 / 手数 / 每手份数 / 金额 / 备注） -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.type" @change="onTypeChange">
            <el-radio-button value="buy">买入</el-radio-button>
            <el-radio-button value="sell">卖出</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="周期" prop="quarter_id">
          <div class="quarter-field">
            <el-select
              v-model="form.quarter_id"
              placeholder="选择周期（不选则归入未归类）"
              clearable
              style="flex: 1"
            >
              <el-option
                v-for="q in quarterOptions"
                :key="q.id"
                :label="q.period"
                :value="q.id"
              />
            </el-select>
            <el-button size="small" @click="openNewQuarter">新建周期</el-button>
          </div>
        </el-form-item>
        <el-form-item label="基金" prop="fund_id">
          <el-select
            v-model="form.fund_id"
            placeholder="请选择基金"
            style="width: 100%"
            @change="loadQuote"
          >
            <el-option
              v-for="f in fundOptions"
              :key="f.id"
              :label="`${f.fund_code} ${f.fund_name}`"
              :value="f.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="交易日期" prop="purchase_date">
          <el-date-picker
            v-model="form.purchase_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="每股价格" prop="price">
          <div class="price-cell">
            <el-popover
              placement="bottom"
              trigger="click"
              width="170"
              :disabled="!quote"
            >
              <template #reference>
                <el-button size="small" :disabled="!quote">选价</el-button>
              </template>
              <div v-if="quote" class="quote-list">
                <div class="quote-group-title">最新</div>
                <div class="quote-item" @click="pickPrice(quote.last, '最新')">
                  最新　{{ fmtPrice(quote.last) }}
                </div>
                <div class="quote-group-title">卖盘（默认卖1）</div>
                <div
                  v-for="(p, i) in quote.ask"
                  :key="'a' + i"
                  class="quote-item"
                  @click="pickPrice(p, '卖' + (i + 1))"
                >
                  卖{{ i + 1 }}　{{ fmtPrice(p) }}
                </div>
                <div class="quote-group-title">买盘</div>
                <div
                  v-for="(p, i) in quote.bid"
                  :key="'b' + i"
                  class="quote-item"
                  @click="pickPrice(p, '买' + (i + 1))"
                >
                  买{{ i + 1 }}　{{ fmtPrice(p) }}
                </div>
              </div>
            </el-popover>
            <el-input-number
              v-model="form.price"
              :min="0.0001"
              :step="0.0001"
              :precision="4"
              :controls="false"
              style="width: 100%"
              placeholder="如 2.6760"
              @change="onPriceChange"
            />
            <el-tag v-if="priceSource" size="small" type="info" effect="plain">
              {{ priceSource }}
            </el-tag>
          </div>
        </el-form-item>
        <el-form-item label="手数" prop="hands">
          <el-input-number
            v-model="form.hands"
            :min="1"
            :step="1"
            :controls="false"
            style="width: 100%"
            placeholder="如 100"
          />
        </el-form-item>
        <el-form-item label="每手份数">
          <el-input-number
            v-model="form.shares_per_hand"
            :min="1"
            :step="1"
            :controls="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="手续费费率">
          <div class="price-cell">
            <el-input-number
              v-model="form.fee_rate"
              :min="0"
              :step="0.01"
              :precision="4"
              :controls="false"
              style="width: 100%"
              placeholder="如 0.03"
            />
            <el-tag v-if="computedFee > 0" size="small" type="warning" effect="plain">
              = ¥{{ money(computedFee) }}
            </el-tag>
          </div>
          <div class="field-tip">
            费率(%)，手续费 = max(5, {{ isSell ? '成交额' : '本金' }} × 费率)，不足 5 元按 5 元；卖出默认 0.07
          </div>
        </el-form-item>
        <el-form-item :label="isSell ? '成交金额' : '本金'">
          <el-input-number
            v-model="form.total_amount"
            :min="0.01"
            :precision="2"
            :controls="false"
            style="width: 100%"
            :placeholder="isSell ? '留空自动计算 = 成交额（不含手续费）' : '留空自动计算 = 本金（不含手续费）'"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="如 2026Q3 定投" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 新建周期弹窗（嵌套在记录弹窗内） -->
    <el-dialog
      v-model="newQuarterVisible"
      title="新建周期"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px">
        <el-form-item label="起始日期" required>
          <el-date-picker
            v-model="newQuarterForm.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择起始日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="预算" required>
          <el-input-number
            v-model="newQuarterForm.budget"
            :min="0"
            :precision="2"
            :controls="false"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="周期标识">
          <span>{{ newQuarterForm.period }}</span>
          <span class="muted">（按方案间隔自动生成）</span>
        </el-form-item>
        <el-form-item label="周期区间">
          <span>{{ newQuarterForm.start_date || '—' }} ~ {{ newQuarterForm.end_date || '—' }}</span>
          <span class="muted">（结束 = 起始 + 方案间隔 {{ planIntervalDays() }} 天）</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newQuarterVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="createQuarter">创建</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import { fundsApi, planApi, purchasesApi, quartersApi, quotesApi } from '../api'
import { intervalLabel, periodFromDate } from '../utils/plan'

// 当前选中的定投方案：季度与购买记录都按方案过滤
const planId = ref(null)
const currentPlan = ref(null) // 当前方案（取 interval/amount，用于新建周期）

// 新建周期弹窗
const newQuarterVisible = ref(false)
const newQuarterForm = reactive({ start_date: '', budget: 0, period: '', end_date: '' })

// 方案间隔天数（周期区间用；缺失回退 91 天）
function planIntervalDays() {
  return currentPlan.value?.interval_days || 91
}

// 日期 + 天数 → 新日期
function addDays(dateStr, days) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  d.setDate(d.getDate() + days)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

watch(
  () => newQuarterForm.start_date,
  (v) => {
    newQuarterForm.period = periodFromDate(v, intervalLabel(currentPlan.value?.interval_days))
    newQuarterForm.end_date = addDays(v, planIntervalDays()) // 结束 = 起始 + 方案间隔
  }
)

const loading = ref(false)
const fundOptions = ref([])
const fundMap = ref({})
const quartersRaw = ref([]) // 原始季度（供下拉选择）
const quarterViews = ref([]) // 季度 + 其下记录 + 折叠状态
const orphanRecords = ref([]) // 未关联季度的记录
const expandedMap = reactive({}) // quarter_id -> 是否展开（默认展开）
const orphanExpanded = ref(true)
const filterFundId = ref(null)

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formRef = ref()
const quote = ref(null) // 当前基金的行情 {last, bid, ask}
const priceSource = ref(null)
let suppressClear = false
const form = reactive({
  type: 'buy', // buy=买入 / sell=卖出
  quarter_id: null,
  fund_id: null,
  purchase_date: '',
  price: null,
  hands: null,
  shares_per_hand: 100,
  total_amount: null,
  fee_rate: 0.03,
  note: '',
})

const rules = {
  fund_id: [{ required: true, message: '请选择基金', trigger: 'change' }],
  purchase_date: [{ required: true, message: '请选择交易日期', trigger: 'change' }],
  price: [{ required: true, message: '请输入每股价格', trigger: 'blur' }],
  hands: [{ required: true, message: '请输入手数', trigger: 'blur' }],
}

const quarterOptions = computed(() => quartersRaw.value)

const isSell = computed(() => form.type === 'sell')

const dialogTitle = computed(() => {
  const action = isSell.value ? '卖出' : '买入'
  return `${isEdit.value ? '编辑' : '新增'}${action}记录`
})

// 手续费 = max(5, 本金/成交额 × 费率%)；买入默认 0.03、卖出默认 0.07
const computedFee = computed(() => {
  const principal = Number(form.price || 0) * (form.hands || 0) * (form.shares_per_hand || 100)
  if (principal <= 0) return 0
  return Math.max(5, +(principal * (form.fee_rate || (isSell.value ? 0.07 : 0.03)) / 100).toFixed(2))
})

// 编辑时回显费率：数据库只存手续费金额、不存费率，无法可靠反推。
// 手续费被最低 5 元钳制（不足 5 按 5）时，fee/principal 会虚高（如 5/几百 = 1%+），
// 一律回类型默认费率（买入 0.03 / 卖出 0.07）；
// 仅当手续费确实超过最低 5 元（费率真实生效）时才用 fee/principal 反推展示。
function effectiveRate(fee, principal, sell = false) {
  const dflt = sell ? 0.07 : 0.03
  if (principal <= 0) return dflt
  if (fee <= 5) return dflt
  const r = (fee / principal) * 100
  return r <= dflt ? dflt : +r.toFixed(4)
}

function fundName(id) {
  return fundMap.value[id] || `#${id}`
}

function isExpanded(id) {
  return expandedMap[id] !== false
}
function toggle(id) {
  expandedMap[id] = !isExpanded(id)
}

// 基金筛选：只影响记录列表显示，不影响季度权益/现金
function filteredRecords(q) {
  if (!filterFundId.value) return q.records
  return q.records.filter((r) => r.fund_id === filterFundId.value)
}
function countFor(q) {
  if (!filterFundId.value) return q.records.length
  return q.records.filter((r) => r.fund_id === filterFundId.value).length
}

async function load() {
  loading.value = true
  try {
    const pp = planId.value ? { plan_id: planId.value } : {}
    const [qData, pData, fData, plans] = await Promise.all([
      quartersApi.list(pp),
      purchasesApi.list({ page: 1, page_size: 100, ...pp }), // 默认排除现金记录
      fundsApi.list({ page: 1, page_size: 100 }),
      planApi.list().catch(() => []),
    ])
    currentPlan.value = (plans || []).find((p) => p.id === planId.value) || null
    quartersRaw.value = qData || []
    // 现金基金不作为可选基金
    const real = (fData.items || []).filter((f) => f.fund_code !== '000000')
    fundOptions.value = real
    fundMap.value = Object.fromEntries(real.map((f) => [f.id, f.fund_name]))

    const qIdSet = new Set(quartersRaw.value.map((q) => q.id))
    const grouped = {}
    const orphans = []
    for (const r of pData.items || []) {
      if (r.quarter_id && qIdSet.has(r.quarter_id)) {
        if (!grouped[r.quarter_id]) grouped[r.quarter_id] = []
        grouped[r.quarter_id].push(r)
      } else {
        orphans.push(r)
      }
    }
    quarterViews.value = quartersRaw.value.map((q) => ({
      ...q,
      budget: Number(q.budget), // el-input-number 需要数字，避免字符串警告
      records: grouped[q.id] || [],
      // equity_amount / total_fee / cash_amount 由后端 quarter 表承载
      equityAmount: Number(q.equity_amount),
      totalFee: Number(q.total_fee),
      cashAmount: Number(q.cash_amount),
    }))
    orphanRecords.value = orphans
  } finally {
    loading.value = false
  }
}

// 方案切换：重新按该方案拉取季度与购买记录
async function onPlanChange() {
  await load()
}

// 修改季度预算：后端自动重算 cash_amount
async function saveBudget(q) {
  try {
    await quartersApi.update(q.id, { budget: q.budget })
    ElMessage.success(`${q.period} 预算已更新，剩余现金已重算`)
  } catch {
    // 失败则回滚显示
  }
  await load()
}

function todayStr() {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

// 新建周期：按方案间隔自动生成 period，创建后回填到当前记录弹窗
function openNewQuarter() {
  newQuarterForm.start_date = todayStr()
  newQuarterForm.budget =
    currentPlan.value && currentPlan.value.amount != null
      ? Number(currentPlan.value.amount)
      : 0
  newQuarterForm.period = periodFromDate(
    newQuarterForm.start_date,
    intervalLabel(currentPlan.value?.interval_days)
  )
  newQuarterForm.end_date = addDays(newQuarterForm.start_date, planIntervalDays())
  newQuarterVisible.value = true
}

async function createQuarter() {
  if (!newQuarterForm.start_date) {
    ElMessage.warning('请选择起始日期')
    return
  }
  if (newQuarterForm.budget <= 0) {
    ElMessage.warning('请输入预算')
    return
  }
  saving.value = true
  try {
    const q = await quartersApi.create({
      plan_id: planId.value,
      period: newQuarterForm.period,
      start_date: newQuarterForm.start_date,
      end_date: newQuarterForm.end_date || null,
      budget: newQuarterForm.budget,
    })
    ElMessage.success(`周期 ${q.period} 已创建`)
    newQuarterVisible.value = false
    form.quarter_id = q.id
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function openCreate(quarterId) {
  Object.assign(form, {
    type: 'buy',
    quarter_id: quarterId ?? null,
    fund_id: null,
    purchase_date: todayStr(),
    price: null,
    hands: null,
    shares_per_hand: 100,
    total_amount: null,
    fee_rate: 0.03,
    note: '',
  })
  quote.value = null
  priceSource.value = null
  isEdit.value = false
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  const sell = row.type === 'sell'
  const principal = Number(row.price) * row.hands * row.shares_per_hand
  Object.assign(form, {
    type: row.type || 'buy',
    quarter_id: row.quarter_id,
    fund_id: row.fund_id,
    purchase_date: row.purchase_date,
    price: Number(row.price),
    hands: row.hands,
    shares_per_hand: row.shares_per_hand,
    total_amount: row.total_amount != null ? Number(row.total_amount) : null,
    fee_rate: effectiveRate(Number(row.fee || 0), principal, sell),
    note: row.note || '',
  })
  quote.value = null
  priceSource.value = null
  isEdit.value = true
  editingId.value = row.id
  dialogVisible.value = true
  loadQuote()
}

// 切换买卖类型时，重置费率默认为该类型的缺省值
function onTypeChange() {
  form.fee_rate = isSell.value ? 0.07 : 0.03
}

// 按当前选中的基金拉行情（含五档），现金基金不取
async function loadQuote() {
  quote.value = null
  priceSource.value = null
  const fund = fundOptions.value.find((f) => f.id === form.fund_id)
  if (!fund || fund.fund_code === '000000') return
  try {
    const data = await quotesApi.list(fund.fund_code)
    quote.value = data.quotes && data.quotes[0]
  } catch {
    quote.value = null
  }
}

function pickPrice(price, label) {
  if (price == null) return
  suppressClear = true
  form.price = price
  priceSource.value = label
  suppressClear = false
}

function onPriceChange() {
  if (!suppressClear) priceSource.value = null
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

async function handleSubmit() {
  await formRef.value.validate()
  // 周期与交易日匹配校验：选了周期时，交易日期应在周期 [start_date, end_date] 内。
  // 不匹配则提示用户去修改周期或交易日期，系统不自行决定。
  if (form.quarter_id && form.purchase_date) {
    const q = quarterOptions.value.find((x) => x.id === form.quarter_id)
    if (q) {
      const pd = new Date(form.purchase_date)
      const tooEarly = q.start_date && pd < new Date(q.start_date)
      const tooLate = q.end_date && pd > new Date(q.end_date)
      if (tooEarly || tooLate) {
        const range = `${q.start_date || '—'} ~ ${q.end_date || '—'}`
        try {
          await ElMessageBox.confirm(
            `交易日期 ${form.purchase_date} 不在周期 ${q.period}（${range}）内。\n请去修改周期或交易日期，使其匹配。`,
            '周期与交易日期不匹配',
            {
              confirmButtonText: '返回修改',
              cancelButtonText: '仍要保存',
              type: 'warning',
            }
          )
          return // 用户选择返回修改，不保存
        } catch {
          // 用户选择仍要保存，继续提交
        }
      }
    }
  }
  const payload = {
    type: form.type,
    quarter_id: form.quarter_id,
    fund_id: form.fund_id,
    plan_id: planId.value,
    purchase_date: form.purchase_date,
    price: form.price,
    hands: form.hands,
    shares_per_hand: form.shares_per_hand,
    fee: computedFee.value,
    note: form.note || null,
  }
  // 金额留空时不传，由后端按 本金/成交额（不含手续费）自动计算
  if (form.total_amount != null) payload.total_amount = form.total_amount

  saving.value = true
  try {
    if (isEdit.value) {
      await purchasesApi.update(editingId.value, payload)
    } else {
      await purchasesApi.create(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load() // 保存后季度权益/现金由后端自动重算
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除 ${row.purchase_date} 的${row.type === 'sell' ? '卖出' : '买入'}记录吗？`,
      '提示',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await purchasesApi.remove(row.id)
  ElMessage.success('删除成功')
  load() // 删除后季度权益/现金由后端自动重算
}

</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-right {
  display: flex;
  gap: 8px;
}
.quarter-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-bottom: 12px;
  background: #fff;
}
.quarter-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: default;
}
.q-left {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.fund-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fund-cell .el-tag {
  margin: 0;
}
.q-arrow {
  color: #909399;
}
.q-period {
  font-size: 15px;
  font-weight: 600;
}
.q-meta {
  color: #909399;
  font-size: 12px;
}
.q-stats {
  display: flex;
  align-items: center;
  gap: 18px;
  color: #606266;
  font-size: 13px;
}
.q-stat {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
.q-stat .el-input-number {
  margin-left: 2px;
}
.cash-val {
  color: #409eff;
}
.q-body {
  border-top: 1px solid #ebeef5;
  padding: 10px 14px;
}
.q-actions {
  margin-top: 10px;
}
.orphan-card .q-period {
  color: #909399;
}
.quarter-field {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.muted {
  color: #c0c4cc;
}
.price-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.price-cell .el-input-number {
  flex: 1;
}
.field-tip {
  width: 100%;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
  margin-top: 4px;
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
</style>
