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

export const fundsApi = {
  // GET /api/v1/funds?page=&page_size=&keyword=
  list: (params) => request.get('/funds', { params }),
  summary: () => request.get('/funds/summary'),
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

export const quartersApi = {
  // GET /api/v1/quarters
  list: () => request.get('/quarters'),
  // GET /api/v1/quarters/{id}
  detail: (id) => request.get(`/quarters/${id}`),
  // POST /api/v1/quarters
  create: (data) => request.post('/quarters', data),
  // PUT /api/v1/quarters/{id}
  update: (id, data) => request.put(`/quarters/${id}`, data),
  // POST /api/v1/quarters/{id}/recalc
  recalc: (id) => request.post(`/quarters/${id}/recalc`),
}
