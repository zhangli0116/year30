# 指数基金定投记录

基于 FastAPI + SQLAlchemy + Vue3 的个人基金定投记录系统：每季度定投多只指数基金，支持买入/卖出、手续费、季度预算、历史行情、实时五档盘口、每日权益/现金流趋势、再平衡规划。

## 快速开始

```bash
# 1. 安装后端依赖（venv 已激活）
pip install -r requirements.txt

# 2. 确认数据库配置（默认 root/123456 连接本机 fund_invest 库），如需修改请编辑 .env
#    .env.example 提供模板；.env 已被 gitignore

# 3. 初始化表结构（一次性）
python scripts/init_db.py   # 或直接执行 schema.sql

# 4. 启动后端（端口在 .env 的 HTTP_PORT，默认 8000）
python -m app.main
```

启动后访问：
- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/

## 前端（ui/，Vue 3 + Vite + Element Plus + ECharts）

```bash
# 终端 1：后端
python -m app.main

# 终端 2：前端
cd ui
npm install        # 首次（含 echarts）
npm run dev        # http://localhost:5173
```

前端通过 Vite 代理把 `/api` 转发到后端（同样读根目录 .env，改 `HTTP_PORT` 两边自动同步）。

页面：汇总（总权益/总资产/累积投入走势、持仓汇总、XIRR 年化收益、再平衡状态）、基金管理、购买记录（按季度折叠）、定投与再平衡计算器（定投录入 + 买入式再平衡）、临时再平衡（年末/突发，按当前持仓超配卖出/低配买入，操作归属「年份+类型」命名的季度）、再平衡体检（偏离判定与参数）、基金价格（K线+成交量+实时五档盘口+同步）、每日权益流水、每日现金流量、方案回测（从历史时点模拟「每期定投 + 买入式平衡 + 年末卖出式再平衡」，算 XIRR 年化/TWR/最大回撤并对比沪深300/上证/创业板/标普500 基准）、系统设置（切换当前数据源：腾讯/新浪，所有取数操作跟随）。各线图统一走 `ui/src/utils/chart.js` 的共享样式，保证风格一致。

构建产物：`cd ui && npm run build`，输出到 `ui/dist/`。

## 日志

loguru 已接入（`app/logger.py`），控制台 + `log/` 文件夹（按天滚动、保留 30 天、UTF-8）。`log/` 已被 gitignore。

## 目录结构

```
app/
├── main.py            # 应用入口：CORS、路由挂载、启动补建缺失表、日志初始化
├── config.py          # 读取 .env，生成数据库连接串
├── database.py        # engine / SessionLocal / Base / get_db
├── logger.py          # loguru 日志配置
├── models.py          # Fund / Quarter / PurchaseRecord / FundPrice / FundHoldingDaily / FundCashDaily / Benchmark / BenchmarkPrice
├── schemas.py         # Pydantic 模型 + 统一响应包装
├── crud/              # 数据访问层
│   ├── benchmark.py   #   对比基准 CRUD + 幂等写入基准日线
│   ├── cash.py        #   每日现金流 生成/查询/缺失检查
│   ├── fund.py        #   基金 CRUD + 汇总（含买卖相减）
│   ├── holding.py     #   每日权益流水 生成/查询/缺失检查
│   ├── price.py       #   历史价格 upsert/查询
│   ├── purchase.py    #   购买记录 CRUD + 手续费计算（买卖费率）
│   └── quarter.py     #   季度 CRUD + 重算（equity/total_fee/cash）
├── services/
│   ├── backtest.py    # 回测引擎（每期买入式 + 年末卖出式再平衡，XIRR/TWR/回撤/基准对比）
│   ├── benchmark.py   # 基准默认种子 + 按 symbol 拉指数日线（直连/代理）+ 幂等同步
│   ├── datasource.py  # 数据源注册表 + 「当前数据源」管理（app_setting 持久化）+ fund→symbol 解析
│   ├── price.py       # 数据源抽象（DataProvider 基类 + TencentProvider：日线窗口分页 + 五档行情）
│   ├── sina.py        # 新浪数据源（新浪五档行情 + 日线，免费日线限最近约 4 年）
│   └── xirr.py        # XIRR/TWR 计算（实时价按当前数据源取）
└── routers/           # API 路由层
    ├── backtest.py    #   /api/v1/backtest（回测 + 数据覆盖检查）
    ├── benchmark.py   #   /api/v1/benchmarks（列表 + 同步）
    ├── cash.py        #   /api/v1/cash
    ├── datasource.py  #   /api/v1/datasource（当前数据源 查询/切换）
    ├── fund.py        #   /api/v1/funds
    ├── holding.py     #   /api/v1/holdings
    ├── price.py       #   /api/v1/prices
    ├── purchase.py    #   /api/v1/purchases
    ├── quarter.py     #   /api/v1/quarters
    └── quote.py       #   /api/v1/quotes（按当前数据源取实时行情）
scripts/
└── init_db.py         # 手动补建缺失表：python scripts/init_db.py
schema.sql             # 数据库表结构（fund/quarter/purchase_record/fund_price/fund_holding_daily/fund_cash_daily/benchmark/benchmark_price）
ui/
└── src/
    ├── api/index.js
    ├── components/    # QuarterChart / TotalEquityChart / PlanSwitcher
    ├── utils/
    │   └── chart.js   # 共享 ECharts 样式工具（调色板/折线/柱/渐变/正负分色/均值线/格式化）
    ├── views/         # Dashboard / Funds / Purchases / Calculator / Rebalance / RebalanceCheck / Prices / Holdings / Cash / Backtest
    └── router/index.js
```

