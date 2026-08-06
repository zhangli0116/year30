// 定投方案相关的共享工具

// 从间隔天数推导周期标签（用于 period 格式）
//   ≤7 天 → weekly；≤31 天 → monthly；否则 → quarterly
export function intervalLabel(days) {
  if (days != null && days <= 7) return 'weekly'
  if (days != null && days <= 31) return 'monthly'
  return 'quarterly'
}

// 按方案周期把起始日期转成 period 标识
//   monthly   → 2026-05
//   quarterly → 2026Q3
//   weekly    → 2026-W23（ISO 周）
export function periodFromDate(dateStr, interval = 'quarterly') {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const y = d.getFullYear()
  if (interval === 'monthly') {
    return `${y}-${String(d.getMonth() + 1).padStart(2, '0')}`
  }
  if (interval === 'weekly') {
    return `${y}-W${String(isoWeek(d)).padStart(2, '0')}`
  }
  const q = Math.floor(d.getMonth() / 3) + 1
  return `${y}Q${q}`
}

// ISO 8601 周数
export function isoWeek(d) {
  const date = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7)) // 本周四决定所属年份
  const week1 = new Date(date.getFullYear(), 0, 4)
  return (
    1 +
    Math.round(
      ((date - week1) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7
    )
  )
}
