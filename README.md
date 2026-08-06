# 指数基金定投记录后端

基于 FastAPI + SQLAlchemy 的个人基金定投记录 Web 服务，提供 `fund`（基金）与 `purchase_record`（购买记录）两张表的 CRUD 及汇总统计接口。

## 快速开始

```bash
# 1. 安装依赖（venv 已激活）
pip install -r requirements.txt

# 2. 确认数据库配置（默认 root/123456 连接本机 fund_invest 库）
#    如需修改请编辑 .env

# 3. 启动服务（端口在 .env 的 HTTP_PORT 配置，默认 8000）
python -m app.main
```

启动后访问：
- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/

## 前端（ui/，Vue 3 + Vite）

需先启动后端，再启动前端 dev server：

```bash
# 终端 1：后端（端口读 .env 的 HTTP_PORT，默认 8000）
python -m app.main

# 终端 2：前端
cd ui
npm install        # 首次
npm run dev        # http://localhost:5173
```

前端通过 Vite 代理把 `/api` 转发到后端端口（同样读根目录 .env，改 `HTTP_PORT` 两边自动同步），
页面访问 http://localhost:5173/（汇总、基金管理、购买记录三个页面）。

构建产物：`cd ui && npm run build`，输出到 `ui/dist/`。

## 目录结构

```
app/
├── main.py          # 应用入口：CORS、路由挂载、启动时补建缺失表
├── config.py        # 读取 .env，生成数据库连接串
├── database.py      # engine / SessionLocal / Base / get_db
├── models.py        # Fund、PurchaseRecord ORM 模型（映射已有表）
├── schemas.py       # Pydantic 模型 + 统一响应包装
├── crud/            # 数据访问层
│   ├── fund.py
│   └── purchase.py
└── routers/         # API 路由层
    ├── fund.py
    └── purchase.py
scripts/
└── init_db.py       # 手动补建缺失表：python scripts/init_db.py
schema.sql           # 数据库表结构（已执行过）
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/funds` | 基金列表（分页 + keyword 模糊搜索） |
| POST | `/api/v1/funds` | 新增基金 |
| GET | `/api/v1/funds/summary` | 全部基金汇总统计（购买次数/累计份数/累计投入/平均成本） |
| GET | `/api/v1/funds/{id}` | 基金详情 + 其全部购买记录 |
| PUT | `/api/v1/funds/{id}` | 修改基金 |
| DELETE | `/api/v1/funds/{id}` | 删除基金（存在买入记录时拒绝） |
| GET | `/api/v1/purchases` | 购买记录列表（分页 + fund_id/日期过滤） |
| POST | `/api/v1/purchases` | 新增购买记录（未传 total_amount 时自动计算） |
| GET | `/api/v1/purchases/{id}` | 记录详情 |
| PUT | `/api/v1/purchases/{id}` | 修改记录 |
| DELETE | `/api/v1/purchases/{id}` | 删除记录 |

## 返回格式

统一返回 `{code, message, data}`，`code = 0` 表示成功：

```json
{ "code": 0, "message": "ok", "data": { ... } }
```

业务错误码：`40001` 基金代码重复，`40002` 删除被关联记录拦截，`40003` 关联基金不存在，`40400` 基金不存在，`40401` 购买记录不存在。