## 数据模型与业务规则

- **fund**：基金维度，含 `target_ratio`（规定比例%）
- **quarter**：季度汇总，`budget`(预算) / `equity_amount`(权益本金，不含手续费) / `total_fee`(手续费总额) / `cash_amount`(剩余现金 = budget − equity − total_fee)
- **purchase_record**：购买记录，`type`('buy'/'sell')，`fee`(手续费)，`total_amount`(买入=本金+费，卖出=成交额)；`quarter_id` 关联季度
  - 手续费：买入默认 0.03%、卖出默认 0.07%，`max(5, 金额×费率)`
- **fund_price**：历史日线 OHLC（数据源可切换，默认腾讯前复权）
- **fund_holding_daily**：每日权益流水 = 累计持有份额 × 当日收盘价
- **fund_cash_daily**：每日现金流量 = 按日历日累计（预算入账 + 卖出回笼 − 买入支出 − 手续费）
- **benchmark**：对比基准指数（回测用），`fund_id` 非空 = 代理基准（标普500→513500，从 fund_price 拷贝收盘价，人民币口径）
- **benchmark_price**：基准历史日线（回测对比用）

## 再平衡判定

「再平衡体检」页 + Dashboard「再平衡状态」卡片共用一套偏离判定，参数（相对带 R / 绝对底线 / 绝对上限 / 金额底线）可在页面调整并落库。完整使用说明见 [docs/rebalance.md](docs/rebalance.md)。

## API 一览

统一前缀 `/api/v1`，返回 `{code, message, data}`（code=0 成功）。

### 基金 funds
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/funds` | 基金列表（分页 + keyword） |
| POST | `/funds` | 新增基金 |
| GET | `/funds/summary` | 汇总统计（份额/成本按买卖相减，成本不含手续费） |
| GET | `/funds/{id}` | 基金详情 + 购买记录 |
| PUT | `/funds/{id}` | 修改基金 |
| DELETE | `/funds/{id}` | 删除基金（有记录时拒绝） |

### 购买记录 purchases
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/purchases` | 列表（分页 + fund_id/日期过滤，默认排除现金记录） |
| POST | `/purchases` | 新增（type/fee/fee_rate；未传 total_amount 自动计算） |
| POST | `/purchases/batch` | 批量录入（季度一键/卖出式再平衡用） |
| PUT | `/purchases/{id}` | 修改 |
| DELETE | `/purchases/{id}` | 删除（自动重算所属季度） |

