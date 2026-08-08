# year30 指数基金定投项目

> 概览/API 见 [README.md](README.md)；系统架构与设计决策见 [docs/architecture.md](docs/architecture.md)；
> 子系统见 [docs/datasource.md](docs/datasource.md)、[docs/rebalance.md](docs/rebalance.md)、[docs/backtest.md](docs/backtest.md)。
> 本文件只放**每次会话都要遵守的操作规则**，架构细节不在此重复。

## 运行（详见 README「快速开始」）
- 后端：`.venv\Scripts\python -m app.main`（:8000）
- 前端：`ui/` 下 `npm run dev`（:5173，代理 /api → 8000）
- Windows 一次性脚本：`.venv\Scripts\python.exe`；依赖：`uv add <pkg>`

## 提交规范
- 直接提交 `master`，不建分支
- 消息：`feat:`/`fix:`/`refactor:` 前缀 + 中文描述，多改动用 ` + ` 连接
- 末尾带：`Co-Authored-By: Claude <noreply@anthropic.com>`
- `docs/project-log.md` 记录需求但 **gitignore 不入库**；CLAUDE.md/README/docs 随仓库提交
- 大改动先过 Plan Mode，改完用 `/verify` 端到端验证

## 开发前先看
- 改架构/数据源/价格相关代码前，先读 [docs/architecture.md](docs/architecture.md) 对应章节（分层、数据流、数据源抽象、设计决策），保持风格一致
- 表结构由 `schema.sql` 管理，**无 Alembic**：`create_all` 只补缺失表，改表手动 ALTER 并同步 schema.sql

## 自测规范（需求完成后的验证标准）
- **纯逻辑/算法**（xirr、再平衡判定、缺失段、fund_symbol、akshare 工具等）：`uv run pytest`（离线秒级，`test/` 下）——不依赖 DB/网络，必须可重复跑；每次改动跑全量（0.6s 成本近零，值得）
- **集成回归**（回测结构/因子金额/stock 类型等，依赖 DB）：`uv run pytest -m integration`（需 MySQL 在跑；默认 `addopts` 跳过）
- **交互/数据管线/真实数据源**：用 `/verify` 端到端验证（起后端 → 调真实接口 → 核对数值）；涉及外部接口改动前先实测确认字段
- **前端改动**：`ui/` 下 `npm run build` 抓语法错
- **何时补用例**：只给改到的**核心逻辑**（算法/数据源/回测引擎/复权/路由分支）补单测——改到哪个函数就补/改哪个模块的用例；**UI/前端/文档/脚本改动不强行建 test 文件**，走 build + 端到端。测试按模块组织（`test_xirr.py`/`test_strategy.py` 等），不按需求堆碎文件、不写无断言/重复的凑数用例
