// 再平衡判定共享模块：Dashboard 卡片与新页面共用。
// 公式与后端 app/services/rebalance.py 保持一致：
//   阈值(%) = clamp(目标% × r_band/100, min_abs, max_abs)
//   状态 = |偏离| > 阈值 且 偏离金额 ≥ 金额底线 → above/below，否则 normal

// 阈值(%)：目标未设返回 null
export function thresholdFor(target, params) {
  if (target == null) return null
  const t = Number(target)
  return Math.min(
    Number(params.max_abs),
    Math.max(Number(params.min_abs), (t * Number(params.r_band)) / 100)
  )
}

// 状态判定：above / below / normal
export function judge(deviation, threshold, params, deviationAmount) {
  if (threshold == null) return 'normal'
  const dev = Number(deviation)
  if (Math.abs(dev) <= Number(threshold)) return 'normal'
  if (deviationAmount != null && Math.abs(Number(deviationAmount)) < Number(params.amount_floor)) {
    return 'normal'
  }
  return dev > 0 ? 'above' : 'below'
}

// 便捷封装：给一行 {target, real} + params + totalMv(元)，返回判定结果
export function evaluate(row, params, totalMv) {
  const deviation = (Number(row.real) - Number(row.target)) || 0
  const threshold = thresholdFor(row.target, params)
  const deviationAmount =
    totalMv != null ? (deviation / 100) * Number(totalMv) : null
  return {
    deviation,
    threshold,
    deviationAmount,
    status: judge(deviation, threshold, params, deviationAmount),
  }
}
