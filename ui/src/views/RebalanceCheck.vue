<template>
  <div class="rebalance-check">
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
            <el-button size="small" type="primary" @click="goCalculator">去计算器配比</el-button>
            <el-button size="small" :loading="loading" @click="load">刷新</el-button>
          </div>
        </div>
      </template>

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
        <el-table-column label="偏离" width="90" align="right">
          <template #default="{ row }">
            <span :class="row.status === 'normal' ? 'muted' : row.status === 'above' ? 'up' : 'down'">
              {{ signedPct(row.deviation) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="90" align="right">
          <template #default="{ row }">{{ row.threshold == null ? '-' : '±' + row.threshold.toFixed(2) + '%' }}</template>
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
            <span :class="row.status === 'normal' ? 'muted' : ''">{{ suggestion(row) }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!data || !data.funds.length" class="empty-tip">暂无基金数据</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { rebalanceApi } from '../api'
import { judge } from '../utils/rebalance'

const router = useRouter()
const DEFAULTS = { r_band: 15, min_abs: 1, max_abs: 3, amount_floor: 300 }

const loading = ref(false)
const saving = ref(false)
const data = ref(null) // {params, total, funds, cash}
const cfg = reactive({ ...DEFAULTS })

// 分析行：用「表单里的参数」实时预览判定（保存后才写库）
const rows = computed(() => {
  if (!data.value) return []
  const params = { ...cfg }
  const fundRows = (data.value.funds || []).map((f) => ({
    ...f,
    status: judge(f.deviation, f.threshold, params, f.deviation_amount),
  }))
  const c = data.value.cash
  if (c) {
    fundRows.push({
      fund_id: -1,
      fund_code: '000000',
      fund_name: '现金',
      price: null,
      target: c.target,
      real: c.real,
      deviation: c.deviation,
      deviation_amount: c.deviation_amount,
      threshold: c.threshold,
      status: judge(c.deviation, c.threshold, params, c.deviation_amount),
    })
  }
  return fundRows
})

const cash = computed(() => data.value?.cash || null)
const deviatingCount = computed(
  () => rows.value.filter((r) => r.status !== 'normal').length
)

async function load() {
  loading.value = true
  try {
    data.value = await rebalanceApi.check()
    Object.assign(cfg, data.value.params)
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

function goCalculator() {
  router.push('/calculator')
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

function suggestion(row) {
  if (row.status === 'normal' || row.target == null) return '—'
  const total = data.value.total
  const gap = ((Number(row.target) - Number(row.real)) / 100) * total // 正=需加仓
  const absGap = Math.abs(gap)
  // 现金行特殊语义
  if (row.fund_code === '000000') {
    return gap > 0 ? '现金偏低，可减少基金买入' : '现金偏多，可加仓低配基金'
  }
  const handPrice = row.price ? Number(row.price) * 100 : 0
  const hands = handPrice > 0 ? Math.floor(absGap / handPrice) : 0
  const action = gap > 0 ? '加仓' : '减仓'
  return hands > 0
    ? `建议${action}约 ${hands} 手（¥${absGap.toFixed(0)}）`
    : `建议${action}约 ¥${absGap.toFixed(0)}`
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

onMounted(load)
</script>

<style scoped>
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
.empty-tip {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 30px 0;
}
</style>
