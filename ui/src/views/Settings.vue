<template>
  <div class="settings">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
          <span class="header-note">修改后即时生效，所有取数操作跟随「当前数据源」</span>
        </div>
      </template>

      <div class="ds-section">
        <div class="ds-label">当前数据源</div>
        <div class="ds-control">
          <el-select v-model="current" placeholder="选择数据源" style="width: 260px" @change="onChange">
            <el-option v-for="p in providers" :key="p.name" :label="p.label" :value="p.name" />
          </el-select>
          <el-tag v-if="current" :type="current === 'sina' ? 'warning' : 'info'" effect="plain" class="ds-tag">
            当前：{{ currentLabel }}
          </el-tag>
        </div>
        <div class="ds-desc">
          以下操作统一从「当前数据源」获取数据，切换后无需改任何代码：
        </div>
        <ul class="ds-list">
          <li>实时行情（汇总页/定投与再平衡计算器/买入卖出/价格页五档盘口 的「获取最新价」）</li>
          <li>XIRR 收益与再平衡体检的实时价格</li>
          <li>同步基金缺失历史价（基金价格页）</li>
          <li>同步基准指数历史价（回测页「同步所选基准」）</li>
          <li>每日自动同步（工作日 17:30 定时任务 + 汇总页「同步全部行情」）</li>
        </ul>
      </div>

      <el-alert
        v-if="current === 'sina'"
        type="warning"
        :closable="false"
        class="ds-tip"
        title="新浪数据源限制"
      >
        新浪免费日线接口最多只能取最近约 4 年（1023 个交易日）的历史，更早的缺口需切回腾讯同步。
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { datasourceApi } from '../api'

const providers = ref([])
const current = ref('tencent')

const currentLabel = computed(
  () => providers.value.find((p) => p.name === current.value)?.label || current.value
)

async function load() {
  try {
    const data = await datasourceApi.get()
    providers.value = data.providers || []
    current.value = data.current || 'tencent'
  } catch {
    // 拦截器已提示
  }
}

async function onChange() {
  try {
    const data = await datasourceApi.set({ provider: current.value })
    current.value = data.current
    ElMessage.success(`已切换数据源：${currentLabel.value}`)
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
.ds-tag {
  margin-left: 4px;
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