### 季度 quarters
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/quarters` | 季度列表 |
| POST | `/quarters` | 创建季度（period 唯一） |
| GET | `/quarters/{id}` | 季度详情 + 记录 |
| PUT | `/quarters/{id}` | 修改预算（唯一可改字段，自动重算现金） |
| POST | `/quarters/{id}/recalc` | 按记录重算 equity/total_fee/cash |
| DELETE | `/quarters/{id}` | 删除季度（记录置空 quarter_id） |

### 数据源 datasource（当前数据源切换）
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/datasource` | 可选数据源列表 + 当前使用哪个 |
| PUT | `/datasource` | 切换「当前数据源」（body `{provider}`，持久化到 app_setting），实时行情/历史价同步/基准同步/每日自动同步统一跟随 |

### 实时行情 quotes
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/quotes` | 实时行情（`codes=513500,513100`），按「当前数据源」取数，返回 `{quotes: [...], source}`，每项含：最新价/昨收/涨跌额/涨跌幅、买卖 1..5 档价与挂单量（手）、时间 |

### 历史价格 prices
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/prices/sources` | 可选数据源列表（兼容旧接口，同 `/datasource`） |
| GET | `/prices` | 查询日线（fund_id + start/end） |
| POST | `/prices/check` | 检查缺失时间段（只统计工作日缺口） |
| POST | `/prices/sync` | 同步缺失日期（幂等，`source` 可选覆盖，缺省用当前数据源） |

### 每日权益流水 holdings
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/holdings` | 某基金日线权益（fund_id + start/end） |
| GET | `/holdings/total` | 全部基金按日求和（总权益走势） |
| POST | `/holdings/check` | 检查缺失交易日（有历史价但无流水） |
| POST | `/holdings/generate` | 生成/更新每日权益流水 |

### 每日现金流量 cash
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/cash` | 查询每日现金流（start/end） |
| POST | `/cash/check` | 检查缺失日历日 |
| POST | `/cash/generate` | 生成/更新每日现金流量 |

### 方案回测 backtest
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/backtest` | 回测（plan_id + start_date + end_date?/amount?/benchmarks?/year_end_rebalance?/unlisted_mode?），返回 XIRR 年化/TWR/最大回撤/每日曲线/交易明细/基准对比；`unlisted_mode` = park(未上市标的现金停放,默认)/redistribute(比例重分配)；年末卖出式再平衡采用「再平衡体检」判定参数（阈值触发，与体检页一致） |
| GET | `/backtest/coverage` | 数据覆盖检查（各基金 + 所选基准在区间的缺失情况，`ready` 是否全部覆盖） |

### 对比基准 benchmarks
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/benchmarks` | 基准列表（回测页多选；首次调用自动灌默认 4 基准） |
| POST | `/benchmarks/sync` | 按区间增量同步基准日线（幂等；代理基准从 fund_price 拷贝，直连基准走腾讯指数日线） |

## 返回格式

```json
{ "code": 0, "message": "ok", "data": { ... } }
```

业务错误码：`40001` 基金代码重复，`40002` 删除被关联记录拦截，`40003` 关联基金不存在，`40005` 周期已存在，`40006` 未知数据源，`40400` 基金不存在，`40401` 购买记录不存在，`40402` 季度不存在，`40403` 方案不存在，`40404` 基准不存在，`50001` 数据源拉取失败。

## 数据源扩展

所有外部取数统一走「当前数据源」（`app/services/datasource.py`，设置页切换，持久化到 `app_setting.datasource.provider`）。新增数据源三步：
1. 继承 `app/services/price.py` 的 `DataProvider`，实现 `fetch_daily(symbol, start, end)`（历史日线，symbol 为完整行情代码如 `sh513500`/`sz399006`）与 `fetch_quotes(symbols)`（实时五档行情）。
2. 在 `app/services/datasource.py::_registry()` 注册实例。
3. 前端「系统设置」页自动出现选项，切换后所有取数操作（行情/历史价/基准同步/每日自动同步/XIRR·再平衡实时价）统一跟随。

已实现：`tencent`（腾讯：日线前复权窗口分页 + 五档行情）、`sina`（新浪：五档行情 + 日线，免费日线限最近约 4 年，更早历史需切回腾讯补）。
