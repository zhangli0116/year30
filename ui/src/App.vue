<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <div class="logo">📈 基金定投</div>
      <el-menu :default-active="$route.path" router class="menu">
        <el-menu-item index="/">
          <el-icon><DataAnalysis /></el-icon>
          <span>汇总</span>
        </el-menu-item>
        <el-menu-item index="/funds">
          <el-icon><Coin /></el-icon>
          <span>基金管理</span>
        </el-menu-item>
        <el-menu-item index="/purchases">
          <el-icon><List /></el-icon>
          <span>购买记录</span>
        </el-menu-item>
        <el-menu-item index="/prices">
          <el-icon><TrendCharts /></el-icon>
          <span>基金价格</span>
        </el-menu-item>
        <el-menu-item index="/holdings">
          <el-icon><Money /></el-icon>
          <span>每日权益流水</span>
        </el-menu-item>
        <el-menu-item index="/cash">
          <el-icon><Wallet /></el-icon>
          <span>每日现金流量</span>
        </el-menu-item>
        <el-menu-item index="/calculator">
          <el-icon><Operation /></el-icon>
          <span>季度计算器</span>
        </el-menu-item>
        <el-menu-item index="/rebalance">
          <el-icon><RefreshLeft /></el-icon>
          <span>卖出式再平衡</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-main class="main">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
// 无额外逻辑，布局由模板负责
</script>

<style scoped>
.layout {
  height: 100vh;
}
.aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  font-size: 18px;
  font-weight: 600;
  border-bottom: 1px solid #e4e7ed;
}
.menu {
  border-right: none;
}
.main {
  background: #f5f7fa;
  padding: 20px;
}
</style>
