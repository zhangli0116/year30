<template>
  <div class="settings">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
          <span class="header-note">按标的类型分别设置数据源，修改后即时生效</span>
        </div>
      </template>

      <div class="ds-section">
        <div class="ds-label">数据源配置（按标的类型分别生效）</div>
        <div v-for="t in types" :key="t.fund_type" class="ds-row">
          <div class="ds-row-label">{{ t.label }}</div>
          <div class="ds-control">
            <el-select
              :model-value="t.current"
              placeholder="选择数据源"
              style="width: 260px"
              @change="(v) => onChange(t.fund_type, v)"
            >
              <el-option v-for="p in t.options" :key="p.name" :label="p.label" :value="p.name" />
            </el-select>
            <el-tag
              v-if="t.current"
              :type="tagType(t.current)"
              effect="plain"
            >
              当前：{{ providerLabel(t) }}
            </el-tag>
          </div>
        </div>
        <div class="ds-desc">
          场内（ETF/LOF）走 K 线 + 实时盘口，场外基金只走净值。切换后无需改任何代码：
        </div>
        <ul class="ds-list">
          <li>实时行情（汇总页/定投与再平衡计算器/买入卖出/价格页五档盘口 的「获取最新价」）</li>
          <li>XIRR 收益与再平衡体检的实时价格</li>
          <li>同步基金缺失历史价 / 场外基金净值（基金价格页）</li>
          <li>同步基准指数历史价（回测页「同步所选基准」，走场内组数据源）</li>
          <li>每日自动同步（工作日 17:30 定时任务 + 汇总页「同步全部行情」）</li>
        </ul>
      </div>

      <el-alert
        v-if="sinaTip"
        type="warning"
        :closable="false"
        class="ds-tip"
        title="新浪数据源限制"
      >
        新浪免费日线接口最多只能取最近约 4 年（1023 个交易日）的历史，更早的缺口需切换其他数据源同步。
      </el-alert>
      <el-alert
        v-if="akshareTip"
        type="warning"
        :closable="false"
        class="ds-tip"
        title="AKShare 为非官方数据源"
      >
        AKShare 为社区开源库（爬取公开页面），有 1~2 秒请求限流与失败重试、并发上限 4；实时行情较慢且无五档盘口，请谨慎用于正式记账。
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { datasourceApi } from '../api'

// [{fund_type, label, options:[{name,label}], current}]
const types = ref([])

function providerLabel(t) {
  return (t.options || []).find((p) => p.name === t.current)?.label || t.current
}

function tagType(name) {
  if (name === 'sina') return 'warning'
  if (name === 'akshare') return 'danger'
  return 'info'
}

const sinaTip = computed(() => types.value.some((t) => t.current === 'sina'))
const akshareTip = computed(() => types.value.some((t) => t.current === 'akshare'))

async function load() {
  try {
    const data = await datasourceApi.get()
    types.value = data.types || []
  } catch {
    // 拦截器已提示
  }
}

async function onChange(fund_type, provider) {
  try {
    const data = await datasourceApi.set({ fund_type, provider })
    types.value = data.types || []
    const t = types.value.find((x) => x.fund_type === fund_type)
    ElMessage.success(`${t?.label || fund_type}数据源已切换：${providerLabel(t || {})}`)
  } catch {
    // 拦截器已提示；失败时回读当前值
    load()
  }
}

onMounted(load)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-note {
  color: #909399;
  font-size: 12px;
  font-weight: normal;
}
.ds-section {
  margin-bottom: 16px;
}
.ds-label {
  color: #606266;
  font-size: 13px;
  margin-bottom: 10px;
}
.ds-control {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ds-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
.ds-row-label {
  width: 120px;
  color: #606266;
  font-size: 13px;
  flex-shrink: 0;
}
.ds-desc {
  margin-top: 16px;
  color: #606266;
  font-size: 13px;
}
.ds-list {
  margin: 8px 0 0;
  padding-left: 20px;
  color: #909399;
  font-size: 13px;
  line-height: 1.9;
}
.ds-tip {
  margin-top: 16px;
}
</style>
