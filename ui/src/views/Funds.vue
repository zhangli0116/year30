<template>
  <div class="funds-page">
  <el-card shadow="never">
    <template #header>
      <div class="header">
        <span>基金管理</span>
        <div class="header-right">
          <el-input
            v-model="query.keyword"
            placeholder="搜索代码或名称"
            clearable
            style="width: 220px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button type="success" @click="openCreate">新增基金</el-button>
        </div>
      </div>
    </template>

    <el-table :data="funds" v-loading="loading" stripe>
      <el-table-column prop="fund_code" label="代码" width="120" />
      <el-table-column prop="fund_name" label="名称" min-width="140" />
      <el-table-column prop="exchange" label="交易所" width="100" />
      <el-table-column prop="currency" label="币种" width="80" />
      <el-table-column label="规定比例" width="100" align="right">
        <template #default="{ row }">
          {{ row.target_ratio == null ? '-' : `${Number(row.target_ratio).toFixed(2)}%` }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="query.page_size"
      :current-page="query.page"
      @current-change="onPageChange"
    />

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑基金' : '新增基金'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="基金代码" prop="fund_code">
          <el-input v-model="form.fund_code" placeholder="如 513500" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="基金名称" prop="fund_name">
          <el-input v-model="form.fund_name" placeholder="如 标普500ETF" />
        </el-form-item>
        <el-form-item label="交易所" prop="exchange">
          <el-select v-model="form.exchange">
            <el-option label="上交所" value="上交所" />
            <el-option label="深交所" value="深交所" />
          </el-select>
        </el-form-item>
        <el-form-item label="币种">
          <el-input v-model="form.currency" />
        </el-form-item>
        <el-form-item label="规定比例">
          <el-input-number
            v-model="form.target_ratio"
            :min="0"
            :max="100"
            :precision="2"
            :controls="false"
            style="width: 100%"
            placeholder="留空表示未设置，如 20"
          />
          <div class="field-tip">占总资金比例（%），留空则不参与配置统计</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>

  <!-- 定投方案管理 -->
  <el-card shadow="never" class="plan-card">
    <template #header>
      <div class="header">
        <span>定投方案管理</span>
        <div class="header-right">
          <el-button :loading="planLoading" @click="loadPlans">刷新</el-button>
          <el-button type="success" @click="openPlanCreate">新建方案</el-button>
        </div>
      </div>
    </template>

    <el-table :data="plans" v-loading="planLoading" stripe>
      <el-table-column prop="name" label="名称" min-width="120">
        <template #default="{ row }">
          <span>{{ row.name }}</span>
          <el-tag v-if="!row.active" size="small" type="info" effect="plain">停用</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="间隔" width="110" align="center">
        <template #default="{ row }">{{ row.interval_days }} 天<span class="muted">±{{ row.tolerance_days }}</span></template>
      </el-table-column>
      <el-table-column label="下次定投" min-width="150">
        <template #default="{ row }">
          <div v-if="row.next_due">
            <span class="due-range">{{ row.next_due.window_start }} ~ {{ row.next_due.window_end }}</span>
            <el-tag size="small" :type="dueTagType(row.next_due.status)" effect="plain" class="due-tag">
              {{ dueText(row.next_due.status) }}
            </el-tag>
          </div>
          <span v-else class="muted">未设起始日期</span>
        </template>
      </el-table-column>
      <el-table-column label="每次金额" width="110" align="right">
        <template #default="{ row }">¥ {{ money(row.amount) }}</template>
      </el-table-column>
      <el-table-column label="再平衡策略" width="100" align="center">
        <template #default="{ row }">{{ strategyText(row.rebalance_strategy) }}</template>
      </el-table-column>
      <el-table-column label="现金比例" width="90" align="right">
        <template #default="{ row }">{{ Number(row.cash_ratio).toFixed(2) }}%</template>
      </el-table-column>
      <el-table-column label="标的配置" min-width="220">
        <template #default="{ row }">
          <span v-if="!row.funds.length" class="muted">未配置</span>
          <el-tag
            v-for="f in row.funds"
            :key="f.fund_id"
            size="small"
            type="info"
            effect="plain"
            class="fund-tag"
          >
            {{ f.fund_code }} {{ Number(f.target_ratio).toFixed(1) }}%
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="openPlanEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="handlePlanDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div v-if="!plans.length" class="empty-tip">暂无方案，点击「新建方案」创建第一个定投方案</div>

    <!-- 方案新建 / 编辑弹窗 -->
    <el-dialog
      v-model="planDialogVisible"
      :title="planIsEdit ? '编辑方案' : '新建方案'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form ref="planFormRef" :model="planForm" :rules="planRules" label-width="100px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="方案名称" prop="name">
              <el-input v-model="planForm.name" placeholder="如 沪深300+纳指组合" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="每次金额" prop="amount">
              <el-input-number
                v-model="planForm.amount"
                :min="0"
                :step="100"
                :precision="2"
                :controls="false"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="起始日期" prop="start_date">
              <el-date-picker
                v-model="planForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="首次定投日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="间隔天数" prop="interval_days">
              <el-input-number
                v-model="planForm.interval_days"
                :min="1"
                :step="1"
                :controls="false"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="容错天数" prop="tolerance_days">
              <el-input-number
                v-model="planForm.tolerance_days"
                :min="0"
                :step="1"
                :controls="false"
                style="width: 100%"
              />
              <div class="field-tip">下次窗口 = 起始 + 间隔 ± 容错</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="再平衡策略" prop="rebalance_strategy">
              <el-select v-model="planForm.rebalance_strategy" style="width: 100%">
                <el-option label="仅体检" value="check" />
                <el-option label="买入式" value="buy" />
                <el-option label="卖出式" value="sell" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="现金比例" prop="cash_ratio">
              <el-input-number
                v-model="planForm.cash_ratio"
                :min="0"
                :max="100"
                :precision="2"
                :controls="false"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="启用">
          <el-switch v-model="planForm.active" />
        </el-form-item>

        <el-divider content-position="left">标的配置</el-divider>
        <div class="fund-editor">
          <div v-for="(pf, idx) in planForm.funds" :key="idx" class="fund-row">
            <el-select
              v-model="pf.fund_id"
              placeholder="选择基金"
              filterable
              style="width: 220px"
            >
              <el-option
                v-for="f in planFundOptions"
                :key="f.id"
                :label="`${f.fund_code} ${f.fund_name}`"
                :value="f.id"
              />
            </el-select>
            <el-input-number
              v-model="pf.target_ratio"
              :min="0"
              :max="100"
              :precision="2"
              :controls="false"
              style="width: 120px"
              placeholder="目标占比%"
            />
            <el-button link type="danger" @click="removePlanFund(idx)">删除</el-button>
          </div>
          <el-button size="small" type="primary" plain @click="addPlanFund">
            ＋ 添加基金
          </el-button>
        </div>
        <div class="ratio-tip">
          Σ 标的占比 ＋ 现金比例 应等于 100%（当前标的 {{ planFundsSum }}% ＋ 现金 {{ planForm.cash_ratio == null ? 0 : Number(planForm.cash_ratio) }}%）
        </div>
      </el-form>
      <template #footer>
        <el-button @click="planDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="planSaving" @click="handlePlanSubmit">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundsApi, planApi } from '../api'

const loading = ref(false)
const funds = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })

