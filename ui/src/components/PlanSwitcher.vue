<template>
  <div class="plan-switcher">
    <span class="plan-label">定投方案</span>
    <el-select
      :model-value="modelValue"
      placeholder="选择定投方案"
      :loading="loading"
      style="width: 220px"
      @update:model-value="onSelect"
    >
      <el-option
        v-for="p in plans"
        :key="p.id"
        :label="p.name"
        :value="p.id"
      >
        <span>{{ p.name }}</span>
        <el-tag v-if="p.active === false" size="small" type="info" effect="plain">停用</el-tag>
      </el-option>
    </el-select>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { planApi } from '../api'

defineProps({
  modelValue: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue', 'change'])

const plans = ref([])
const loading = ref(false)

// 页面刷新时默认选中第一个 active 方案（无 active 则取第一个），
// 选中后 emit change 交由页面重新拉取数据。
async function loadPlans() {
  loading.value = true
  try {
    const list = await planApi.list()
    plans.value = list || []
    if (plans.value.length) {
      const active = plans.value.find((p) => p.active) || plans.value[0]
      emit('update:modelValue', active.id)
      emit('change', active.id)
    }
  } catch {
    // 具体错误已由拦截器弹出
  } finally {
    loading.value = false
  }
}

function onSelect(id) {
  emit('update:modelValue', id)
  emit('change', id)
}

onMounted(loadPlans)
</script>

<style scoped>
.plan-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
}
.plan-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}
</style>
