<template>
  <div class="rebalance-check">
    <div class="plan-bar">
      <PlanSwitcher
        :model-value="planId"
        @update:model-value="planId = $event"
        @change="onPlanChange"
      />
    </div>

    <!-- 判定参数 -->
    <el-card shadow="never" class="cfg-card">
      <template #header>
        <div class="card-header">
          <span>判定参数</span>
          <div class="header-right">
            <span class="header-note">
              阈值(%) = clamp(目标% × 相对带, 底线, 上限)；|偏离| 超阈值且偏离金额 ≥ 底线才提示
            </span>
            <el-button size="small" @click="resetParams">恢复默认</el-button>
            <el-button size="small" type="primary" :loading="saving" @click="saveParams">保存</el-button>
          </div>
        </div>
      </template>
      <div class="cfg-grid">
        <div class="cfg-item">
          <span class="cfg-label">相对带 R（%）</span>
          <el-input-number v-model="cfg.r_band" :min="0" :max="100" :step="1" :precision="1" controls-position="right" />
        </div>
        <div class="cfg-item">
          <span class="cfg-label">绝对底线（%）</span>
          <el-input-number v-model="cfg.min_abs" :min="0" :max="10" :step="0.5" :precision="1" controls-position="right" />
        </div>
        <div class="cfg-item">
          <span class="cfg-label">绝对上限（%）</span>
          <el-input-number v-model="cfg.max_abs" :min="0" :max="20" :step="0.5" :precision="1" controls-position="right" />
        </div>
        <div class="cfg-item">
          <span class="cfg-label">金额底线（元）</span>
          <el-input-number v-model="cfg.amount_floor" :min="0" :step="100" controls-position="right" />
        </div>
      </div>
      <div class="cfg-tip">
        调整参数后分析表实时预览；「保存」会写入数据库。小目标仓位相对更紧（按比例），大目标仓位受上限封顶。
      </div>
    </el-card>

    <!-- 偏离分析 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>偏离分析</span>
          <div class="header-right">
            <span class="header-note">
              总市值 ¥{{ money(data?.total) }} · 现金占比 {{ cash ? cash.real.toFixed(2) + '%' : '-' }} · 需关注 {{ deviatingCount }} 项
            </span>
            <el-button size="small" type="primary" @click="goAction">{{ actionLabel }}</el-button>
            <el-button size="small" :loading="loading" @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <div class="rb-note">
        判定说明：阈值 = clamp(目标% × R, 底线, 上限)。
        <b>「偏离」列</b>：上行为<em>绝对偏离</em>（百分点 = 当前占比 − 目标占比），下行为<em>相对偏离</em>（= |偏离| ÷ 目标，相对自身目标真实跑偏幅度）；
        <b>「阈值」列</b>：上行为绝对阈值，下行标注其相对目标的比例（= R）或触底线/上限。
        同一绝对偏离，目标越小相对幅度越大。
      </div>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column label="基金" min-width="150">
          <template #default="{ row }">
            <div class="fund-name">
              <span class="code">{{ row.fund_code || '现金' }}</span>
              <span>{{ row.fund_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="现价" width="90" align="right">
          <template #default="{ row }">{{ row.price == null ? '-' : Number(row.price).toFixed(3) }}</template>
        </el-table-column>
        <el-table-column label="目标" width="80" align="right">
          <template #default="{ row }">{{ row.target == null ? '-' : row.target.toFixed(2) + '%' }}</template>
        </el-table-column>
        <el-table-column label="当前" width="90" align="right">
          <template #default="{ row }">{{ row.real.toFixed(2) + '%' }}</template>
        </el-table-column>
        <el-table-column label="偏离" width="120" align="right">
          <template #default="{ row }">
            <div class="two-line">
              <span
                class="main"
                :class="row.status === 'normal' ? 'muted' : row.status === 'above' ? 'up' : 'down'"
                :title="'绝对偏离（百分点）= 当前占比 − 目标占比'"
              >
                {{ signedPct(row.deviation) }}
              </span>
              <span class="sub" :title="'相对偏离 = |偏离| ÷ 目标：该基金相对自身目标比例的真实跑偏幅度'">
                相对 {{ relDev(row) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="130" align="right">
          <template #default="{ row }">
            <div v-if="row.threshold != null" class="two-line">
              <span class="main" :title="'阈值 = clamp(目标% × R, 底线, 上限)，超出才提示'">
                ±{{ row.threshold.toFixed(2) }}%
              </span>
              <span class="sub" :title="'阈值相对目标的比例 = 阈值 ÷ 目标；触底线/上限时小于 R'">
                {{ thresholdRel(row) }}
              </span>
            </div>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="偏离金额" width="120" align="right">
          <template #default="{ row }">{{ signedMoney(row.deviation_amount) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="tagType(row)" effect="plain">{{ tagText(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建议动作" min-width="190">
          <template #default="{ row }">
            <span :class="row.status === 'normal' ? 'muted' : ''">{{ row.suggestion }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!data || !data.funds.length" class="empty-tip">暂无基金数据</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PlanSwitcher from '../components/PlanSwitcher.vue'
import { rebalanceApi } from '../api'

const router = useRouter()
const DEFAULTS = { r_band: 15, min_abs: 1, max_abs: 3, amount_floor: 300 }

// 当前选中的定投方案
const planId = ref(null)

const loading = ref(false)
const saving = ref(false)
const data = ref(null) // {params, total, funds, cash}
const cfg = reactive({ ...DEFAULTS })

// 分析行：status 与 suggestion 由后端统一计算（前端只展示）
const rows = computed(() => {
  if (!data.value) return []
  const fundRows = (data.value.funds || []).map((f) => ({ ...f }))
  const c = data.value.cash
  if (c) {
    fundRows.push({ ...c, fund_id: -1, fund_code: '000000', fund_name: '现金', price: null })
  }
  return fundRows
})

const cash = computed(() => data.value?.cash || null)
const deviatingCount = computed(
  () => rows.value.filter((r) => r.status !== 'normal').length
)
// 存在超配 → 需卖出纠正（买入式无法处理），跳「临时再平衡」；否则补低配，跳「定投与再平衡计算器」
const hasOver = computed(() => rows.value.some((r) => r.status === 'above'))
const actionLabel = computed(() => (hasOver.value ? '去临时再平衡' : '去计算器配比'))

let loadedKey = null // 最近一次生效的参数快照，用于预览去重

// 方案内参数：check 时带 plan_id
function planParams() {
  return planId.value ? { plan_id: planId.value } : {}
}

// 初始/刷新：取保存参数 + 分析结果（按当前方案）
async function load() {
  loading.value = true
  try {
    const d = await rebalanceApi.check(planParams())
    data.value = d
    loadedKey = JSON.stringify({ ...d.params, plan_id: planId.value })
    Object.assign(cfg, d.params)
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

// 方案切换：重新加载分析结果
async function onPlanChange() {
  await load()
}

// 参数变化时用「未保存的参数」向后端做预览（后端统一判定，不落库）
let previewTimer = null
watch(cfg, () => {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(preview, 300)
}, { deep: true })

async function preview() {
  const key = JSON.stringify({ ...cfg, plan_id: planId.value })
  if (key === loadedKey) return // 与生效参数一致，无需刷新
  loading.value = true
  try {
    data.value = await rebalanceApi.check({ ...cfg, ...planParams() })
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function saveParams() {
  saving.value = true
  try {
    const updated = await rebalanceApi.saveParams({ ...cfg })
    Object.assign(cfg, updated)
    ElMessage.success('判定参数已保存')
    await load()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function resetParams() {
  Object.assign(cfg, DEFAULTS)
}

function goAction() {
  router.push(hasOver.value ? '/rebalance' : '/calculator')
}

function tagType(row) {
  if (row.target == null) return 'info'
  if (row.status === 'above') return 'danger'
  if (row.status === 'below') return 'warning'
  return 'success'
}
function tagText(row) {
  if (row.target == null) return '未设目标'
  if (row.status === 'above') return '超配'
  if (row.status === 'below') return '低配'
  return '达标'
}

// 相对幅度：|偏离| ÷ 目标（相对自身目标的真实跑偏幅度）
function relDev(row) {
  if (row.target == null || !row.target) return '-'
  return (Math.abs(row.deviation) / row.target * 100).toFixed(1) + '%'
}
// 阈值来源：用「未钳制的自然阈值」(目标×R) 严格判断是否真被底线/上限改变；
// 只有真的被压/被抬的才标"触上限/触底线"，否则统一显示相对目标比例（= R）
function thresholdRel(row) {
  if (row.threshold == null || row.target == null) return '-'
  const raw = (row.target * cfg.r_band) / 100 // 自然阈值（未钳制）
  if (raw > cfg.max_abs) return `触上限 ${cfg.max_abs}%` // 被上限压到 max_abs
  if (raw < cfg.min_abs) return `触底线 ${cfg.min_abs}%` // 被底线抬到 min_abs
  return '相对目标 ' + (row.threshold / row.target * 100).toFixed(1) + '%'
}

function signedPct(v) {
  const n = Number(v || 0)
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}
function signedMoney(v) {
  const n = Number(v || 0)
  const abs = Math.abs(n).toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
  return (n >= 0 ? '+' : '-') + '¥' + abs
}
function money(v) {
  return Number(v || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

</script>

<style scoped>
.plan-bar {
  margin-bottom: 16px;
}
.cfg-card {
  margin-bottom: 16px;
}
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
}
.header-note {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
}
.cfg-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
}
.cfg-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.cfg-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}
.cfg-tip {
  margin-top: 10px;
  color: #c0c4cc;
  font-size: 12px;
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
.up {
  color: #f56c6c;
}
.down {
  color: #67c23a;
}
.muted {
  color: #c0c4cc;
}
.rb-note {
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
  line-height: 1.6;
}
.rb-note em {
  color: #606266;
  font-style: normal;
  font-weight: 600;
}
.two-line {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  line-height: 1.4;
}
.two-line .main {
  font-variant-numeric: tabular-nums;
}
.two-line .sub {
  color: #c0c4cc;
  font-size: 12px;
  white-space: nowrap;
}
.empty-tip {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 30px 0;
}
</style>
