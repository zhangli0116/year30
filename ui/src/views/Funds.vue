<template>
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
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundsApi } from '../api'

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
</style>
