import { createRouter, createWebHashHistory } from 'vue-router'

import Calculator from '../views/Calculator.vue'
import Cash from '../views/Cash.vue'
import Dashboard from '../views/Dashboard.vue'
import Funds from '../views/Funds.vue'
import Holdings from '../views/Holdings.vue'
import Prices from '../views/Prices.vue'
import Purchases from '../views/Purchases.vue'
import Rebalance from '../views/Rebalance.vue'
import RebalanceCheck from '../views/RebalanceCheck.vue'

// 使用 hash 模式：后续若把构建产物交给 FastAPI 托管，也无需服务端路由配置
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: '汇总' } },
    { path: '/funds', name: 'funds', component: Funds, meta: { title: '基金管理' } },
    { path: '/prices', name: 'prices', component: Prices, meta: { title: '基金价格' } },
    { path: '/holdings', name: 'holdings', component: Holdings, meta: { title: '每日权益流水' } },
    { path: '/cash', name: 'cash', component: Cash, meta: { title: '每日现金流量' } },
    { path: '/purchases', name: 'purchases', component: Purchases, meta: { title: '购买记录' } },
    { path: '/calculator', name: 'calculator', component: Calculator, meta: { title: '季度计算器' } },
    { path: '/rebalance', name: 'rebalance', component: Rebalance, meta: { title: '卖出式再平衡' } },
    { path: '/rebalance-check', name: 'rebalance-check', component: RebalanceCheck, meta: { title: '再平衡体检' } },
  ],
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 基金定投记录` : '基金定投记录'
})

export default router
