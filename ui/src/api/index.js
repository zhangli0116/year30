import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端统一返回 {code, message, data}；code === 0 表示成功
const request = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

request.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body
  },
  (err) => {
    const detail = err.response?.data?.detail
    ElMessage.error(
      detail || err.response?.data?.message || err.message || '网络错误'
    )
    return Promise.reject(err)
  }
)

export const planApi = {
  // 定投方案：GET/POST/PUT/DELETE /api/v1/plans
  // plan funds 形如 [{fund_id, target_ratio}]，create/update 时随 body 提交
  list: () => request.get('/plans'),
  detail: (id) => request.get(`/plans/${id}`),
  create: (data) => request.post('/plans', data),
  update: (id, data) => request.put(`/plans/${id}`, data),
  remove: (id) => request.delete(`/plans/${id}`),
}

export const fundsApi = {
  // GET /api/v1/funds?page=&page_size=&keyword=
  list: (params) => request.get('/funds', { params }),
  // GET /api/v1/funds/summary?plan_id=   （传 plan_id 时 target_ratio 为该方案内比例）
  summary: (params) => request.get('/funds/summary', { params }),
  detail: (id) => request.get(`/funds/${id}`),
  create: (data) => request.post('/funds', data),
  update: (id, data) => request.put(`/funds/${id}`, data),
  remove: (id) => request.delete(`/funds/${id}`),
}

export const purchasesApi = {
  // GET /api/v1/purchases?page=&page_size=&fund_id=&start_date=&end_date=
  list: (params) => request.get('/purchases', { params }),
  create: (data) => request.post('/purchases', data),
  // POST /api/v1/purchases/batch —— 季度一键录入（数组）
  batch: (data) => request.post('/purchases/batch', data),
  update: (id, data) => request.put(`/purchases/${id}`, data),
  remove: (id) => request.delete(`/purchases/${id}`),
}

export const quotesApi = {
  // GET /api/v1/quotes?codes=513500,513100  （后端转发腾讯公开行情）
  list: (codes) => request.get('/quotes', { params: { codes } }),
}

export const pricesApi = {
  // GET /api/v1/prices/sources  可选数据源
  sources: () => request.get('/prices/sources'),
  // GET /api/v1/prices?fund_id=&start_date=&end_date=
  list: (params) => request.get('/prices', { params }),
  // POST /api/v1/prices/check  {fund_id, start_date, end_date, source}  确认缺失时间段
  check: (data) => request.post('/prices/check', data),
  // POST /api/v1/prices/sync  {fund_id, start_date, end_date, source}
  sync: (data) => request.post('/prices/sync', data),
  // POST /api/v1/prices/{fund_id}/adj-nav  场外基金计算复权净值（分红复投，较慢）
  adjNav: (fundId) => request.post(`/prices/${fundId}/adj-nav`, null, { timeout: 180000 }),
}

export const cashApi = {
  // GET /api/v1/cash?start_date=&end_date=
  list: (params) => request.get('/cash', { params }),
  // POST /api/v1/cash/check  {start_date, end_date}
  check: (data) => request.post('/cash/check', data),
  // POST /api/v1/cash/generate  {start_date, end_date}
  generate: (data) => request.post('/cash/generate', data),
}

export const holdingsApi = {
  // GET /api/v1/holdings?fund_id=&start_date=&end_date=
  list: (params) => request.get('/holdings', { params }),
  // GET /api/v1/holdings/total?start_date=&end_date=  全部基金按日求和
  total: (params) => request.get('/holdings/total', { params }),
  // POST /api/v1/holdings/check  {fund_id, start_date, end_date}
  check: (data) => request.post('/holdings/check', data),
  // POST /api/v1/holdings/generate  {fund_id, start_date, end_date}
  generate: (data) => request.post('/holdings/generate', data),
}

export const quartersApi = {
  // GET /api/v1/quarters?plan_id=   （可选按方案过滤）
  list: (params) => request.get('/quarters', { params }),
  // GET /api/v1/quarters/{id}
  detail: (id) => request.get(`/quarters/${id}`),
  // POST /api/v1/quarters
  create: (data) => request.post('/quarters', data),
  // PUT /api/v1/quarters/{id}
  update: (id, data) => request.put(`/quarters/${id}`, data),
  // POST /api/v1/quarters/{id}/recalc
  recalc: (id) => request.post(`/quarters/${id}/recalc`),
}

export const xirrApi = {
  // GET /api/v1/xirr?plan_id= → {account: {...}, funds: [...]}
  get: (params) => request.get('/xirr', { params }),
}

export const syncApi = {
  // POST /api/v1/sync/all —— 一键同步全部行情并生成权益/现金流
  // 同步可能较慢（拉取多只基金），放宽超时到 60s
  all: () => request.post('/sync/all', null, { timeout: 60000 }),
}

export const rebalanceApi = {
  // GET /api/v1/rebalance/check → {params, total, funds:[...], cash}
  // 可选传 r_band/min_abs/max_abs/amount_floor 临时覆盖参数做预览（不落库）
  check: (params) => request.get('/rebalance/check', { params }),
  // GET /api/v1/rebalance/params → 判定参数
  getParams: () => request.get('/rebalance/params'),
  // PUT /api/v1/rebalance/params {r_band?, min_abs?, max_abs?, amount_floor?}
  saveParams: (data) => request.put('/rebalance/params', data),
}

export const backtestApi = {
  // GET /api/v1/backtest → 回测结果
  // params: {plan_id, start_date, end_date?, amount?, benchmarks?(逗号分隔), buy_rebalance?, sell_rebalance?}
  run: (params) => request.get('/backtest', { params }),
  // POST /api/v1/backtest/strategy → 策略实验室（完整策略配置 + 动态金额因子）
  runStrategy: (data) => request.post('/backtest/strategy', data, { timeout: 60000 }),
  // GET /api/v1/backtest/coverage → 数据覆盖检查
  coverage: (params) => request.get('/backtest/coverage', { params }),
}

export const benchmarksApi = {
  // GET /api/v1/benchmarks → 可选对比基准列表
  list: () => request.get('/benchmarks'),
  // POST /api/v1/benchmarks/sync?symbol=&start_date=&end_date=
  sync: (params) => request.post('/benchmarks/sync', null, { params }),
}

export const datasourceApi = {
  // GET /api/v1/datasource → {types:[{fund_type,label,options,current}]}
  get: () => request.get('/datasource'),
  // PUT /api/v1/datasource {fund_type, provider} → 设置该标的类型的数据源（持久化）
  set: (data) => request.put('/datasource', data),
}
