<template>
  <el-card shadow="never">
    <template #header>
      <div class="header">
        <span>购买记录（按季度）</span>
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
      <!-- 按季度分组 -->
      <div v-for="q in quarterViews" :key="q.id" class="quarter-card">
        <div class="quarter-header">
          <div class="q-left" @click="toggle(q.id)">
            <el-icon class="q-arrow">
              <ArrowDown v-if="isExpanded(q.id)" />
              <ArrowRight v-else />
            </el-icon>
            <span class="q-period">{{ q.period }}</span>
            <span v-if="q.start_date" class="q-meta">{{ q.start_date }} 起</span>
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
              <el-table-column prop="purchase_date" label="购买日期" width="120" />
              <el-table-column label="单价" width="100" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(4) }}</template>
              </el-table-column>
              <el-table-column prop="hands" label="手数" width="70" align="right" />
              <el-table-column label="份数" width="100" align="right">
                <template #default="{ row }">
                  {{ (row.hands * row.shares_per_hand).toLocaleString('zh-CN') }}
                </template>
              </el-table-column>
              <el-table-column label="总金额" width="120" align="right">
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

      <!-- 未归类记录（不在任何季度内） -->
      <div v-if="orphanRecords.length" class="quarter-card orphan-card">
        <div class="quarter-header">
          <div class="q-left" @click="orphanExpanded = !orphanExpanded">
            <el-icon class="q-arrow">
              <ArrowDown v-if="orphanExpanded" />
              <ArrowRight v-else />
            </el-icon>
            <span class="q-period">未归类记录</span>
            <span class="q-meta">（未关联季度）</span>
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
              <el-table-column prop="purchase_date" label="购买日期" width="120" />
              <el-table-column label="单价" width="100" align="right">
                <template #default="{ row }">{{ Number(row.price).toFixed(4) }}</template>
              </el-table-column>
              <el-table-column prop="hands" label="手数" width="70" align="right" />
              <el-table-column label="份数" width="100" align="right">
                <template #default="{ row }">
                  {{ (row.hands * row.shares_per_hand).toLocaleString('zh-CN') }}
                </template>
              </el-table-column>
              <el-table-column label="总金额" width="120" align="right">
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
      :title="isEdit ? '编辑购买记录' : '新增购买记录'"
      width="520px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="季度" prop="quarter_id">
          <el-select
            v-model="form.quarter_id"
            placeholder="选择季度（不选则归入未归类）"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="q in quarterOptions"
              :key="q.id"
              :label="q.period"
              :value="q.id"
            />
          </el-select>
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
        <el-form-item label="购买日期" prop="purchase_date">
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
          <div class="field-tip">费率(%)，手续费 = max(5, 本金 × 费率)，不足 5 元按 5 元</div>
        </el-form-item>
        <el-form-item label="总金额">
          <el-input-number
            v-model="form.total_amount"
            :min="0.01"
            :precision="2"
            :controls="false"
            style="width: 100%"
            placeholder="留空自动计算 = 本金 + 手续费"
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
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundsApi, purchasesApi, quartersApi, quotesApi } from '../api'

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
  purchase_date: [{ required: true, message: '请选择购买日期', trigger: 'change' }],
  price: [{ required: true, message: '请输入每股价格', trigger: 'blur' }],
  hands: [{ required: true, message: '请输入手数', trigger: 'blur' }],
}

const quarterOptions = computed(() => quartersRaw.value)

// 手续费 = max(5, 本金 × 费率%)，费率默认 0.03
const computedFee = computed(() => {
  const principal = Number(form.price || 0) * (form.hands || 0) * (form.shares_per_hand || 100)
  if (principal <= 0) return 0
  return Math.max(5, +(principal * (form.fee_rate || 0.03) / 100).toFixed(2))
})

// 编辑时由存量手续费反推费率展示；等于最低 5 元时回默认 0.03
function effectiveRate(fee, principal) {
  if (principal <= 0) return 0.03
  const r = (fee / principal) * 100
  return r <= 0.03 ? 0.03 : +r.toFixed(4)
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
    const [qData, pData, fData] = await Promise.all([
      quartersApi.list(),
      purchasesApi.list({ page: 1, page_size: 100 }), // 默认排除现金记录
      fundsApi.list({ page: 1, page_size: 100 }),
    ])
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

function openCreate(quarterId) {
  Object.assign(form, {
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
  const principal = Number(row.price) * row.hands * row.shares_per_hand
  Object.assign(form, {
    quarter_id: row.quarter_id,
    fund_id: row.fund_id,
    purchase_date: row.purchase_date,
    price: Number(row.price),
    hands: row.hands,
    shares_per_hand: row.shares_per_hand,
    total_amount: row.total_amount != null ? Number(row.total_amount) : null,
    fee_rate: effectiveRate(Number(row.fee || 0), principal),
    note: row.note || '',
  })
  quote.value = null
  priceSource.value = null
  isEdit.value = true
  editingId.value = row.id
  dialogVisible.value = true
  loadQuote()
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
  const payload = {
    quarter_id: form.quarter_id,
    fund_id: form.fund_id,
    purchase_date: form.purchase_date,
    price: form.price,
    hands: form.hands,
    shares_per_hand: form.shares_per_hand,
    fee: computedFee.value,
    note: form.note || null,
  }
  // 总金额留空时不传，由后端按 本金 + 手续费 自动计算
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
      `确定删除 ${row.purchase_date} 的购买记录吗？`,
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

onMounted(load)
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