const dialogVisible = ref(false)
const isEdit = ref(false)
const editingId = ref(null)
const saving = ref(false)
const formRef = ref()
const form = reactive({
  fund_code: '',
  fund_name: '',
  exchange: '上交所',
  currency: 'CNY',
  target_ratio: null,
})

// ---- 定投方案管理 ----
const plans = ref([])
const planLoading = ref(false)
const planSaving = ref(false)
const planDialogVisible = ref(false)
const planIsEdit = ref(false)
const planFormRef = ref()
const planEditingId = ref(null)
const planForm = reactive({
  name: '',
  start_date: null,
  interval_days: 90,
  tolerance_days: 5,
  amount: null,
  rebalance_strategy: 'check',
  cash_ratio: null,
  active: true,
  funds: [], // [{fund_id, target_ratio}]
})
const planFundOptions = ref([]) // 方案标的可选基金（不含现金）
const planRules = {
  name: [{ required: true, message: '请输入方案名称', trigger: 'blur' }],
  amount: [{ required: true, message: '请输入每次投入金额', trigger: 'blur' }],
  interval_days: [{ required: true, message: '请输入间隔天数', trigger: 'blur' }],
  tolerance_days: [{ required: true, message: '请输入容错天数', trigger: 'blur' }],
}

const planFundsSum = computed(() =>
  planForm.funds.reduce((s, f) => s + Number(f.target_ratio || 0), 0)
)

