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

页面：汇总（总权益/总资产/累积投入走势、持仓汇总、XIRR 年化收益、再平衡状态）、基金管理、购买记录（按季度折叠）、季度计算器（买入式再平衡）、卖出式再平衡、再平衡体检（偏离判定与参数）、基金价格（K线+成交量+实时五档盘口+同步）、每日权益流水、每日现金流量。各线图统一走 `ui/src/utils/chart.js` 的共享样式，保证风格一致。

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
├── models.py          # Fund / Quarter / PurchaseRecord / FundPrice / FundHoldingDaily / FundCashDaily
├── schemas.py         # Pydantic 模型 + 统一响应包装
├── crud/              # 数据访问层
│   ├── cash.py        #   每日现金流 生成/查询/缺失检查
│   ├── fund.py        #   基金 CRUD + 汇总（含买卖相减）
│   ├── holding.py     #   每日权益流水 生成/查询/缺失检查
│   ├── price.py       #   历史价格 upsert/查询
│   ├── purchase.py    #   购买记录 CRUD + 手续费计算（买卖费率）
│   └── quarter.py     #   季度 CRUD + 重算（equity/total_fee/cash）
├── services/
│   ├── price.py       # 价格数据源抽象层（PriceSource 基类 + TencentPriceSource + 注册表）
│   └── quote.py       # 实时行情：昨收/涨跌额/涨跌幅 + 买卖五档价与挂单量（腾讯公开接口转发）
└── routers/           # API 路由层
    ├── cash.py        #   /api/v1/cash
    ├── fund.py        #   /api/v1/funds
    ├── holding.py     #   /api/v1/holdings
    ├── price.py       #   /api/v1/prices
    ├── purchase.py    #   /api/v1/purchases
    ├── quarter.py     #   /api/v1/quarters
    └── quote.py       #   /api/v1/quotes
scripts/
└── init_db.py         # 手动补建缺失表：python scripts/init_db.py
schema.sql             # 数据库表结构（fund/quarter/purchase_record/fund_price/fund_holding_daily/fund_cash_daily）
ui/
└── src/
    ├── api/index.js
    ├── components/    # QuarterChart / TotalEquityChart
    ├── utils/
    │   └── chart.js   # 共享 ECharts 样式工具（调色板/折线/柱/渐变/均值线/格式化）
    ├── views/         # Dashboard / Funds / Purchases / Calculator / Rebalance / Prices / Holdings / Cash
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

### 实时行情 quotes
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/quotes` | 实时行情（`codes=513500,513100`），返回 `{quotes: [...]}`，每项含：最新价/昨收/涨跌额/涨跌幅、买卖 1..5 档价与挂单量（手）、时间 |

### 历史价格 prices
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/prices/sources` | 可选数据源列表 |
| GET | `/prices` | 查询日线（fund_id + start/end） |
| POST | `/prices/check` | 检查缺失时间段（只统计工作日缺口） |
| POST | `/prices/sync` | 同步缺失日期（幂等，source 指定数据源） |

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

## 返回格式

```json
{ "code": 0, "message": "ok", "data": { ... } }
```

业务错误码：`40001` 基金代码重复，`40002` 删除被关联记录拦截，`40003` 关联基金不存在，`40005` 周期已存在，`40006` 未知数据源，`40400` 基金不存在，`40401` 购买记录不存在，`40402` 季度不存在，`50001` 数据源拉取失败。

## 数据源扩展

新增价格数据源：继承 `app/services/price.py` 的 `PriceSource`，实现 `fetch_daily(code, start, end)`，注册进 `SOURCES` 字典，前端「数据源」下拉自动出现。