const rules = {
  fund_code: [
    { required: true, message: '请输入基金代码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '代码为 6 位数字', trigger: 'blur' },
  ],
  fund_name: [{ required: true, message: '请输入基金名称', trigger: 'blur' }],
  exchange: [{ required: true, message: '请选择交易所', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    const data = await fundsApi.list(query)
    // 现金基金不参与基金管理，仅由 quarter 表承载，这里隐藏
    funds.value = data.items.filter((f) => f.fund_code !== '000000')
    const hasCash = data.items.some((f) => f.fund_code === '000000')
    total.value = data.total - (hasCash ? 1 : 0)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function onPageChange(page) {
  query.page = page
  load()
}

function openCreate() {
  Object.assign(form, {
    fund_code: '',
    fund_name: '',
    exchange: '上交所',
    currency: 'CNY',
    target_ratio: null,
  })
  isEdit.value = false
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    fund_code: row.fund_code,
    fund_name: row.fund_name,
    exchange: row.exchange,
    currency: row.currency,
    target_ratio: row.target_ratio != null ? Number(row.target_ratio) : null,
  })
  isEdit.value = true
  editingId.value = row.id
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (isEdit.value) {
      // 编辑时 fund_code 已禁用，payload 里已带原值，传入记录 id
      await fundsApi.update(editingId.value, form)
    } else {
      await fundsApi.create(form)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch {
    // 拦截器已弹出具体错误
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除基金「${row.fund_name}」吗？存在买入记录时会被拒绝。`,
      '提示',
      { type: 'warning' }
    )
  } catch {
    return
  }
  await fundsApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}

// ---- 方案管理操作 ----
function strategyText(v) {
  return { check: '仅体检', buy: '买入式', sell: '卖出式' }[v] || v
}
function dueText(v) {
  return { upcoming: '未到', due: '该投了', overdue: '已逾期' }[v] || v
}
function dueTagType(v) {
  return { upcoming: 'info', due: 'warning', overdue: 'danger' }[v] || 'info'
}
function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

async function loadPlans() {
  planLoading.value = true
  try {
    plans.value = (await planApi.list()) || []
  } finally {
    planLoading.value = false
  }
}

function openPlanCreate() {
  Object.assign(planForm, {
    name: '',
    start_date: null,
    interval_days: 90,
    tolerance_days: 5,
    amount: null,
    rebalance_strategy: 'check',
    cash_ratio: null,
    active: true,
    funds: [],
  })
  planIsEdit.value = false
  planDialogVisible.value = true
}

function openPlanEdit(row) {
  Object.assign(planForm, {
    name: row.name,
    start_date: row.start_date || null,
    interval_days: row.interval_days != null ? row.interval_days : 90,
    tolerance_days: row.tolerance_days != null ? row.tolerance_days : 5,
    amount: row.amount != null ? Number(row.amount) : null,
    rebalance_strategy: row.rebalance_strategy,
    cash_ratio: row.cash_ratio != null ? Number(row.cash_ratio) : null,
    active: row.active,
    funds: (row.funds || []).map((f) => ({
      fund_id: f.fund_id,
      target_ratio: Number(f.target_ratio),
    })),
  })
  planIsEdit.value = true
  planEditingId.value = row.id
  planDialogVisible.value = true
}

function addPlanFund() {
  planForm.funds.push({ fund_id: null, target_ratio: null })
}
function removePlanFund(idx) {
  planForm.funds.splice(idx, 1)
}

async function handlePlanSubmit() {
  await planFormRef.value.validate()
  // 校验：Σ 标的占比 + 现金比例 = 100
  const cash = Number(planForm.cash_ratio || 0)
  const total = planFundsSum.value + cash
  if (Math.abs(total - 100) > 0.01) {
    ElMessage.warning(`标的占比合计 ${planFundsSum.value.toFixed(2)}% ＋ 现金 ${cash.toFixed(2)}% = ${total.toFixed(2)}%，应等于 100%`)
    return
  }
  // 校验：已选基金不重复
  const ids = planForm.funds.map((f) => f.fund_id).filter((v) => v != null)
  if (new Set(ids).size !== ids.length) {
    ElMessage.warning('同一基金只能配置一次')
    return
  }
  const payload = {
    name: planForm.name,
    start_date: planForm.start_date,
    interval_days: planForm.interval_days,
    tolerance_days: planForm.tolerance_days,
    amount: planForm.amount,
    rebalance_strategy: planForm.rebalance_strategy,
    cash_ratio: planForm.cash_ratio,
    active: planForm.active,
    funds: planForm.funds
      .filter((f) => f.fund_id != null)
      .map((f) => ({ fund_id: f.fund_id, target_ratio: Number(f.target_ratio || 0) })),
  }
  planSaving.value = true
  try {
    if (planIsEdit.value) {
      await planApi.update(planEditingId.value, payload)
    } else {
      await planApi.create(payload)
    }
    ElMessage.success('方案已保存')
    planDialogVisible.value = false
    loadPlans()
  } catch {
    // 具体错误已由拦截器弹出（含后端比例校验）
  } finally {
    planSaving.value = false
  }
}

async function handlePlanDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除方案「${row.name}」吗？已有季度或购买记录归属时会被拒绝。`,
      '提示',
      { type: 'warning' }
    )
  } catch {
    return
  }
  const ok = await planApi.remove(row.id)
  if (ok !== false) ElMessage.success('方案已删除')
  loadPlans()
}

onMounted(async () => {
  load()
  loadPlans()
  // 方案编辑弹窗的基金下拉：加载真实基金元数据
  try {
    const data = await fundsApi.list({ page: 1, page_size: 100 })
    planFundOptions.value = (data.items || []).filter((f) => f.fund_code !== '000000')
  } catch {
    // 拦截器已提示
  }
})
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
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
.field-tip {
  width: 100%;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
  margin-top: 4px;
}
.plan-card {
  margin-top: 16px;
}
.fund-tag {
  margin: 2px 4px 2px 0;
}
.fund-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.fund-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ratio-tip {
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}
.muted {
  color: #c0c4cc;
}
.empty-tip {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
</style>
